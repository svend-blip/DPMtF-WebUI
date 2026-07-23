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

        # 2. Claim oldest APPROVED job
        job = self.repo.claim(self.worker_id)
        if job is None:
            return {"claimed": False, "recovered": recovered}

        result = {"claimed": True, "job_id": job.job_id, "recovered": recovered}

        try:
            # 3. Context-fit preflight
            fit_state = self._context_fit_check(job)
            self.repo.update(job.job_id, context_fit_state=fit_state)

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

            # 6. Dispatch (signal_send to start the role)
            dispatch_result = self._dispatch(job)
            result["dispatch"] = dispatch_result

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

    def _context_fit_check(self, job: Job) -> str:
        """Evaluate context fit. Returns a fit state."""
        # Simple heuristic for now — production will use context_fit_spike
        # If goal is very large, require split
        goal_tokens = len(job.goal) // 4
        if goal_tokens > 5000:
            return "SPLIT_REQUIRED"
        return "FITS"

    def _resolve_alias(self, job: Job) -> str:
        """Resolve allocator alias for the job's role."""
        from bridge_lib import get_effective_model_source
        source, alias = get_effective_model_source(
            job.role_key, flow_key=job.flow_key, db_path=self.repo.db_path
        )
        return alias or ""

    def _dispatch(self, job: Job) -> dict:
        """Dispatch the job via dispatch.py signal_send."""
        try:
            result = subprocess.run(
                [sys.executable, self.dispatch_script,
                 "--db-flow", job.flow_key,
                 "--signal-send",
                 "--from-role", "human",
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
        """Check if the job's deliverable file exists."""
        # Check for deliverable in the bridge directory
        bridge_dir = config.get_bridge_base_path()
        # Look for files matching the handoff pattern
        import glob
        patterns = [
            os.path.join(bridge_dir, job.flow_key, "**", f"*{job.handoff_id or job.job_id[-3:]}*"),
            os.path.join(bridge_dir, "**", f"*{job.handoff_id}*"),
        ]
        for pattern in patterns:
            matches = glob.glob(pattern, recursive=True)
            if matches:
                return True
        # If no handoff_id is set, we can't check — assume not complete
        return False

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
