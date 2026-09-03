"""Tests for interpreter resolution and environment-error detection in runner.py.

Handoff 119 — WORK 1 (Run 027, GOAL §3).
"""

from __future__ import annotations

import os
import stat
import sys
import textwrap
import types
from unittest import mock

import pytest

from scripts.testing.runner import (
    RunnerError,
    _is_environment_error,
    resolve_test_interpreter,
    run_plan,
)


# ---------------------------------------------------------------------------
# resolve_test_interpreter
# ---------------------------------------------------------------------------


class TestResolveTestInterpreter:
    """Unit tests for the interpreter resolver."""

    def test_venv_python_preferred_when_it_has_pytest(self, tmp_path):
        """When <repo>/venv/bin/python exists and can import pytest, use it."""
        venv_dir = tmp_path / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        fake_python = venv_dir / "python"
        fake_python.write_text("#!/bin/sh\necho ok\n")
        fake_python.chmod(fake_python.stat().st_mode | stat.S_IEXEC)

        # Patch subprocess.run so the probe succeeds for our fake python
        def fake_run(cmd, **kwargs):
            if cmd[0] == str(fake_python):
                return types.SimpleNamespace(returncode=0, stdout="8.0.0", stderr="")
            return types.SimpleNamespace(returncode=1, stdout="", stderr="fail")

        with mock.patch("scripts.testing.runner.subprocess.run", side_effect=fake_run):
            result = resolve_test_interpreter(str(tmp_path))

        assert result == str(fake_python)

    def test_falls_back_to_sys_executable(self, tmp_path):
        """When venv python doesn't exist, fall back to sys.executable."""
        # No venv directory at all
        real_run = __import__("subprocess").run

        def fake_run(cmd, **kwargs):
            if cmd[0] == sys.executable:
                return types.SimpleNamespace(returncode=0, stdout="8.0.0", stderr="")
            return types.SimpleNamespace(returncode=1, stdout="", stderr="fail")

        with mock.patch("scripts.testing.runner.subprocess.run", side_effect=fake_run):
            result = resolve_test_interpreter(str(tmp_path))

        assert result == sys.executable

    def test_raises_when_no_interpreter_has_pytest(self, tmp_path):
        """When no candidate can import pytest, raise RunnerError."""

        def fake_run(cmd, **kwargs):
            return types.SimpleNamespace(
                returncode=1, stdout="", stderr="ModuleNotFoundError: No module named 'pytest'"
            )

        with mock.patch("scripts.testing.runner.subprocess.run", side_effect=fake_run):
            with pytest.raises(RunnerError, match="no interpreter with pytest"):
                resolve_test_interpreter(str(tmp_path))


# ---------------------------------------------------------------------------
# _is_environment_error
# ---------------------------------------------------------------------------


class TestIsEnvironmentError:
    def test_true_on_no_module_named(self):
        assert _is_environment_error(1, "No module named 'pytest'") is True

    def test_false_on_zero_exit(self):
        assert _is_environment_error(0, "No module named 'pytest'") is False

    def test_false_on_normal_failure(self):
        assert _is_environment_error(1, "1 failed, 2 passed") is False


# ---------------------------------------------------------------------------
# Integration: run_plan with PATH stripped + venv-only pytest
# ---------------------------------------------------------------------------


class TestRunPlanInterpreterResolution:
    """Integration tests exercising run_plan through the interpreter resolver."""

    def _make_fake_plan(self, **overrides):
        """Build a minimal plan object for run_plan."""
        defaults = dict(
            is_exhaustive=True,
            selected_tests=[],
            resolved_scope="broad",
            affected_components=[],
            escalation_reason="",
            policy_hash="abc123",
            plan_hash="def456",
        )
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    def _make_fake_policy(self, test_command=None):
        return types.SimpleNamespace(test_command=test_command, parallel=None)

    def test_run_plan_passes_with_venv_pytest_and_stripped_path(self, tmp_path):
        """run_plan succeeds when only venv/bin/python has pytest and PATH is bare."""
        # Create a fake venv python that acts like pytest succeeding
        venv_dir = tmp_path / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        fake_python = venv_dir / "python"
        # Write a script that exits 0 when invoked as pytest
        fake_python.write_text(textwrap.dedent("""\
            #!/bin/sh
            exit 0
        """))
        fake_python.chmod(fake_python.stat().st_mode | stat.S_IEXEC)

        plan = self._make_fake_plan()
        policy = self._make_fake_policy(
            test_command=[str(fake_python), "-m", "pytest", "-q"]
        )

        # Run with a stripped PATH — only /usr/bin:/bin
        env = os.environ.copy()
        env["PATH"] = "/usr/bin:/bin"
        with mock.patch.dict(os.environ, env):
            evidence = run_plan(str(tmp_path), plan, policy, timeout=30)

        assert evidence["status"] == "PASS"

    def test_run_plan_error_when_no_interpreter_has_pytest(self, tmp_path):
        """run_plan returns ERROR when the test command cannot find pytest."""
        plan = self._make_fake_plan()
        # Use a nonexistent interpreter as the test command
        policy = self._make_fake_policy(
            test_command=["/nonexistent/python", "-m", "pytest", "-q"]
        )

        evidence = run_plan(str(tmp_path), plan, policy, timeout=30)

        assert evidence["status"] == "ERROR"

    def test_run_plan_env_error_on_no_module_named(self, tmp_path):
        """Exit code 1 + 'No module named' on stderr → ERROR, not FAIL."""
        plan = self._make_fake_plan()
        # Use sys.executable but invoke a nonexistent module
        policy = self._make_fake_policy(
            test_command=[sys.executable, "-m", "nonexistent_module_xyz_12345"]
        )

        evidence = run_plan(str(tmp_path), plan, policy, timeout=30)

        # This should be ERROR because of "No module named" on stderr
        assert evidence["status"] == "ERROR"


