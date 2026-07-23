"""Tests for the Python Runtime spike's path safety."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))


def test_rejects_absolute_path(tmp_path):
    from runtime_spike import safe_resolve
    for bad in ["/etc/passwd", "/home/svend/.env"]:
        try:
            safe_resolve(str(tmp_path), bad)
            assert False, f"absolute path should be rejected: {bad}"
        except ValueError:
            pass


def test_rejects_dotdot(tmp_path):
    from runtime_spike import safe_resolve
    for bad in ["../escape.py", "a/../../x.py", "foo/../../../etc/passwd"]:
        try:
            safe_resolve(str(tmp_path), bad)
            assert False, f"'..' path should be rejected: {bad}"
        except ValueError:
            pass


def test_rejects_symlink_escape(tmp_path):
    """Symlink that escapes project root must be rejected."""
    from runtime_spike import safe_resolve
    # Create a symlink inside project root that points outside
    link = tmp_path / "escape_link"
    outside = tmp_path.parent / "outside_target.txt"
    outside.write_text("secret")
    try:
        os.symlink(outside, link)
        try:
            safe_resolve(str(tmp_path), "escape_link")
            assert False, "symlink escape should be rejected"
        except ValueError:
            pass
    finally:
        if link.exists():
            link.unlink()
        if outside.exists():
            outside.unlink()


def test_accepts_valid_relative(tmp_path):
    from runtime_spike import safe_resolve
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "file.py").write_text("# ok")
    target = safe_resolve(str(tmp_path), "src/file.py")
    assert target.is_file()


def test_creates_parent_dirs(tmp_path):
    """APPLY_PATCH should create parent directories."""
    from runtime_spike import execute_action
    changed = set()
    action = {"action": "APPLY_PATCH", "path": "new/deep/dir/file.py", "content": "# new"}
    obs = execute_action(action, str(tmp_path), changed)
    assert "wrote" in obs.lower()
    assert (tmp_path / "new" / "deep" / "dir" / "file.py").exists()
