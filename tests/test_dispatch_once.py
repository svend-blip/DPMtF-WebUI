"""Run 034 D1 — the injection-point guard refuses a second dispatch.

Defect, measured live on 2026-08-25: dispatch.py main() falls through
unconditionally to `run_flow_step_db` after every signal action, and
`run_flow_step_db` re-runs the FIRST flow step — which for
preferred_cloud_harness is `supervisor-imple01` with `rule_key="handoff"`.
That convention re-injects the implementer's handoff into a pane that has
already processed it. One `--signal-complete` ⇒ many redundant
dispatches (handoff 115: 11:28:39Z legit, 11:31:54Z and 11:35:35Z
redundant `Delivered ... (DB-driven)`).

D1's answer is the module-level function
`dispatch.handoff_already_dispatched(flow_key, step, handoff_id)`, which
reads trace.log and answers whether this (from_role->to_role, handoff_id)
already has a `dispatched` event. The refusal in `run_flow_step_db` fires
BEFORE any session/harness/deliverable check; it is idempotent success
(`return True`), never silent (print + trace), never fatal. The trace
status is the NEW, FIELD-EXACT `dispatched_skipped` — a `dispatched`
needle must not count it.

These tests are hermetic: a temp DB (sqlite3 backup of prod), a temp
bridge dir (DPMTF_BRIDGE_DIR), a synthetic trace.log, and every outbound
seam (inject_prompt, session_alive, log, ...) patched. No live tmux, no
live trace.log, no live DB.

Names matter: TG3 selects by `-k "refuses_second"`, so the
second-dispatch refusal case MUST contain that substring.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

import dispatch

REAL_DB = PROJECT_ROOT / "databases" / "dpmtf.db"
FLOW = "preferred_cloud_harness"
STEP_KEY = "supervisor-imple01"
HID = "999"
FROM_ROLE = "super-deep-deep4"
TO_ROLE = "imple-codex-minimaxM3"
DIRECTION = f"{FROM_ROLE}->{TO_ROLE}"
DELIVERABLE = f"preferred_cloud_harness/handoffs/{HID}-handoff.md"


class _InjectionCaptured(Exception):
    """Raised by the patched injection seam — proves an injection fired
    (and lets the test stop before post-dispatch side effects)."""


def _copy_prod_db(tmp_path):
    """sqlite3.backup of the prod DB (WAL-safe)."""
    db = tmp_path / "test.db"
    src = sqlite3.connect(str(REAL_DB))
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    dst.close()
    src.close()
    return db


def _patch_outbound(monkeypatch, db):
    """Patch every outbound seam `run_flow_step_db` reaches for."""
    monkeypatch.setattr(dispatch, "_db_path", lambda: str(db))
    monkeypatch.setattr(dispatch, "session_alive", lambda s: True)
    monkeypatch.setattr(dispatch, "harness_alive", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "log", _capturing_log())
    monkeypatch.setattr(dispatch, "get_effective_model_source",
                        lambda *a, **k: ("", ""))
    monkeypatch.setattr(dispatch, "_run_allocator_start", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "_run_allocator_stop", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "_release_from_model_first",
                        lambda *a, **k: False)
    monkeypatch.setattr(dispatch, "append_trade_mcp_context",
                        lambda prompt, *a, **k: prompt)
    monkeypatch.setattr(dispatch, "_run_pre_dispatch_scripts",
                        lambda *a, **k: (True, None))

    models_mod = importlib.import_module("models")

    class _NoJobRepo:
        def __init__(self, *a, **k):
            raise RuntimeError("job DB blocked in tests")

    monkeypatch.setattr(models_mod, "JobRepository", _NoJobRepo)


def _capturing_log():
    """Return a `log` callable that appends every (direction, id, status,
    message) tuple to a module-level list. Tests inspect that list."""
    captured = []

    def _log(direction, handoff_id, status, message, source=None):
        captured.append((direction, str(handoff_id), status, message))

    _log.captured = captured
    return _log


def _write_trace(bridge, lines):
    """Write a synthetic trace.log inside the temp bridge dir."""
    bridge.mkdir(parents=True, exist_ok=True)
    trace = bridge / "trace.log"
    with open(trace, "w", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Hermetic test environment: temp DB, temp bridge dir, all seams patched.

    inject_prompt is patched by the test itself (each test wants a different
    sentinel: capture+raise for the inject path; or a fail-on-call sentinel
    for the refusal path)."""
    db = _copy_prod_db(tmp_path)
    bridge = tmp_path / "bridge"
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(bridge))
    _patch_outbound(monkeypatch, db)
    return SimpleNamespace(db=db, bridge=bridge)


