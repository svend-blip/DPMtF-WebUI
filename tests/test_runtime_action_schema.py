"""Tests for the Python Runtime spike's action schema."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))


def test_unknown_action_returns_rejection(tmp_path):
    from runtime_spike import execute_action
    changed = set()
    action = {"action": "DELETE_FILE", "path": "x.py"}
    obs = execute_action(action, str(tmp_path), changed)
    assert "unknown action" in obs.lower()


def test_shell_exec_not_in_allowed_actions():
    """The runtime must not allow shell execution."""
    spike_path = PROJECT_ROOT / "scripts" / "python-runtime" / "runtime_spike.py"
    source = spike_path.read_text()
    assert "SHELL_EXEC" not in source
    assert "RUN_COMMAND" not in source
    assert "shell=True" not in source


def test_no_git_commit_in_runtime():
    """The runtime must never commit."""
    spike_path = PROJECT_ROOT / "scripts" / "python-runtime" / "runtime_spike.py"
    source = spike_path.read_text()
    assert "git commit" not in source
    assert "git push" not in source
    assert "git add" not in source


def test_max_turns_cap_exists():
    """The runtime must have a hard turn cap."""
    spike_path = PROJECT_ROOT / "scripts" / "python-runtime" / "runtime_spike.py"
    source = spike_path.read_text()
    assert "MAX_TURNS" in source
