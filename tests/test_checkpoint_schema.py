"""Tests for the Checkpoint schema spike (Task 4.3)."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

from checkpoint_schema import (
    Checkpoint, VerificationResult, validate_checkpoint,
    CHECKPOINT_SCHEMA_VERSION, make_checkpoint_from_runtime_spike,
)


def test_checkpoint_roundtrip():
    """Checkpoint serializes to JSON and back."""
    cp = Checkpoint(
        job_id="JOB-001",
        handoff_id="178",
        workflow_run_id="WF-ABCD",
        flow_key="strict_review",
        step_key="archi01-imple01",
        role_key="imple01",
        changed_files=["scripts/new_feature.py"],
        verification_results=[
            VerificationResult(check="py_compile", file="scripts/new_feature.py", status="PASS"),
        ],
        implementation_summary="Added new_feature.py",
        model_alias="imple01-local",
        resolved_backend="ollama",
        resolved_concrete_model="qwen3-coder:30b-256k",
        execution_adapter="python-runtime",
    )
    
    json_str = cp.to_json()
    restored = Checkpoint.from_json(json_str)
    
    assert restored.job_id == "JOB-001"
    assert restored.changed_files == ["scripts/new_feature.py"]
    assert restored.verification_results[0].status == "PASS"
    assert restored.model_alias == "imple01-local"


def test_checkpoint_validation_missing_fields():
    """Empty checkpoint must fail validation."""
    cp = Checkpoint()
    errors = validate_checkpoint(cp)
    assert len(errors) > 0
    assert any("job_id" in e for e in errors)
    assert any("handoff_id" in e for e in errors)
    assert any("model_alias" in e for e in errors)


def test_checkpoint_validation_wrong_schema_version():
    """Wrong schema version must be rejected."""
    cp = Checkpoint(
        checkpoint_schema_version="0.9",
        job_id="JOB-001",
        handoff_id="178",
        flow_key="strict_review",
        step_key="step1",
        role_key="imple01",
        changed_files=["a.py"],
        verification_results=[VerificationResult(check="py_compile", file="a.py", status="PASS")],
        implementation_summary="done",
        model_alias="imple01-local",
        resolved_backend="ollama",
        resolved_concrete_model="qwen3-coder:30b-256k",
    )
    errors = validate_checkpoint(cp)
    assert any("Schema version mismatch" in e for e in errors)


def test_checkpoint_validation_bad_verification_status():
    """VerificationResult with invalid status must be rejected."""
    cp = Checkpoint(
        job_id="JOB-001",
        handoff_id="178",
        flow_key="strict_review",
        step_key="step1",
        role_key="imple01",
        changed_files=["a.py"],
        verification_results=[
            VerificationResult(check="py_compile", file="a.py", status="MAYBE"),
        ],
        implementation_summary="done",
        model_alias="imple01-local",
        resolved_backend="ollama",
        resolved_concrete_model="qwen3-coder:30b-256k",
    )
    errors = validate_checkpoint(cp)
    assert any("status must be PASS or FAIL" in e for e in errors)


def test_checkpoint_from_runtime_spike():
    """make_checkpoint_from_runtime_spike creates a valid checkpoint."""
    cp = make_checkpoint_from_runtime_spike(
        handoff_id="SPIKE-1",
        flow_key="strict_review",
        step_key="archi01-imple01",
        role_key="imple01",
        changed_files=["scripts/spike_marker.py"],
        validation_results=["py_compile scripts/spike_marker.py: PASS"],
        summary="Created spike_marker.py",
        model_alias="imple01-local",
        backend="ollama",
        concrete_model="qwen3-coder:30b-256k",
    )
    errors = validate_checkpoint(cp)
    assert not errors, f"Validation errors: {errors}"
    assert cp.execution_adapter == "python-runtime"
    assert cp.verification_results[0].check == "py_compile"
    assert cp.verification_results[0].status == "PASS"


def test_checkpoint_is_model_independent():
    """Checkpoint must NOT require conversation or scrollback."""
    cp = Checkpoint(
        job_id="JOB-001",
        handoff_id="178",
        flow_key="strict_review",
        step_key="archi01-imple01",
        role_key="imple01",
        changed_files=["scripts/new.py"],
        verification_results=[
            VerificationResult(check="py_compile", file="scripts/new.py", status="PASS"),
        ],
        implementation_summary="Added new.py",
        model_alias="imple01-local",
        resolved_backend="ollama",
        resolved_concrete_model="qwen3-coder:30b-256k",
        execution_adapter="python-runtime",
    )
    
    # The next role can start from:
    # 1. The checkpoint (this object)
    # 2. The approved contract (handoff file)
    # 3. The relevant diff (git diff)
    # 4. Required artifacts (changed_files list)
    
    # It must NOT require:
    # - Previous model conversation (not in checkpoint)
    # - tmux scrollback (not in checkpoint)
    
    json_str = cp.to_json()
    data = json.loads(json_str)
    
    # No conversation messages
    assert "messages" not in data
    assert "conversation" not in data
    assert "scrollback" not in data
    
    # Has everything needed for continuation
    assert data["changed_files"] == ["scripts/new.py"]
    assert data["implementation_summary"] == "Added new.py"
    assert data["model_alias"] == "imple01-local"