def _ensure_deliverable(bridge):
    """Create the handoff file run_flow_step_db needs to find at step 5."""
    parent = bridge / "preferred_cloud_harness" / "handoffs"
    parent.mkdir(parents=True, exist_ok=True)
    (parent / f"{HID}-handoff.md").write_text(
        f"<handoff_id>{HID}</handoff_id>\n"
        f"<source_role>{FROM_ROLE}</source_role>\n"
        f"<role>test role</role>\n<task>test task</task>\n"
        f"<constraint>test constraint</constraint>\n",
        encoding="utf-8",
    )


def test_refuses_second_dispatch(env, monkeypatch):
    """The guard refuses a second dispatch of the same (direction, handoff).

    Trace pre-arranged with one `dispatched` line for this
    (direction, handoff); we call run_flow_step_db for the
    rule_key="handoff" step. Expected:
      - inject_prompt is NOT called (the whole point — no re-injection)
      - run_flow_step_db returns True (idempotent success, not False)
      - trace gained a line whose status field is EXACTLY
        "dispatched_skipped" (not "dispatched" — the field-exact
        taxonomy is what keeps the watchdog from re-counting this
        refusal as a delivery).
    """
    _write_trace(env.bridge, [
        "2026-08-25T10:00:00Z | super-deep-deep4->other-role | 998 | "
        "dispatched | manual | unrelated handoff",
        f"2026-08-25T11:00:00Z | {DIRECTION} | {HID} | dispatched | "
        f"manual | Handoff {HID}-handoff.md dispatched to {TO_ROLE}",
    ])

    inject_calls = []

    def _must_not_call(session_name, text, **kwargs):
        inject_calls.append((session_name, text))
        raise AssertionError(
            "inject_prompt fired on a refused re-dispatch — "
            "the guard is the point"
        )

    monkeypatch.setattr(dispatch, "inject_prompt", _must_not_call)

    log_callable = dispatch.log  # already patched in env to a capture list
    log_callable.captured.clear()

    ok = dispatch.run_flow_step_db(
        FLOW, STEP_KEY, HID, bridge_dir=str(env.bridge))

    assert inject_calls == [], (
        "inject_prompt fired on a refused re-dispatch — the guard is "
        "the point. Calls: " + repr(inject_calls)
    )
    assert ok is True, (
        "refusal must be idempotent success (return True). A False "
        "return would make _dispatch_main_run sys.exit(1) and every "
        "future nudge print as a failure."
    )
    skipped = [row for row in log_callable.captured
               if row[2] == "dispatched_skipped"]
    assert len(skipped) == 1, (
        "expected exactly one `dispatched_skipped` trace line, got: "
        + repr(log_callable.captured)
    )
    assert skipped[0][0] == DIRECTION, (
        f"trace line direction wrong: {skipped[0][0]!r}"
    )
    assert skipped[0][1] == HID, (
        f"trace line handoff_id wrong: {skipped[0][1]!r}"
    )


def test_permits_first_dispatch(env, monkeypatch):
    """The guard permits the FIRST dispatch (the legitimate signal).

    Empty trace (no `dispatched` line for this handoff); we call
    run_flow_step_db for the same rule_key="handoff" step. Expected:
      - inject_prompt IS called (the implementer must receive the handoff)
      - run_flow_step_db returns True
      - no `dispatched_skipped` line is written (a permitted dispatch
        should NOT be re-tagged as skipped)
    """
    _write_trace(env.bridge, [])  # empty trace
    _ensure_deliverable(env.bridge)

    inject_calls = []

    def _capture(session_name, text, **kwargs):
        inject_calls.append((session_name, text))
        raise _InjectionCaptured()

    monkeypatch.setattr(dispatch, "inject_prompt", _capture)

    log_callable = dispatch.log
    log_callable.captured.clear()

    with pytest.raises(_InjectionCaptured):
        dispatch.run_flow_step_db(
            FLOW, STEP_KEY, HID, bridge_dir=str(env.bridge))

    assert len(inject_calls) == 1, (
        "inject_prompt must be called on a permitted first dispatch. "
        "Calls: " + repr(inject_calls)
    )
    skipped = [row for row in log_callable.captured
               if row[2] == "dispatched_skipped"]
    assert skipped == [], (
        "a permitted dispatch must NOT log `dispatched_skipped`; "
        "got: " + repr(skipped)
    )


