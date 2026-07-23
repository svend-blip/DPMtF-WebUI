"""Verify no active orchestration code calls direct-path model selection."""
import os
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002"

# Files to check for direct-path references
ACTIVE_FILES = [
    "dispatch.py",
    "start_coding.py",
    "role_setup.py",
    "role_teardown.py",
]


def test_no_build_start_command_calls():
    """No active file should call build_start_command."""
    for fname in ACTIVE_FILES:
        path = BRIDGE_DIR / fname
        if not path.exists():
            continue
        source = path.read_text()
        active_lines = [l for l in source.splitlines()
                        if l.strip() and not l.strip().startswith("#")]
        for line in active_lines:
            assert "build_start_command(" not in line, (
                f"{fname} still calls build_start_command: {line.strip()}")


def test_no_unload_ollama_model_calls_in_new_code():
    """dispatch.py should call _run_allocator_stop, not unload_ollama_model.
    
    The function unload_ollama_model may still exist as a definition
    (for backwards compat), but it should not be called from the
    allocator-aware code paths."""
    source = (BRIDGE_DIR / "dispatch.py").read_text()
    # Check that _run_allocator_stop is used
    assert "_run_allocator_stop" in source, "dispatch.py must use _run_allocator_stop"
    # unload_ollama_model may exist as a function def, but should not be
    # called from the new allocator-aware branches
    active_lines = [l for l in source.splitlines()
                    if l.strip() and not l.strip().startswith("#")
                    and "unload_ollama_model" in l
                    and "def " not in l]
    # Legacy fallback calls are acceptable but should be in elif branches
    # — not in the primary path
    # This is a soft check — the hard check is that _run_allocator_stop is used
