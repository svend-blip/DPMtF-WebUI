"""Result writer — produces structured result files and checkpoints.

After a runtime execution completes (or is blocked), this module writes:
1. A result .md file (human-readable, for bridge deliverable)
2. A checkpoint JSON file (machine-readable, for fresh-context continuation)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from checks import CheckResult
from checkpoint_schema import Checkpoint, VerificationResult, make_checkpoint_from_runtime_spike


def write_result(
    result_path: str,
    handoff_id: str,
    model: str,
    status: str,
    summary: str,
    changed: list[str],
    check_results: list[CheckResult],
    project_root: str,
):
    """Write a human-readable result .md file."""
    validation_lines = [f"- {r.check} {r.file}: {r.status}" + (f" {r.detail}" if r.detail else "")
                        for r in check_results] or ["(none)"]
    
    git_diff = subprocess.run(
        ["git", "-C", project_root, "diff", "--stat"],
        capture_output=True, text=True,
    ).stdout.strip() or "(no diff)"

    blocks = [
        "# imple01 Result",
        f"## Handoff ID\n{handoff_id}",
        f"## Runtime\n- Backend: python_runtime\n- Model: {model}",
        f"## Status\n{status}",
        f"## Implementation Summary\n{summary}",
        "## Changed Files\n" + ("\n".join(f"- {c}" for c in sorted(changed)) or "(none)"),
        "## Validation\n" + "\n".join(validation_lines),
        "## Git State\n- No commit created\n- Changes unstaged\n" + git_diff,
    ]

    out = Path(result_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(blocks) + "\n")


def write_checkpoint(
    checkpoint_dir: str,
    handoff_id: str,
    flow_key: str,
    step_key: str,
    role_key: str,
    changed: list[str],
    check_results: list[CheckResult],
    summary: str,
    model_alias: str,
    backend: str,
    concrete_model: str,
) -> str:
    """Write a structured checkpoint JSON file. Returns path."""
    verification_results = [
        VerificationResult(check=r.check, file=r.file, status=r.status, detail=r.detail)
        for r in check_results
    ]

    cp = Checkpoint(
        job_id=f"JOB-{handoff_id}",
        handoff_id=handoff_id,
        flow_key=flow_key,
        step_key=step_key,
        role_key=role_key,
        changed_files=changed,
        verification_results=verification_results,
        implementation_summary=summary,
        model_alias=model_alias,
        resolved_backend=backend,
        resolved_concrete_model=concrete_model,
        execution_adapter="python-runtime",
    )

    out_dir = Path(checkpoint_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{handoff_id}.json"
    out_path.write_text(cp.to_json())
    return str(out_path)