def test_handoff_already_dispatched_requires_exact_dispatched_field(
        env, monkeypatch):
    """The reader's field-exactness — `dispatched_skipped` is NOT `dispatched`.

    A trace containing ONLY a `dispatched_skipped` line (or a
    `dispatched_backend_down` line) for the (direction, handoff) must
    make `handoff_already_dispatched(...)` return False: it is the run's
    OWN refusal / backend-down statuses, not a successful delivery. A
    trace containing `dispatched` for the same (direction, handoff)
    must make it return True.

    `dispatched` is a SUBSTRING of `dispatched_skipped` and of
    `dispatched_backend_down`. Substring matching here would let the
    second-dispatch case refuse the FIRST dispatch — the most dangerous
    failure mode. This test is the regression guard.
    """
    step = {"from_role": FROM_ROLE, "to_role": TO_ROLE}

    # Substring trap: only a `dispatched_skipped` line — must return False.
    _write_trace(env.bridge, [
        f"2026-08-25T11:30:00Z | {DIRECTION} | {HID} | dispatched_skipped | "
        f"manual | previous refusal (not a delivery)",
    ])
    assert dispatch.handoff_already_dispatched(FLOW, step, HID) is False, (
        "the reader must compare the status field EXACTLY — "
        "`dispatched_skipped` is not `dispatched`. Got True."
    )

    # Substring trap: only a `dispatched_backend_down` line — must
    # return False.
    _write_trace(env.bridge, [
        f"2026-08-25T11:30:00Z | {DIRECTION} | {HID} | "
        f"dispatched_backend_down | manual | backend was down",
    ])
    assert dispatch.handoff_already_dispatched(FLOW, step, HID) is False, (
        "the reader must compare the status field EXACTLY — "
        "`dispatched_backend_down` is not `dispatched`. Got True."
    )

    # Exact match: a real `dispatched` line — must return True.
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {DIRECTION} | {HID} | dispatched | "
        f"manual | Handoff {HID}-handoff.md dispatched to {TO_ROLE}",
    ])
    assert dispatch.handoff_already_dispatched(FLOW, step, HID) is True, (
        "a real `dispatched` line for the (direction, handoff) must "
        "return True. Got False."
    )

    # Negative control: a `dispatched` line for a DIFFERENT handoff id
    # must NOT match. Same-direction, same-status, different id.
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {DIRECTION} | 998 | dispatched | "
        f"manual | some other handoff",
    ])
    assert dispatch.handoff_already_dispatched(FLOW, step, HID) is False, (
        "handoff id is a field-exact match too — `998` must not match "
        "`999`. Got True."
    )

    # Negative control: same handoff id, `dispatched` status, but a
    # DIFFERENT direction. Must NOT match.
    other_dir = f"{TO_ROLE}->{FROM_ROLE}"
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {other_dir} | {HID} | dispatched | "
        f"manual | some other direction",
    ])
    assert dispatch.handoff_already_dispatched(FLOW, step, HID) is False, (
        "direction is a field-exact match — a different direction must "
        "not match. Got True."
    )


# ── D6 — the root-cause removal (Run 034 §1 D6) ──────────────────────────
# Before D6, dispatch.py main() fell through to
# `_dispatch_main_run(run_flow_step_db, ...)` after every successful
# signal action, re-dispatching the implementer's handoff into the
# implementer's pane. The D1 guard converted each fall-through to a
# `dispatched_skipped` no-op (correct, but noisy: it still ran
# run_flow_step_db's pre-delivery machinery). D6 removes the fall-through
# entirely: each of the four signal branches now exits 0 explicitly.
# This test pins the D6 invariant: a SUCCESSFUL signal path must NOT reach
# run_flow_step_db. TG7 (no_fall_through) is verified directly via
# `-k "no_fall_through"`, not via check_testgoals.py (it is not in
# GOAL.md's testgoals block).

