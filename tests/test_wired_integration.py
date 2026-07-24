"""Tests for wired integration — cron_tick, handoff compiler endpoint, checkpoint in dispatch."""
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
sys.path.insert(0, str(PROJECT_ROOT))


def test_cron_tick_importable():
    """cron_tick.py can be imported and has a main function."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
    import cron_tick
    assert hasattr(cron_tick, "main")
    assert callable(cron_tick.main)


def test_handoff_compiler_endpoint(client):
    """POST /api/bridge-v2/jobs/compile creates bounded jobs from a goal."""
    resp = client.post("/api/bridge-v2/jobs/compile", json={
        "goal": "Add a function to file.py",
        "flow_key": "strict_review",
        "role_key": "imple01",
        "target_project": "/tmp/test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert data["jobs"][0]["context_fit_state"] in ("FITS", "FITS_WITH_LOW_MARGIN")


def test_handoff_compiler_endpoint_missing_field(client):
    """POST with missing field returns 400."""
    resp = client.post("/api/bridge-v2/jobs/compile", json={
        "goal": "test",
    })
    assert resp.status_code == 400


def test_checkpoint_integration_importable():
    """checkpoint_integration module is importable and callable."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))
    from checkpoint_integration import create_checkpoint_for_dispatch
    assert callable(create_checkpoint_for_dispatch)


def test_model_lease_importable():
    """model_lease module is importable."""
    from model_lease import LeaseRegistry
    assert hasattr(LeaseRegistry, "acquire")
    assert hasattr(LeaseRegistry, "release")


def test_dispatch_has_checkpoint_call(tmp_path):
    """dispatch.py signal_complete should reference checkpoint_integration."""
    dispatch_path = PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py"
    source = dispatch_path.read_text()
    assert "checkpoint_integration" in source, "dispatch.py doesn't import checkpoint_integration"
    assert "create_checkpoint_for_dispatch" in source, "dispatch.py doesn't call create_checkpoint_for_dispatch"


def test_dispatch_has_lease_call():
    """dispatch.py should reference model_lease."""
    dispatch_path = PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py"
    source = dispatch_path.read_text()
    assert "model_lease" in source, "dispatch.py doesn't import model_lease"
    assert "LeaseRegistry" in source, "dispatch.py doesn't use LeaseRegistry"


def test_scheduler_dispatch_is_real():
    """scheduler._dispatch should inject into tmux, not return a mock."""
    sched_path = PROJECT_ROOT / "scripts" / "job_queue" / "scheduler.py"
    source = sched_path.read_text()
    # The _dispatch method should call inject_prompt to dispatch via tmux
    dispatch_section = source[source.find("def _dispatch"):source.find("def _check_completion")]
    assert "inject_prompt" in dispatch_section, "scheduler._dispatch doesn't call inject_prompt"
    assert "session_alive" in dispatch_section, "scheduler._dispatch doesn't check session_alive"


def test_scheduler_check_completion_is_real():
    """scheduler._check_completion should check for files, not return True."""
    sched_path = PROJECT_ROOT / "scripts" / "job_queue" / "scheduler.py"
    source = sched_path.read_text()
    completion_section = source[source.find("def _check_completion"):source.find("def _write_checkpoint")]
    assert "return True" not in completion_section or "glob" in completion_section, \
        "scheduler._check_completion still returns True unconditionally"
