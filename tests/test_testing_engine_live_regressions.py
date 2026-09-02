"""Regressions found on 2026-09-02 when the test-selection engine was run
against this repository for the first time with a real policy.

1. test_index._static_selection mutated the set it iterated when a changed
   component had reverse dependencies -> RuntimeError, swallowed by the
   planner, which then returned the smoke tests only.
2. planner.plan_tests with symbols/closure and no usable index selection
   dropped the component tests (three smoke tests at component scope).
3. A changed test file had no owning component and escalated to broad.
4. gate-test-impact recorded PASS when the target had no policy at all.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.testing.policy import load_policy  # noqa: E402
from scripts.testing.planner import plan_tests  # noqa: E402
from scripts.testing.dependency_graph import build_graph, reverse_closure, node_id  # noqa: E402

POLICY = {
    "components": {"core": ["src/core.py"], "api": ["src/api.py"]},
    "test_mappings": {"core": ["tests/test_core.py"], "api": ["tests/test_api.py"]},
    "component_dependencies": {"api": ["core"]},
    "mandatory_smoke_tests": ["tests/test_smoke.py"],
    "high_fanout_files": [],
    "full_regression_triggers": [],
}


def _repo(tmp_path, with_policy=True):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "core.py").write_text("def f():\n    return 1\n")
    (tmp_path / "src" / "api.py").write_text("from src.core import f\n\ndef g():\n    return f()\n")
    for t in ("test_core", "test_api", "test_smoke"):
        (tmp_path / "tests" / f"{t}.py").write_text("def test_ok():\n    assert True\n")
    if with_policy:
        (tmp_path / ".dpmtf").mkdir()
        (tmp_path / ".dpmtf" / "test-policy.json").write_text(json.dumps(POLICY))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)
    return tmp_path


def test_reverse_dependencies_do_not_crash_the_index_selection_and_component_tests_survive(tmp_path):
    repo = _repo(tmp_path)
    pol = load_policy(str(repo))
    graph = build_graph(str(repo))
    closure = reverse_closure(graph, [node_id("src/core.py", "f")])
    plan = plan_tests(str(repo), pol, {"src/core.py": "modified"},
                      symbols={"src/core.py": {"f"}}, closure=closure)
    # core changed; api depends on core -> both components' tests, plus smoke.
    assert "tests/test_core.py" in plan.selected_tests
    assert "tests/test_api.py" in plan.selected_tests
    assert "tests/test_smoke.py" in plan.selected_tests
    assert plan.resolved_scope in ("symbol", "file", "component")


def test_failed_index_selection_falls_back_to_component_tests(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pol = load_policy(str(repo))
    import scripts.testing.planner as planner_mod

    def boom(**kwargs):
        raise RuntimeError("index unavailable")

    monkeypatch.setattr(planner_mod, "_tests_for_index", boom)
    plan = plan_tests(str(repo), pol, {"src/core.py": "modified"},
                      symbols={"src/core.py": {"f"}}, closure=object())
    assert plan.resolved_scope == "component"
    assert "tests/test_core.py" in plan.selected_tests
    assert "tests/test_api.py" in plan.selected_tests


def test_changed_test_file_selects_itself_at_file_scope(tmp_path):
    repo = _repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"tests/test_api.py": "modified"})
    assert plan.resolved_scope == "file"
    assert set(plan.selected_tests) == {"tests/test_api.py", "tests/test_smoke.py"}


def test_changed_test_file_next_to_source_keeps_component_scope_and_itself(tmp_path):
    repo = _repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"src/api.py": "modified", "tests/test_new_api.py": "added"})
    assert plan.resolved_scope == "component"
    assert "tests/test_new_api.py" in plan.selected_tests
    assert "tests/test_api.py" in plan.selected_tests


def _gate():
    spec = importlib.util.spec_from_file_location(
        "gate_test_impact_live", ROOT / "scripts" / "bridgeV002" / "gate-test-impact.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gate_reports_skipped_not_pass_when_target_has_no_policy(tmp_path, capsys):
    repo = _repo(tmp_path, with_policy=False)
    (repo / "src" / "core.py").write_text("def f():\n    return 2\n")
    gate = _gate()
    result = gate.engine_chain(str(repo), "x-02-ELOOP", "1", bridge_dir=str(tmp_path))
    assert result["status"] == "SKIPPED"
    assert result["success"] is True
    assert result["evidence"]["test_command"] == ["skip-empty-policy"]
    assert "SKIPPED, not a pass" in capsys.readouterr().out


def test_gate_composes_symbol_narrowing_when_policy_present(tmp_path):
    repo = _repo(tmp_path)
    (repo / "src" / "core.py").write_text("def f():\n    return 2\n")
    gate = _gate()
    result = gate.engine_chain(str(repo), "x-02-ELOOP", "1", bridge_dir=str(tmp_path))
    assert result["narrowing"].startswith("symbols for 1 Python file(s)")
    assert result["status"] in ("PASS", "FAIL", "ERROR")
    assert "tests/test_core.py" in result["evidence"]["selected_tests"]


def test_virtualenv_and_vendor_dirs_are_never_indexed_as_tests(tmp_path):
    repo = _repo(tmp_path)
    vendored = repo / "venv" / "lib" / "python3.12" / "site-packages" / "attrs"
    vendored.mkdir(parents=True)
    (vendored / "validators.py").write_text("from src.core import f\n\ndef test_like():\n    return f()\n")
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "test_pkg.py").write_text("from src.core import f\n")
    pol = load_policy(str(repo))
    graph = build_graph(str(repo))
    closure = reverse_closure(graph, [node_id("src/core.py", "f")])
    plan = plan_tests(str(repo), pol, {"src/core.py": "modified"},
                      symbols={"src/core.py": {"f"}}, closure=closure)
    assert not [t for t in plan.selected_tests if t.startswith(("venv/", "node_modules/"))]
    assert "tests/test_core.py" in plan.selected_tests