@pytest.mark.parametrize("flag,extra_args", [
    ("--signal-send",
     ["--to-role", "imple-codex-minimaxM3"]),
    ("--signal-escalation",
     ["--to-role", "imple-codex-minimaxM3"]),
    ("--signal-answer",
     ["--to-role", "imple-codex-minimaxM3"]),
    ("--signal-complete",
     ["--step-key", "supervisor-imple01"]),
])
def test_no_fall_through(env, monkeypatch, flag, extra_args):
    """D6 invariant: successful signal paths must terminate explicitly.

    With every signal function patched to return True (success), and
    `run_flow_step_db` patched to a sentinel that raises if reached, the
    expected behaviour is:
      - main() raises SystemExit with code 0 (the restored explicit exit)
      - the run_flow_step_db sentinel was NEVER called

    The current (unfixed) dispatch.py falls through into run_flow_step_db
    after the successful signal branch; the sentinel raises, _dispatch_main_run
    catches it, prints ERROR, and sys.exit(1) — failing the test. The D6
    fix adds `sys.exit(0)` after each successful signal branch, which makes
    the fall-through unreachable.
    """
    # Every signal function returns True (success) — _dispatch_main_run
    # therefore returns and main() continues. The bug is what happens next.
    monkeypatch.setattr(dispatch, "signal_send", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "signal_escalation", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "signal_answer", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "signal_complete", lambda *a, **k: True)

    # run_flow_step_db sentinel — must NEVER be called by a successful
    # signal path. If main() falls through, the sentinel records the call
    # and raises. _dispatch_main_run catches the AssertionError and
    # sys.exit(1)s, which then fails the explicit-exit assertion below.
    flow_step_calls = []

    def _sentinel(*a, **k):
        flow_step_calls.append((a, k))
        raise AssertionError(
            "main() fell through to run_flow_step_db after a successful "
            "signal action — the D6 fix must terminate explicitly"
        )

    monkeypatch.setattr(dispatch, "run_flow_step_db", _sentinel)

    base_argv = ["dispatch.py", "--db-flow", FLOW, "--id", HID,
                 "--from-role", FROM_ROLE]
    test_argv = base_argv + [flag] + extra_args
    monkeypatch.setattr(sys, "argv", test_argv)

    with pytest.raises(SystemExit) as exc_info:
        dispatch.main()

    assert exc_info.value.code == 0, (
        f"main() must exit 0 after a successful signal action, got "
        f"{exc_info.value.code!r}"
    )
    assert flow_step_calls == [], (
        "main() reached run_flow_step_db after a successful signal "
        f"action — the fall-through is the bug D6 removes. Calls: "
        f"{flow_step_calls!r}"
    )


# ── D2 + D3 — the nudger mechanism (Run 034 §1 D2/D3) ──────────────────────
# The autonomous supervisor NEVER emits signal_complete for its own step
# (the anti-loop rule). Both nudgers treated that designed silence as a
# stall — for the dispatch step (supervisor-imple01, rule_key="handoff")
# the predicate "did from_role signal?" is permanently FALSE, so the
# nudger kept "repairing" it. The repair ran dispatch.py --signal-complete
# as a DIRECT subprocess (no broker enqueue), bypassing the run-025 D1
# idempotency guard. D2 fixes the predicate (read trace.log for `dispatched`).
# D3 routes every repair through the broker so the guard screens it.

import importlib

scheduler_mod = importlib.import_module("scheduler")
watchdog_mod = importlib.import_module("chain_watchdog")


def _dispatched_helper_name():
    """Discover the helper name added by the fix. The D2 fix adds a method
    or module-level function called `_dispatched_in_trace` (scheduler) and
    the same in chain_watchdog. If absent, the test is RED (fix not
    applied) — the helper-resolution failure is itself the regression
    signal. Returns (scheduler_helper, watchdog_helper)."""
    sched_helper = getattr(scheduler_mod, "_dispatched_in_trace", None)
    if sched_helper is None and hasattr(scheduler_mod, "Scheduler"):
        sched_helper = getattr(scheduler_mod.Scheduler, "_dispatched_in_trace", None)
    wd_helper = getattr(watchdog_mod, "_dispatched_in_trace", None)
    return sched_helper, wd_helper


