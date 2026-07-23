"""Checkpoint integration — writes structured checkpoints during dispatch.

When signal_complete fires, this module:
1. Reads the deliverable file (the role's output)
2. Runs validation checks on changed files
3. Creates a structured checkpoint JSON
4. Stores the checkpoint path in the job record (if a job exists)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

from checkpoint_schema import Checkpoint, VerificationResult, validate_checkpoint


def create_checkpoint_for_dispatch(
    handoff_id: str,
    flow_key: str,
    step_key: str,
    from_role: str,
    to_role: str,
    deliverable_path: str,
    bridge_dir: str,
    model_alias: str = "",
    model_backend: str = "",
    concrete_model: str = "",
) -> Optional[str]:
    """Create a checkpoint after signal_complete dispatches to the next role.

    Returns checkpoint file path, or None if creation fails.
    """
    checkpoint_dir = Path(PROJECT_ROOT) / "jobs" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Read deliverable for summary (if it exists)
    summary = ""
    if os.path.exists(deliverable_path):
        try:
            with open(deliverable_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Extract summary from first 500 chars
            summary = content[:500]
        except Exception:
            pass

    # Get git diff stat for changed files
    changed_files = []
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "diff", "--name-only"],
            capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip():
            changed_files = [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        pass

    # Run verification on changed files
    verification_results = []
    for rel in changed_files:
        abs_path = str(Path(PROJECT_ROOT) / rel)
        if rel.endswith(".py"):
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "py_compile", abs_path],
                    capture_output=True, text=True, timeout=30,
                )
                status = "PASS" if r.returncode == 0 else "FAIL"
                detail = "" if r.returncode == 0 else r.stderr.strip()[:200]
                verification_results.append(VerificationResult(
                    check="py_compile", file=rel, status=status, detail=detail
                ))
            except Exception:
                verification_results.append(VerificationResult(
                    check="py_compile", file=rel, status="FAIL", detail="error"
                ))

    # Create checkpoint
    cp = Checkpoint(
        handoff_id=handoff_id,
        flow_key=flow_key,
        step_key=step_key,
        role_key=from_role,
        changed_files=changed_files,
        verification_results=verification_results,
        implementation_summary=summary,
        model_alias=model_alias,
        resolved_backend=model_backend,
        resolved_concrete_model=concrete_model,
        execution_adapter="dispatch",
    )

    # Validate
    errors = validate_checkpoint(cp)
    if errors:
        # Log but still write — partial info is better than none
        print(f"  Checkpoint validation warnings: {errors}", file=sys.stderr)

    # Write
    checkpoint_path = checkpoint_dir / f"{handoff_id}_{from_role}_to_{to_role}.json"
    checkpoint_path.write_text(cp.to_json())

    # Update job if one exists for this handoff
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from job_queue.models import JobRepository
        repo = JobRepository()
        jobs = repo.list_jobs(flow_key=flow_key)
        for job in jobs:
            if job.handoff_id == handoff_id:
                repo.update(job.job_id, checkpoint_path=str(checkpoint_path))
                break
    except Exception:
        pass  # No job table or no matching job — not an error

    return str(checkpoint_path)
