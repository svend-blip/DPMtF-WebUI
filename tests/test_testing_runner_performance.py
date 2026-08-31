"""Tests for the runner's parallel-execution strategy (Run 014, handoff 107).

Each test creates a fresh temporary git repository (tempfile.mkdtemp) with
real pytest test files, so worker subprocesses have something genuine to
execute. The runner module is loaded via ``importlib.util.spec_from_file_location``
so the tests are independent of ``sys.path`` and the DPMtF-WebUI working
tree.

Public API under test:
    run_plan(repo_root, plan, policy, timeout, collect_coverage, parallel)
        → evidence dict (22 canonical keys + additive ``parallel_executed``
          and optional ``parallel_workers``).

The required test functions (TG1, TG2, TG3, TG5) are present:
    test_selection_is_identical_before_and_after
    test_a_failing_test_still_fails_in_parallel
    test_policy_parallelism_restrictions_are_honoured
    test_unprovable_isolation_falls_back_to_serial

The four required tests plus four structural tests satisfy TG7 (≥8 tests).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # DPMtF-WebUI root
RUNNER_PATH = PROJECT_ROOT / "scripts" / "testing" / "runner.py"

# Load the runner module from its absolute path.
#
# NOTE: ``concurrent.futures.ProcessPoolExecutor`` pickles the worker
# callable and asks the child to import it by module name. The dynamic
# import path used by ``spec_from_file_location`` creates a module
# that is findable by attribute on the test process but NOT by name in
# the spawned child — child import fails with "import of module
# 'runner_perf_test' failed" and every worker raises an exception. We
# sidestep that by registering the module in ``sys.modules`` under its
# declared name before executing it.
import sys  # noqa: E402

_runner_spec = importlib.util.spec_from_file_location(
    "runner_perf_test", RUNNER_PATH
)
_runner_mod = importlib.util.module_from_spec(_runner_spec)
sys.modules["runner_perf_test"] = _runner_mod
_runner_spec.loader.exec_module(_runner_mod)

run_plan = _runner_mod.run_plan
_get_process_pool_executor = _runner_mod._get_process_pool_executor
_get_serial_components = _runner_mod._get_serial_components
_resolve_worker_count = _runner_mod._resolve_worker_count
_group_tests_round_robin = _runner_mod._group_tests_round_robin


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


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
    is_exhaustive=False,
    selected_tests=None,
    resolved_scope="component",
    affected_components=None,
    escalation_reason="",
    policy_hash="pol-hash",
    plan_hash="plan-hash",
):
    return SimpleNamespace(
        is_exhaustive=is_exhaustive,
        selected_tests=list(selected_tests or []),
        resolved_scope=resolved_scope,
        affected_components=list(affected_components or []),
        escalation_reason=escalation_reason,
        policy_hash=policy_hash,
        plan_hash=plan_hash,
    )


def _make_policy(
    test_command=None,
    parallel=None,
):
    """Build a SimpleNamespace that quacks like Policy for the runner."""
    return SimpleNamespace(test_command=test_command, parallel=parallel)


def _make_repo_with_tests(num_passing: int = 2, num_failing: int = 0) -> str:
    """Create a temp git repo with *num_passing* passing and *num_failing*
    failing pytest test files. Returns the repo path.
    """
    tmpdir = tempfile.mkdtemp()
    _init_repo(tmpdir)
    for i in range(num_passing):
        _write_pytest_test(
            tmpdir,
            f"test_pass_{i}.py",
            "class TestPass:\n"
            f"    def test_pass_{i}(self):\n"
            "        assert True\n",
        )
    for i in range(num_failing):
        _write_pytest_test(
            tmpdir,
            f"test_fail_{i}.py",
            "class TestFailing:\n"
            f"    def test_fail_{i}(self):\n"
            "        assert False\n",
        )
    return tmpdir


def _selected_test_paths(repo: str, *names: str) -> list[str]:
    """Build a deterministic ``selected_tests`` list (absolute paths)."""
    return [os.path.join(repo, n) for n in names]


# ---------------------------------------------------------------------------
# TG1: Selection identity before and after parallel execution.
# ---------------------------------------------------------------------------


class TestSelectionIdentity(unittest.TestCase):
    """``selected_tests`` is byte-identical whether the runner runs serially
    or in parallel. Parallelism is an execution optimisation; selection is not.
    """

    def setUp(self):
        self.repo = _make_repo_with_tests(num_passing=3)
        self.test_paths = _selected_test_paths(
            self.repo, "test_pass_0.py", "test_pass_1.py", "test_pass_2.py"
        )

    def test_selection_is_identical_before_and_after(self):
        """Run serial and parallel on the same plan; selected_tests matches
        byte-for-byte. (TG1.)
        """
        plan = _make_plan(selected_tests=self.test_paths)
        policy = _make_policy()

        serial = run_plan(self.repo, plan, policy, parallel=False)
        parallel = run_plan(self.repo, plan, policy, parallel=True)

        self.assertEqual(serial["status"], "PASS")
        self.assertEqual(parallel["status"], "PASS")

        self.assertEqual(serial["selected_tests"], self.test_paths)
        self.assertEqual(parallel["selected_tests"], self.test_paths)
        self.assertEqual(serial["selected_tests"], parallel["selected_tests"])

        # Status, plan_hash, policy_hash are also identical (the test selection
        # does not depend on how it is executed).
        self.assertEqual(serial["status"], parallel["status"])
        self.assertEqual(serial["plan_hash"], parallel["plan_hash"])
        self.assertEqual(serial["policy_hash"], parallel["policy_hash"])


# ---------------------------------------------------------------------------
# TG2: A failing test still fails under parallel execution.
# ---------------------------------------------------------------------------


class TestFailurePropagation(unittest.TestCase):
    """Failures must propagate through parallel workers."""

    def setUp(self):
        self.repo = _make_repo_with_tests(num_passing=1, num_failing=1)
        self.test_paths = _selected_test_paths(
            self.repo, "test_pass_0.py", "test_fail_0.py"
        )

    def test_a_failing_test_still_fails_in_parallel(self):
        """Run a failing test in parallel; status is FAIL, not PASS. (TG2.)"""
        plan = _make_plan(selected_tests=self.test_paths)
        policy = _make_policy()

        evidence = run_plan(self.repo, plan, policy, parallel=True)

        self.assertEqual(evidence["status"], "FAIL")
        # The escalation reason should mention a non-zero exit code.
        self.assertIn("exit code", evidence["escalation_reason"])
        # Parallel actually executed, not a serial fallback.
        self.assertTrue(evidence["parallel_executed"])
        self.assertGreaterEqual(evidence["parallel_workers"], 1)


# ---------------------------------------------------------------------------
# TG3: Policy serial_components restriction is honoured.
# ---------------------------------------------------------------------------


class TestSerialComponentRestriction(unittest.TestCase):
    """When an affected component is in policy.parallel.serial_components,
    the runner falls back to serial even when parallel=True."""

    def setUp(self):
        self.repo = _make_repo_with_tests(num_passing=2)
        self.test_paths = _selected_test_paths(
            self.repo, "test_pass_0.py", "test_pass_1.py"
        )

    def test_policy_parallelism_restrictions_are_honoured(self):
        """A plan with affected_components overlapping serial_components
        executes serially. (TG3.)
        """
        plan = _make_plan(
            selected_tests=self.test_paths,
            affected_components=["database", "frontend"],
        )
        policy = _make_policy(parallel={
            "enabled": True,
            "workers": 2,
            "serial_components": ["database"],
        })

        evidence = run_plan(self.repo, plan, policy, parallel=True)

        self.assertEqual(evidence["status"], "PASS")
        self.assertFalse(evidence["parallel_executed"])
        self.assertEqual(
            evidence["serial_fallback_reason"],
            "serial_components_restriction",
        )


# ---------------------------------------------------------------------------
# TG5: Unprovable worker isolation → serial fallback.
# ---------------------------------------------------------------------------


class TestUnprovableIsolation(unittest.TestCase):
    """When ``ProcessPoolExecutor`` cannot be loaded, the runner must run
    serially. A parallel runner that cannot prove worker independence is a
    machine for turning real failures into passes.
    """

    def setUp(self):
        self.repo = _make_repo_with_tests(num_passing=2)
        self.test_paths = _selected_test_paths(
            self.repo, "test_pass_0.py", "test_pass_1.py"
        )

    def test_unprovable_isolation_falls_back_to_serial(self):
        """Patching ``_get_process_pool_executor`` to return None forces
        a serial fallback. (TG5.)
        """
        plan = _make_plan(selected_tests=self.test_paths)
        policy = _make_policy(parallel={
            "enabled": True,
            "workers": 2,
            "serial_components": [],
        })

        with mock.patch.object(
            _runner_mod, "_get_process_pool_executor", return_value=None
        ):
            evidence = run_plan(self.repo, plan, policy, parallel=True)

        self.assertEqual(evidence["status"], "PASS")
        self.assertFalse(evidence["parallel_executed"])
        self.assertEqual(
            evidence["serial_fallback_reason"], "process_pool_unavailable"
        )


# ---------------------------------------------------------------------------
# Structural and edge-case tests (TG7 ≥ 8 tests total).
# ---------------------------------------------------------------------------


class TestStructuralInvariants(unittest.TestCase):
    """Structural tests on the parallel API surface."""

    def test_run_plan_has_parallel_parameter_default_false(self):
        """``run_plan`` exposes ``parallel`` defaulting to ``False``."""
        import inspect

        sig = inspect.signature(run_plan)
        self.assertIn("parallel", sig.parameters)
        param = sig.parameters["parallel"]
        self.assertEqual(param.default, False)

    def test_parallel_with_one_test_runs_serial(self):
        """When only one test file is selected, parallel collapses to a
        serial run (no parallelism is possible with one worker).
        """
        repo = _make_repo_with_tests(num_passing=1)
        test_paths = _selected_test_paths(repo, "test_pass_0.py")
        plan = _make_plan(selected_tests=test_paths)
        policy = _make_policy()

        evidence = run_plan(repo, plan, policy, parallel=True)

        self.assertEqual(evidence["status"], "PASS")
        self.assertFalse(evidence["parallel_executed"])
        self.assertEqual(
            evidence["serial_fallback_reason"], "fewer_than_two_workers"
        )

    def test_parallel_false_default_preserves_existing_behaviour(self):
        """``parallel=False`` (default) leaves the runner identical to Run 013."""
        repo = _make_repo_with_tests(num_passing=2)
        test_paths = _selected_test_paths(
            repo, "test_pass_0.py", "test_pass_1.py"
        )
        plan = _make_plan(selected_tests=test_paths)
        policy = _make_policy()

        evidence = run_plan(repo, plan, policy)  # parallel default

        self.assertEqual(evidence["status"], "PASS")
        self.assertFalse(evidence["parallel_executed"])
        self.assertNotIn("parallel_workers", evidence)

    def test_parallel_executed_and_workers_are_set_when_parallel_runs(self):
        """When parallel=True runs successfully, evidence carries both
        ``parallel_executed=True`` and ``parallel_workers`` matching the
        configured worker count.
        """
        repo = _make_repo_with_tests(num_passing=3)
        test_paths = _selected_test_paths(
            repo, "test_pass_0.py", "test_pass_1.py", "test_pass_2.py"
        )
        plan = _make_plan(selected_tests=test_paths)
        policy = _make_policy(parallel={
            "enabled": True,
            "workers": 3,
            "serial_components": [],
        })

        evidence = run_plan(repo, plan, policy, parallel=True)

        self.assertEqual(evidence["status"], "PASS")
        self.assertTrue(evidence["parallel_executed"])
        self.assertEqual(evidence["parallel_workers"], 3)


class TestPolicyAndGroupingHelpers(unittest.TestCase):
    """Tests for the internal helpers exposed to the parallel path."""

    def test_get_serial_components_returns_empty_when_no_block(self):
        """A policy missing ``parallel`` has no serial_components."""
        policy = SimpleNamespace(test_command=None, parallel=None)
        self.assertEqual(_get_serial_components(policy), [])

    def test_get_serial_components_returns_list_when_block_set(self):
        """``policy.parallel.serial_components`` is returned verbatim."""
        policy = SimpleNamespace(
            test_command=None,
            parallel={"serial_components": ["db", "browser"]},
        )
        self.assertEqual(_get_serial_components(policy), ["db", "browser"])

    def test_resolve_worker_count_auto_falls_back_to_cpu_count(self):
        """``"auto"`` resolves to ``max(1, os.cpu_count())``."""
        policy = SimpleNamespace(test_command=None, parallel={})
        self.assertEqual(_resolve_worker_count(policy), max(1, os.cpu_count() or 1))

    def test_resolve_worker_count_honours_positive_int(self):
        """A positive int ``workers`` is returned verbatim."""
        policy = SimpleNamespace(
            test_command=None,
            parallel={"workers": 4},
        )
        self.assertEqual(_resolve_worker_count(policy), 4)

    def test_group_tests_round_robin_balances_groups(self):
        """Round-robin groups are roughly balanced and deterministic."""
        groups = _group_tests_round_robin(["a", "b", "c", "d", "e"], 2)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], ["a", "c", "e"])
        self.assertEqual(groups[1], ["b", "d"])

    def test_group_tests_round_robin_drops_empty_groups(self):
        """When num_groups exceeds len(tests), empty groups are dropped."""
        groups = _group_tests_round_robin(["a", "b"], 5)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], ["a"])
        self.assertEqual(groups[1], ["b"])


if __name__ == "__main__":
    unittest.main()