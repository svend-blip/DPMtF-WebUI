"""C# targets for the selection engine (2026-09-02).

A .NET policy carries ``"test_command": ["dotnet", "test", "--no-restore"]``
and maps components to test projects (``tests/A.Tests/A.Tests.csproj`` or
the project directory). ``dotnet test`` accepts one project or solution
per invocation, so the runner runs once per selected project and
aggregates; the collection step is structural (the project must exist);
exhaustive runs call ``dotnet test`` on the repository root; the parallel
path is never taken. No toolchain is needed here: a stub ``dotnet``
executable on PATH records what it was asked to do.
"""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.testing import runner as runner_mod  # noqa: E402
from scripts.testing.planner import plan_tests  # noqa: E402
from scripts.testing.policy import load_policy  # noqa: E402

POLICY = {
    "components": {
        "core": ["src/Core/*.cs"],
        "api": ["src/Api/*.cs"],
        "core-tests": ["tests/Core.Tests/*.cs"],
        "api-tests": ["tests/Api.Tests/*.cs"],
    },
    "test_mappings": {
        "core": ["tests/Core.Tests/Core.Tests.csproj"],
        "api": ["tests/Api.Tests"],
        "core-tests": ["tests/Core.Tests/Core.Tests.csproj"],
        "api-tests": ["tests/Api.Tests"],
    },
    "component_dependencies": {"api": ["core"]},
    "mandatory_smoke_tests": [],
    "high_fanout_files": [],
    "full_regression_triggers": ["Directory.Build.props", ".dpmtf/test-policy.json"],
    "test_command": ["dotnet", "test", "--no-restore"],
}

STUB = """#!/bin/sh
echo "$@" >> "$DOTNET_STUB_LOG"
case "$*" in *Fail*) exit 1;; esac
exit 0
"""


def _repo(tmp_path):
    for d in ("src/Core", "src/Api", "tests/Core.Tests", "tests/Api.Tests", ".dpmtf"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "src" / "Core" / "Core.cs").write_text("namespace Core { public class A {} }\n")
    (tmp_path / "src" / "Api" / "Api.cs").write_text("namespace Api { public class B {} }\n")
    (tmp_path / "tests" / "Core.Tests" / "Core.Tests.csproj").write_text("<Project Sdk=\"Microsoft.NET.Sdk\" />\n")
    (tmp_path / "tests" / "Core.Tests" / "ATests.cs").write_text("// tests\n")
    (tmp_path / "tests" / "Api.Tests" / "Api.Tests.csproj").write_text("<Project Sdk=\"Microsoft.NET.Sdk\" />\n")
    (tmp_path / "tests" / "Api.Tests" / "BTests.cs").write_text("// tests\n")
    (tmp_path / "Directory.Build.props").write_text("<Project />\n")
    (tmp_path / ".dpmtf" / "test-policy.json").write_text(json.dumps(POLICY))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)
    return tmp_path


def _stub_dotnet(tmp_path, monkeypatch):
    bindir = tmp_path / "stubbin"
    bindir.mkdir()
    exe = bindir / "dotnet"
    exe.write_text(STUB)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "dotnet.log"
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("DOTNET_STUB_LOG", str(log))
    return log


def test_dotnet_command_is_recognised_and_toolchain_dirs_include_dotnet_homes():
    assert runner_mod._is_dotnet_command(["dotnet", "test"])
    assert not runner_mod._is_dotnet_command(["go", "test"])
    assert "~/.dotnet" in runner_mod._TOOLCHAIN_FALLBACK_DIRS


def test_core_change_plans_core_and_api_test_projects(tmp_path):
    repo = _repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"src/Core/Core.cs": "modified"})
    assert plan.resolved_scope == "component"
    assert set(plan.selected_tests) == {"tests/Core.Tests/Core.Tests.csproj", "tests/Api.Tests"}


def test_changed_test_source_selects_its_own_project(tmp_path):
    repo = _repo(tmp_path)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"tests/Api.Tests/BTests.cs": "modified"})
    assert plan.resolved_scope == "component"
    assert plan.selected_tests == ["tests/Api.Tests"]


def test_selected_projects_run_one_dotnet_invocation_each(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    log = _stub_dotnet(tmp_path, monkeypatch)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"src/Core/Core.cs": "modified"})
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=60)
    assert evidence["status"] == "PASS", evidence
    calls = log.read_text().strip().splitlines()
    assert calls == [
        "test --no-restore tests/Api.Tests",
        "test --no-restore tests/Core.Tests/Core.Tests.csproj",
    ]
    assert evidence["parallel_executed"] is False
    assert evidence["test_command"][1:] == ["test", "--no-restore", "tests/Api.Tests", "tests/Core.Tests/Core.Tests.csproj"]


def test_one_failing_project_fails_the_run_and_names_it(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stub_dotnet(tmp_path, monkeypatch)
    (repo / "tests" / "Fail.Tests").mkdir()
    (repo / "tests" / "Fail.Tests" / "Fail.Tests.csproj").write_text("<Project />\n")
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"src/Api/Api.cs": "modified"})
    plan.selected_tests.append("tests/Fail.Tests")
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=60)
    assert evidence["status"] == "FAIL"
    assert "exit code 1" in evidence["escalation_reason"]


def test_missing_project_is_not_collectable(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stub_dotnet(tmp_path, monkeypatch)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"src/Api/Api.cs": "modified"})
    plan.selected_tests.append("tests/Nowhere.Tests")
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=60)
    assert evidence["status"] == "ERROR"
    assert "SELECTED_TESTS_NOT_COLLECTABLE" in evidence["escalation_reason"]
    assert "tests/Nowhere.Tests: does not exist" in evidence["escalation_reason"]


def test_exhaustive_plan_calls_dotnet_test_once_on_the_root(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    log = _stub_dotnet(tmp_path, monkeypatch)
    pol = load_policy(str(repo))
    plan = plan_tests(str(repo), pol, {"Directory.Build.props": "modified"})
    assert plan.resolved_scope == "full"
    evidence = runner_mod.run_plan(str(repo), plan, pol, timeout=60)
    assert evidence["status"] == "PASS"
    assert log.read_text().strip().splitlines() == ["test --no-restore"]
