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
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

import config
from job_queue.models import JobRepository, Job, IllegalTransitionError


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

    def tick(self) -> dict:
        """One scheduler pass. Returns summary of what happened."""
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
        1. Try to advance the chain (if an intermediate result exists)
        2. Check if the final deliverable exists → mark COMPLETED

        Returns list of completed job_ids.
        """
        completed = []
        running_jobs = self.repo.list_jobs(status="RUNNING")
        for job in running_jobs:
            # Try to advance the chain (dispatch next step if needed)
            self._advance_chain(job)

            # Check if the final deliverable exists
            if self._check_completion(job):
                try:
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
        from bridge_lib import load_flow_from_db, get_next_id_for_flow, load_role_from_db
        from dispatch import build_step_payload

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

        # Assign handoff ID
        handoff_id = str(get_next_id_for_flow(job.flow_key, db_path=self.repo.db_path))
        self.repo.update(job.job_id, handoff_id=handoff_id)
        job = self.repo.get_job(job.job_id)

        # Build payload
        payload = build_step_payload(step, job.flow_key, handoff_id, bridge_dir)

        # Load to_role governance
        to_role = load_role_from_db(payload["to_role"], db_path=self.repo.db_path)
        gov_file = to_role.get("governance_file", "")
        gov_path = str(PROJECT_ROOT / "docs" / "governance-templates-v2" / gov_file) if gov_file else ""

        # Build handoff prompt
        deliverable_dir = payload.get("deliverable_dir", "")
        deliverable_pattern = payload.get("deliverable_pattern", "{ID}-handoff.md")
        deliverable_file = deliverable_pattern.replace("{ID}", handoff_id).replace("{role_key}", payload["from_role"])
        handoff_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)
        signal_cmd = f"python3 {PROJECT_ROOT}/scripts/bridgeV002/dispatch.py --db-flow {job.flow_key} --signal-complete --from-role {job.role_key} --id {handoff_id}"

        # Find the next step (the one that receives from this role) to determine
        # where the result should be written. The result file is the deliverable
        # of the NEXT step (e.g. imple01→review01 has deliverable in results/).
        result_path = ""
        for idx, s in enumerate(steps):
            if s.get("from_role") == job.role_key and idx + 1 < len(steps):
                next_step = steps[idx + 1]
                next_dir = next_step.get("deliverable_dir", "")
                next_pattern = next_step.get("deliverable_pattern", "{ID}-result.md")
                next_file = next_pattern.replace("{ID}", handoff_id).replace("{role_key}", job.role_key)
                if os.path.isabs(next_dir):
                    result_path = os.path.join(next_dir, next_file)
                else:
                    result_path = os.path.join(bridge_dir, next_dir, next_file)
                break

        lines = [
            f"<role>You are {job.role_key} in the DPMtF {job.flow_key} flow.",
        ]
        if gov_path:
            lines.append(f"Your role is defined in {gov_path}.")
        lines.append("Read it now before proceeding.</role>")
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
        lines.append(f"1. Write result file to {result_path}")
        lines.append(f"2. SIGNAL completion: {signal_cmd}")
        lines.append("")
        lines.append("IMPORTANT: The result file MUST start with these XML sections")
        lines.append("(dispatch validation rejects files without them):")
        lines.append(f"  <handoff_id>{handoff_id}</handoff_id>")
        lines.append(f"  <source_role>{job.role_key}</source_role>")
        lines.append(f"  <deliverable_input>")
        lines.append(f"    {handoff_path}")
        lines.append(f"  </deliverable_input>")
        lines.append(f"  <deliverable_output>")
        lines.append(f"    result: {result_path}")
        lines.append(f"  </deliverable_output>")
        lines.append("Then write your result content below the XML header.")
        lines.append("</task>")
        lines.append("<constraint>")
        lines.append("DO NOT COMMIT. Leave all changes unstaged.")
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
        from bridge_lib import load_flow_from_db, load_role_from_db
        import config as dpmtf_config

        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path())

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

        inject_prompt(tmux_session, inject_text, enter_command)

        return {
            "action": "inject_handoff",
            "flow_key": job.flow_key,
            "role_key": job.role_key,
            "tmux_session": tmux_session,
            "handoff_path": handoff_path,
            "status": "dispatched",
        }

    def _check_completion(self, job: Job) -> bool:
        """Check if the job's FINAL deliverable exists — meaning the full chain is done.

        Loads the flow steps, finds the LAST step's deliverable pattern,
        and checks if that file exists. This ensures the job is only marked
        COMPLETED when the entire chain (archi01→imple01→review01→review02→human)
        has finished, not just the first step.
        """
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())
        import glob
        hid = job.handoff_id or ""
        if not hid:
            return False

        # Load flow steps to find the final deliverable
        from bridge_lib import load_flow_from_db
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

    def _advance_chain(self, job: Job) -> bool:
        """Check if an intermediate step's result exists and advance the chain.

        For each step in the flow (except the first and last), check if the
        step's deliverable file exists. If it does AND the next step's deliverable
        does NOT exist, run signal_complete to dispatch to the next role.

        Step 0 is skipped because it's dispatched by _dispatch (direct injection).
        The handoff file (step 0's deliverable) is written by the scheduler, not by
        a model — so its existence doesn't indicate model completion.

        Returns True if a chain advancement was made.
        """
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())
        hid = job.handoff_id or ""
        if not hid:
            return False

        from bridge_lib import load_flow_from_db
        try:
            flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
            steps = flow_data["steps"]
        except Exception:
            return False

        if not steps or len(steps) < 2:
            return False

        for i, step in enumerate(steps[1:-1], start=1):
            # Check if this step's deliverable exists
            deliverable_dir = step.get("deliverable_dir", "")
            deliverable_pattern = step.get("deliverable_pattern", "{ID}-result.md")
            deliverable_file = deliverable_pattern.replace("{ID}", hid).replace("{role_key}", step.get("from_role", ""))

            if os.path.isabs(deliverable_dir):
                step_path = os.path.join(deliverable_dir, deliverable_file)
            else:
                step_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)

            if not os.path.exists(step_path):
                continue  # This step hasn't completed yet

            # Check if the NEXT step's deliverable exists
            next_step = steps[i + 1]
            next_dir = next_step.get("deliverable_dir", "")
            next_pattern = next_step.get("deliverable_pattern", "{ID}-result.md")
            next_file = next_pattern.replace("{ID}", hid).replace("{role_key}", next_step.get("from_role", ""))

            if os.path.isabs(next_dir):
                next_path = os.path.join(next_dir, next_file)
            else:
                next_path = os.path.join(bridge_dir, next_dir, next_file)

            if os.path.exists(next_path):
                continue  # Next step already done — chain already advanced

            # This step's deliverable exists but next step's doesn't — advance!
            from_role = step.get("from_role", "")
            to_role = step.get("to_role", "")
            print(f"  Chain advancement: {from_role} completed (step {i+1}/{len(steps)}), "
                  f"dispatching to {to_role}")

            try:
                result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py"),
                     "--db-flow", job.flow_key,
                     "--signal-complete",
                     "--from-role", from_role,
                     "--id", hid],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                    timeout=120,
                )
                if result.returncode == 0:
                    print(f"  Chain advanced: {from_role} -> {to_role}")
                    return True
                else:
                    print(f"  Chain advancement failed: {result.stderr[-200:] if result.stderr else result.stdout[-200:]}")
            except subprocess.TimeoutExpired:
                print(f"  Chain advancement timed out for {from_role}")
            except Exception as e:
                print(f"  Chain advancement error: {e}")

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
