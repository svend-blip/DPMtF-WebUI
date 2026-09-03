"""Tests for scripts/testing/runner.py — the runner module.

Uses unittest style. Creates temp git repos with test files for execution tests.
Never touches the DPMtF-WebUI working tree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # DPMtF-WebUI root
RUNNER_PATH = PROJECT_ROOT / "scripts" / "testing" / "runner.py"

# Load the module from its absolute path.
_runner_spec = __import__("importlib").util.spec_from_file_location(
    "runner_test", RUNNER_PATH
)
_runner_mod = __import__("importlib").util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(_runner_mod)

run_plan = _runner_mod.run_plan
RunnerError = _runner_mod.RunnerError


def _init_repo(path: str) -> None:
    """Create a valid git repo at *path* with an initial commit."""
    subprocess.run(["git", "init", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@dpm.tf"],
        check=True, capture_output=True, cwd=path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True, capture_output=True, cwd=path,
    )
    readme = Path(path, "README.md")
    readme.write_text("hello", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        check=True, capture_output=True, cwd=path,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        check=True, capture_output=True, cwd=path,
    )


def _write_pytest_test(repo: str, name: str, content: str) -> str:
    """Write a .py test file into *repo* and return its absolute path."""
    p = Path(repo, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


def _make_plan(
    is_exhaustive=True,
    selected_tests=None,
    resolved_scope="full",
    affected_components=None,
    escalation_reason="",
    policy_hash="pol-hash",
    plan_hash="plan-hash",
):
    return SimpleNamespace(
        is_exhaustive=is_exhaustive,
        selected_tests=selected_tests or [],
        resolved_scope=resolved_scope,
        affected_components=affected_components or [],
        escalation_reason=escalation_reason,
        policy_hash=policy_hash,
        plan_hash=plan_hash,
    )


def _make_policy(test_command=None):
    return SimpleNamespace(test_command=test_command)


class TestRunnerError(unittest.TestCase):
    """Tests for RunnerError exception."""

    def test_runner_error_is_exception(self):
        """RunnerError is an Exception subclass."""
        self.assertTrue(issubclass(RunnerError, Exception))

    def test_runner_error_message(self):
        """RunnerError carries the provided message."""
        exc = RunnerError("something went wrong")
        self.assertEqual(str(exc), "something went wrong")


class TestRunPlanExhaustive(unittest.TestCase):
    """Tests for exhaustive test plans."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        # Create a class-based passing test file.
        _write_pytest_test(
            self.tmpdir,
            "test_pass.py",
            "class TestPass:\n    def test_pass(self):\n        assert True\n",
        )
        subprocess.run(
            ["git", "add", "test_pass.py"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )
        subprocess.run(
            ["git", "commit", "-m", "add test"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )

    def test_an_exhaustive_plan_runs_the_suite_not_the_list(self):
        """Create a TestPlan with is_exhaustive=True and selected_tests set to
        specific test paths; verify that run_plan runs the full suite (no test
        paths in command)."""
        plan = _make_plan(
            is_exhaustive=True,
            selected_tests=["test_pass.py", "test_other.py"],
        )
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy)
        self.assertEqual(evidence["status"], "PASS")
        # In exhaustive mode, selected_tests should NOT appear in the command.
        self.assertNotIn("test_pass.py", evidence["test_command"])
        self.assertNotIn("test_other.py", evidence["test_command"])
        # The command should be the default pytest command with the
        # interpreter resolved (not bare "python3").
        cmd = evidence["test_command"]
        self.assertEqual(cmd[1:], ["-m", "pytest", "-q", "-p", "no:cacheprovider"])
        self.assertNotEqual(cmd[0], "python3")

    def test_selective_plan_runs_selected_tests_only(self):
        """Create a Plan with is_exhaustive=False and specific selected tests;
        verify only those test paths are in the command."""
        plan = _make_plan(
            is_exhaustive=False,
            selected_tests=["test_pass.py"],
            resolved_scope="broad",
        )
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy)
        self.assertEqual(evidence["status"], "PASS")
        # The selected test paths should be appended to the command.
        self.assertIn("test_pass.py", evidence["test_command"])
        # But not unrelated ones.
        self.assertNotIn("test_other.py", evidence["test_command"])


