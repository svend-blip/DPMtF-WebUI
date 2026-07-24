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
        """Check all RUNNING jobs for deliverable files.

        If a deliverable is found, transition to VERIFYING → write checkpoint → COMPLETED.
        Returns list of completed job_ids.
        """
        completed = []
        running_jobs = self.repo.list_jobs(status="RUNNING")
        for job in running_jobs:
            if self._check_completion(job):
                try:
                    self.repo.transition(job.job_id, "VERIFYING", actor=self.worker_id)
                    self._write_checkpoint(job)
                    self.repo.transition(job.job_id, "COMPLETED", actor=self.worker_id)
                    completed.append(job.job_id)
                    print(f"  Job {job.job_id} completed — checkpoint written")
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
        result_dir = os.path.join(os.path.dirname(deliverable_dir) if deliverable_dir else bridge_dir, "results")
        result_path = os.path.join(result_dir, f"{handoff_id}-result.md")
        signal_cmd = f"python3 {PROJECT_ROOT}/scripts/bridgeV002/dispatch.py --db-flow {job.flow_key} --signal-complete --from-role {job.role_key}"

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
        lines.append("</task>")
        lines.append("<constraint>")
        lines.append("DO NOT COMMIT. Leave all changes unstaged.")
        lines.append("Execute ALL steps in <task> — especially the signal completion command.")
        lines.append("</constraint>")

        prompt_text = "\n".join(lines)

        # Write handoff file
        deliverable_pattern = payload.get("deliverable_pattern", "{ID}-handoff.md")
        deliverable_file = deliverable_pattern.replace("{ID}", handoff_id).replace("{role_key}", payload["from_role"])
        handoff_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)
        os.makedirs(os.path.dirname(handoff_path), exist_ok=True)
        with open(handoff_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        print(f"  Handoff file written: {handoff_path}")

    def _dispatch(self, job: Job) -> dict:
        """Dispatch the job via dispatch.py signal_send.

        Uses the step's from_role (not hardcoded) so it works for any step
        in the flow, not just the first.
        """
        # Resolve from_role from the step
        from bridge_lib import load_flow_from_db
        try:
            flow_data = load_flow_from_db(job.flow_key, db_path=self.repo.db_path)
            from_role = "human"  # default for first step
            for s in flow_data["steps"]:
                if s.get("to_role") == job.role_key:
                    from_role = s.get("from_role", "human")
                    break
                if s.get("from_role") == job.role_key:
                    # This role is a sender, not a receiver — skip
                    continue
        except Exception:
            from_role = "human"

        try:
            result = subprocess.run(
                [sys.executable, self.dispatch_script,
                 "--db-flow", job.flow_key,
                 "--signal-send",
                 "--from-role", from_role,
                 "--to-role", job.role_key,
                 "--id", job.handoff_id or job.job_id[-3:]],
                capture_output=True, text=True,
                cwd=str(PROJECT_ROOT),
                timeout=120,
            )
            return {
                "action": "signal_send",
                "flow_key": job.flow_key,
                "role_key": job.role_key,
                "allocator_alias": job.allocator_alias,
                "status": "dispatched" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "output": (result.stdout or "")[-500:],
            }
        except subprocess.TimeoutExpired:
            return {"action": "signal_send", "status": "timeout"}
        except Exception as e:
            return {"action": "signal_send", "status": "error", "error": str(e)}

    def _check_completion(self, job: Job) -> bool:
        """Check if the job's result/deliverable file exists.

        Looks specifically for result files and callback files — NOT the
        handoff file itself (which is the input, not the output).
        """
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", config.get_bridge_base_path())
        import glob
        hid = job.handoff_id or ""
        if not hid:
            return False
        # Look for result files, callback files, verdict files — not handoff files
        # The handoff file (input) is excluded; only output deliverables count.
        result_patterns = [
            os.path.join(bridge_dir, job.flow_key, "**", f"*{hid}-result*"),
            os.path.join(bridge_dir, job.flow_key, "**", f"*{hid}-callback*"),
            os.path.join(bridge_dir, job.flow_key, "**", f"*{hid}-verdict*"),
            os.path.join(bridge_dir, job.flow_key, "results", f"*{hid}*"),
        ]
        for pattern in result_patterns:
            matches = glob.glob(pattern, recursive=True)
            if matches:
                # Exclude the handoff file itself (it's the input, not output)
                matches = [m for m in matches if "-handoff" not in m]
                if matches:
                    return True
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
