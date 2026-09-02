"""D1 guard tests for bridge_broker.cmd_enqueue (Run 025 handoff 094).

The defect (GOAL.md §1 D1): cmd_enqueue's idempotency guard counted a
gate-REJECTED delivery as "already delivered", silently swallowing every
re-signal after a gate rejection. D1 makes the guard read the bridge dir
trace.log and treat a rejected prior delivery as NOT delivered
(last-relevant-event-wins).

Hermetic isolation contract (governance §8 + GOAL.md §5 disclosed
incident): ALL THREE of temp DB + temp bridge dir + temp trace must be
present in every test — a DB-only fixture once wrote parser-inert retry
lines into the LIVE trace.

The three tests in this file pin D1 only:
  1. gate-rejected prior delivery -> re-enqueue is NOT suppressed
     (TG1 contract — test name MUST contain the token "rejected").
  2. delivered prior delivery -> still suppresses (regression pin for
     the run-019 double-signal suppression lesson).
  3. no trace evidence -> suppress (pre-025 behavior, pinned).

D2 (transient-session retry) and D3 (end-report re-closure) tests are
handoff 095 — do NOT write them here.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Make the bridgeV002 package importable so we can import bridge_broker directly.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))

import bridge_broker  # noqa: E402


# Trace-line timestamp prefix (UTC, mirror dispatch.py:log()'s format).
_TS_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── fixtures ──────────────────────────────────────────────


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """An isolated SQLite database with the dispatch queue schema pre-applied.

    Mirrors the tmp_db fixture in tests/test_bridge_broker.py — the broker's
    self-bootstrap schema lives at bridge_broker._SCHEMA_DISPATCH_SQL. We
    run only the dispatch schema here (the resilience tests do not exercise
    the materialize path).
    """
    db_path = tmp_path / "test_dpmtf_resilience.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    return str(db_path)


@pytest.fixture()
def tmp_bridge_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated bridge_dir at tmp_path (NO trace.log yet — tests write
    their own scenario trace)."""
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(bridge_dir))
    return bridge_dir


def _write_trace_line(bridge_dir: Path, direction: str, handoff_id: str,
                      event: str, source: str = "test",
                      message: str = "fixture") -> None:
    """Append a single trace line to bridge_dir/trace.log in dispatch.log format."""
    trace_log = bridge_dir / "trace.log"
    entry = (
        f"{_TS_UTC} | {direction} | {handoff_id} | {event} | "
        f"{source} | {message}\n"
    )
    with open(trace_log, "a", encoding="utf-8") as f:
        f.write(entry)