class TestRunPlanSelective(unittest.TestCase):
    """Tests for selective test plans and error handling."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        _write_pytest_test(
            self.tmpdir,
            "test_pass.py",
            "class TestPass:\n    def test_pass(self):\n        assert True\n",
        )

    def test_an_uncollectable_selected_test_is_an_error_not_a_pass(self):
        """Create a Plan with is_exhaustive=False and selected_tests pointing to
        tests that cannot be collected (nonexistent path); verify the evidence
        has status='ERROR' and the escalation_reason contains
        'SELECTED_TESTS_NOT_COLLECTABLE'."""
        plan = _make_plan(
            is_exhaustive=False,
            selected_tests=["test_nonexistent_test_file.py"],
            resolved_scope="broad",
        )
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy)
        self.assertEqual(evidence["status"], "ERROR")
        self.assertIn("SELECTED_TESTS_NOT_COLLECTABLE", evidence["escalation_reason"])

    def test_nonzero_exit_becomes_fail(self):
        """Create a Plan and a test file that fails; verify evidence has
        status='FAIL' and escalation_reason mentions exit code."""
        _write_pytest_test(
            self.tmpdir,
            "test_failing.py",
            "class TestFailing:\n    def test_fail(self):\n        assert False\n",
        )
        plan = _make_plan(
            is_exhaustive=False,
            selected_tests=["test_failing.py"],
        )
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy)
        self.assertEqual(evidence["status"], "FAIL")
        self.assertIn("exit code", evidence["escalation_reason"])

    def test_missing_python_becomes_error(self):
        """Set test_command to a non-existent command; verify evidence has
        status='ERROR'."""
        plan = _make_plan(is_exhaustive=True)
        policy = _make_policy(test_command=["nonexistent_binary_xyz", "-q"])
        evidence = run_plan(self.tmpdir, plan, policy)
        self.assertEqual(evidence["status"], "ERROR")
        self.assertIn("Command execution failed", evidence["escalation_reason"])


class TestRunPlanTiming(unittest.TestCase):
    """Tests for timing and duration measurement."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        _write_pytest_test(
            self.tmpdir,
            "test_pass.py",
            "class TestPass:\n    def test_pass(self):\n        assert True\n",
        )

    def test_duration_is_measured_and_rounded(self):
        """Verify duration_seconds is a float rounded to 2 decimal places."""
        plan = _make_plan()
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy)
        duration = evidence["duration_seconds"]
        self.assertIsInstance(duration, float)
        # Rounded to 2 decimal places: multiplying by 100 should give integer.
        self.assertEqual(duration, round(duration, 2))
        # Duration should be positive (some time elapsed).
        self.assertGreater(duration, 0)


class TestRunPlanTimeout(unittest.TestCase):
    """Tests for timeout handling."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        _write_pytest_test(
            self.tmpdir,
            "test_pass.py",
            "class TestPass:\n    def test_pass(self):\n        assert True\n",
        )

    def test_run_plan_with_timeout(self):
        """Verify timeout parameter is passed to subprocess and works for a
        quick test (no timeout)."""
        plan = _make_plan()
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy, timeout=30)
        self.assertEqual(evidence["status"], "PASS")
        # A passing test should complete well within 30 seconds.
        self.assertLess(evidence["duration_seconds"], 30)


class TestRunPlanPolicy(unittest.TestCase):
    """Tests for policy handling."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        _write_pytest_test(
            self.tmpdir,
            "test_pass.py",
            "class TestPass:\n    def test_pass(self):\n        assert True\n",
        )

    def test_none_policy_uses_default_command(self):
        """A policy with test_command=None falls back to the default pytest command."""
        plan = _make_plan()
        policy = _make_policy(test_command=None)
        evidence = run_plan(self.tmpdir, plan, policy)
        self.assertEqual(evidence["status"], "PASS")
        cmd = evidence["test_command"]
        self.assertEqual(cmd[1:], ["-m", "pytest", "-q", "-p", "no:cacheprovider"])
        self.assertNotEqual(cmd[0], "python3")


if __name__ == "__main__":
    unittest.main()


class TestCollectMeasuresExitCodeNotSubstrings(unittest.TestCase):
    """A selected test whose NAME contains 'error' must be collectable.

    Regression guard for the 2026-08-31 defect: _collect_tests scanned
    the collect output for the substring 'error' and rejected any
    selection containing a legitimately named test such as
    test_returns_dispatch_error. The exit code is the measurement.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        _write_pytest_test(
            self.tmpdir,
            "test_named_error.py",
            "def test_returns_dispatch_error():\n    assert True\n",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_a_test_named_error_is_collectable_and_runs(self):
        plan = _make_plan(
            is_exhaustive=False,
            selected_tests=["test_named_error.py"],
            resolved_scope="component",
        )
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy, timeout=60)
        self.assertEqual(evidence["status"], "PASS")

    def test_an_unloadable_selection_still_fails_closed(self):
        plan = _make_plan(
            is_exhaustive=False,
            selected_tests=["test_does_not_exist.py"],
            resolved_scope="component",
        )
        policy = _make_policy()
        evidence = run_plan(self.tmpdir, plan, policy, timeout=60)
        self.assertEqual(evidence["status"], "ERROR")