# ─── Test 1: D2 predicate — field-exact semantics ────────────────────────
def test_d2_predicate_field_exact_dispatched(env, monkeypatch):
    """D2 predicate — field-exact `dispatched` only.

    The helper MUST compare the status field EXACTLY: a trace with ONLY
    `dispatched_skipped` (or `dispatched_backend_down`) for the
    (from_role, to_role, handoff) transition must NOT count as dispatched.
    A real `dispatched` line must. This is the regression guard for the
    field-exact taxonomy (the same mistake has been made three times in
    this project).
    """
    sched_helper, wd_helper = _dispatched_helper_name()
    assert sched_helper is not None, (
        "scheduler._dispatched_in_trace is missing — D2 fix not applied "
        "to scheduler.py"
    )
    assert wd_helper is not None, (
        "chain_watchdog._dispatched_in_trace is missing — D2 fix not "
        "applied to chain_watchdog.py"
    )

    direction = DIRECTION  # super-deep-deep4->imple-codex-minimaxM3
    from_role, to_role = FROM_ROLE, TO_ROLE

    # Substring trap: ONLY a `dispatched_skipped` line — must return False.
    _write_trace(env.bridge, [
        f"2026-08-25T11:30:00Z | {direction} | {HID} | dispatched_skipped | "
        f"manual | previous refusal (not a delivery)",
    ])
    assert sched_helper(env.bridge, from_role, to_role, HID) is False, (
        "scheduler helper: must compare status FIELD-EXACTLY — "
        "`dispatched_skipped` is not `dispatched`. Got True."
    )
    assert wd_helper(env.bridge, from_role, to_role, HID) is False, (
        "watchdog helper: must compare status FIELD-EXACTLY — "
        "`dispatched_skipped` is not `dispatched`. Got True."
    )

    # Substring trap: ONLY a `dispatched_backend_down` line — must False.
    _write_trace(env.bridge, [
        f"2026-08-25T11:30:00Z | {direction} | {HID} | "
        f"dispatched_backend_down | manual | backend was down",
    ])
    assert sched_helper(env.bridge, from_role, to_role, HID) is False, (
        "scheduler helper: `dispatched_backend_down` must not match. "
        "Got True."
    )
    assert wd_helper(env.bridge, from_role, to_role, HID) is False, (
        "watchdog helper: `dispatched_backend_down` must not match. "
        "Got True."
    )

    # Real match: a `dispatched` line — must return True.
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {direction} | {HID} | dispatched | "
        f"manual | Handoff {HID}-handoff.md dispatched to {to_role}",
    ])
    assert sched_helper(env.bridge, from_role, to_role, HID) is True, (
        "scheduler helper: a real `dispatched` line must return True. "
        "Got False."
    )
    assert wd_helper(env.bridge, from_role, to_role, HID) is True, (
        "watchdog helper: a real `dispatched` line must return True. "
        "Got False."
    )

    # Different handoff id — must NOT match (field-exact on id).
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {direction} | 998 | dispatched | "
        f"manual | some other handoff",
    ])
    assert sched_helper(env.bridge, from_role, to_role, HID) is False, (
        "scheduler helper: handoff id is field-exact — `998` must not "
        "match `999`. Got True."
    )


