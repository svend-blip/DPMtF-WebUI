"""Test that start_coding.py uses model_allocator for all non-human roles."""
import inspect
import sys
from pathlib import Path

def test_start_coding_does_not_import_build_start_command():
    """After Phase 2, start_coding.py must not import build_start_command."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002" / "start_coding.py"
    source = script.read_text()
    # The import should be removed or commented out
    # We check that it's not in an active import line
    active_lines = [l for l in source.splitlines() if l.strip() and not l.strip().startswith("#")]
    for line in active_lines:
        assert "from command_builder import build_start_command" not in line, (
            f"start_coding.py still imports build_start_command: {line}"
        )

def test_start_coding_does_not_call_build_start_command():
    """After Phase 2, start_coding.py must not call build_start_command."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002" / "start_coding.py"
    source = script.read_text()
    active_lines = [l for l in source.splitlines() if l.strip() and not l.strip().startswith("#")]
    for line in active_lines:
        assert "build_start_command(" not in line, (
            f"start_coding.py still calls build_start_command: {line}"
        )
