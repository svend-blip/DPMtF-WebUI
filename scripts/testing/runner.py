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

Opt-in parallel execution (Run 014)
-----------------------------------
``run_plan`` accepts ``parallel: bool = False``. The default leaves the
runner identical to Run 013: tests execute serially via ``_run_command``
and the evidence dict gets one additive field, ``parallel_executed``,
`` set to ``False``. When the caller sets ``parallel=True`` AND the
plan is selective with two or more test files AND worker isolation can
be proven, the runner splits the selected tests into groups and
dispatches each group to a fresh Python subprocess via
``concurrent.futures.ProcessPoolExecutor``. When worker isolation cannot
be proven — the executor import fails, fewer than two effective
workers would run, or ``policy.parallel.serial_components`` overlaps
with the plan's ``affected_components`` — the runner falls back to the
same serial path as ``parallel=False`` and reports
``parallel_executed=False`` plus a ``serial_fallback_reason``.

Parallel execution NEVER alters which tests are selected. It is an
optimization of *how* selected tests are executed; selection identity
before and after Run 014 is byte-identical.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scripts.testing.evidence import build_evidence

__all__ = ["run_plan", "RunnerError"]

_DEFAULT_TEST_COMMAND: List[str] = [
    "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
]


class RunnerError(Exception):
    """Raised for truly unexpected failures during test execution."""