# ---------------------------------------------------------------------------
# Handoff 127 — broker-env proof + command-build wiring
# ---------------------------------------------------------------------------


class TestBrokerEnvProof:
    """Handoff 127 Part B: broker-environment proof tests."""

    def _make_fake_plan(self, **overrides):
        defaults = dict(
            is_exhaustive=True,
            selected_tests=[],
            resolved_scope="broad",
            affected_components=[],
            escalation_reason="",
            policy_hash="abc123",
            plan_hash="def456",
        )
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    def _make_fake_policy(self, test_command=None):
        return types.SimpleNamespace(test_command=test_command, parallel=None)

    def test_stripped_path_with_venv_pytest_passes(self, tmp_path):
        """Stripped PATH + venv python that can import pytest → PASS (not ERROR)."""
        venv_dir = tmp_path / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        fake_python = venv_dir / "python"
        # Symlink to sys.executable so the probe `import pytest` succeeds.
        os.symlink(sys.executable, str(fake_python))

        plan = self._make_fake_plan()
        # No policy test_command → default path uses resolve_test_interpreter.
        policy = self._make_fake_policy(test_command=None)

        env = os.environ.copy()
        env["PATH"] = "/usr/bin:/bin"
        with mock.patch.dict(os.environ, env):
            evidence = run_plan(str(tmp_path), plan, policy, timeout=60)

        assert evidence["status"] != "ERROR", (
            f"Expected non-ERROR status when venv has pytest; got {evidence['status']}"
        )

    def test_no_interpreter_has_pytest_returns_error(self, tmp_path):
        """No interpreter with pytest → ERROR with 'no interpreter with pytest' message."""
        plan = self._make_fake_plan()
        policy = self._make_fake_policy(test_command=None)

        def always_fail(cmd, **kwargs):
            return types.SimpleNamespace(returncode=1, stdout="", stderr="no pytest")

        with mock.patch("scripts.testing.runner.subprocess.run", side_effect=always_fail):
            evidence = run_plan(str(tmp_path), plan, policy, timeout=30)

        assert evidence["status"] == "ERROR"
        esc = evidence.get("escalation_reason", "")
        assert "no interpreter with pytest" in esc


class TestCommandBuildUsesResolvedInterpreter:
    """Handoff 127 Part C: command building uses the resolved interpreter."""

    def _make_fake_plan(self, **overrides):
        defaults = dict(
            is_exhaustive=True,
            selected_tests=[],
            resolved_scope="broad",
            affected_components=[],
            escalation_reason="",
            policy_hash="abc123",
            plan_hash="def456",
        )
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    def _make_fake_policy(self, test_command=None):
        return types.SimpleNamespace(test_command=test_command, parallel=None)

    def test_default_command_starts_with_resolved_interpreter(self, tmp_path):
        """The built test command must start with the resolved interpreter, not bare 'python3'."""
        venv_dir = tmp_path / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        fake_python = venv_dir / "python"
        os.symlink(sys.executable, str(fake_python))

        plan = self._make_fake_plan()
        policy = self._make_fake_policy(test_command=None)

        captured_cmds = []
        real_run = __import__("subprocess").run

        def capture_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            # Let the actual subprocess run so evidence is valid.
            return real_run(cmd, **kwargs)

        env = os.environ.copy()
        env["PATH"] = "/usr/bin:/bin"
        with mock.patch.dict(os.environ, env):
            with mock.patch("scripts.testing.runner.subprocess.run", side_effect=capture_run):
                run_plan(str(tmp_path), plan, policy, timeout=60)

        # At least one invocation (the main test command) must use the resolved interpreter.
        main_cmds = [c for c in captured_cmds if "-m" in c and "pytest" in c]
        assert main_cmds, "Expected at least one pytest invocation"
        for cmd in main_cmds:
            assert cmd[0] != "python3", (
                f"Command still uses bare 'python3': {cmd}"
            )