def _seed_completed_row(db_path: str, flow: str, from_role: str,
                        to_role: str, handoff_id: str,
                        action: str = "signal-complete") -> None:
    """Insert a 'completed' dispatch row for the test's enqueue args.

    Mirrors tests/test_bridge_broker.py:seed_idempotency_setup, but inlined
    here so the fixture is hermetic and does not need the materialize
    schema (resilience tests only need the dispatch schema).
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        (flow, from_role, to_role, handoff_id, action),
    )
    conn.commit()
    conn.close()


def _row_count(db_path: str, handoff_id: str | None = None) -> int:
    """Count rows in bridge_dispatch_queue (optionally filtered to one handoff)."""
    conn = sqlite3.connect(db_path)
    try:
        if handoff_id is None:
            row = conn.execute(
                "SELECT COUNT(*) FROM bridge_dispatch_queue"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM bridge_dispatch_queue "
                "WHERE handoff_id = ?",
                (handoff_id,),
            ).fetchone()
    finally:
        conn.close()
    return row[0]


# ── Test 1: gate-rejected prior delivery → re-enqueue NOT suppressed ──


def test_gate_rejected_row_does_not_suppress_re_enqueue(
    tmp_db: str, tmp_bridge_dir: Path,
) -> None:
    """D1 contract (TG1): when the LAST relevant trace event is a gate
    rejection for the sender, cmd_enqueue MUST insert a NEW pending row
    instead of silently suppressing the re-signal.

    Scenario:
      - A completed row for (flow, from=imple-codex-minimaxM3,
        to=review-claude-sonnet5, id=042, action=signal-complete) exists.
      - The trace holds a 'gate_rejected' line for that sender+handoff
        as the LAST relevant event.
      - A re-enqueue with the SAME args MUST insert a new pending row
        (count goes 1 -> 2).

    Test name contains the token "rejected" so TG1's `-k "rejected"`
    filter catches it.
    """
    _seed_completed_row(
        tmp_db,
        flow="preferred_cloud_harness",
        from_role="imple-codex-minimaxM3",
        to_role="review-claude-sonnet5",
        handoff_id="042",
        action="signal-complete",
    )
    # The trace's LAST relevant event is the gate_rejected for the SENDER
    # (parts[1].split('->')[0] == imple-codex-minimaxM3,
    #  parts[2] == '042', parts[3] == 'gate_rejected').
    # Write an earlier delivery line first so the test proves LAST-wins
    # (a delivery BEFORE a rejection must NOT suppress a re-enqueue; only
    # the LAST relevant event determines suppression).
    _write_trace_line(
        tmp_bridge_dir,
        direction="imple-codex-minimaxM3->review-claude-sonnet5",
        handoff_id="042",
        event="dispatched",
        message="earlier delivery, superseded by rejection",
    )
    _write_trace_line(
        tmp_bridge_dir,
        direction="imple-codex-minimaxM3->review-claude-sonnet5",
        handoff_id="042",
        event="gate_rejected",
        message="the rejection that must let the re-signal through",
    )

    assert _row_count(tmp_db, "042") == 1  # sanity: just the completed row

    # Re-enqueue with the SAME args — must NOT be suppressed.
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "42",
        "--action", "signal-complete",
    ])
    assert rc == 0, f"enqueue must succeed; got rc={rc}"

    # A new pending row was inserted (1 -> 2). The original completed row
    # is still there (regression pin: never delete prior rows).
    assert _row_count(tmp_db, "042") == 2, (
        "gate-rejected prior delivery MUST NOT suppress the re-enqueue; "
        "row count must go 1 -> 2"
    )

    # And the new row is 'pending' (not silently dropped).
    conn = sqlite3.connect(tmp_db)
    try:
        new_row = conn.execute(
            "SELECT status FROM bridge_dispatch_queue "
            "WHERE handoff_id = '042' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert new_row[0] == "pending", (
        f"new row must be 'pending'; got status={new_row[0]!r}"
    )


# ── Test 2: delivered prior delivery → still suppresses (regression pin) ──


def test_delivered_row_still_suppresses_re_enqueue(
    tmp_db: str, tmp_bridge_dir: Path,
) -> None:
    """Regression pin (run-019 lesson): a genuinely DELIVERED duplicate
    is still suppressed. This pins the legitimate purpose of the
    idempotency guard (double-signal suppression).

    Scenario:
      - A completed row exists.
      - The trace holds a 'signal_complete' delivery line as the LAST
        relevant event.
      - A re-enqueue with the SAME args MUST be suppressed (count stays 1).

    Plus: a DELIVERY line AFTER a REJECTION line still suppresses
    (last-relevant-event-wins: a delivery after a rejection is a
    delivered duplicate, so it suppresses again).
    """
    _seed_completed_row(
        tmp_db,
        flow="preferred_cloud_harness",
        from_role="imple-codex-minimaxM3",
        to_role="review-claude-sonnet5",
        handoff_id="042",
        action="signal-complete",
    )
    # Plain delivery case — single 'signal_complete' line.
    _write_trace_line(
        tmp_bridge_dir,
        direction="imple-codex-minimaxM3->review-claude-sonnet5",
        handoff_id="042",
        event="signal_complete",
        message="the genuine delivery (run-019 pin)",
    )

    assert _row_count(tmp_db, "042") == 1

    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "42",
        "--action", "signal-complete",
    ])
    assert rc == 0
    assert _row_count(tmp_db, "042") == 1, (
        "delivered prior delivery MUST still suppress; "
        "row count must stay at 1 (run-019 regression pin)"
    )


def test_delivery_after_rejection_still_suppresses(
    tmp_db: str, tmp_bridge_dir: Path,
) -> None:
    """Last-relevant-event-wins: a DELIVERY line written AFTER a
    rejection line still suppresses (the late delivery is the
    authoritative event; the rejection is now stale).

    This pins the asymmetry explicitly: rejection-then-delivery is a
    delivered duplicate, but delivery-then-rejection (test 1) is a
    fresh rejected duplicate that must let the re-enqueue through.
    """
    _seed_completed_row(
        tmp_db,
        flow="preferred_cloud_harness",
        from_role="imple-codex-minimaxM3",
        to_role="review-claude-sonnet5",
        handoff_id="042",
        action="signal-complete",
    )
    _write_trace_line(
        tmp_bridge_dir,
        direction="imple-codex-minimaxM3->review-claude-sonnet5",
        handoff_id="042",
        event="gate_rejected",
        message="earlier rejection (now stale)",
    )
    _write_trace_line(
        tmp_bridge_dir,
        direction="imple-codex-minimaxM3->review-claude-sonnet5",
        handoff_id="042",
        event="signal_complete",
        message="later delivery — the authoritative event",
    )

    assert _row_count(tmp_db, "042") == 1

    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "42",
        "--action", "signal-complete",
    ])
    assert rc == 0
    assert _row_count(tmp_db, "042") == 1, (
        "delivery AFTER rejection (last-relevant-event-wins) MUST suppress; "
        "row count must stay at 1"
    )


# ── Test 3: no trace evidence → suppress (pre-025 behavior pinned) ──


def test_no_trace_evidence_suppresses(
    tmp_db: str, tmp_bridge_dir: Path,
) -> None:
    """Pre-025 behavior pinned: when the bridge dir has NO relevant
    trace evidence (no trace.log at all, or trace.log with no line
    for this sender+handoff), the existing completed row stands and
    the re-enqueue is suppressed.

    This is the safe default — the row evidence is treated as
    authoritative when the trace is silent. A noisy re-signal under
    that regime stays suppressed.
    """
    _seed_completed_row(
        tmp_db,
        flow="preferred_cloud_harness",
        from_role="imple-codex-minimaxM3",
        to_role="review-claude-sonnet5",
        handoff_id="042",
        action="signal-complete",
    )
    # No trace line written — no trace.log at all.
    assert not (tmp_bridge_dir / "trace.log").exists()

    assert _row_count(tmp_db, "042") == 1

    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "42",
        "--action", "signal-complete",
    ])
    assert rc == 0
    assert _row_count(tmp_db, "042") == 1, (
        "no trace evidence MUST still suppress (pre-025 behavior, pinned); "
        "row count must stay at 1"
    )


def test_trace_with_unrelated_lines_suppresses(
    tmp_db: str, tmp_bridge_dir: Path,
) -> None:
    """Sibling case for test_no_trace_evidence_suppresses: trace.log
    EXISTS but contains NO line for this sender+handoff. The
    pre-025 default (row evidence stands) still applies.
    """
    _seed_completed_row(
        tmp_db,
        flow="preferred_cloud_harness",
        from_role="imple-codex-minimaxM3",
        to_role="review-claude-sonnet5",
        handoff_id="042",
        action="signal-complete",
    )
    # Unrelated trace line — different sender, different handoff.
    _write_trace_line(
        tmp_bridge_dir,
        direction="review-claude-sonnet5->super-deep-deep4",
        handoff_id="099",
        event="signal_complete",
        message="a different transition entirely",
    )

    assert _row_count(tmp_db, "042") == 1

    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "42",
        "--action", "signal-complete",
    ])
    assert rc == 0
    assert _row_count(tmp_db, "042") == 1, (
        "unrelated trace lines do NOT constitute evidence for THIS "
        "sender+handoff; row count must stay at 1"
    )


# ══════════════════════════════════════════════════════════════════════════
# Run 025 Handoff 095 — D2 + D3 + their tests
#
# D2 — bounded transient-session retry.
# D3 — end-report enqueue guard keys on destination absence.
#
# Hermetic isolation contract (governance §8 + GOAL.md §5 disclosed incident):
# ALL THREE of temp DB + temp bridge dir + temp trace must be present in
# every test. Live trace.log / live queues / live DB are NEVER touched.
#
# The D2 tests pin (Run 025 §4 TG2):
#   1. retry-then-succeed.
#   2. retry exhausts the bound (4 attempts, 3 trace lines, backoff 30/60/120).
#   3. non-transient failure is NOT retried.
#
# The D3 tests pin (Run 025 §4 TG3):
#   4. re-materialize ALLOWED when the destination file is absent.
#   5. re-materialize REFUSED when the destination file is present.
#
# The existing 5 D1 tests above stay UNCHANGED — these are APPENDS only.


# ─── fixtures for D2 / D3 (three-way isolation) ─────────────────────────


@pytest.fixture()
def tmp_dispatch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Hermetic dispatch DB — same shape as tmp_db but kept as a separate
    fixture so D2/D3 tests don't accidentally share state with D1 tests."""
    db_path = tmp_path / "test_dpmtf_resilience_d23.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    return str(db_path)