def resolve_test_interpreter(repo_root: str) -> str:
    """Resolve the Python interpreter that can run pytest.

    Priority order:
      1. ``<repo_root>/venv/bin/python`` — if it exists AND can import pytest.
      2. ``sys.executable`` — if it can import pytest.
      3. Raises ``RunnerError("no interpreter with pytest")`` otherwise.

    A bare ``python3`` on PATH is never used as a fallback — it may lack
    pytest and produce misleading FAIL results instead of an honest ERROR.
    """
    candidates: list[str] = []
    venv_python = os.path.join(repo_root, "venv", "bin", "python")
    if os.path.isfile(venv_python):
        candidates.append(venv_python)
    candidates.append(sys.executable)

    probe_cmd = "import pytest; print(pytest.__version__)"
    for candidate in candidates:
        try:
            proc = subprocess.run(
                [candidate, "-c", probe_cmd],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                return candidate
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue

    raise RunnerError("no interpreter with pytest")


def _is_environment_error(rc: int, stderr: str) -> bool:
    """True when the failure is an environment problem, not a test failure.

    Exit code 1 with ``No module named`` on stderr means the interpreter
    lacks a required package. ``FileNotFoundError`` is caught at the
    call site and already produces ERROR; this helper handles the case
    where the subprocess ran but reported a missing module.
    """
    return rc != 0 and "No module named" in stderr


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


def _tail_lines(text: str, n: int = 40) -> str:
    """Return the last *n* lines of *text*, preserving line endings.

    Returns an empty string when *text* is empty. The returned string
    has no trailing newline unless the original last line had one.
    """
    if not text:
        return ""
    lines = text.splitlines(keepends=True)
    tail = lines[-n:]
    result = "".join(tail)
    return result.rstrip("\n")


def _is_pytest_command(cmd: List[str]) -> bool:
    """True for the default runner and any ``pytest``/``python -m pytest`` form."""
    if not cmd:
        return False
    head = os.path.basename(cmd[0])
    if head in ("pytest", "py.test"):
        return True
    return head.startswith("python") and "pytest" in cmd[:4]


def _is_go_command(cmd: List[str]) -> bool:
    return bool(cmd) and os.path.basename(cmd[0]) == "go"


def _is_dotnet_command(cmd: List[str]) -> bool:
    return bool(cmd) and os.path.basename(cmd[0]) == "dotnet"


_TOOLCHAIN_FALLBACK_DIRS = (
    "~/.local/bin", "~/go/bin", "/usr/local/go/bin", "~/.dotnet", "/usr/share/dotnet",
)

_DOTNET_PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj", ".sln")


def resolve_command(cmd: List[str]) -> List[str]:
    """Return *cmd* with its executable resolved.

    The gate runs from whatever environment dispatched it (a systemd user
    unit, a tmux pane, a test), and a Go toolchain installed under the
    user's home is not on that PATH. A policy must not carry an absolute
    home path either, so the runner looks in the conventional toolchain
    directories when ``which`` fails. Everything else is left alone.
    """
    if not cmd:
        return cmd
    if os.path.sep in cmd[0] or shutil.which(cmd[0]):
        return list(cmd)
    for d in _TOOLCHAIN_FALLBACK_DIRS:
        candidate = os.path.join(os.path.expanduser(d), cmd[0])
        if os.access(candidate, os.X_OK):
            return [candidate, *cmd[1:]]
    return list(cmd)


def _collect_go_packages(repo_root: str, packages: List[str], go_cmd: List[str]) -> tuple[bool, str]:
    """``go list`` is to Go what ``--collect-only`` is to pytest: it fails
    when a selected package pattern matches nothing or does not build."""
    cmd = [go_cmd[0], "list", *packages]
    try:
        rc, stdout, stderr = _run_command(cmd, repo_root, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"go list failed to run: {exc}"
    if rc == 0:
        return True, ""
    return False, stdout + stderr


def _collect_dotnet_projects(repo_root: str, targets: List[str]) -> tuple[bool, str]:
    """``dotnet test`` takes one project or solution per invocation, so the
    collection step is structural: every selected target must be a project
    or solution file under the repository, or a directory holding exactly
    one. Listing tests would build every project first; existence is the
    honest cheap check, and the run itself is the measurement."""
    problems: List[str] = []
    for target in targets:
        full = os.path.join(repo_root, target)
        if os.path.isfile(full):
            if not full.endswith(_DOTNET_PROJECT_SUFFIXES):
                problems.append(f"{target}: not a project or solution file")
        elif os.path.isdir(full):
            projects = [
                f for f in os.listdir(full)
                if f.endswith(_DOTNET_PROJECT_SUFFIXES)
            ]
            if len(projects) != 1:
                problems.append(
                    f"{target}: directory holds {len(projects)} project/solution files, need exactly 1"
                )
        else:
            problems.append(f"{target}: does not exist")
    if problems:
        return False, "; ".join(problems)
    return True, ""


def _run_per_target(
    base: List[str],
    targets: List[str],
    cwd: str,
    timeout: Optional[float],
) -> tuple[int, str, str]:
    """Run ``base + [target]`` once per target within one total timeout.

    The first non-zero exit code is the aggregate code; outputs are
    concatenated with a header per target so the evidence shows which
    project failed."""
    deadline = None if timeout is None else perf_counter() + timeout
    rc_all = 0
    out_parts: List[str] = []
    err_parts: List[str] = []
    for target in targets:
        remaining = None if deadline is None else max(0.0, deadline - perf_counter())
        if remaining is not None and remaining <= 0:
            raise subprocess.TimeoutExpired(base + [target], timeout or 0)
        rc, stdout, stderr = _run_command(base + [target], cwd, timeout=remaining)
        out_parts.append(f"=== {target} (exit {rc}) ===\n{stdout}")
        if stderr:
            err_parts.append(f"=== {target} ===\n{stderr}")
        if rc != 0 and rc_all == 0:
            rc_all = rc
    return rc_all, "\n".join(out_parts), "\n".join(err_parts)


def _collect_tests(
    repo_root: str,
    test_paths: List[str],
) -> tuple[bool, str]:
    """Check whether all requested test paths can be collected.

    Returns (ok, error_detail).
    ok is True when collection succeeds, False otherwise.
    error_detail describes the failure when ok is False.
    """
    interpreter = resolve_test_interpreter(repo_root)
    cmd: List[str] = [
        interpreter, "-m", "pytest",
        "--collect-only", "-q",
        "-p", "no:cacheprovider",
        *test_paths,
    ]
    rc, stdout, stderr = _run_command(cmd, repo_root)
    combined = stdout + stderr
    # The exit code is the measurement. A substring scan of the output is
    # not: a test NAMED test_..._error is a legitimate collected item, not
    # a collection failure. pytest returns 0 on successful collection, 5
    # when nothing was collected, 2 on collection errors.
    if rc == 0:
        return True, ""
    return False, combined


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


# ---------------------------------------------------------------------------
# Parallel execution helpers (Run 014, handoff 107)
# ---------------------------------------------------------------------------


def _get_process_pool_executor() -> Any:
    """Return ``ProcessPoolExecutor`` or ``None`` when unavailable.

    A ``None`` return signals the parallel path to fall back to serial —
    a parallel runner that cannot prove worker independence is a machine
    for turning real failures into passes.
    """
    try:
        from concurrent.futures import ProcessPoolExecutor

        return ProcessPoolExecutor
    except ImportError:
        return None


def _get_serial_components(policy: Any) -> List[str]:
    """Return ``policy.parallel.serial_components`` when set, else ``[]``.

    Serial-component restriction: any affected component in this list
    forces the runner to execute serially. With no per-test component
    mapping available to the runner, the conservative interpretation
    is "any overlap forces a serial run for the whole plan".
    """
    parallel_cfg = getattr(policy, "parallel", None)
    if isinstance(parallel_cfg, dict):
        sc = parallel_cfg.get("serial_components", [])
        if isinstance(sc, list):
            return [str(s) for s in sc if isinstance(s, str)]
    return []


def _resolve_worker_count(policy: Any) -> int:
    """Resolve worker count from ``policy.parallel.workers`` or ``os.cpu_count()``.

    ``"auto"`` (the default) maps to ``max(1, os.cpu_count())``. Any
    positive integer is honoured verbatim. Anything else falls back to
    ``"auto"`` semantics — the runner never guesses on worker count.
    """
    parallel_cfg = getattr(policy, "parallel", None)
    workers: Any = "auto"
    if isinstance(parallel_cfg, dict):
        workers = parallel_cfg.get("workers", "auto")
    if isinstance(workers, int) and not isinstance(workers, bool) and workers >= 1:
        return int(workers)
    return max(1, os.cpu_count() or 1)


def _group_tests_round_robin(
    tests: List[str], num_groups: int
) -> List[List[str]]:
    """Split *tests* into *num_groups* groups using round-robin assignment.

    Empty groups are dropped so the worker count equals the number of
    non-empty groups actually executed. The assignment is deterministic:
    ``tests[0]`` goes to group 0, ``tests[1]`` to group 1, etc.
    """
    if num_groups < 1 or not tests:
        return []
    groups: List[List[str]] = [[] for _ in range(num_groups)]
    for i, t in enumerate(tests):
        groups[i % num_groups].append(t)
    return [g for g in groups if g]


def _aggregate_worker_results(
    worker_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Reduce worker outputs to a summary dict for status determination.

    Returns:
        ``max_returncode``: highest individual returncode seen.
        ``failed``: number of workers whose returncode is non-zero.
        ``error_count``: number of workers that reported an exception.
        ``errors``: list of error message strings (capped at 3 in messages).
    """
    max_rc = 0
    failed = 0
    error_count = 0
    errors: List[str] = []
    for r in worker_results:
        rc = int(r.get("returncode", 0))
        if rc > max_rc:
            max_rc = rc
        if rc != 0:
            failed += 1
        err = r.get("error")
        if err:
            error_count += 1
            errors.append(str(err))
    return {
        "max_returncode": max_rc,
        "failed": failed,
        "error_count": error_count,
        "errors": errors,
    }


def _parallel_worker_run(args: Tuple[str, List[str], Optional[float]]) -> Dict[str, Any]:
    """Run pytest on *test_paths* in a worker subprocess.

    Must be defined at module level so ``ProcessPoolExecutor`` can
    pickle it across the spawn boundary. The worker shares no state
    with the parent — a fresh subprocess invokes pytest with the same
    ``-p no:cacheprovider`` and ``-q`` flags the serial path uses.

    Args:
        args: ``(repo_root, test_paths, timeout)``.

    Returns:
        ``dict`` with ``returncode``, ``stdout``, ``stderr``,
        ``duration``, and an optional ``error`` field.
    """
    repo_root, test_paths, timeout = args
    interpreter = resolve_test_interpreter(repo_root)
    cmd: List[str] = [
        interpreter, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        *test_paths,
    ]
    start = perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = round(perf_counter() - start, 2)
        return {
            "returncode": int(proc.returncode),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration": duration,
        }
    except subprocess.TimeoutExpired:
        duration = round(perf_counter() - start, 2)
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Worker timeout",
            "duration": duration,
            "error": "timeout",
        }
    except (FileNotFoundError, OSError) as exc:
        duration = round(perf_counter() - start, 2)
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "duration": duration,
            "error": str(exc),
        }


def _execute_serial_for_fallback(
    repo_root: str,
    plan: Any,
    cmd: List[str],
    timeout: Optional[float],
) -> Dict[str, Any]:
    """Serial execution path used by parallel-fallback scenarios.

    Identical in effect to the default serial branch in ``run_plan``:
    builds evidence with ``build_evidence`` and stamps the standard
    escalation reasons for ``FAIL`` and ``ERROR`` outcomes.
    """
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
        stdout_tail=_tail_lines(stdout),
        stderr_tail=_tail_lines(stderr),
    )

    if status == "FAIL":
        evidence["escalation_reason"] = f"Tests failed with exit code {rc}"

    return evidence


def _run_plan_parallel(
    repo_root: str,
    plan: Any,
    policy: Any,
    selected_tests: List[str],
    test_command: List[str],
    cmd: List[str],
    timeout: Optional[float],
    collect_coverage: bool,
) -> Dict[str, Any]:
    """Execute the plan's selected tests in parallel worker subprocesses.

    Falls back to serial execution (and the same evidence shape) when:

    1. ``policy.parallel.serial_components`` overlaps with the plan's
       ``affected_components`` — serial restriction applies.
    2. ``ProcessPoolExecutor`` cannot be imported — worker isolation
       is unprovable.
    3. The resolved worker count collapses to fewer than two effective
       groups — no parallelism is possible.

    When parallel execution succeeds, the returned evidence dict carries
    ``parallel_executed=True`` and ``parallel_workers=<n>``. When any
    fallback runs, the dict carries ``parallel_executed=False`` and a
    ``serial_fallback_reason`` naming the cause.
    """
    # Serial-components restriction
    serial_components = _get_serial_components(policy)
    affected_components = list(getattr(plan, "affected_components", []))
    if serial_components and any(
        c in serial_components for c in affected_components
    ):
        evidence = _execute_serial_for_fallback(repo_root, plan, cmd, timeout)
        evidence["parallel_executed"] = False
        evidence["serial_fallback_reason"] = "serial_components_restriction"
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
        return evidence

    # Fewer-than-two selected tests: nothing to parallelize.
    if len(selected_tests) < 2:
        evidence = _execute_serial_for_fallback(repo_root, plan, cmd, timeout)
        evidence["parallel_executed"] = False
        evidence["serial_fallback_reason"] = "fewer_than_two_workers"
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
        return evidence

    # ProcessPoolExecutor availability — isolation must be provable
    pool_cls = _get_process_pool_executor()
    if pool_cls is None:
        evidence = _execute_serial_for_fallback(repo_root, plan, cmd, timeout)
        evidence["parallel_executed"] = False
        evidence["serial_fallback_reason"] = "process_pool_unavailable"
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
        return evidence

    # Group tests using the resolved worker count
    worker_count = _resolve_worker_count(policy)
    groups = _group_tests_round_robin(selected_tests, worker_count)
    actual_workers = len(groups)

    if actual_workers < 2:
        # No parallelism possible — fall back to serial.
        evidence = _execute_serial_for_fallback(repo_root, plan, cmd, timeout)
        evidence["parallel_executed"] = False
        evidence["serial_fallback_reason"] = "fewer_than_two_workers"
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
        return evidence

    # Dispatch workers
    start = perf_counter()
    worker_results: List[Dict[str, Any]] = []
    executor_failed = False
    try:
        with pool_cls(max_workers=actual_workers) as executor:
            futures = [
                executor.submit(_parallel_worker_run, (repo_root, group, timeout))
                for group in groups
            ]
            for future in futures:
                try:
                    worker_results.append(future.result())
                except Exception as exc:  # noqa: BLE001 — surface worker error
                    worker_results.append({
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"Worker exception: {exc}",
                        "duration": 0.0,
                        "error": str(exc),
                    })
    except Exception as exc:  # noqa: BLE001 — executor broken, fall back
        executor_failed = True
        fallback_exc = exc
    else:
        executor_failed = False
        fallback_exc = None

    if executor_failed:
        evidence = _execute_serial_for_fallback(repo_root, plan, cmd, timeout)
        evidence["parallel_executed"] = False
        evidence["serial_fallback_reason"] = (
            f"executor_creation_failed: {fallback_exc}"
        )
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
        return evidence

    duration = round(perf_counter() - start, 2)

    # Aggregate results into a status decision
    agg = _aggregate_worker_results(worker_results)
    if agg["error_count"] > 0:
        status = "ERROR"
    elif agg["failed"] > 0:
        status = "FAIL"
    else:
        status = "PASS"

    # Aggregate stdout/stderr tails from all workers for the evidence record.
    combined_stdout = "\n".join(
        r.get("stdout", "") for r in worker_results if r.get("stdout")
    )
    combined_stderr = "\n".join(
        r.get("stderr", "") for r in worker_results if r.get("stderr")
    )

    evidence = build_evidence(
        repo_root=repo_root,
        plan=plan,
        test_command=cmd,
        status=status,
        duration_seconds=duration,
        stdout_tail=_tail_lines(combined_stdout),
        stderr_tail=_tail_lines(combined_stderr),
    )

    if status == "FAIL":
        escalation = getattr(plan, "escalation_reason", "")
        if escalation:
            escalation += "; "
        escalation += (
            f"Tests failed with exit code {agg['max_returncode']} in "
            f"{agg['failed']} of {actual_workers} parallel worker(s)"
        )
        evidence["escalation_reason"] = escalation
    elif status == "ERROR":
        escalation = getattr(plan, "escalation_reason", "")
        if escalation:
            escalation += "; "
        sample = "; ".join(agg["errors"][:3])
        escalation += (
            f"Worker errors in {agg['error_count']} of "
            f"{actual_workers} parallel worker(s): {sample}"
        )
        evidence["escalation_reason"] = escalation

    evidence["parallel_executed"] = True
    evidence["parallel_workers"] = actual_workers

    _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
    return evidence


def run_plan(
    repo_root: str,
    plan: Any,
    policy: Any,
    timeout: Optional[float] = None,
    collect_coverage: bool = False,
    parallel: bool = False,
) -> Dict[str, Any]:
    """Execute a test plan and return a fully populated evidence dict.

    Args:
        repo_root: path to the repository root.
        plan: a TestPlan object with attributes:
            is_exhaustive, selected_tests, resolved_scope,
            affected_components, escalation_reason, policy_hash, plan_hash.
        policy: a Policy object with attribute test_command (list[str] | None)
            and an optional ``parallel`` dict (Run 014).
        timeout: optional maximum seconds for the test command.
        collect_coverage: when True AND ``plan.resolved_scope`` is
            ``"broad"`` or ``"full"``, a CoverageRecord is built and
            persisted to ``.dpmtf/coverage-index.json``. The returned
            evidence dict is unchanged — coverage never alters the
            22-key schema. Default ``False``.
        parallel: when True AND the plan is selective with two or more
            test files AND worker isolation can be proven, the runner
            dispatches the selected tests to fresh subprocess workers
            via ``concurrent.futures.ProcessPoolExecutor``. When worker
            isolation cannot be proven, the suite runs serially via the
            same path as ``parallel=False``. Default ``False``. See the
            module docstring for the full fallback contract.

    Returns:
        A fully populated evidence dict from ``build_evidence()`` with
        an additive ``parallel_executed`` field (``True`` when a parallel
        run actually executed, ``False`` otherwise). When parallel
        execution ran, ``parallel_workers`` is also present.
    """
    # Resolve test command
    test_command = getattr(policy, "test_command", None)
    if test_command is None:
        test_command = list(_DEFAULT_TEST_COMMAND)
        # Default pytest path: replace the placeholder interpreter with
        # one that can actually import pytest. A policy-provided command
        # is left alone — the operator chose that interpreter explicitly.
        try:
            interpreter = resolve_test_interpreter(repo_root)
        except RunnerError as exc:
            evidence = build_evidence(
                repo_root=repo_root,
                plan=plan,
                test_command=test_command,
                status="ERROR",
                duration_seconds=0.0,
            )
            evidence["escalation_reason"] = str(exc)
            evidence["parallel_executed"] = False
            return evidence
        test_command[0] = interpreter
    else:
        test_command = list(test_command)

    is_exhaustive = getattr(plan, "resolved_scope", "") == "full"
    selected_tests = list(getattr(plan, "selected_tests", []))
    test_command = resolve_command(test_command)
    pytest_runner = _is_pytest_command(test_command)

    # Determine actual command and test paths
    if is_exhaustive:
        cmd = list(test_command)
        if _is_go_command(test_command) and not any(a.startswith("./") or a == "..." for a in cmd[1:]):
            # ``go test`` with no package argument tests only the current
            # directory; exhaustive means the whole module.
            cmd.append("./...")
    else:
        cmd = list(test_command) + list(selected_tests)

    # Selective mode: verify collectability first
    if not is_exhaustive and selected_tests:
        if pytest_runner:
            collect_ok, collect_error = _collect_tests(repo_root, selected_tests)
        elif _is_go_command(test_command):
            collect_ok, collect_error = _collect_go_packages(repo_root, selected_tests, test_command)
        elif _is_dotnet_command(test_command):
            collect_ok, collect_error = _collect_dotnet_projects(repo_root, selected_tests)
        else:
            # An unknown runner has no collection step; the run itself is
            # the measurement.
            collect_ok, collect_error = True, ""
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
            evidence["parallel_executed"] = False
            _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
            return evidence

    # Decide whether to attempt parallel execution. Parallel is only
    # meaningful for selective plans — exhaustive plans ignore
    # ``selected_tests``. The parallel path itself short-circuits when
    # there are fewer than two test files to distribute; keeping the
    # gating here at the selective-plan level lets that fallback be
    # reported with its own ``serial_fallback_reason``.
    # The parallel path shards test FILES across pytest workers; it has
    # no meaning for another runner.
    parallel_attempted = parallel and not is_exhaustive and pytest_runner
    if parallel_attempted:
        return _run_plan_parallel(
            repo_root=repo_root,
            plan=plan,
            policy=policy,
            selected_tests=selected_tests,
            test_command=test_command,
            cmd=cmd,
            timeout=timeout,
            collect_coverage=collect_coverage,
        )

    # Default serial path — unchanged from Run 005/010/013 except for
    # the additive ``parallel_executed`` field.
    start = perf_counter()
    try:
        if _is_dotnet_command(test_command) and not is_exhaustive and selected_tests:
            # dotnet test accepts a single project or solution per call.
            rc, stdout, stderr = _run_per_target(
                list(test_command), selected_tests, repo_root, timeout
            )
        else:
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
        evidence["parallel_executed"] = False
        _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
        return evidence

    duration = round(perf_counter() - start, 2)

    # Determine status from exit code
    if _is_environment_error(rc, stderr):
        status = "ERROR"
    elif rc == 0:
        status = "PASS"
    else:
        status = "FAIL"

    evidence = build_evidence(
        repo_root=repo_root,
        plan=plan,
        test_command=cmd,
        status=status,
        duration_seconds=duration,
        stdout_tail=_tail_lines(stdout),
        stderr_tail=_tail_lines(stderr),
    )

    if status == "FAIL":
        escalation = getattr(plan, "escalation_reason", "")
        if escalation:
            escalation += "; "
        escalation += f"Tests failed with exit code {rc}"
        evidence["escalation_reason"] = escalation

    if status == "ERROR":
        escalation = getattr(plan, "escalation_reason", "")
        if escalation:
            escalation += "; "
        escalation += f"Environment error: {stderr.strip()}"
        evidence["escalation_reason"] = escalation

    evidence["parallel_executed"] = False
    _maybe_collect_coverage(repo_root, plan, policy, collect_coverage)
    return evidence
