"""Job Queue scheduler — picks up APPROVED jobs, runs preflight, dispatches.

One tick = one pass: claim oldest APPROVED → context-fit preflight →
resolve model via allocator → compile prompt → dispatch via dispatch.py →
monitor for completion → write checkpoint → transition state.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

import config
import requests
from job_queue.models import JobRepository, Job, IllegalTransitionError

# Import these at module level for better performance and mocking 
from bridge_lib import load_flow_from_db, get_effective_model_source, get_next_id_for_flow, load_role_from_db
from dispatch import build_step_payload


class Scheduler:
    """Picks up APPROVED jobs and dispatches them through the DPMtF pipeline."""

    def __init__(self, db_path: str = None, worker_id: str = "scheduler-1"):
        self.repo = JobRepository(db_path=db_path)
        self.worker_id = worker_id
        self.allocator_script = os.path.join(
            config.get_project_path("model-allocator"), "scripts", "model-allocator"
        )
        self.dispatch_script = str(
            PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py"
        )
        # Chain-nudge configuration — shared with chain_watchdog.py via the
        # machine profile [watchdog] section (configurable, not hardcoded).
        wd = self._watchdog_profile()
        self.stall_minutes = int(wd.get("stall_minutes", 12))
        self.max_nudges = int(wd.get("max_nudges_per_step", 2))
        # Fast path: nudge as soon as the WRITER's pane has been idle on
        # idle_confirmations consecutive ticks (it finished generating) and
        # the deliverable has had fast_nudge_minutes to be signaled by the
        # model itself. Much faster than waiting out stall_minutes.
        self.fast_nudge_minutes = int(wd.get("fast_nudge_minutes", 2))
        self.idle_confirmations = int(wd.get("idle_confirmations", 2))
        self.nudge_state_path = PROJECT_ROOT / "logs" / "job-queue-nudge-state.json"

    def _preflight(self) -> dict:
        """Invariant preflight at the start of each scheduler tick.

        Never dispatch onto a broken foundation: the app must be healthy,
        the database must answer, and the jobs table must not have lost
        rows since the previous tick (a decrease means something deleted
        production rows — the 2026-07-27 incident class).

        Returns {'passed': bool, 'reason': str}. Tests patch this method
        to bypass the environment-dependent checks.
        """
        # Check 1: App health endpoint
        try:
            import requests
            health_url = f"http://{config.get_host()}:{config.get_port()}/api/health"
            response = requests.get(health_url, timeout=5)
            if response.status_code != 200:
                return {
                    "passed": False,
                    "reason": f"App health endpoint failed with status {response.status_code}",
                }
        except Exception as e:
            return {
                "passed": False,
                "reason": f"App health endpoint unreachable: {e}",
            }

        # Check 2: Database connectivity
        try:
            self.repo.list_jobs(status="DRAFT")  # simple read test
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Database connectivity failed: {e}",
            }

        # Check 3: Jobs table row count invariant (non-decreasing)
        try:
            state = self._read_nudge_state()
            last_count = state.get("last_jobs_count", 0)
            current_count = len(self.repo.list_jobs())
            if current_count < last_count:
                return {
                    "passed": False,
                    "reason": f"Jobs table row count decreased from {last_count} to {current_count}",
                }
            state["last_jobs_count"] = current_count
            self._write_nudge_state(state)
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Jobs count check failed: {e}",
            }

        return {"passed": True, "reason": ""}

    @staticmethod
    def _watchdog_profile() -> dict:
        try:
            path = PROJECT_ROOT / "profiles" / "machine.local.json"
            return json.loads(path.read_text()).get("watchdog", {})
        except (OSError, json.JSONDecodeError):
            return {}

    def _resolve_verdict_outcome(self, job: Job) -> Optional[tuple[str, str]]:
        """Resolve verdict status from deliverable and return (target_state, detail) or None.
        
        This method consolidates the verdict parsing logic that was previously
        duplicated in tick() and _check_running_jobs() to ensure consistent behavior
        and reduce code duplication.
        """
        try:
            bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())
            
            # Find out if the last deliverable is a verdict file pattern
            flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
            steps = flow_data["steps"]
            last_step = steps[-1]
            deliverable_dir = last_step.get("deliverable_dir", "")
            deliverable_pattern = last_step.get("deliverable_pattern", "{ID}-result.md")
            
            hid = job.handoff_id or ""
            if not hid:
                # Empty handoff_id - log a warning as per finding #6
                print(f"WARNING: Job {job.job_id} has empty handoff_id but is being processed for verdict. "
                      f"This job will be treated as non-verdict.")
                return None
                
            deliverable_file = deliverable_pattern.replace("{ID}", hid).replace("{role_key}", last_step.get("from_role", ""))
            if os.path.isabs(deliverable_dir):
                final_path = os.path.join(deliverable_dir, deliverable_file)
            else:
                final_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)
            
            verdict_status = self._parse_verdict_file(final_path)
            
            # Transition based on verdict
            if verdict_status and verdict_status.upper() in ('APPROVED', 'APPROVED WITH NOTES', 'APPROVED WITHOUT NOTES'):
                return ("COMPLETED", "") 
            elif verdict_status and verdict_status.upper() == 'REJECTED':
                return ("CHANGES_REQUESTED", f"Verdict file: {final_path}")
            else:
                # Any other status or error → REVIEW_REQUIRED
                return ("REVIEW_REQUIRED", f"Verdict file: {final_path}")
        except Exception:
            # If we can't resolve the verdict, return None to allow normal completion flow
            return None

    def tick(self) -> dict:
        """One scheduler pass. Returns summary of what happened."""
        # 1. Invariant preflight — never claim/dispatch on a broken foundation.
        preflight = self._preflight()
        if not preflight["passed"]:
            return {
                "claimed": False,
                "recovered": 0,
                "completed": [],
                "outcome": f"preflight_failed:{preflight['reason']}"
            }

        # 1. Recover expired leases
        recovered = self.repo.recover_expired_leases()

        # 1b. Check all RUNNING jobs for completion
        completed_jobs = self._check_running_jobs()

        # 2. Claim oldest APPROVED job
        job = self.repo.claim(self.worker_id)
        if job is None:
            return {"claimed": False, "recovered": recovered,
                    "completed": completed_jobs}

        result = {"claimed": True, "job_id": job.job_id, "recovered": recovered}

        try:
            # 3. Context-fit preflight
            fit_state = self._context_fit_check(job)
            self.repo.update(job.job_id, context_fit_state=fit_state)

            if fit_state == "SPLIT_REQUIRED":
                # Auto-split: create continuation jobs
                self._auto_split(job, fit_state)
                self.repo.transition(job.job_id, "BLOCKED",
                    detail=f"auto-split: {fit_state}")
                result["outcome"] = "split"
                return result

            if fit_state not in ("FITS", "FITS_WITH_LOW_MARGIN"):
                # Not executable — block and require human
                self.repo.transition(job.job_id, "BLOCKED",
                    detail=f"context_fit={fit_state}")
                result["outcome"] = f"blocked:{fit_state}"
                return result

            # 4. Transition to RUNNING
            self.repo.transition(job.job_id, "RUNNING", actor=self.worker_id)

            # 5. Resolve allocator alias if not set
            if not job.allocator_alias:
                alias = self._resolve_alias(job)
                if alias:
                    self.repo.update(job.job_id, allocator_alias=alias)
                    job = self.repo.get_job(job.job_id)

            # 6. Compile handoff prompt + write handoff file + dispatch
            self._compile_handoff(job)
            # Refresh job to get the handoff_id set by _compile_handoff
            job = self.repo.get_job(job.job_id)
            dispatch_result = self._dispatch(job)
            result["dispatch"] = dispatch_result

            # 6b. Check if dispatch failed — fail fast rather than waiting
            #     for lease expiry. The job can be retried via lease recovery
            #     or human re-approval.
            dispatch_status = dispatch_result.get("status", "")
            if dispatch_status in ("failed", "timeout", "error"):
                err_msg = dispatch_result.get("output") or \
                         dispatch_result.get("error") or \
                         dispatch_status
                self.repo.transition(job.job_id, "FAILED",
                    detail=f"dispatch failed: {err_msg[:400]}")
                result["outcome"] = "dispatch_failed"
                return result

            # 7. Check completion
            completed = self._check_completion(job)
            if completed:
                # Determine if this is a verdict file and parse it accordingly
                if self._is_verdict_deliverable(job):
                    # Resolve verdict outcome from deliverable
                    verdict_outcome = self._resolve_verdict_outcome(job)
                    if verdict_outcome:
                        target_state, detail = verdict_outcome
                        self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                        # 8. Write checkpoint
                        self._write_checkpoint(job)
                        # 9. Complete or transition based on verdict
                        self.repo.transition(job.job_id, target_state, actor=self.worker_id, detail=detail)
                        result["outcome"] = target_state.lower().replace("_", "-")
                    else:
                        # Fallback for cases where we can't parse verdict (treated as no verdict)
                        self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                        # 8. Write checkpoint
                        self._write_checkpoint(job)
                        # 9. Complete
                        self.repo.transition(job.job_id, "COMPLETED", actor=self.worker_id)
                        result["outcome"] = "completed"
                else:
                    # Regular non-verdict flow — proceed as before
                    self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                    # 8. Write checkpoint
                    self._write_checkpoint(job)
                    # 9. Complete
                    self.repo.transition(job.job_id, "COMPLETED", actor=self.worker_id)
                    result["outcome"] = "completed"
            else:
                result["outcome"] = "running"

        except IllegalTransitionError as e:
            result["outcome"] = f"error:{e}"
        except Exception as e:
            result["outcome"] = f"error:{type(e).__name__}:{e}"
            try:
                self.repo.transition(job.job_id, "FAILED",
                    detail=str(e)[:500])
            except (IllegalTransitionError, ValueError):
                pass

        return result

    def _check_running_jobs(self) -> list[str]:
        """Check all RUNNING jobs for completion and advance chains.

        For each RUNNING job:
        1. Try to advance the chain (fallback if model forgot signal-complete)
        2. Check if the final deliverable exists → mark COMPLETED

        Returns list of completed job_ids.
        """
        completed = []
        running_jobs = self.repo.list_jobs(status="RUNNING")
        for job in running_jobs:
            # Try to advance the chain (fallback for models that forget signal-complete)
            self._advance_chain(job)

            # Check if the final deliverable exists
            if self._check_completion(job):
                try:
                    # Determine if this is a verdict file and parse it accordingly
                    is_verdict = self._is_verdict_deliverable(job)
                    
                    if is_verdict:
                        # Resolve verdict outcome from deliverable using shared method
                        verdict_outcome = self._resolve_verdict_outcome(job)
                        if verdict_outcome:
                            target_state, detail = verdict_outcome
                            self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                            self._write_checkpoint(job)
                            self.repo.transition(job.job_id, target_state, actor=self.worker_id, detail=detail)
                        else:
                            # Fallback for cases where we can't parse verdict (treated as no verdict)
                            self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                            self._write_checkpoint(job)
                            self.repo.transition(job.job_id, "COMPLETED", actor=self.worker_id)
                    else:
                        # Regular non-verdict flow — proceed as before
                        self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                        self._write_checkpoint(job)
                        self.repo.transition(job.job_id, "COMPLETED", actor=self.worker_id)
                    completed.append(job.job_id)
                    print(f"  Job {job.job_id} completed — full chain done, checkpoint written")
                except IllegalTransitionError:
                    pass  # State changed concurrently
        return completed

    def _context_fit_check(self, job: Job) -> str:
        """Evaluate context fit using real allocator context window."""
        ctx_window = self._resolve_context_window(job)
        goal_tokens = len(job.goal) // 4
        # Simple heuristic: if goal tokens exceed 30% of context window, flag it
        if goal_tokens > ctx_window * 0.3:
            return "SPLIT_REQUIRED"
        if goal_tokens > ctx_window * 0.15:
            return "FITS_WITH_LOW_MARGIN"
        return "FITS"

    def _resolve_alias(self, job: Job) -> str:
        """Resolve allocator alias for the job's role."""
        from bridge_lib import get_effective_model_source
        source, alias = get_effective_model_source(
            job.role_key, flow_key=job.flow_key, db_path=self.repo.db_path
        )
        return alias or ""

    def _resolve_context_window(self, job: Job) -> int:
        """Resolve the model's context window via allocator."""
        if not job.allocator_alias:
            return 131072
        try:
            result = subprocess.run(
                [self.allocator_script, "validate",
                 "--alias", job.allocator_alias,
                 "--client", "opencode",
                 "--json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode in (0, 2):
                data = json.loads(result.stdout)
                return data.get("resolved_context", 131072) or 131072
        except Exception:
            pass
        return 131072

    def _compile_handoff(self, job: Job):
        """Compile the handoff prompt and write the handoff file.

        Calls the prompt_compiler logic internally (not via HTTP) to generate
        the handoff file that dispatch.py --signal-send expects to exist.
        """
        bridge_dir = config.get_bridge_base_path()

        flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
        steps = flow_data["steps"]

        # Find the step matching this role
        step = None
        for s in steps:
            if s.get("to_role") == job.role_key or s.get("from_role") == job.role_key:
                step = s
                break
        if not step:
            step = steps[0] if steps else None
        if not step:
            return

        # Assign handoff ID — but only if not already assigned (lease recovery reuses)
        if job.handoff_id:
            handoff_id = job.handoff_id
        else:
            handoff_id = str(get_next_id_for_flow(job.flow_key, db_path=self.repo.db_path))
            self.repo.update(job.job_id, handoff_id=handoff_id)
            job = self.repo.get_job(job.job_id)

        # Build payload
        payload = build_step_payload(step, job.flow_key, handoff_id, bridge_dir)

        # Load governance for the role that will EXECUTE this step (job.role_key)
        # NOT the next role (payload["to_role"]) — the next role is for signal_complete
        from_role = load_role_from_db(job.role_key, db_path=self.repo.db_path)
        gov_file = from_role.get("governance_file", "")
        gov_path = str(PROJECT_ROOT / "docs" / "governance-templates-v2" / gov_file) if gov_file else ""

        # Build handoff prompt
        # The deliverable is the file signal_complete will validate and pass to the next role.
        # For step 1 (archi01→imple01), this is handoffs/{ID}-handoff.md.
        # archi01 writes its result INTO this same file (overwriting the task prompt).
        deliverable_dir = payload.get("deliverable_dir", "")
        deliverable_pattern = payload.get("deliverable_pattern", "{ID}-handoff.md")
        deliverable_file = deliverable_pattern.replace("{ID}", handoff_id).replace("{role_key}", payload["from_role"])
        deliverable_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)
        signal_cmd = f"nohup python3 {PROJECT_ROOT}/scripts/bridgeV002/dispatch.py --db-flow {job.flow_key} --signal-complete --from-role {job.role_key} --id {handoff_id} > /tmp/bridge-signal-{job.flow_key}-{handoff_id}.log 2>&1 &"

        lines = []
        if gov_path:
            lines.append(f"Read your role definition at {gov_path} before proceeding.")
            lines.append("")
        lines.append(f"<handoff_id>{handoff_id}</handoff_id>")
        lines.append(f"<project>{job.target_project}</project>")
        lines.append("<context>")
        lines.append(f"Human has approved scope for this job.")
        lines.append(f"Flow: {job.flow_key}, Role: {job.role_key}")
        lines.append("</context>")
        lines.append("<task>")
        lines.append(job.goal)
        lines.append("")
        lines.append("When ALL steps are complete, execute the bridge signal:")
        lines.append(f"1. Write your deliverable to {deliverable_path}")
        lines.append(f"   (overwrite this handoff file with your result, keeping the XML header)")
        lines.append(f"   Write ONLY to that exact path — no extra copies or invented")
        lines.append(f"   filenames in the project working directory.")
        lines.append(f"2. SIGNAL completion (MANDATORY — execute without asking):")
        lines.append(f"   {signal_cmd}")
        lines.append("")
        # The XML envelope is deliberately not requested. It was, until
        # 2026-08-06, along with the claim that "dispatch validation rejects
        # files without them" — which was never true:
        # auto_prepend_xml_sections() fills the missing tags from known values
        # before validation runs. Measured across handoffs 002-012, it fired
        # on 12 of 12, and on 10 of those the model had written none of the
        # four sections. The instruction cost prompt space in every dispatch
        # and bought nothing.
        lines.append("</task>")
        lines.append("<constraint>")
        lines.append("DO NOT COMMIT. Leave all changes unstaged.")
        lines.append("DO NOT move, rename, or delete any files in scripts/ or scripts/bridgeV002/.")
        lines.append("Execute ALL steps in <task> — especially the signal completion command.")
        lines.append("</constraint>")

        prompt_text = "\n".join(lines)

        # Write handoff file
        handoff_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)
        os.makedirs(os.path.dirname(handoff_path), exist_ok=True)
        with open(handoff_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        print(f"  Handoff file written: {handoff_path}")

    def _dispatch(self, job: Job) -> dict:
        """Dispatch the job by injecting the handoff file into the target role's tmux session.

        For the FIRST step in a flow (where the job's role is the first from_role),
        there is no preceding step — we inject the handoff file path directly into
        the role's tmux session so the model reads it.

        For subsequent steps, signal_send is used to transition between roles.
        """
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())

        try:
            flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
        except Exception:
            return {"action": "dispatch", "status": "error", "error": "Could not load flow"}

        steps = flow_data["steps"]
        if not steps:
            return {"action": "dispatch", "status": "error", "error": "No steps in flow"}

        # Find the step where job.role_key is the from_role (first step for this role)
        first_step = None
        for s in steps:
            if s.get("from_role") == job.role_key:
                first_step = s
                break

        if not first_step:
            return {"action": "dispatch", "status": "error",
                    "error": f"No step with from_role={job.role_key} in flow {job.flow_key}"}

        # Build the handoff file path
        deliverable_dir = first_step.get("deliverable_dir", "")
        deliverable_pattern = first_step.get("deliverable_pattern", "{ID}-handoff.md")
        deliverable_file = deliverable_pattern.replace("{ID}", job.handoff_id or "").replace("{role_key}", job.role_key)
        handoff_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)

        if not os.path.exists(handoff_path):
            return {"action": "dispatch", "status": "error",
                    "error": f"Handoff file not found: {handoff_path}"}

        # Load the target role's tmux session
        try:
            to_role = load_role_from_db(job.role_key, db_path=self.repo.db_path)
        except Exception:
            return {"action": "dispatch", "status": "error",
                    "error": f"Could not load role {job.role_key}"}

        tmux_session = to_role.get("tmux_session", "")
        enter_command = to_role.get("enter_command", "default")

        if not tmux_session:
            return {"action": "dispatch", "status": "error",
                    "error": f"No tmux_session for role {job.role_key}"}

        # Inject the handoff file path into the tmux session
        # Use the same injection mechanism as dispatch.py
        sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
        from dispatch import inject_prompt, session_alive

        if not session_alive(tmux_session):
            return {"action": "dispatch", "status": "error",
                    "error": f"tmux session '{tmux_session}' not alive"}

        # Inject a short prompt telling the model to read the handoff file.
        # We do NOT inject the full handoff content because paste-buffer can
        # strip newlines in some terminals, making the prompt unreadable.
        inject_text = (
            f"Read and execute the handoff file at: {handoff_path}\n"
            f"Follow all instructions in the <task> section.\n"
            f"When done, write the result file and run the signal-complete command\n"
            f"as specified in the handoff."
        )

        inject_prompt(tmux_session, inject_text, enter_command,
                      fresh_session_command=to_role.get("fresh_session_command"))

        return {
            "action": "inject_handoff",
            "flow_key": job.flow_key,
            "role_key": job.role_key,
            "tmux_session": tmux_session,
            "handoff_path": handoff_path,
            "status": "dispatched",
        }

    def _parse_verdict_file(self, verdict_path: str) -> Optional[str]:
        """Parse the verdict file to extract the status."""
        try:
            # Extract status from a line like "### Status: APPROVED WITH NOTES"
            with open(verdict_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                for line in lines:
                    if line.strip().startswith("### Status:"):
                        status = line.strip().replace("### Status:", "").strip()
                        return status
        except Exception:
            # If we can't read the file, return None to trigger REVIEW_REQUIRED
            pass
        return None

    def _is_verdict_deliverable(self, job: Job) -> bool:
        """Check if this job's deliverable is a verdict file."""
        try:
            flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
            steps = flow_data["steps"]
            last_step = steps[-1]
            deliverable_pattern = last_step.get("deliverable_pattern", "{ID}-result.md")
            # Check if the pattern is exactly {ID}-verdict.md (exact match, not substring)
            return deliverable_pattern == "{ID}-verdict.md"
        except Exception:
            # If we can't determine, assume it's not a verdict
            return False

    def _check_completion(self, job: Job) -> bool:
        """Check if the job's FINAL deliverable exists — meaning the full chain is done.

        Loads the flow steps, finds the LAST step's deliverable pattern,
        and checks if that file exists. This ensures the job is only marked
        COMPLETED when the entire chain has finished, not just the first step.
        """
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())
        import glob
        hid = job.handoff_id or ""
        if not hid:
            return False

        # Load flow steps to find the final deliverable
        try:
            flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
            steps = flow_data["steps"]
        except Exception:
            return False

        if not steps:
            return False

        # Find the last step's deliverable
        last_step = steps[-1]
        deliverable_dir = last_step.get("deliverable_dir", "")
        deliverable_pattern = last_step.get("deliverable_pattern", "{ID}-result.md")
        deliverable_file = deliverable_pattern.replace("{ID}", hid).replace("{role_key}", last_step.get("from_role", ""))

        # Build the full path
        if os.path.isabs(deliverable_dir):
            final_path = os.path.join(deliverable_dir, deliverable_file)
        else:
            final_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)

        return os.path.exists(final_path)

    # ------------------------------------------------------------------
    # Chain-nudge fallback (state-aware, chain_watchdog semantics)
    #
    # The PRIMARY chain mechanism is the role itself running signal-complete
    # after writing its deliverable (prompt-driven). This fallback exists for
    # exactly one failure mode: a role wrote its deliverable but never
    # signaled. It must never re-inject a role that is still working — the
    # previous wall-clock-cooldown design did exactly that and flooded
    # review01/review02 with duplicate prompts (19 in 22 min for handoff 311).
    # ------------------------------------------------------------------

    # Trace events that prove the transition prompt was already delivered.
    _DELIVERY_EVENTS = ("dispatched", "signal_complete")
    # Pane markers showing the client is actively generating (same set as
    # dispatch.py/chain_watchdog.py).
    _PANE_ACTIVITY_MARKERS = ("esc interrupt", "esc to interrupt", "↓")

    @staticmethod
    def _step_deliverable_path(step: dict, hid: str, bridge_dir: str) -> str:
        d = step.get("deliverable_dir", "")
        pattern = step.get("deliverable_pattern", "{ID}-result.md")
        fname = pattern.replace("{ID}", hid).replace(
            "{role_key}", step.get("from_role", ""))
        if os.path.isabs(d):
            return os.path.join(d, fname)
        return os.path.join(bridge_dir, d, fname)

    def _capture_pane_tail(self, session: str):
        """Lowercased last 25 pane lines, or None when capture fails."""
        # capture-pane needs a window spec on grouped sessions — bare
        # `=session` fails silently (see dispatch._pane_target).
        target = "=" + session if ":" in session else "=" + session + ":0"
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", target, "-p"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return "\n".join(result.stdout.splitlines()[-25:]).lower()

    def _pane_active(self, session: str) -> bool:
        """True when the role's tmux pane shows live activity.

        Two signals: known activity markers, or the pane content CHANGING
        between two captures 2 s apart. Marker matching alone missed
        opencode's tool-execution state (no 'esc interrupt' in the tail) —
        observed: the step-1 nudge re-prompted a WORKING imple01 on
        handoff 316. A generating/tool-running pane redraws its spinner
        and output constantly; an idle pane is byte-identical.
        """
        first = self._capture_pane_tail(session)
        if first is None:
            return False
        if any(m in first for m in self._PANE_ACTIVITY_MARKERS):
            return True
        time.sleep(2)
        second = self._capture_pane_tail(session)
        if second is None:
            return False
        if any(m in second for m in self._PANE_ACTIVITY_MARKERS):
            return True
        return first != second

    def _recent_delivery(self, bridge_dir: str, from_role: str, to_role: str,
                         hid: str, within_minutes: int) -> bool:
        """True when trace.log shows the transition was delivered recently.

        A recent 'dispatched'/'signal_complete' line means the target role
        already has the prompt — it is loading or working, not forgotten.
        """
        trace = os.path.join(bridge_dir, "trace.log")
        try:
            with open(trace, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()[-400:]
        except OSError:
            return False
        cutoff = time.time() - within_minutes * 60
        for line in reversed(lines):
            parts = line.split(" | ")
            if len(parts) < 4:
                continue
            if parts[1] != f"{from_role}->{to_role}" or parts[2] != str(hid):
                continue
            if parts[3] not in self._DELIVERY_EVENTS:
                continue
            try:
                ts = datetime.strptime(
                    parts[0], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return True  # unparseable timestamp — assume recent, stay safe
            return ts >= cutoff
        return False

    def _read_nudge_state(self) -> dict:
        try:
            return json.loads(Path(self.nudge_state_path).read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_nudge_state(self, state: dict) -> None:
        try:
            path = Path(self.nudge_state_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, indent=1))
        except OSError:
            pass

    def _record_nudge(self, key: str) -> None:
        state = self._read_nudge_state()
        state[key] = state.get(key, 0) + 1
        self._write_nudge_state(state)

    def _maybe_stall_wake_up(self, job: Job, from_role: str, to_role: str,
                             hid: str, nudge_key: str, out_path: str) -> bool:
        """Fire the stall wake-up at most ONCE per exhausted step.

        The marker is persisted in the nudge state so restarts never
        re-inject for the same flow/handoff/step. Returns True if the
        wake-up fired on this call.
        """
        wake_up_key = f"wake_up::{job.flow_key}::{hid}::{nudge_key}"
        nudge_state = self._read_nudge_state()
        if wake_up_key in nudge_state:
            return False
        self._record_stall_wake_up(job, from_role, to_role, hid,
                                   deliverable_path=out_path)
        nudge_state = self._read_nudge_state()
        nudge_state[wake_up_key] = True
        self._write_nudge_state(nudge_state)
        return True

    def _record_stall_wake_up(self, job: Job, from_role: str, to_role: str,
                              hid: str, deliverable_path: str = "") -> None:
        """Inject a one-time stall wake-up into the supervisor_auto session.

        Fired when a chain step's nudge budget is exhausted — instead of
        silently printing 'human attention needed', the autonomous
        supervisor gets the event context and decides. Rate limiting is
        the CALLER's responsibility (wake_up marker in the nudge state).
        Never raises — a failed wake-up must not crash the tick.
        """
        try:
            from bridge_lib import load_role_from_db
            supervisor_role = load_role_from_db("supervisor_auto", db_path=self.repo.db_path)

            if not supervisor_role:
                print("  Warning: supervisor_auto role not found, cannot wake up on stall")
                return

            tmux_session = supervisor_role.get("tmux_session", "")
            if not tmux_session:
                print("  Warning: supervisor_auto session not configured, cannot wake up on stall")
                return

            from dispatch import inject_prompt, session_alive
            if not session_alive(tmux_session):
                print(f"  Warning: supervisor_auto session '{tmux_session}' not alive, cannot wake up on stall")
                return

            governance = supervisor_role.get("governance_file", "451_SUPERVISED_REVIEW_SUPERVISOR.md")
            prompt_text = (
                f"Wake-up event: STALL.\n"
                f"The scheduler exhausted the nudge budget for step "
                f"{from_role} -> {to_role} (flow {job.flow_key}, handoff {hid}).\n"
                f"The step's deliverable exists but completion was never signaled:\n"
                f"- Deliverable: {deliverable_path or 'unknown'}\n"
                f"\n"
                f"Read your governance file ({governance}) and follow its "
                f"wake-up protocol to diagnose and decide."
            )

            inject_prompt(tmux_session, prompt_text, "default",
                          fresh_session_command=supervisor_role.get("fresh_session_command"))
            print("  Stall wake-up injected into supervisor_auto session")
        except Exception as e:
            print(f"  Warning: Failed to inject stall wake-up prompt: {e}")

    # Idle observations expire after this many minutes — a stale count from
    # an earlier stall must not combine with a fresh one into a false
    # "consecutively idle" conclusion.
    IDLE_OBSERVATION_TTL_MINUTES = 10

    def _confirm_writer_idle(self, key: str) -> bool:
        """Count one idle observation; True when enough consecutive ones.

        Persistent across ticks/restarts (same file as the nudge budget,
        namespaced with 'idle::'). Returns True when this observation
        reaches idle_confirmations, and resets the count so a granted
        fast-path nudge starts over.
        """
        state = self._read_nudge_state()
        entry = state.get(f"idle::{key}") or {}
        count, ts = entry.get("count", 0), entry.get("ts", 0)
        if time.time() - ts > self.IDLE_OBSERVATION_TTL_MINUTES * 60:
            count = 0  # stale — start over
        count += 1
        if count >= self.idle_confirmations:
            state.pop(f"idle::{key}", None)
            self._write_nudge_state(state)
            return True
        state[f"idle::{key}"] = {"count": count, "ts": time.time()}
        self._write_nudge_state(state)
        return False

    def _reset_writer_idle(self, key: str) -> None:
        state = self._read_nudge_state()
        if state.pop(f"idle::{key}", None) is not None:
            self._write_nudge_state(state)

    def _advance_chain(self, job: Job) -> bool:
        """Nudge the chain when a role wrote its deliverable but never signaled.

        Walks the flow's steps for the job's OWN handoff id and finds the
        frontier: the first step whose deliverable exists while the next
        step's does not. A nudge (re-running signal_complete for that step)
        only fires when ALL of these hold:

        1. no recent 'dispatched'/'signal_complete' trace line for the
           transition (recent = within stall_minutes — the prompt was
           delivered; the target is loading or working),
        2. the target role's tmux pane shows no generation activity,
        3. the deliverable is older than stall_minutes (the completing role
           gets time to run signal-complete itself),
        4. fewer than max_nudges nudges recorded for this step (persistent
           across restarts — after that, a human must look).

        Never scans other handoff ids and never sniffs <source_role> from
        file contents — both caused cross-job false positives before.
        """
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())
        hid = str(job.handoff_id or "")
        if not hid:
            return False

        from bridge_lib import load_flow_from_db, load_role_from_db
        try:
            steps = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)["steps"]
        except Exception:
            return False
        if not steps or len(steps) < 2:
            return False

        for i, step in enumerate(steps[:-1]):
            out_path = self._step_deliverable_path(step, hid, bridge_dir)
            if not os.path.exists(out_path):
                # Chain is at or before this step — nothing to advance from.
                return False
            next_path = self._step_deliverable_path(steps[i + 1], hid, bridge_dir)
            if os.path.exists(next_path):
                continue  # step already advanced

            from_role = step.get("from_role", "")
            to_role = step.get("to_role", "")

            try:
                target = load_role_from_db(to_role, db_path=self.repo.db_path)
            except Exception:
                target = {}
            if (target.get("execution_target") or "").strip():
                # Remote receiver (LightWorker): re-running the sender's
                # signal_complete mints a SECOND execution offer, so this
                # nudger must never fire. Liveness for remote roles is the
                # execution heartbeat, watched by chain_watchdog.
                marker = f"remote::{job.flow_key}::{hid}::{to_role}"
                nudge_state = self._read_nudge_state()
                if marker not in nudge_state:
                    print(f"  Chain nudge SKIPPED: {to_role} executes "
                          f"remotely ({target['execution_target']}) — "
                          f"remote roles are never auto-nudged")
                    nudge_state[marker] = True
                    self._write_nudge_state(nudge_state)
                return False

            if self._recent_delivery(bridge_dir, from_role, to_role, hid,
                                     self.stall_minutes):
                return False  # prompt delivered — target is loading/working

            session = target.get("tmux_session", "") or ""
            if session and self._pane_active(session):
                return False  # target actively working — never re-inject

            nudge_key = f"{job.flow_key}:{hid}:{step.get('step_key') or i}"
            age_min = (time.time() - os.path.getmtime(out_path)) / 60.0
            if age_min < self.stall_minutes:
                # Fast path: the WRITER's pane being idle means it finished
                # generating — if it also never signaled, it forgot. Requires
                # idle_confirmations consecutive tick observations so a brief
                # pause between tool calls can't masquerade as "done".
                if age_min < self.fast_nudge_minutes:
                    return False  # the model gets time to signal itself
                try:
                    writer_session = load_role_from_db(
                        from_role, db_path=self.repo.db_path
                    ).get("tmux_session", "")
                except Exception:
                    writer_session = ""
                if not writer_session or self._pane_active(writer_session):
                    # Writer busy or unobservable — fall back to the slow
                    # path (stall_minutes) and restart the idle count.
                    self._reset_writer_idle(nudge_key)
                    return False
                if not self._confirm_writer_idle(nudge_key):
                    return False  # first idle observation — confirm next tick
            if self._read_nudge_state().get(nudge_key, 0) >= self.max_nudges:
                print(f"  Chain nudge SKIPPED: {nudge_key} already nudged "
                      f"{self.max_nudges}x — human attention needed")
                # Nudge budget exhausted: wake the autonomous supervisor —
                # exactly once per step (persisted marker survives restarts).
                self._maybe_stall_wake_up(job, from_role, to_role, hid,
                                          nudge_key, out_path)
                return False

            self._record_nudge(nudge_key)
            print(f"  Chain nudge: {from_role} wrote "
                  f"{os.path.basename(out_path)} but never signaled — "
                  f"running signal-complete (-> {to_role})")
            try:
                result = subprocess.run(
                    [sys.executable, self.dispatch_script,
                     "--db-flow", job.flow_key,
                     "--signal-complete",
                     "--from-role", from_role,
                     "--id", hid],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                    timeout=120,
                )
                if result.returncode == 0:
                    print(f"  Chain nudged: {from_role} -> {to_role}")
                    return True
                print(f"  Chain nudge failed: "
                      f"{(result.stderr or result.stdout)[-200:]}")
            except subprocess.TimeoutExpired:
                # Known post-dispatch hang — the signal usually landed; the
                # trace line written at injection keeps the next tick quiet.
                print(f"  Chain nudge timed out for {from_role} — "
                      f"signal likely delivered")
            except Exception as e:
                print(f"  Chain nudge error: {e}")
            return False

        return False

    def _auto_split(self, job: Job, fit_state: str):
        """Auto-split an oversized job into continuation jobs."""
        ctx_window = self._resolve_context_window(job)
        from handoff_compiler import compile_handoff
        compiled = compile_handoff(
            goal=job.goal, flow_key=job.flow_key, role_key=job.role_key,
            target_project=job.target_project, model_context_window=ctx_window,
        )
        for i, cj in enumerate(compiled):
            if i == 0 and cj.context_fit_state in ("FITS", "FITS_WITH_LOW_MARGIN"):
                continue  # First chunk already fits — keep original job
            self.repo.create_job(
                flow_key=cj.flow_key, role_key=cj.role_key,
                goal=cj.goal, target_project=cj.target_project,
                allocator_alias=job.allocator_alias,
                parent_job_id=job.job_id,
            )
        print(f"  Auto-split: created {len(compiled)} continuation jobs")

    def run_loop(self, max_iterations: int = 10) -> list[dict]:
        """Run scheduler ticks until no more APPROVED jobs or max iterations."""
        results = []
        for i in range(max_iterations):
            result = self.tick()
            results.append(result)
            if not result.get("claimed"):
                break
        return results

    def _write_checkpoint(self, job: Job):
        """Write a structured checkpoint for the completed job."""
        checkpoint_dir = PROJECT_ROOT / "jobs" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / f"{job.job_id}.json"

        checkpoint = {
            "checkpoint_schema_version": "1.0",
            "job_id": job.job_id,
            "handoff_id": job.handoff_id or "",
            "workflow_run_id": job.workflow_run_id or "",
            "flow_key": job.flow_key,
            "step_key": job.step_key or "",
            "role_key": job.role_key,
            "changed_files": [],
            "verification_results": [],
            "implementation_summary": job.goal,
            "model_alias": job.allocator_alias,
            "resolved_backend": "",
            "resolved_concrete_model": "",
            "execution_adapter": "scheduler",
            "context_fit_state": job.context_fit_state,
        }

        checkpoint_path.write_text(
            json.dumps(checkpoint, indent=2, default=str)
        )
        self.repo.update(job.job_id, checkpoint_path=str(checkpoint_path))