# ─── Test 2: D2 in scheduler — short-circuits handoff step ───────────────
def test_scheduler_d2_short_circuits_handoff_step(env, monkeypatch, tmp_path):
    """D2 — scheduler skips handoff steps when trace shows dispatched.

    For a rule_key="handoff" step (the dispatch step), if trace.log
    already shows a `dispatched` event for the (from_role, to_role,
    handoff_id), the scheduler MUST NOT nudge. The autonomous supervisor
    never signals for this step by design (the anti-loop rule); the old
    "did from_role signal?" predicate was permanently false → every
    tick looked like a stall → the repair re-dispatched the handoff.
    With D2: a real dispatch event proves the step is NOT stalled.
    """
    # Build a minimal Job (only flow_key and handoff_id are read by
    # _advance_chain).
    job = scheduler_mod.Job(flow_key=FLOW, handoff_id=HID)

    # Steps with rule_key="handoff" for step 0, callback for step 1.
    steps = [
        {"from_role": FROM_ROLE, "to_role": TO_ROLE,
         "rule_key": "handoff", "step_key": "supervisor-imple01",
         "deliverable_dir": "preferred_cloud_harness/handoffs",
         "deliverable_pattern": "{ID}-handoff.md"},
        {"from_role": TO_ROLE, "to_role": "review-claude-sonnet5",
         "rule_key": "callback", "step_key": "imple01-review01",
         "deliverable_dir": "preferred_cloud_harness/results",
         "deliverable_pattern": "{ID}-result.md"},
        {"from_role": "review-claude-sonnet5", "to_role": FROM_ROLE,
         "rule_key": "agent_delivery", "step_key": "review01-supervisor",
         "deliverable_dir": "preferred_cloud_harness/verdicts",
         "deliverable_pattern": "{ID}-verdict.md"},
    ]

    # Deliverable for step[0] exists (handoff file). Step[1] does not
    # (frontier sits AT step[0]).
    (env.bridge / "preferred_cloud_harness" / "handoffs").mkdir(
        parents=True, exist_ok=True)
    (env.bridge / "preferred_cloud_harness" / "handoffs" /
     f"{HID}-handoff.md").write_text(
         f"<handoff_id>{HID}</handoff_id>\n", encoding="utf-8")
    # Step[1] deliverable deliberately missing.

    # Trace shows the handoff was dispatched (the legitimate first dispatch).
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {DIRECTION} | {HID} | dispatched | "
        f"manual | Handoff {HID}-handoff.md dispatched to {TO_ROLE}",
    ])

    # Patch bridge_lib.load_flow_from_db and load_role_from_db (the
    # scheduler module imports them via `from bridge_lib import ...` at
    # module level, but also re-imports them inside the function — patch
    # both reference sites).
    monkeypatch.setattr("bridge_lib.load_flow_from_db",
                        lambda *a, **k: {"steps": steps})
    monkeypatch.setattr("scheduler.load_flow_from_db",
                        lambda *a, **k: {"steps": steps})
    monkeypatch.setattr("bridge_lib.load_role_from_db",
                        lambda *a, **k: {})
    monkeypatch.setattr("scheduler.load_role_from_db",
                        lambda *a, **k: {})

    # Capture every subprocess.run call (no real subprocess ever fires).
    subprocess_calls = []

    def _record_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("scheduler.subprocess.run", _record_subprocess)

    # Force the deliverable's mtime older than stall_minutes (default 12)
    # so the fast-path writer-idle block does not short-circuit on
    # "freshly written" — we want to reach the nudge firing point.
    import os as _os
    import time as _time
    handoff_file = (
        env.bridge / "preferred_cloud_harness" / "handoffs"
        / f"{HID}-handoff.md"
    )
    _os.utime(str(handoff_file),
              (_time.time() - 1800, _time.time() - 1800))

    sched = scheduler_mod.Scheduler(db_path=str(env.db))
    sched.nudge_state_path = tmp_path / "nudge_state.json"
    sched._step_deliverable_path = (
        lambda step, hid_, bridge_dir: str(
            env.bridge / step["deliverable_dir"]
            / step["deliverable_pattern"].replace("{ID}", hid_)
        )
    )
    monkeypatch.setattr(sched, "_pane_active", lambda *a, **k: False)
    # Bypass the consecutive-tick confirmation requirement (default 2).
    monkeypatch.setattr(sched, "_confirm_writer_idle",
                        lambda key: True)

    result = sched._advance_chain(job)

    assert result is False, (
        "D2 short-circuit must return False (no nudge, no further work)."
    )
    assert subprocess_calls == [], (
        "D2: scheduler invoked subprocess.run even though the handoff "
        "step already shows `dispatched` — this is the Mechanism A bug. "
        f"Calls: {subprocess_calls!r}"
    )


