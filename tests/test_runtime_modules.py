"""Tests for the modular execution runtime — file_tools, prompt_parser, checks, result."""
import sys
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

from file_tools import safe_resolve, read_file, apply_patch
from prompt_parser import extract_json, _fix_json_newlines
from checks import run_check, run_checks_for_files, CheckResult, CHECKS
from result import write_checkpoint, write_result


# ── file_tools ───────────────────────────────────────────────────

def test_safe_resolve_rejects_absolute(tmp_path):
    for bad in ["/etc/passwd", "/home/svend/.env"]:
        try:
            safe_resolve(str(tmp_path), bad)
            assert False, f"absolute path should be rejected: {bad}"
        except ValueError:
            pass


def test_safe_resolve_rejects_dotdot(tmp_path):
    for bad in ["../escape.py", "a/../../x.py"]:
        try:
            safe_resolve(str(tmp_path), bad)
            assert False
        except ValueError:
            pass


def test_safe_resolve_rejects_symlink_escape(tmp_path):
    link = tmp_path / "escape"
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret")
    try:
        os.symlink(outside, link)
        try:
            safe_resolve(str(tmp_path), "escape")
            assert False
        except ValueError:
            pass
    finally:
        if link.exists(): link.unlink()
        if outside.exists(): outside.unlink()


def test_safe_resolve_accepts_valid(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "file.py").write_text("# ok")
    target = safe_resolve(str(tmp_path), "src/file.py")
    assert target.is_file()


def test_read_file(tmp_path):
    (tmp_path / "test.py").write_text("print('hello')")
    content = read_file(str(tmp_path), "test.py")
    assert "hello" in content


def test_apply_patch_creates_dirs(tmp_path):
    n = apply_patch(str(tmp_path), "new/deep/dir/file.py", "# content")
    assert n > 0
    assert (tmp_path / "new" / "deep" / "dir" / "file.py").exists()


# ── prompt_parser ───────────────────────────────────────────────

def test_extract_json_normal_fields():
    raw = '{"action": "READ_FILE", "path": "test.py"}'
    result = extract_json(raw)
    assert result["action"] == "READ_FILE"


def test_extract_json_alternate_fields():
    raw = '{"operation": "READ_FILE", "filepath": "test.py"}'
    result = extract_json(raw)
    assert result["action"] == "READ_FILE"
    assert result["path"] == "test.py"


def test_extract_json_actual_newlines_in_content():
    raw = '{"action": "APPLY_PATCH", "path": "t.py", "content": "def x():\n    return 1\n"}'
    result = extract_json(raw)
    assert result is not None
    assert result["action"] == "APPLY_PATCH"
    assert "\n" in result["content"]


def test_extract_json_multiple_objects_takes_first():
    raw = '{"action": "APPLY_PATCH", "path": "t.py", "content": "x"}\n{"action": "FINISH"}'
    result = extract_json(raw)
    assert result["action"] == "APPLY_PATCH"


def test_extract_json_returns_none_on_garbage():
    assert extract_json("not json at all") is None
    assert extract_json("") is None


def test_fix_json_newlines():
    text = '{"content": "line1\nline2"}'
    fixed = _fix_json_newlines(text)
    assert json.loads(fixed)["content"] == "line1\nline2"


# ── checks ───────────────────────────────────────────────────────

def test_py_compile_pass(tmp_path):
    f = tmp_path / "good.py"
    f.write_text("def x():\n    return 1\n")
    result = run_check("py_compile", str(f))
    assert result.status == "PASS"


def test_py_compile_fail(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def x(\n")
    result = run_check("py_compile", str(f))
    assert result.status == "FAIL"


def test_unknown_check():
    result = run_check("nonexistent", "test.py")
    assert result.status == "FAIL"
    assert "unknown" in result.detail


def test_run_checks_for_files(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.js").write_text("var x = 1;\n")
    results = run_checks_for_files(["a.py", "b.js"], str(tmp_path))
    assert len(results) == 2
    checks = {r.check for r in results}
    assert "py_compile" in checks


# ── result ──────────────────────────────────────────────────────

def test_write_checkpoint(tmp_path):
    check_results = [CheckResult(check="py_compile", file="test.py", status="PASS")]
    path = write_checkpoint(
        str(tmp_path), "HANDOFF-1", "strict_review", "step1", "imple01",
        ["test.py"], check_results, "did stuff",
        "imple01-local", "ollama", "qwen3-coder:30b-256k",
    )
    cp = json.loads(Path(path).read_text())
    assert cp["handoff_id"] == "HANDOFF-1"
    assert cp["model_alias"] == "imple01-local"
    assert cp["verification_results"][0]["status"] == "PASS"
    assert cp["execution_adapter"] == "python-runtime"


def test_write_result(tmp_path):
    check_results = [CheckResult(check="py_compile", file="test.py", status="PASS")]
    path = str(tmp_path / "result.md")
    write_result(path, "HANDOFF-1", "qwen3-coder", "COMPLETED",
                 "did stuff", ["test.py"], check_results, str(tmp_path))
    content = Path(path).read_text()
    assert "COMPLETED" in content
    assert "py_compile" in content
    assert "test.py" in content


# ── Security: no shell, no git commit ────────────────────────────

def test_no_shell_true_in_runtime():
    """Runtime must never use shell=True in active code."""
    for module in ["file_tools", "prompt_parser", "checks", "result", "runtime"]:
        path = PROJECT_ROOT / "scripts" / "python-runtime" / f"{module}.py"
        if path.exists():
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                assert "shell=True" not in stripped, f"{module}.py: {stripped}"


def test_no_git_commit_in_runtime():
    """Runtime must never commit/push/add in active code."""
    for module in ["file_tools", "prompt_parser", "checks", "result", "runtime"]:
        path = PROJECT_ROOT / "scripts" / "python-runtime" / f"{module}.py"
        if path.exists():
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                assert "git commit" not in stripped
                assert "git push" not in stripped
                assert "git add" not in stripped
