"""The selection engine on a Go target (2026-09-02, for the 9000 family
whose target is FlowRunner).

A Go policy carries ``"test_command": ["go", "test", "-count=1"]`` and maps
components to package patterns (``./internal/x/...``). The runner must
resolve the toolchain without a home path in the policy, use ``go list``
as the collection step, never shard across pytest workers, and append
``./...`` to an exhaustive run.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.testing import runner as runner_mod  # noqa: E402
from scripts.testing.planner import plan_tests  # noqa: E402
from scripts.testing.policy import load_policy  # noqa: E402

GO = runner_mod.resolve_command(["go"])[0]
needs_go = pytest.mark.skipif(
    not (os.path.sep in GO and os.access(GO, os.X_OK)) and not shutil.which("go"),
    reason="no Go toolchain",
)

POLICY = {
    "components": {
        "mathx": ["internal/mathx/*.go"],
        "app": ["cmd/app/*.go"],
    },
    "test_mappings": {
        "mathx": ["./internal/mathx/..."],
        "app": ["./cmd/app/..."],
    },
    "component_dependencies": {"app": ["mathx"]},
    "mandatory_smoke_tests": [],
    "high_fanout_files": [],
    "full_regression_triggers": ["go.mod", "go.sum", ".dpmtf/test-policy.json"],
    "test_command": ["go", "test", "-count=1"],
}


def _go_repo(tmp_path):
    (tmp_path / "internal" / "mathx").mkdir(parents=True)
    (tmp_path / "cmd" / "app").mkdir(parents=True)
    (tmp_path / ".dpmtf").mkdir()
    (tmp_path / "go.mod").write_text("module example.com/m\n\ngo 1.22\n")
    (tmp_path / "internal" / "mathx" / "mathx.go").write_text("package mathx\n\nfunc Add(a, b int) int { return a + b }\n")
    (tmp_path / "internal" / "mathx" / "mathx_test.go").write_text(
        "package mathx\n\nimport \"testing\"\n\nfunc TestAdd(t *testing.T) {\n\tif Add(1, 2) != 3 {\n\t\tt.Fatal(\"bad\")\n\t}\n}\n")
    (tmp_path / "cmd" / "app" / "main.go").write_text(
        "package main\n\nimport (\n\t\"fmt\"\n\t\"example.com/m/internal/mathx\"\n)\n\nfunc main() { fmt.Println(mathx.Add(1, 2)) }\n")
    (tmp_path / "cmd" / "app" / "main_test.go").write_text(
        "package main\n\nimport \"testing\"\n\nfunc TestMain_(t *testing.T) {}\n")
    (tmp_path / ".dpmtf" / "test-policy.json").write_text(json.dumps(POLICY))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)
    return tmp_path


def test_resolve_command_leaves_known_executables_alone():
    assert runner_mod.resolve_command(["python3", "-m", "pytest"])[0] == "python3"
    assert runner_mod.resolve_command(["/bin/sh", "-c", "x"]) == ["/bin/sh", "-c", "x"]


def test_pytest_and_go_commands_are_recognised():
    assert runner_mod._is_pytest_command(["python3", "-m", "pytest", "-q"])
    assert runner_mod._is_pytest_command(["pytest"])
    assert not runner_mod._is_pytest_command(["go", "test"])
    assert runner_mod._is_go_command(["/opt/go/bin/go", "test"])


def test_go_change_plans_the_package_and_its_dependents(tmp_path):
    repo = _go_repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"internal/mathx/mathx.go": "modified"})
    assert plan.resolved_scope == "component"
    assert set(plan.selected_tests) == {"./internal/mathx/...", "./cmd/app/..."}


@needs_go
def test_go_plan_runs_with_go_test_and_passes(tmp_path):
    repo = _go_repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"internal/mathx/mathx.go": "modified"})
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=300)
    assert evidence["status"] == "PASS", evidence
    assert os.path.basename(evidence["test_command"][0]) == "go"
    assert evidence["test_command"][1:3] == ["test", "-count=1"]
    assert "./internal/mathx/..." in evidence["test_command"]
    assert evidence["parallel_executed"] is False


@needs_go
def test_go_plan_with_unknown_package_is_not_collectable(tmp_path):
    repo = _go_repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"internal/mathx/mathx.go": "modified"})
    plan.selected_tests.append("./internal/nowhere/...")
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=300)
    assert evidence["status"] == "ERROR"
    assert "SELECTED_TESTS_NOT_COLLECTABLE" in evidence["escalation_reason"]


@needs_go
def test_exhaustive_go_plan_tests_the_whole_module(tmp_path):
    repo = _go_repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"go.mod": "modified"})
    assert plan.resolved_scope == "full"
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=300)
    assert evidence["status"] == "PASS", evidence
    assert evidence["test_command"][-1] == "./..."