# ─── Test 3: D3 in scheduler — broker routing ────────────────────────────
def test_scheduler_d3_routes_through_broker(env, monkeypatch, tmp_path):
    """D3 — scheduler nudge repair MUST target bridge_broker enqueue.

    When the nudge DOES fire (a genuinely stalled non-handoff step), the
    repair subprocess argv MUST contain `bridge_broker.py enqueue ...
    --action signal-complete`. It MUST NOT contain `dispatch.py
    --signal-complete`. The run-025 D1 idempotency guard screens
    broker-routed repairs; direct subprocess repairs bypass it.
    """
    job = scheduler_mod.Job(flow_key=FLOW, handoff_id=HID)

    # Non-handoff step (rule_key="callback") — D2 must NOT short-circuit.
    steps = [
        {"from_role": FROM_ROLE, "to_role": TO_ROLE,
         "rule_key": "handoff", "step_key": "supervisor-imple01",
         "deliverable_dir": "preferred_cloud_harness/handoffs",
         "deliverable_pattern": "{ID}-handoff.md"},
        {"from_role": TO_ROLE, "to_role": "review-claude-sonnet5",
         "rule_key": "callback", "step_key": "imple01-review01",
         "deliverable_dir": "preferred_cloud_harness/results",
         "deliverable_pattern": "{ID}-result.md"},
        {"from_role": "review-claude-sonnet5", "to_role": FROM_ROLE,
         "rule_key": "agent_delivery", "step_key": "review01-supervisor",
         "deliverable_dir": "preferred_cloud_harness/verdicts",
         "deliverable_pattern": "{ID}-verdict.md"},
    ]

    # Both step[0] and step[1] deliverables exist; step[1] is the frontier.
    (env.bridge / "preferred_cloud_harness" / "handoffs").mkdir(
        parents=True, exist_ok=True)
    (env.bridge / "preferred_cloud_harness" / "handoffs" /
     f"{HID}-handoff.md").write_text(
         f"<handoff_id>{HID}</handoff_id>\n", encoding="utf-8")
    (env.bridge / "preferred_cloud_harness" / "results").mkdir(
        parents=True, exist_ok=True)
    (env.bridge / "preferred_cloud_harness" / "results" /
     f"{HID}-result.md").write_text("result\n", encoding="utf-8")
    # Step[2] deliverable deliberately missing.

    # Trace empty (no recent delivery) — the heuristic proceeds.
    _write_trace(env.bridge, [])

    monkeypatch.setattr("bridge_lib.load_flow_from_db",
                        lambda *a, **k: {"steps": steps})
    monkeypatch.setattr("scheduler.load_flow_from_db",
                        lambda *a, **k: {"steps": steps})
    monkeypatch.setattr("bridge_lib.load_role_from_db",
                        lambda *a, **k: {})
    monkeypatch.setattr("scheduler.load_role_from_db",
                        lambda *a, **k: {})

    subprocess_calls = []

    def _record_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("scheduler.subprocess.run", _record_subprocess)

    sched = scheduler_mod.Scheduler(db_path=str(env.db))
    sched.nudge_state_path = tmp_path / "nudge_state.json"
    sched._step_deliverable_path = (
        lambda step, hid_, bridge_dir: str(
            env.bridge / step["deliverable_dir"]
            / step["deliverable_pattern"].replace("{ID}", hid_)
        )
    )
    monkeypatch.setattr(sched, "_pane_active", lambda *a, **k: False)
    # Bypass the age/idle-confirmations slow path — pretend the deliverable
    # is older than stall_minutes AND the writer is idle.
    import os as _os
    deliverable_path = (
        env.bridge / "preferred_cloud_harness" / "results" /
        f"{HID}-result.md"
    )
    # Force mtime to be older than stall_minutes (default 12).
    import time as _time
    _os.utime(str(deliverable_path),
              (_time.time() - 1800, _time.time() - 1800))

    sched._advance_chain(job)

    # The repair must have been enqueued.
    assert len(subprocess_calls) >= 1, (
        "D3: scheduler did not invoke subprocess.run at all — the nudge "
        "path did not fire. The test setup is supposed to make it fire."
    )

    # The argv of the LAST subprocess.run call is what we inspect.
    last_call_args = subprocess_calls[-1][0]
    argv = list(last_call_args[0]) if last_call_args else []
    argv_str = " ".join(str(a) for a in argv)

    assert "bridge_broker.py" in argv_str, (
        "D3: scheduler repair must invoke bridge_broker.py, got: "
        f"{argv_str!r}"
    )
    assert "enqueue" in argv, (
        "D3: scheduler repair argv must include the `enqueue` subcommand, "
        f"got: {argv!r}"
    )
    assert "signal-complete" in argv, (
        "D3: scheduler repair argv must include `--action signal-complete`, "
        f"got: {argv!r}"
    )
    assert "dispatch.py" not in argv_str, (
        "D3: scheduler repair must NOT invoke dispatch.py directly — "
        "that bypasses the run-025 D1 idempotency guard. Got: "
        f"{argv_str!r}"
    )