@pytest.fixture()
def tmp_bridge_dir_for_d23(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Hermetic bridge_dir — different name so D2/D3 tests are isolated
    from D1 tests' tmp_bridge_dir fixture even at module scope."""
    bridge_dir = tmp_path / "bridge_d23"
    bridge_dir.mkdir()
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(bridge_dir))
    return bridge_dir


def _seed_pending_dispatch_row(
    db_path: str, handoff_id: str = "042", action: str = "signal-complete",
    flow: str = "preferred_cloud_harness",
    from_role: str = "imple-codex-minimaxM3",
    to_role: str = "review-claude-sonnet5",
) -> None:
    """Insert a pending dispatch row for _process_one to claim."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        (flow, from_role, to_role, handoff_id, action),
    )
    conn.commit()
    conn.close()


def _row_status(db_path: str, handoff_id: str) -> str:
    """Return the status of the test's row (latest by id)."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM bridge_dispatch_queue WHERE handoff_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (handoff_id,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else "<missing>"


def _row_error_msg(db_path: str, handoff_id: str) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT error_msg FROM bridge_dispatch_queue WHERE handoff_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (handoff_id,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _count_retry_trace_lines(bridge_dir: Path) -> int:
    """Count lines in bridge_dir/trace.log that start with `delivery_retry | `."""
    trace_log = bridge_dir / "trace.log"
    if not trace_log.exists():
        return 0
    n = 0
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("delivery_retry | "):
                n += 1
    return n


def _read_retry_backoffs(bridge_dir: Path) -> list[int]:
    """Return the backoffs (in seconds) for each `delivery_retry` line, in order."""
    trace_log = bridge_dir / "trace.log"
    if not trace_log.exists():
        return []
    out: list[int] = []
    with open(trace_log, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("delivery_retry | "):
                parts = [p.strip() for p in line.split("|")]
                bp = parts[6] if len(parts) > 6 else ""
                if bp.startswith("backoff ") and bp.endswith("s"):
                    out.append(int(bp[len("backoff "):-1]))
    return out


# ─── D2 tests (TG2 — `-k "retry"`) ──────────────────────────────────────


def test_d2_retry_then_succeeds(
    tmp_dispatch_db: str, tmp_bridge_dir_for_d23: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2 contract: a transient 'is not running' error is retried with
    bounded backoff. If a retry finally succeeds, the row is marked
    'completed' and `_run_dispatch` was called exactly N+1 times (N
    transient failures + 1 success)."""
    _seed_pending_dispatch_row(tmp_dispatch_db)

    monkeypatch.setattr(bridge_broker, "_RETRY_SLEEP", lambda _s: None)

    call_count = {"n": 0}

    def _flaky_dispatch(_row):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return (1, "ERROR: target session 'review-claude-sonnet5' is not running\n")
        return (0, "")

    monkeypatch.setattr(bridge_broker, "_run_dispatch", _flaky_dispatch)

    rc = bridge_broker.main(["process-once"])
    assert rc == 0, f"process-once must succeed; got rc={rc}"

    assert call_count["n"] == 3, (
        f"retry-then-succeed must invoke _run_dispatch 3 times; "
        f"got {call_count['n']}"
    )
    assert _row_status(tmp_dispatch_db, "042") == "completed", (
        "transient failure followed by success must mark the row 'completed'; "
        "the retry loop must NOT mark it 'failed' on the first transient attempt"
    )

    assert _count_retry_trace_lines(tmp_bridge_dir_for_d23) == 2, (
        "two transient failures must produce two delivery_retry trace lines"
    )
    backoffs = _read_retry_backoffs(tmp_bridge_dir_for_d23)
    assert backoffs == [30, 60], (
        f"backoffs must be 30s, 60s (third retry never fires because the "
        f"third attempt succeeded); got {backoffs!r}"
    )


def test_d2_retry_exhausts_bound(
    tmp_dispatch_db: str, tmp_bridge_dir_for_d23: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2 contract: when every attempt returns 'is not running', the
    retry loop exhausts the bound and marks the row 'failed' with an
    error_msg that names BOTH the attempt count and the backoff."""
    _seed_pending_dispatch_row(tmp_dispatch_db)

    sleep_calls: list[int] = []

    def _fake_sleep(s: int) -> None:
        sleep_calls.append(s)

    call_count = {"n": 0}

    def _always_transient(_row):
        call_count["n"] += 1
        return (1, "ERROR: target session 'review-claude-sonnet5' is not running\n")

    monkeypatch.setattr(bridge_broker, "_RETRY_SLEEP", _fake_sleep)
    monkeypatch.setattr(bridge_broker, "_run_dispatch", _always_transient)

    rc = bridge_broker.main(["process-once"])
    assert rc == 0

    assert call_count["n"] == 4, (
        f"retry-exhausts-bound must invoke _run_dispatch exactly 4 times "
        f"(1 initial + 3 retries); got {call_count['n']}"
    )
    assert sleep_calls == [30, 60, 120], (
        f"_RETRY_SLEEP must be called 3 times with 30, 60, 120 (in order); "
        f"got {sleep_calls!r}"
    )
    assert _count_retry_trace_lines(tmp_bridge_dir_for_d23) == 3, (
        "exactly 3 delivery_retry trace lines must be written when the bound "
        "is exhausted"
    )
    backoffs = _read_retry_backoffs(tmp_bridge_dir_for_d23)
    assert backoffs == [30, 60, 120], (
        f"trace-line backoffs must be 30s, 60s, 120s in order; got {backoffs!r}"
    )

    assert _row_status(tmp_dispatch_db, "042") == "failed", (
        "exhausted retry bound must mark the row 'failed'"
    )
    err = _row_error_msg(tmp_dispatch_db, "042") or ""
    assert "4 attempts" in err, (
        f"error_msg MUST name the attempt count; got {err!r}"
    )
    assert "30s/60s/120s" in err, (
        f"error_msg MUST name the backoff (30s/60s/120s); got {err!r}"
    )


def test_d2_non_transient_no_retry(
    tmp_dispatch_db: str, tmp_bridge_dir_for_d23: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2 contract: a NON-transient error (does NOT contain
    'is not running') is marked failed immediately. _run_dispatch is
    called exactly once; no _RETRY_SLEEP calls; no retry trace lines."""
    _seed_pending_dispatch_row(tmp_dispatch_db)

    sleep_calls: list[int] = []

    def _fake_sleep(s: int) -> None:
        sleep_calls.append(s)

    call_count = {"n": 0}

    def _non_transient(_row):
        call_count["n"] += 1
        # A non-transient error — no `is not running` substring.
        return (1, "ERROR: dispatch subprocess crashed\n")

    monkeypatch.setattr(bridge_broker, "_RETRY_SLEEP", _fake_sleep)
    monkeypatch.setattr(bridge_broker, "_run_dispatch", _non_transient)

    rc = bridge_broker.main(["process-once"])
    assert rc == 0

    assert call_count["n"] == 1, (
        f"non-transient failure must NOT be retried; _run_dispatch must be "
        f"called exactly once; got {call_count['n']}"
    )
    assert sleep_calls == [], (
        f"non-transient failure must NOT trigger _RETRY_SLEEP; got {sleep_calls!r}"
    )
    assert _count_retry_trace_lines(tmp_bridge_dir_for_d23) == 0, (
        "non-transient failure must NOT write any delivery_retry trace lines"
    )
    assert _row_status(tmp_dispatch_db, "042") == "failed"
    err = _row_error_msg(tmp_dispatch_db, "042") or ""
    assert "crashed" in err, (
        f"non-transient error_msg must be the raw dispatch error (no retry "
        f"wording); got {err!r}"
    )


# ─── D3 tests (TG3 — `-k "end_report"`) ─────────────────────────────────


@pytest.fixture()
def tmp_materialize_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> str:
    """Hermetic materialize-DB fixture: db_path, with BOTH dispatch and
    materialize schemas applied (D3 exercises the materialize queue).

    Also creates the bridge_flows + bridge_roles + bridge_flow_steps
    minimal tables (these are normally created by migrations; we
    inline the minimal subset the broker needs for end-report flow
    validation so the test stays self-contained).
    """
    db_path = tmp_path / "test_dpmtf_materialize.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bridge_flows (
            flow_key TEXT PRIMARY KEY,
            target_project_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS bridge_roles (
            role_key TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS bridge_flow_steps (
            flow_key TEXT NOT NULL,
            from_role TEXT NOT NULL,
            to_role TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    return str(db_path)


def _seed_completed_materialize_row(
    db_path: str, flow: str, run_id: int, artifact_type: str = "end-report",
) -> None:
    """Insert a 'completed' materialize row to simulate the prior end-report
    closure row that the OLD code used to suppress a re-closure."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bridge_materialize_queue "
        "(flow_key, run_id, handoff_id, role_key, artifact_type, "
        "content, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'completed')",
        (flow, run_id, None, None, artifact_type,
         "# prior end-report placeholder\n"),
    )
    conn.commit()
    conn.close()


def _count_materialize_rows(
    db_path: str, flow: str, run_id: int, artifact_type: str,
) -> int:
    """Count materialize_queue rows for (flow, run_id, artifact_type)."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM bridge_materialize_queue "
            "WHERE flow_key = ? AND run_id = ? AND artifact_type = ?",
            (flow, run_id, artifact_type),
        ).fetchone()
    finally:
        conn.close()
    return row[0]


def test_d3_end_report_rematerialize_allowed_when_dest_absent(
    tmp_materialize_db: str, tmp_bridge_dir_for_d23: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D3 contract: when runs/{NNN}/END-REPORT.md is ABSENT, the
    end-report enqueue MUST proceed (a new pending row is created)
    — even if a prior 'completed' end-report row exists for the run."""
    _seed_completed_materialize_row(
        tmp_materialize_db, flow="preferred_cloud_harness", run_id=42,
    )
    runs_dir = (
        tmp_bridge_dir_for_d23 / "preferred_cloud_harness" / "runs"
    )
    assert not (runs_dir / "042" / "END-REPORT.md").exists()
    assert not (runs_dir / "042").exists(), (
        "this test pins destination ABSENCE: the run directory itself "
        "must not exist either"
    )

    conn = sqlite3.connect(tmp_materialize_db)
    try:
        conn.execute(
            "INSERT INTO bridge_flows (flow_key, target_project_path, "
            "created_at) VALUES (?, ?, datetime('now'))",
            ("preferred_cloud_harness", "/tmp/d3-test-target"),
        )
        conn.commit()
    finally:
        conn.close()

    before = _count_materialize_rows(
        tmp_materialize_db, "preferred_cloud_harness", 42, "end-report",
    )
    assert before == 1, (
        f"sanity: one prior completed row exists before enqueue; got {before}"
    )

    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "end-report",
        "--run-id", "42",
        "--content", "# re-closure\n\n**Status:** SUCCESS — CLOSED\n\n## Outcome\n- re-closure\n",
    ])
    assert rc == 0, f"materialize must succeed; got rc={rc}"

    after = _count_materialize_rows(
        tmp_materialize_db, "preferred_cloud_harness", 42, "end-report",
    )
    assert after == 2, (
        f"destination-absent end-report enqueue MUST insert a new pending row "
        f"(1 -> 2) even when a prior 'completed' row exists; got {after}"
    )


def test_d3_end_report_rematerialize_refused_when_dest_present(
    tmp_materialize_db: str, tmp_bridge_dir_for_d23: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D3 contract: when runs/{NNN}/END-REPORT.md IS PRESENT, the
    end-report enqueue MUST be refused (no new pending row) — the
    one-shot live-report protection stands."""
    end_report_path = (
        tmp_bridge_dir_for_d23
        / "preferred_cloud_harness"
        / "runs"
        / "042"
        / "END-REPORT.md"
    )
    end_report_path.parent.mkdir(parents=True, exist_ok=True)
    end_report_path.write_text("# existing end-report\n", encoding="utf-8")

    conn = sqlite3.connect(tmp_materialize_db)
    try:
        conn.execute(
            "INSERT INTO bridge_flows (flow_key, target_project_path, "
            "created_at) VALUES (?, ?, datetime('now'))",
            ("preferred_cloud_harness", "/tmp/d3-test-target"),
        )
        conn.commit()
    finally:
        conn.close()

    before = _count_materialize_rows(
        tmp_materialize_db, "preferred_cloud_harness", 42, "end-report",
    )
    assert before == 0, (
        f"sanity: no prior end-report rows; got {before}"
    )

    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "end-report",
        "--run-id", "42",
        "--content", "# attempted re-closure\n\n**Status:** SUCCESS — CLOSED\n\n## Outcome\n- attempted re-closure\n",
    ])
    assert rc == 0, (
        f"materialize silently returns 0 when refused (matching the old "
        f"idempotent-skip convention); got rc={rc}"
    )

    after = _count_materialize_rows(
        tmp_materialize_db, "preferred_cloud_harness", 42, "end-report",
    )
    assert after == 0, (
        f"destination-present end-report enqueue MUST be refused (no new "
        f"pending row); got {after}"
    )
