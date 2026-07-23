#!/usr/bin/env python3
"""Checkpoint spike — versioned, validated schema for durable step artifacts.

A checkpoint is a model-independent continuation record. The next role
can start from the checkpoint + the approved contract + the diff,
without requiring the previous model conversation or tmux scrollback.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import re


CHECKPOINT_SCHEMA_VERSION = "1.0"


@dataclass
class VerificationResult:
    check: str
    file: str
    status: str  # PASS | FAIL
    detail: str = ""


@dataclass
class Checkpoint:
    """Durable, model-independent checkpoint for a completed step."""
    # Identity
    checkpoint_schema_version: str = CHECKPOINT_SCHEMA_VERSION
    job_id: str = ""
    handoff_id: str = ""
    workflow_run_id: str = ""
    flow_key: str = ""
    step_key: str = ""
    role_key: str = ""
    
    # Scope
    approved_scope_version: str = ""
    scope_hash: str = ""
    base_commit: str = ""
    result_commit: str = ""
    
    # Artifacts
    changed_files: list[str] = field(default_factory=list)
    verification_results: list[VerificationResult] = field(default_factory=list)
    test_results: dict = field(default_factory=dict)
    implementation_summary: str = ""
    unresolved_items: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    
    # Model info
    model_alias: str = ""
    resolved_backend: str = ""
    resolved_concrete_model: str = ""
    execution_adapter: str = ""  # opencode | claude-code | python-runtime
    
    # Timestamps
    started_at: str = ""
    completed_at: str = ""
    
    def to_json(self) -> str:
        """Serialize to JSON with proper nested dataclass handling."""
        d = asdict(self)
        return json.dumps(d, indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "Checkpoint":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        # Handle nested VerificationResult objects
        vrs = data.pop("verification_results", [])
        verified_vrs = []
        for vr in vrs:
            if isinstance(vr, dict):
                verified_vrs.append(VerificationResult(**vr))
            else:
                verified_vrs.append(vr)
        data["verification_results"] = verified_vrs
        return cls(**data)


# ── Validation ───────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "checkpoint_schema_version",
    "job_id",
    "handoff_id",
    "flow_key",
    "step_key",
    "role_key",
    "changed_files",
    "verification_results",
    "implementation_summary",
    "model_alias",
    "resolved_backend",
    "resolved_concrete_model",
]


def validate_checkpoint(checkpoint: Checkpoint) -> list[str]:
    """Validate a checkpoint. Returns list of error messages (empty = valid)."""
    errors = []
    
    for field_name in REQUIRED_FIELDS:
        value = getattr(checkpoint, field_name, None)
        if not value:
            errors.append(f"Missing required field: {field_name}")
    
    if checkpoint.checkpoint_schema_version != CHECKPOINT_SCHEMA_VERSION:
        errors.append(
            f"Schema version mismatch: got {checkpoint.checkpoint_schema_version}, "
            f"expected {CHECKPOINT_SCHEMA_VERSION}"
        )
    
    # scope_hash must be a valid hex string if present
    if checkpoint.scope_hash:
        if not re.match(r'^[a-f0-9]+$', checkpoint.scope_hash):
            errors.append(f"Invalid scope_hash: {checkpoint.scope_hash}")
    
    # verification_results must be VerificationResult objects
    for i, vr in enumerate(checkpoint.verification_results):
        if not isinstance(vr, VerificationResult):
            errors.append(f"verification_results[{i}] is not a VerificationResult")
            continue
        if vr.status not in ("PASS", "FAIL"):
            errors.append(f"verification_results[{i}].status must be PASS or FAIL, got {vr.status}")
        if not vr.check or not vr.file:
            errors.append(f"verification_results[{i}] missing check or file")
    
    # test_results must have passed/failed counts
    if checkpoint.test_results:
        if "passed" not in checkpoint.test_results:
            errors.append("test_results missing 'passed' key")
        if "failed" not in checkpoint.test_results:
            errors.append("test_results missing 'failed' key")
    
    return errors


def make_checkpoint_from_runtime_spike(
    handoff_id: str, flow_key: str, step_key: str, role_key: str,
    changed_files: list[str], validation_results: list[str],
    summary: str, model_alias: str, backend: str, concrete_model: str,
) -> Checkpoint:
    """Create a checkpoint from the Python Runtime spike's output."""
    verification_results = []
    for result in validation_results:
        # Format: "py_compile scripts/file.py: PASS" or "node --check file.js: FAIL ..."
        status = "PASS" if "PASS" in result else "FAIL"
        if ":" in result:
            before_colon = result.rsplit(":", 1)[0].strip()
            parts = before_colon.split(None, 1)
            check_name = parts[0] if parts else before_colon
            file = parts[1] if len(parts) > 1 else ""
        else:
            check_name = result.strip()
            file = ""
        verification_results.append(VerificationResult(
            check=check_name, file=file, status=status, detail=result
        ))
    
    return Checkpoint(
        job_id=f"JOB-{handoff_id}",
        handoff_id=handoff_id,
        flow_key=flow_key,
        step_key=step_key,
        role_key=role_key,
        changed_files=changed_files,
        verification_results=verification_results,
        implementation_summary=summary,
        model_alias=model_alias,
        resolved_backend=backend,
        resolved_concrete_model=concrete_model,
        execution_adapter="python-runtime",
    )