# ─── Test 4: D2 in watchdog — short-circuits handoff step ────────────────
def test_watchdog_d2_short_circuits_handoff_step(env, monkeypatch):
    """D2 — watchdog skips handoff steps when trace shows dispatched.

    For a rule_key="handoff" step, if trace.log already shows a
    `dispatched` event, `check_once_generic` MUST NOT nudge and MUST NOT
    escalate. The watchdog's load_flow_steps now returns rule_key.
    """
    steps = [
        {"from_role": FROM_ROLE, "to_role": TO_ROLE,
         "rule_key": "handoff", "step_key": "supervisor-imple01",
         "dir": str(env.bridge / "preferred_cloud_harness/handoffs"),
         "pattern": "{ID}-handoff.md"},
        {"from_role": TO_ROLE, "to_role": "review-claude-sonnet5",
         "rule_key": "callback", "step_key": "imple01-review01",
         "dir": str(env.bridge / "preferred_cloud_harness/results"),
         "pattern": "{ID}-result.md"},
        {"from_role": "review-claude-sonnet5", "to_role": FROM_ROLE,
         "rule_key": "agent_delivery", "step_key": "review01-supervisor",
         "dir": str(env.bridge / "preferred_cloud_harness/verdicts"),
         "pattern": "{ID}-verdict.md"},
    ]
    sessions = {FROM_ROLE: FROM_ROLE, TO_ROLE: TO_ROLE,
                "review-claude-sonnet5": "review-claude-sonnet5"}

    # Trace shows the handoff was dispatched.
    _write_trace(env.bridge, [
        f"2026-08-25T11:00:00Z | {DIRECTION} | {HID} | dispatched | "
        f"manual | Handoff {HID}-handoff.md dispatched to {TO_ROLE}",
    ])

    # Deliverables exist for steps 0 and 1, missing for step 2 → step 1
    # would normally be a frontier. But the handoff step (step 0) is
    # the one the D2 fix targets: it must be skipped.
    (env.bridge / "preferred_cloud_harness" / "handoffs").mkdir(
        parents=True, exist_ok=True)
    (env.bridge / "preferred_cloud_harness" / "handoffs" /
     f"{HID}-handoff.md").write_text(
         f"<handoff_id>{HID}</handoff_id>\n", encoding="utf-8")

    # Patch load_remote_targets, pane_active, save_state, nudge, escalate.
    monkeypatch.setattr(watchdog_mod, "load_remote_targets", lambda: {})
    monkeypatch.setattr(watchdog_mod, "pane_active", lambda s: False)
    monkeypatch.setattr(watchdog_mod, "save_state", lambda s: None)
    # sample_ollama runs subprocess.run(["ollama", "ps"]) at the top of
    # check_once_generic — irrelevant to the D2 invariant. Mock it so
    # only the dispatch-related subprocess calls appear.
    monkeypatch.setattr(watchdog_mod, "sample_ollama", lambda: None)

    subprocess_calls = []

    def _record_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(watchdog_mod.subprocess, "run", _record_subprocess)

    state = {}
    # NOT dry_run — the watchdog must actually try the nudge path so the
    # D2 short-circuit has a chance to skip the handoff step.
    result = watchdog_mod.check_once_generic(
        FLOW, steps, sessions, HID, 12, state, dry_run=False)

    dispatch_calls = [c for c in subprocess_calls
                      if "dispatch.py" in " ".join(str(a) for a in c[0][0])
                      or "bridge_broker.py" in " ".join(str(a) for a in c[0][0])]
    assert dispatch_calls == [], (
        "D2: watchdog invoked the dispatch subprocess even though the "
        "handoff step already shows `dispatched`. Calls: "
        f"{dispatch_calls!r}"
    )
    assert result != "nudged", (
        f"D2: watchdog returned {result!r} — must NOT return `nudged` "
        "when the handoff step is already dispatched."
    )


# ─── Test 5: D3 in watchdog — broker routing ─────────────────────────────
def test_watchdog_d3_routes_through_broker(env, monkeypatch):
    """D3 — watchdog nudge() MUST invoke bridge_broker enqueue, NOT
    dispatch.py --signal-complete. The `force` parameter is accepted for
    signature compatibility but the broker has no --force flag.
    """
    subprocess_calls = []

    def _record_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(watchdog_mod.subprocess, "run", _record_subprocess)

    watchdog_mod.nudge(FROM_ROLE, HID, flow_key=FLOW)

    assert len(subprocess_calls) >= 1, (
        "D3: watchdog.nudge() did not invoke subprocess.run."
    )

    last_call_args = subprocess_calls[-1][0]
    argv = list(last_call_args[0]) if last_call_args else []
    argv_str = " ".join(str(a) for a in argv)

    assert "bridge_broker.py" in argv_str, (
        "D3: watchdog nudge must invoke bridge_broker.py, got: "
        f"{argv_str!r}"
    )
    assert "enqueue" in argv, (
        "D3: watchdog nudge argv must include `enqueue`, got: "
        f"{argv!r}"
    )
    assert "signal-complete" in argv, (
        "D3: watchdog nudge argv must include `--action signal-complete`, "
        f"got: {argv!r}"
    )
    assert "dispatch.py" not in argv_str, (
        "D3: watchdog nudge must NOT invoke dispatch.py directly. Got: "
        f"{argv_str!r}"
    )
    assert "--force" not in argv, (
        "D3: watchdog nudge argv must NOT include `--force` — the broker "
        "has no `--force` flag (run-025 D1 idempotency guard is the "
        f"screen). Got: {argv!r}"
    )
