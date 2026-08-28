"""Deterministic test execution engine for the test-impact subsystem.

Executes a test plan against a repository and returns a fully populated
evidence dict. Used by the execution step (D2) in the 1000 flow.
"""

from __future__ import annotations

import subprocess
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence

from scripts.testing.evidence import build_evidence

__all__ = ["run_plan", "RunnerError"]

_DEFAULT_TEST_COMMAND: List[str] = [
    "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
]


class RunnerError(Exception):
    """Raised for truly unexpected failures during test execution."""


def _run_command(
    cmd: List[str],
    cwd: str,
    timeout: Optional[float] = None,
) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _collect_tests(
    repo_root: str,
    test_paths: List[str],
) -> tuple[bool, str]:
    """Check whether all requested test paths can be collected.

    Returns (ok, error_detail).
    ok is True when collection succeeds, False otherwise.
    error_detail describes the failure when ok is False.
    """
    cmd: List[str] = [
        "python3", "-m", "pytest",
        "--collect-only", "-q",
        "-p", "no:cacheprovider",
        *test_paths,
    ]
    rc, stdout, stderr = _run_command(cmd, repo_root)
    combined = stdout + stderr
    if rc != 5 and "error" in combined.lower():
        return False, combined
    if rc == 5:
        # pytest --collect-only returns 5 when no tests collected
        # Check if tests were actually found
        if "no tests" in combined.lower() or "no tests collected" in combined.lower():
            return False, combined
    # rc == 0 or rc == 4 (some tests collected but nothing to run) with no error text
    return True, ""


def run_plan(
    repo_root: str,
    plan: Any,
    policy: Any,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Execute a test plan and return a fully populated evidence dict.

    Args:
        repo_root: path to the repository root.
        plan: a TestPlan object with attributes:
            is_exhaustive, selected_tests, resolved_scope,
            affected_components, escalation_reason, policy_hash, plan_hash.
        policy: a Policy object with attribute test_command (list[str] | None).
        timeout: optional maximum seconds for the test command.

    Returns:
        A fully populated evidence dict from build_evidence().
    """
    # Resolve test command
    test_command = getattr(policy, "test_command", None)
    if test_command is None:
        test_command = list(_DEFAULT_TEST_COMMAND)
    else:
        test_command = list(test_command)

    is_exhaustive = bool(getattr(plan, "is_exhaustive", False))
    selected_tests = list(getattr(plan, "selected_tests", []))

    # Determine actual command and test paths
    if is_exhaustive:
        cmd = list(test_command)
    else:
        cmd = list(test_command) + list(selected_tests)

    # Selective mode: verify collectability first
    if not is_exhaustive and selected_tests:
        collect_ok, collect_error = _collect_tests(repo_root, selected_tests)
        if not collect_ok:
            duration = 0.0
            evidence = build_evidence(
                repo_root=repo_root,
                plan=plan,
                test_command=cmd,
                status="ERROR",
                duration_seconds=duration,
            )
            escalation = getattr(plan, "escalation_reason", "")
            if escalation:
                escalation += "; "
            escalation += "SELECTED_TESTS_NOT_COLLECTABLE: " + collect_error.strip()
            evidence["escalation_reason"] = escalation
            return evidence

    # Execute the test command
    start = perf_counter()
    try:
        rc, stdout, stderr = _run_command(cmd, repo_root, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        duration = round(perf_counter() - start, 2)
        evidence = build_evidence(
            repo_root=repo_root,
            plan=plan,
            test_command=cmd,
            status="ERROR",
            duration_seconds=duration,
        )
        evidence["escalation_reason"] = f"Command execution failed: {exc}"
        return evidence

    duration = round(perf_counter() - start, 2)

    # Determine status from exit code
    if rc == 0:
        status = "PASS"
    else:
        status = "FAIL"

    evidence = build_evidence(
        repo_root=repo_root,
        plan=plan,
        test_command=cmd,
        status=status,
        duration_seconds=duration,
    )

    if status == "FAIL":
        escalation = getattr(plan, "escalation_reason", "")
        if escalation:
            escalation += "; "
        escalation += f"Tests failed with exit code {rc}"
        evidence["escalation_reason"] = escalation

    return evidence
