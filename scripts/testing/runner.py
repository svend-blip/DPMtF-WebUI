"""Deterministic test execution engine for the test-impact subsystem.

Executes a test plan against a repository and returns a fully populated
evidence dict. Used by the execution step (D2) in the 1000 flow.

Opt-in coverage collection
--------------------------
``run_plan`` accepts ``collect_coverage``. The default is ``False`` and
the runner behaves **exactly** as Run 005 left it. When ``True`` AND the
plan's ``resolved_scope`` is ``"broad"`` or ``"full"``, the runner
attempts to build a :class:`CoverageRecord` and persists it to
``<repo_root>/.dpmtf/coverage-index.json``. The evidence dict is
returned unchanged either way — coverage never alters the 22-key
evidence schema.
"""

from __future__ import annotations

import os
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


# ---------------------------------------------------------------------------
# Coverage helpers (opt-in, off by default)
# ---------------------------------------------------------------------------


def _git_repo_fingerprint(repo_root: str) -> str:
    """Return a stable SHA-256 over the current ``git rev-parse HEAD``.

    Returns the empty string when git is unavailable or the call fails —
    that empty string makes any coverage record built from it
    incompatible with every state, which is the desired fail-closed
    behaviour.
    """
    import hashlib

    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    sha = proc.stdout.strip()
    if not sha:
        return ""
    return hashlib.sha256(sha.encode("utf-8")).hexdigest()


def _persist_coverage_record(
    repo_root: str,
    record: Any,
) -> Optional[str]:
    """Persist a CoverageRecord to ``.dpmtf/coverage-index.json``.

    Returns the on-disk path on success, ``None`` on failure (the
    caller treats coverage as best-effort and continues).
    """
    try:
        dpmtf_dir = os.path.join(repo_root, ".dpmtf")
        os.makedirs(dpmtf_dir, exist_ok=True)
        path = os.path.join(dpmtf_dir, "coverage-index.json")
        record_dict = record.to_dict()
        import json as _json

        with open(path, "w", encoding="utf-8") as f:
            _json.dump(record_dict, f, indent=2, sort_keys=True)
            f.write("\n")
        return path
    except OSError:
        return None


def _try_build_empty_coverage_record(
    repo_root: str,
    plan: Any,
    policy: Any,
) -> Any:
    """Build an empty :class:`CoverageRecord` bound to the current state.

    The record is empty because the runner does not parse ``.coverage``
    or ``coverage.json`` output — that parsing is a follow-up Run. The
    *bound* record (correct fingerprints, correct ``run_scope``,
    ``collected_at``) is what the contract requires for this Run: the
    index module, the merge semantics, and the staleness guard are all
    exercised end-to-end against a real record; only the *content* is
    empty.

    Returns ``None`` if the coverage-index module cannot be imported
    (caller treats this as "not collected").
    """
    try:
        from scripts.testing.coverage_index import CoverageRecord
    except Exception:
        return None

    repo_fp = _git_repo_fingerprint(repo_root)
    policy_fp = str(getattr(policy, "policy_hash", "") or "")
    resolved_scope = str(getattr(plan, "resolved_scope", "broad"))
    if resolved_scope not in ("broad", "full"):
        resolved_scope = "broad"

    return CoverageRecord(
        symbol_to_tests={},
        repo_fingerprint=repo_fp,
        policy_fingerprint=policy_fp,
        run_scope=resolved_scope,
    )


def _maybe_collect_coverage(
    repo_root: str,
    plan: Any,
    policy: Any,
    collect_coverage: bool,
) -> Optional[Any]:
    """Return a CoverageRecord when collection is requested and applicable.

    Collection only proceeds when:
    1. The caller opted in (``collect_coverage is True``).
    2. The plan's resolved scope is ``"broad"`` or ``"full"`` — coverage
       is meaningless at narrower rungs of the scope ladder.
    3. The coverage-index module can be imported.

    The record is *also* persisted to ``.dpmtf/coverage-index.json`` so
    a later handoff can read it without re-collecting. Persistence
    failure is silent — coverage is best-effort.
    """
    if not collect_coverage:
        return None
    resolved_scope = str(getattr(plan, "resolved_scope", ""))
    if resolved_scope not in ("broad", "full"):
        return None

    record = _try_build_empty_coverage_record(repo_root, plan, policy)
    if record is None:
        return None

    _persist_coverage_record(repo_root, record)
    return record


def run_plan(
    repo_root: str,
    plan: Any,
    policy: Any,
    timeout: Optional[float] = None,
    collect_coverage: bool = False,
) -> Dict[str, Any]:
    """Execute a test plan and return a fully populated evidence dict.

    Args:
        repo_root: path to the repository root.
        plan: a TestPlan object with attributes:
            is_exhaustive, selected_tests, resolved_scope,
            affected_components, escalation_reason, policy_hash, plan_hash.
        policy: a Policy object with attribute test_command (list[str] | None).
        timeout: optional maximum seconds for the test command.
        collect_coverage: when True AND ``plan.resolved_scope`` is
            ``"broad"`` or ``"full"``, a CoverageRecord is built and
            persisted to ``.dpmtf/coverage-index.json``. The returned
            evidence dict is unchanged — coverage never alters the
            22-key schema. Default ``False``.

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
            _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
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
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
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

    _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
    return evidence
