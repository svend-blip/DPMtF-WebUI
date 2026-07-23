"""Tests for checkpoint integration with dispatch (Structured Checkpoints)."""
import sys
import json
import os
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
sys.path.insert(0, str(PROJECT_ROOT))

from checkpoint_integration import create_checkpoint_for_dispatch
from checkpoint_schema import Checkpoint, validate_checkpoint


def test_checkpoint_created_with_correct_fields(tmp_path):
    """create_checkpoint_for_dispatch produces a valid checkpoint."""
    deliverable = tmp_path / "result.md"
    deliverable.write_text("# Result\n\n## Summary\nDid the thing")
    
    # Mock PROJECT_ROOT for git diff
    with patch("checkpoint_integration.PROJECT_ROOT", tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "", "stderr": "", "returncode": 0
            })()
            path = create_checkpoint_for_dispatch(
                handoff_id="178",
                flow_key="strict_review",
                step_key="archi01-imple01",
                from_role="archi01",
                to_role="imple01",
                deliverable_path=str(deliverable),
                bridge_dir=str(tmp_path / "bridge"),
                model_alias="archi-local",
                model_backend="ollama",
                concrete_model="qwen3.6:35b-a3b-64k",
            )
    
    assert path is not None
    cp_data = json.loads(Path(path).read_text())
    assert cp_data["handoff_id"] == "178"
    assert cp_data["flow_key"] == "strict_review"
    assert cp_data["role_key"] == "archi01"
    assert cp_data["model_alias"] == "archi-local"
    assert cp_data["execution_adapter"] == "dispatch"


def test_checkpoint_works_without_deliverable(tmp_path):
    """Checkpoint is created even if deliverable file is missing."""
    with patch("checkpoint_integration.PROJECT_ROOT", tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "", "stderr": "", "returncode": 0
            })()
            path = create_checkpoint_for_dispatch(
                handoff_id="179",
                flow_key="strict_review",
                step_key="imple01-review01",
                from_role="imple01",
                to_role="review01",
                deliverable_path="/nonexistent/file.md",
                bridge_dir=str(tmp_path),
                model_alias="imple01-local",
                model_backend="ollama",
                concrete_model="qwen3-coder:30b-256k",
            )
    
    assert path is not None
    cp_data = json.loads(Path(path).read_text())
    assert cp_data["implementation_summary"] == ""  # empty since no deliverable


def test_checkpoint_contains_changed_files(tmp_path):
    """Checkpoint includes git diff changed files."""
    # Create a fake git diff
    with patch("checkpoint_integration.PROJECT_ROOT", tmp_path):
        with patch("subprocess.run") as mock_run:
            # First call: git diff --name-only → returns changed files
            # Second call: py_compile → pass
            mock_run.side_effect = [
                type("R", (), {"stdout": "scripts/new.py\nstatic/js/app.js\n", "stderr": "", "returncode": 0})(),
                type("R", (), {"stdout": "", "stderr": "", "returncode": 0})(),
            ]
            path = create_checkpoint_for_dispatch(
                handoff_id="180",
                flow_key="strict_review",
                step_key="imple01-review01",
                from_role="imple01",
                to_role="review01",
                deliverable_path="",
                bridge_dir=str(tmp_path),
                model_alias="imple01-local",
            )
    
    assert path is not None
    cp_data = json.loads(Path(path).read_text())
    assert "scripts/new.py" in cp_data["changed_files"]
    assert "static/js/app.js" in cp_data["changed_files"]


def test_checkpoint_schema_version_correct(tmp_path):
    """Checkpoint must have schema version 1.0."""
    with patch("checkpoint_integration.PROJECT_ROOT", tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()
            path = create_checkpoint_for_dispatch(
                handoff_id="181", flow_key="strict_review",
                step_key="s1", from_role="r1", to_role="r2",
                deliverable_path="", bridge_dir=str(tmp_path),
            )
    
    cp_data = json.loads(Path(path).read_text())
    assert cp_data["checkpoint_schema_version"] == "1.0"
