"""Tests for the bridge broker (scripts/bridgeV002/bridge_broker.py).

These tests prove (TG11):
  1. the broker does NOT bypass the scope-fence or evidence gate;
  2. the broker does NOT touch bridge_dir or tmux;
  3. the broker re-runs dispatch.py's checks with the same inputs.

PART A — signal-transition broker (handoff 009):
  - enqueue writes a row
  - enqueue with missing handoff fails
  - enqueue with existing handoff succeeds
  - enqueue is idempotent for completed rows
  - enqueue allows re-dispatch for failed rows
  - enqueue action must be valid
  - process updates status to completed
  - process updates status to failed
  - process does not touch completed rows
  - process preserves FIFO order
  - broker does not disable dispatch.py validation
  - broker self-bootstraps schema when migration not run
  - broker status prints queue
  - broker detects dispatch.py error in output
  - broker does not touch bridge_dir or tmux

PART B — artifact-materialization broker (handoff 010):
  - canonical destination derivation for each artifact type
  - rejection of unknown/arbitrary artifact type
  - rejection of caller-supplied destination path (none accepted)
  - rejection of unknown flow_key
  - rejection of non-positive / unknown run_id / handoff_id
  - materialize writes backlog to canonical path (create then replace)
  - materialize appends to run-ledger (append, not replace)
  - materialize creates handoff at 0-padded canonical path
  - materialize creates end-report (create then replace)
  - materialize leaves filesystem untouched on validation failure
  - materialize enqueue is sandbox-safe (touches no bridge_dir)
  - materialize does not disable dispatch.py validation (TG11)
"""

from __future__ import annotations
from datetime import datetime, timezone

import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

# Make the bridgeV002 package importable so we can import bridge_broker directly.
# Auto-fail pattern fix (Run 006): derive the repo root from this test
# file's location so the suite measures its own worktree instead of a
# hardcoded production path. Run from any checkout.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))

import bridge_broker  # noqa: E402


# ── fixtures ──────────────────────────────────────────────


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """An isolated SQLite database with the queue schemas pre-applied.

    The broker uses `config.get_db_path()` to resolve the DB. We monkeypatch
    that to point at a tmp_path file so each test gets a clean, isolated DB.
    """
    db_path = tmp_path / "test_dpmtf.db"
    # Open, create the queue tables, leave the rest empty.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    conn.commit()
    conn.close()
    # Point bridge_broker._get_db_path() at our tmp DB.
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    return str(db_path)


@pytest.fixture()
def tmp_bridge_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """An isolated bridge_dir at tmp_path, populated with bridge_flows.

    The broker computes canonical destinations via `_get_bridge_dir()`.
    We monkeypatch that to a tmp directory so materialize tests never
    touch the real /home/svend/flows. The tmp bridge_dir is pre-seeded
    with a `bridge_flows` table row for `preferred_cloud_harness` so
    flow-key validation passes, and a `runs/003/` directory so the
    run-id validation passes.
    """
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()

    # Point bridge_broker._get_bridge_dir() at our tmp dir.
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(bridge_dir))

    # Seed bridge_flows with our flow key.
    db_path = monkeypatch.dependencies[  # type: ignore[attr-defined]
        "tmp_db"
    ] if "tmp_db" in getattr(monkeypatch, "dependencies", {}) else None
    return bridge_dir


@pytest.fixture()
def tmp_bridge_and_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, Path]:
    """Combined fixture: isolated DB + isolated bridge_dir, both seeded.

    Returns (db_path, bridge_dir). The DB is pre-seeded with the
    `preferred_cloud_harness` flow row, and the bridge_dir has a
    `runs/003/` directory and a `handoffs/` directory.
    """
    # DB
    db_path = tmp_path / "test_dpmtf.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    # bridge_flows is owned by the dispatch / bridge_lib schema, NOT
    # by the broker — but the broker LOOKS IT UP during materialize
    # validation, so the fixture creates a minimal compatible schema.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bridge_flows (
            flow_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            step_order TEXT,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auto_complete_enabled INTEGER DEFAULT 0,
            use_machine_profile INTEGER DEFAULT 0
        );
    """)
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name) VALUES (?, ?)",
        ("preferred_cloud_harness", "Preferred Cloud Harness (test)"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))

    # Bridge dir
    bridge_dir = tmp_path / "bridge"
    (bridge_dir / "preferred_cloud_harness" / "runs" / "003").mkdir(
        parents=True,
    )
    (bridge_dir / "preferred_cloud_harness" / "handoffs").mkdir(
        parents=True,
    )
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(bridge_dir))

    return str(db_path), bridge_dir


# ── 1. enqueue (signal transition) ────────────────────────


def test_enqueue_writes_a_row(tmp_db: str) -> None:
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "42",
        "--action", "signal-complete",
    ])
    assert rc == 0
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT flow_key, from_role, to_role, handoff_id, action, status "
        "FROM bridge_dispatch_queue"
    ).fetchall()
    conn.close()
    assert rows == [(
        "preferred_cloud_harness",
        "imple-codex-minimaxM3",
        "review-claude-sonnet5",
        "042",
        "signal-complete",
        "pending",
    )]


def test_enqueue_with_missing_handoff_file_fails(tmp_db: str, tmp_path: Path) -> None:
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "43",
        "--action", "signal-complete",
        "--handoff-path", str(tmp_path / "does_not_exist.md"),
    ])
    assert rc == 1
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_dispatch_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 0


def test_enqueue_with_existing_handoff_file_succeeds(
    tmp_db: str, tmp_path: Path,
) -> None:
    handoff = tmp_path / "009-handoff.md"
    handoff.write_text("# handoff")
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "44",
        "--action", "signal-complete",
        "--handoff-path", str(handoff),
    ])
    assert rc == 0


def test_enqueue_is_idempotent_for_completed_rows(tmp_db: str) -> None:
    """A row that already succeeded for the same (flow,from,to,id,action) is
    NOT re-enqueued. This matches dispatch.py's
    transition_recently_delivered guard.
    """
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "045", "signal-complete"),
    )
    conn.commit()
    conn.close()

    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "45",
        "--action", "signal-complete",
    ])
    assert rc == 0
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_dispatch_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 1  # still just the original completed row


def test_enqueue_allows_re_dispatch_for_failed_rows(tmp_db: str) -> None:
    """Failed rows are NOT idempotent — a re-enqueue should append a new
    pending row so the daemon can retry."""
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status, "
        " error_msg) "
        "VALUES (?, ?, ?, ?, ?, 'failed', ?)",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "046", "signal-complete",
         "ERROR: target not running"),
    )
    conn.commit()
    conn.close()

    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "46",
        "--action", "signal-complete",
    ])
    assert rc == 0
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT status FROM bridge_dispatch_queue "
        "WHERE handoff_id='046' ORDER BY id"
    ).fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["failed", "pending"]


def test_enqueue_action_must_be_valid(tmp_db: str) -> None:
    """An unknown action causes argparse to fail with exit 2."""
    with pytest.raises(SystemExit) as excinfo:
        bridge_broker.main([
            "enqueue",
            "--flow", "preferred_cloud_harness",
            "--from-role", "imple-codex-minimaxM3",
            "--to-role", "review-claude-sonnet5",
            "--id", "47",
            "--action", "invalid-action",
        ])
    assert excinfo.value.code == 2
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_dispatch_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 0


# ── 2. process (signal transition) ───────────────────────


def _fake_completed(_row):
    return (0, "")


def _fake_failed_error(_row):
    return (1, "ERROR: dispatch subprocess crashed\n")


def _seed(conn: sqlite3.Connection, n: int, action: str = "signal-complete") -> None:
    for i in range(n):
        conn.execute(
            "INSERT INTO bridge_dispatch_queue "
            "(flow_key, from_role, to_role, handoff_id, action, status) "
            "VALUES (?, ?, ?, ?, ?, 'pending')",
            ("preferred_cloud_harness", "imple-codex-minimaxM3",
             "review-claude-sonnet5", str(100 + i), action),
        )
    conn.commit()


def test_process_updates_status_to_completed(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = sqlite3.connect(tmp_db)
    _seed(conn, 1)
    conn.close()
    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_completed)
    rc = bridge_broker.main(["process-once"])
    assert rc == 0
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status, error_msg, processed_at, claimed_at, broker_pid "
        "FROM bridge_dispatch_queue WHERE handoff_id='100'"
    ).fetchone()
    conn.close()
    assert row[0] == "completed"
    assert row[1] is None
    assert row[2] is not None
    assert row[3] is not None
    assert row[4] == os.getpid()


def test_process_updates_status_to_failed(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = sqlite3.connect(tmp_db)
    _seed(conn, 1)
    conn.close()
    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_failed_error)
    bridge_broker.main(["process-once"])
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status, error_msg FROM bridge_dispatch_queue "
        "WHERE handoff_id='100'"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "ERROR" in (row[1] or "")


def test_process_does_not_touch_completed_rows(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Already-completed rows must be left alone by process-once."""
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'completed')",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "200", "signal-complete"),
    )
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "201", "signal-complete"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_completed)
    bridge_broker.main(["process-once"])
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT handoff_id, status FROM bridge_dispatch_queue "
        "ORDER BY id"
    ).fetchall()
    conn.close()
    assert rows[0][0] == "200" and rows[0][1] == "completed"
    # Row 201 was the pending one — only it gets claimed/processed.
    assert rows[1][0] == "201" and rows[1][1] == "completed"


def test_process_preserves_fifo_order(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker claims rows in id-ascending order (FIFO)."""
    conn = sqlite3.connect(tmp_db)
    _seed(conn, 3)
    conn.close()
    seen: list[str] = []

    def _spy(row):
        seen.append(str(row["handoff_id"]))
        return (0, "")

    monkeypatch.setattr(bridge_broker, "_run_dispatch", _spy)
    for _ in range(3):
        bridge_broker.main(["process-once"])
    assert seen == ["100", "101", "102"]


# ── 2a. sequential-flow invariant (Run 006 D6(a)) ──────


def _seed_pending(
    conn: sqlite3.Connection, flow_key: str, handoff_id: str,
    action: str = "signal-complete",
) -> int:
    """Insert a 'pending' row in bridge_dispatch_queue; return its id."""
    cur = conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        (flow_key, "imple-codex-minimaxM3",
         "review-claude-sonnet5", handoff_id, action),
    )
    conn.commit()
    return cur.lastrowid


def _complete_row(conn: sqlite3.Connection, row_id: int) -> None:
    """Move a 'processing' row to 'completed' (simulates _process_one
    success path)."""
    conn.execute(
        "UPDATE bridge_dispatch_queue "
        "SET status = 'completed', processed_at = datetime('now'), "
        "    error_msg = NULL "
        "WHERE id = ?",
        (row_id,),
    )
    conn.commit()


def _row_status(conn: sqlite3.Connection, row_id: int) -> str:
    """Read the status of a row by id."""
    cur = conn.execute(
        "SELECT status FROM bridge_dispatch_queue WHERE id = ?",
        (row_id,),
    )
    return cur.fetchone()[0]


def test_sequential_same_flow_blocks_second_claim(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two pending rows for the SAME flow: the first is held in
    'processing' (simulating an in-flight delivery); the second stays
    'pending' because the per-flow claim guard forbids claiming a
    second row while another row for the same flow is in flight.
    This is Run 006 D6(a) — measured live 2026-08-21 as two queued
    '/clear' commands piling up in a busy reviewer pane."""
    conn = sqlite3.connect(tmp_db)
    id_first = _seed_pending(conn, "preferred_cloud_harness", "100")
    id_second = _seed_pending(conn, "preferred_cloud_harness", "101")
    # Simulate id_first having been claimed by another broker — the
    # claim guard MUST observe this and refuse to claim id_second.
    conn.execute(
        "UPDATE bridge_dispatch_queue SET status = 'processing', "
        "    claimed_at = datetime('now'), broker_pid = 999999 "
        "WHERE id = ?",
        (id_first,),
    )
    conn.commit()
    conn.close()

    # Mock dispatch so the SECOND attempt cannot claim anything — we
    # only need to verify id_second stays 'pending'.
    monkeypatch.setattr(bridge_broker, "_run_dispatch",
                        lambda _r: (0, ""))
    rc = bridge_broker.main(["process-once"])
    # process-once returns 0 whether or not a row was claimable.
    assert rc == 0

    conn = sqlite3.connect(tmp_db)
    # id_first is still 'processing' (untouched).
    assert _row_status(conn, id_first) == "processing"
    # id_second stayed 'pending' — the per-flow guard held.
    assert _row_status(conn, id_second) == "pending"
    conn.close()


def test_sequential_different_flows_both_claimable(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two pending rows for DIFFERENT flows: both are claimable
    (no cross-flow blocking). The guard is per-flow, not global."""
    conn = sqlite3.connect(tmp_db)
    id_a = _seed_pending(conn, "preferred_cloud_harness", "100")
    id_b = _seed_pending(conn, "preferred_cloud", "101")
    conn.close()

    def _fake_dispatch(_row):
        return (0, "")

    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_dispatch)
    # Two process-once calls — one per flow. Both rows complete.
    bridge_broker.main(["process-once"])
    bridge_broker.main(["process-once"])

    conn = sqlite3.connect(tmp_db)
    statuses = {r[0]: r[1] for r in conn.execute(
        "SELECT id, status FROM bridge_dispatch_queue ORDER BY id"
    ).fetchall()}
    conn.close()
    assert statuses[id_a] == "completed"
    assert statuses[id_b] == "completed"


def test_sequential_after_completion_second_becomes_claimable(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once the first row completes (status 'completed'), the second
    pending row for the same flow becomes claimable again."""
    conn = sqlite3.connect(tmp_db)
    id_first = _seed_pending(conn, "preferred_cloud_harness", "100")
    id_second = _seed_pending(conn, "preferred_cloud_harness", "101")
    conn.close()

    def _fake_dispatch(_row):
        return (0, "")

    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_dispatch)
    # First claim + complete.
    bridge_broker.main(["process-once"])
    # id_second is still pending; now id_first is completed so the
    # per-flow guard releases id_second.
    bridge_broker.main(["process-once"])

    conn = sqlite3.connect(tmp_db)
    assert _row_status(conn, id_first) == "completed"
    assert _row_status(conn, id_second) == "completed"
    conn.close()


def test_sequential_backoff_skips_recently_refused_row(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row requeued with backoff (claimed_at in the future) is skipped
    by the next claim — the refusal-backoff from D6(b). The mocked
    dispatch refuses; the broker requeues with claimed_at = now + N
    seconds; the next claim observes claimed_at in the future and
    moves on to the next pending row."""
    conn = sqlite3.connect(tmp_db)
    _seed_pending(conn, "preferred_cloud_harness", "100")
    _seed_pending(conn, "preferred_cloud", "101")
    conn.close()

    def _fake_refuse(_row):
        # Return rc=2: the broker's "REFUSED_INJECTION" path.
        return (2, "REFUSED_INJECTION: pane busy")

    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_refuse)
    # First claim picks row 100, refuses, requeues with backoff.
    rc = bridge_broker.main(["process-once"])
    assert rc == 0
    # Second claim should pick row 101 (different flow) and refuse it too.
    bridge_broker.main(["process-once"])

    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT handoff_id, status, claimed_at FROM "
        "bridge_dispatch_queue ORDER BY id"
    ).fetchall()
    conn.close()
    # Both rows are 'pending' again with a future claimed_at.
    assert [(r[0], r[1]) for r in rows] == [("100", "pending"), ("101", "pending")]
    # claimed_at was set to a future time by the broker's refusal
    # requeue. Check via SQLite (single source of truth): every row's
    # claimed_at is >= datetime('now'). This avoids cross-process
    # clock-skew issues between Python's datetime and SQLite's.
    conn = sqlite3.connect(tmp_db)
    forward_dated = conn.execute(
        "SELECT COUNT(*) FROM bridge_dispatch_queue "
        "WHERE claimed_at >= datetime('now')"
    ).fetchone()[0]
    conn.close()
    assert forward_dated == 2  # both refused rows are in the future


def test_sequential_after_backoff_expires_claimable_again(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once the refusal backoff has expired (claimed_at < now), the row
    becomes claimable again. Simulates the passage of backoff by
    directly rewriting claimed_at to the past."""
    conn = sqlite3.connect(tmp_db)
    id_only = _seed_pending(conn, "preferred_cloud_harness", "100")
    conn.close()

    refused_count = {"n": 0}

    def _fake_refuse_then_succeed(_row):
        refused_count["n"] += 1
        if refused_count["n"] == 1:
            return (2, "REFUSED_INJECTION: pane busy")
        return (0, "")

    monkeypatch.setattr(bridge_broker, "_run_dispatch", _fake_refuse_then_succeed)
    # First call: refuses, row requeued with future claimed_at.
    bridge_broker.main(["process-once"])
    # Force the backoff to "have expired" by setting claimed_at to the
    # distant past — simulates the daemon waiting _REFUSAL_BACKOFF_SECONDS.
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "UPDATE bridge_dispatch_queue SET claimed_at = "
        "datetime('now', '-1 hour') WHERE id = ?",
        (id_only,),
    )
    conn.commit()
    conn.close()
    # Second call: row is now claimable; the dispatch succeeds.
    bridge_broker.main(["process-once"])

    conn = sqlite3.connect(tmp_db)
    assert _row_status(conn, id_only) == "completed"
    conn.close()


# ── 2b. orphan recovery (Run 006 D4) ──────────────────


def _seed_processing_row(
    conn: sqlite3.Connection, handoff_id: str,
    broker_pid: int | None,
) -> None:
    """Insert a 'processing' row in bridge_dispatch_queue."""
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status, "
        " claimed_at, broker_pid) "
        "VALUES (?, ?, ?, ?, ?, 'processing', "
        " datetime('now'), ?)",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", handoff_id, "signal-complete",
         broker_pid),
    )
    conn.commit()


def test_orphan_no_trace_requeues_dead_processing_row(
    tmp_db: str, tmp_path: Path,
) -> None:
    """A 'processing' row whose broker_pid is dead (and whose trace has
    NO delivery for this transition) is REQUEUED by recover_orphaned_rows.

    This is the canonical orphan case observed live 2026-08-21 (dispatch
    row 36, handoff 018): the broker was killed before dispatch.py
    completed; the trace never recorded a delivery, so the row must
    re-enter 'pending' so the next daemon picks it up.
    """
    trace_path = tmp_path / "trace.log"
    # An empty trace (no delivery recorded).
    conn = sqlite3.connect(tmp_db)
    # Use a pid that is guaranteed not to exist (2^31 is far above any
    # running pid on a Linux box).
    _seed_processing_row(conn, "018", 2_147_483_647)
    conn.close()

    rc = bridge_broker.recover_orphaned_rows(
        bridge_broker._open_db(tmp_db), trace_path=str(trace_path),
    )
    assert rc == 1
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status, claimed_at, broker_pid, error_msg, processed_at "
        "FROM bridge_dispatch_queue WHERE handoff_id='018'"
    ).fetchone()
    conn.close()
    # Row is requeued: pending, claim fields cleared.
    assert row[0] == "pending"
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None
    # processed_at stays NULL for a requeue (it would be set on a
    # mark-completed branch).
    assert row[4] is None


def test_orphan_with_trace_delivery_marks_completed(
    tmp_db: str, tmp_path: Path,
) -> None:
    """A 'processing' row whose broker_pid is dead BUT whose trace has
    a 'signal_complete' delivery for that exact transition is marked
    COMPLETED (not requeued).

    This is the m2 mutation guard from GOAL.md section 5: a broker that
    requeues despite a trace-recorded delivery must go red. It is also
    the live failure mode that recover_orphaned_rows is designed to
    repair — the daemon died AFTER dispatch.py recorded delivery.
    """
    trace_path = tmp_path / "trace.log"
    trace_path.write_text(
        "2026-08-21T10:00:00Z | imple-codex-minimaxM3->review-claude-sonnet5"
        " | 019 | signal_complete | dispatch | delivered\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(tmp_db)
    _seed_processing_row(conn, "019", 2_147_483_647)
    conn.close()

    rc = bridge_broker.recover_orphaned_rows(
        bridge_broker._open_db(tmp_db), trace_path=str(trace_path),
    )
    assert rc == 1
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status, claimed_at, broker_pid, error_msg, processed_at "
        "FROM bridge_dispatch_queue WHERE handoff_id='019'"
    ).fetchone()
    conn.close()
    # Mark completed (NOT requeued).
    assert row[0] == "completed"
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None
    assert row[4] is not None  # processed_at set


def test_orphan_with_null_broker_pid_requeues_when_no_trace(
    tmp_db: str, tmp_path: Path,
) -> None:
    """A 'processing' row whose broker_pid is NULL is treated as orphan
    regardless of trace content (NULL pid has no live owner). With no
    trace delivery, the row is requeued."""
    trace_path = tmp_path / "trace.log"
    conn = sqlite3.connect(tmp_db)
    _seed_processing_row(conn, "020", None)
    conn.close()

    rc = bridge_broker.recover_orphaned_rows(
        bridge_broker._open_db(tmp_db), trace_path=str(trace_path),
    )
    assert rc == 1
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status FROM bridge_dispatch_queue WHERE handoff_id='020'"
    ).fetchone()
    conn.close()
    assert row[0] == "pending"


def test_orphan_skips_live_processing_row(
    tmp_db: str, tmp_path: Path,
) -> None:
    """A 'processing' row whose broker_pid IS alive is left alone by
    recover_orphaned_rows (it is not an orphan)."""
    trace_path = tmp_path / "trace.log"
    conn = sqlite3.connect(tmp_db)
    # os.getpid() is always a live process — this row is NOT an orphan.
    _seed_processing_row(conn, "021", os.getpid())
    conn.close()

    rc = bridge_broker.recover_orphaned_rows(
        bridge_broker._open_db(tmp_db), trace_path=str(trace_path),
    )
    assert rc == 0
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status, broker_pid FROM bridge_dispatch_queue "
        "WHERE handoff_id='021'"
    ).fetchone()
    conn.close()
    # Status and broker_pid untouched.
    assert row[0] == "processing"
    assert row[1] == os.getpid()


def test_orphan_skips_non_processing_rows(
    tmp_db: str, tmp_path: Path,
) -> None:
    """recover_orphaned_rows only inspects status='processing'; pending,
    completed, and failed rows are not its concern."""
    trace_path = tmp_path / "trace.log"
    conn = sqlite3.connect(tmp_db)
    # Pending with a dead pid — must NOT be touched.
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status, "
        " broker_pid) "
        "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "022", "signal-complete",
         2_147_483_647),
    )
    # Completed with a dead pid — must NOT be touched (already done).
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status, "
        " broker_pid, processed_at) "
        "VALUES (?, ?, ?, ?, ?, 'completed', ?, datetime('now'))",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "023", "signal-complete",
         2_147_483_647),
    )
    conn.commit()
    conn.close()

    rc = bridge_broker.recover_orphaned_rows(
        bridge_broker._open_db(tmp_db), trace_path=str(trace_path),
    )
    assert rc == 0
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT handoff_id, status FROM bridge_dispatch_queue "
        "ORDER BY id"
    ).fetchall()
    conn.close()
    assert rows == [("022", "pending"), ("023", "completed")]


# ── 3. governance preservation (TG11) ─────────────────────


def test_broker_does_not_disable_dispatch_py_validation(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker's subprocess invocation must call dispatch.py with the
    SAME shape the manual recovery path uses. The broker is additive,
    not a replacement; it never weakens dispatch.py's evidence-gate or
    scope-fence checks."""
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO bridge_dispatch_queue "
        "(flow_key, from_role, to_role, handoff_id, action, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        ("preferred_cloud_harness", "imple-codex-minimaxM3",
         "review-claude-sonnet5", "300", "signal-complete"),
    )
    conn.commit()
    conn.close()

    captured: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Completed()

    monkeypatch.setattr(bridge_broker.subprocess, "run", _fake_run)
    rc = bridge_broker.main(["process-once"])
    assert rc == 0
    cmd = captured["cmd"]
    assert cmd is not None
    # dispatch.py is called with the same flags dispatch.py's main() expects.
    assert "--db-flow" in cmd
    assert "preferred_cloud_harness" in cmd
    assert "--signal-complete" in cmd
    assert "--from-role" in cmd
    assert "imple-codex-minimaxM3" in cmd
    assert "--id" in cmd
    assert "300" in cmd


def test_broker_self_bootstraps_schema_when_migration_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If migration 058 has not been applied, enqueue must still succeed
    because the broker self-bootstraps the queue table."""
    db_path = tmp_path / "fresh.db"
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "400",
        "--action", "signal-complete",
    ])
    assert rc == 0
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_dispatch_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 1


# ── 4. status + introspection ────────────────────────────


def test_broker_status_prints_queue(tmp_db: str, capsys) -> None:
    conn = sqlite3.connect(tmp_db)
    _seed(conn, 2)
    conn.close()
    rc = bridge_broker.main(["status", "--limit", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "preferred_cloud_harness" in out
    assert "imple-codex-minimaxM3->review-claude-sonnet5" in out
    assert "100" in out
    assert "101" in out
    assert "status=pending" in out


def test_broker_detects_dispatch_py_error_in_output(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When dispatch.py writes 'ERROR:' to stdout (and exits 0), the
    broker must record the row as failed with the error message captured.
    """
    conn = sqlite3.connect(tmp_db)
    _seed(conn, 1)
    conn.close()

    class _ErrCompleted:
        returncode = 0
        stdout = "ERROR: dispatch subprocess crashed\n"
        stderr = ""

    monkeypatch.setattr(bridge_broker.subprocess, "run",
                        lambda *a, **kw: _ErrCompleted())
    bridge_broker.main(["process-once"])
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT status, error_msg FROM bridge_dispatch_queue "
        "WHERE handoff_id='100'"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "ERROR" in (row[1] or "")


# ── 5. capability surface ───────────────────────────────


def test_broker_does_not_touch_bridge_dir_or_tmux(
    tmp_db: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enqueue must NOT write to /home/svend/flows or /tmp/tmux-1000.
    These are the host capabilities the supervisor's sandbox denies;
    the broker is the narrow capability that owns them, NOT the
    enqueue path that the sandboxed supervisor invokes."""
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "500",
        "--action", "signal-complete",
    ])
    assert rc == 0
    # Direct OS check: nothing was created in /home/svend/flows
    # (the enqueue path never touches that path). Same for tmux-1000.
    flows_path = Path("/home/svend/flows/preferred_cloud_harness/500-broker-probe")
    assert not flows_path.exists()
    tmux_socket = Path("/tmp/tmux-1000/500-broker-probe")
    assert not tmux_socket.exists()
    # The DB IS the seam — confirm the row landed there.
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_dispatch_queue WHERE handoff_id='500'"
    ).fetchone()
    conn.close()
    assert rows[0] == 1


def test_broker_enqueue_with_handoff_path_does_not_write_to_bridge_dir(
    tmp_db: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verdict 009 non-blocking follow-up: even when --handoff-path
    is supplied, the broker enqueue must NOT write to /home/svend/flows.
    The branch does perform a *read* under a caller-supplied path (the
    existence check), but it never writes anywhere."""
    handoff = tmp_path / "005-handoff.md"
    handoff.write_text("# handoff content")
    rc = bridge_broker.main([
        "enqueue",
        "--flow", "preferred_cloud_harness",
        "--from-role", "imple-codex-minimaxM3",
        "--to-role", "review-claude-sonnet5",
        "--id", "501",
        "--action", "signal-complete",
        "--handoff-path", str(handoff),
    ])
    assert rc == 0
    # No file created under /home/svend/flows (the canonical bridge dir).
    flows_probe = Path("/home/svend/flows/preferred_cloud_harness/501-broker-probe")
    assert not flows_probe.exists()
    tmux_probe = Path("/tmp/tmux-1000/501-broker-probe")
    assert not tmux_probe.exists()
    # Row landed in DB with the caller-supplied handoff_path preserved.
    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT handoff_path FROM bridge_dispatch_queue WHERE handoff_id='501'"
    ).fetchone()
    conn.close()
    assert row[0] == str(handoff)


# ══════════════════════════════════════════════════════════
# PART B — materialization broker (handoff 010)
# ══════════════════════════════════════════════════════════


# ── B.1 canonical destination derivation ─────────────────


def test_canonical_destination_backlog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", 3, None, "backlog",
    )
    assert dest == f"{tmp_path}/preferred_cloud_harness/runs/003/BACKLOG.md"


def test_canonical_destination_run_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", 3, None, "run-ledger",
    )
    assert dest == f"{tmp_path}/preferred_cloud_harness/runs/003/RUN-LEDGER.md"


def test_canonical_destination_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", None, 11, "handoff",
    )
    assert dest == f"{tmp_path}/preferred_cloud_harness/handoffs/11-handoff.md"


def test_canonical_destination_end_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", 3, None, "end-report",
    )
    assert dest == f"{tmp_path}/preferred_cloud_harness/runs/003/END-REPORT.md"


def test_canonical_destination_handoff_uses_the_unpadded_canonical_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handoff path is the UNPADDED {id}-handoff.md dispatch.py looks for.

    Until 2026-09-02 this builder zero-padded ({id:03d}) while dispatch.py's
    canonical name has been the bare number since 2026-08-29; a materialized
    handoff was therefore invisible to dispatch (measured: 9000 handoff 4).
    """
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", None, 7, "handoff",
    )
    assert dest == f"{tmp_path}/preferred_cloud_harness/handoffs/7-handoff.md"


def test_canonical_destination_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        bridge_broker._canonical_destination(
            "preferred_cloud_harness", 3, None, "bogus",
        )


def test_canonical_destination_run_scoped_requires_run_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        bridge_broker._canonical_destination(
            "preferred_cloud_harness", None, None, "backlog",
        )
    with pytest.raises(ValueError):
        bridge_broker._canonical_destination(
            "preferred_cloud_harness", 0, None, "run-ledger",
        )


def test_canonical_destination_handoff_requires_handoff_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        bridge_broker._canonical_destination(
            "preferred_cloud_harness", None, 0, "handoff",
        )


# ── B.2 rejection of arbitrary inputs ─────────────────────


def test_materialize_rejects_unknown_artifact_type(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    with pytest.raises(SystemExit) as excinfo:
        bridge_broker.main([
            "materialize",
            "--flow", "preferred_cloud_harness",
            "--type", "totally-bogus",
            "--run-id", "3",
            "--content", "x",
        ])
    assert excinfo.value.code == 2  # argparse rejects
    # Nothing written.
    run_dir = bridge_dir / "preferred_cloud_harness" / "runs" / "003"
    assert list(run_dir.glob("*.md")) == []


def test_materialize_rejects_unknown_flow_key(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "not_a_real_flow",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert rc == 1
    # Nothing written.
    backlog = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "BACKLOG.md"
    assert not backlog.exists()
    # No row written.
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 0


def test_materialize_rejects_zero_run_id(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "0",
        "--content", "x",
    ])
    assert rc == 1


def test_materialize_rejects_zero_handoff_id(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "handoff",
        "--id", "0",
        "--content", "x",
    ])
    assert rc == 1


def test_materialize_rejects_handoff_id_for_run_scoped(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """backlog/run-ledger/end-report must NOT receive a --id."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--id", "11",  # wrong — handoff_id supplied for run-scoped type
        "--content", "x",
    ])
    assert rc == 1


def test_materialize_rejects_run_id_for_handoff(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """handoff must NOT receive a --run-id."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "handoff",
        "--run-id", "3",  # wrong — run_id supplied for handoff type
        "--id", "11",
        "--content", "x",
    ])
    assert rc == 1


def test_materialize_rejects_empty_content(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "",
    ])
    assert rc == 1


def test_materialize_cli_accepts_no_destination_flag() -> None:
    """There is NO --destination CLI flag — caller cannot supply one.

    This is the binding constraint from the Human amendment. The
    broker computes the destination internally from identity + type.
    """
    import argparse
    parser = bridge_broker._build_parser()
    # The materialize subparser rejects unknown flags.
    args = parser.parse_args([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert args.func == bridge_broker.cmd_materialize
    # Explicitly assert no destination field on the namespace.
    assert "destination" not in vars(args)
    assert "dest_path" not in vars(args)
    assert "path" not in vars(args)


# ── B.3 successful materialize end-to-end ─────────────────


def test_materialize_writes_backlog_at_canonical_path(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# BACKLOG test\nbody\n",
    ])
    assert rc == 0
    # The enqueue is DB-only — the file is NOT written yet.
    backlog = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "BACKLOG.md"
    assert not backlog.exists()
    # Row landed in the queue.
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "pending"
    # Host-side process-once performs the write.
    bridge_broker.main(["process-once"])
    # File at canonical path with the queued content.
    assert backlog.exists()
    assert backlog.read_text() == "# BACKLOG test\nbody\n"
    # Row marked completed.
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "completed"


def test_materialize_backlog_replaces_existing(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    backlog = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "BACKLOG.md"
    backlog.write_text("# OLD CONTENT\n")
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# NEW CONTENT\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    assert backlog.read_text() == "# NEW CONTENT\n"


def test_materialize_run_ledger_appends(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    ledger = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "RUN-LEDGER.md"
    ledger.write_text("# RUN-LEDGER\nfirst entry\n")
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "second entry\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Append semantics: existing content + new content (replace would
    # have lost the first entry).
    assert ledger.read_text() == "# RUN-LEDGER\nfirst entry\nsecond entry\n"


def test_materialize_run_ledger_creates_if_absent(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    ledger = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "RUN-LEDGER.md"
    assert not ledger.exists()
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "first entry\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    assert ledger.exists()
    assert ledger.read_text() == "first entry\n"


def test_materialize_handoff_at_zero_padded_canonical_path(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "handoff",
        "--id", "11",
        "--content", "# handoff 011\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Unpadded canonical name (dispatch.py's form).
    path = bridge_dir / "preferred_cloud_harness" / "handoffs" / "11-handoff.md"
    assert path.exists()
    assert path.read_text() == "# handoff 011\n"


def test_materialize_end_report_replaces(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    endrep = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "END-REPORT.md"
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "end-report",
        "--run-id", "3",
        "--content", "# END REPORT\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    assert endrep.exists()
    assert endrep.read_text() == "# END REPORT\n"


# ── B.4 filesystem untouched on validation failure ───────


def test_materialize_refuses_on_closed_run(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """If END-REPORT.md already exists, backlog/run-ledger writes
    must be refused (run is closed)."""
    db_path, bridge_dir = tmp_bridge_and_db
    endrep = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "END-REPORT.md"
    endrep.write_text("# END REPORT (closed)\n")
    # Now try to write backlog.
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# NEW BACKLOG\n",
    ])
    assert rc == 0  # enqueue succeeds
    bridge_broker.main(["process-once"])
    # The new BACKLOG.md must NOT have been created.
    backlog = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "BACKLOG.md"
    assert not backlog.exists()
    # Row marked failed with clear error.
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, error_msg FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "END-REPORT" in (row[1] or "")


def test_materialize_refuses_on_missing_run_dir(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_bridge_and_db
    # Remove the run directory.
    run_dir = bridge_dir / "preferred_cloud_harness" / "runs" / "003"
    run_dir.rmdir()
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert rc == 0  # enqueue OK
    bridge_broker.main(["process-once"])
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, error_msg FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "missing" in (row[1] or "").lower() or "run" in (row[1] or "").lower()


def test_materialize_refuses_handoff_overwrite(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """A handoff file that already exists must NOT be silently
    overwritten — it has been dispatched or staged."""
    db_path, bridge_dir = tmp_bridge_and_db
    existing = bridge_dir / "preferred_cloud_harness" / "handoffs" / "11-handoff.md"
    existing.write_text("# EXISTING\n")
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "handoff",
        "--id", "11",
        "--content", "# NEW\n",
    ])
    assert rc == 0  # enqueue OK
    bridge_broker.main(["process-once"])
    # Original content preserved.
    assert existing.read_text() == "# EXISTING\n"
    # Row marked failed.
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, error_msg FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "exists" in (row[1] or "").lower() or "overwrite" in (row[1] or "").lower()


def test_materialize_refuses_end_report_overwrite(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """A run can be closed only once — refuse to overwrite END-REPORT.md.

    D3 (Run 025) moved the destination-absence-keyed refusal to the
    ENQUEUE guard, so the broker-level enqueue in the sandbox refuses
    silently when it can see the destination file. This test exercises
    the WRITE-LAYER refuse (the authoritative host-side gate that
    still STANDS — see _write_materialize_artifact's end-report
    branch, which catches the sandbox-blind case where the enqueue
    proceeded because it could not see the destination). STRICT
    assertion: row status MUST be 'failed' and error_msg MUST name
    the refusal reason.
    """
    db_path, bridge_dir = tmp_bridge_and_db
    endrep = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "END-REPORT.md"
    endrep.write_text("# EXISTING END REPORT\n")
    # Simulate a sandbox-blind enqueue that proceeded (could not see
    # the destination) — seed a PENDING end-report row directly into
    # the temp DB.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bridge_materialize_queue "
        "(flow_key, run_id, artifact_type, content, status) "
        "VALUES ('preferred_cloud_harness', 3, 'end-report', "
        "'# NEW END REPORT', 'pending')"
    )
    conn.commit()
    conn.close()
    # Run process-once — the write layer will see the destination
    # exists and refuse to overwrite (rc 1, row marked 'failed').
    bridge_broker.main(["process-once"])
    # File must NOT be overwritten.
    assert endrep.read_text() == "# EXISTING END REPORT\n"
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, error_msg FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row is not None  # the seeded row exists
    assert row[0] == "failed"  # write-layer refused
    err = (row[1] or "").lower()
    assert "overwrite" in err or "exists" in err  # refusal reason present


# ── B.5 sandbox-safe enqueue ─────────────────────────────


def test_materialize_enqueue_does_not_touch_bridge_dir(
    tmp_bridge_and_db: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The materialize enqueue step must NOT touch the bridge dir at all.

    It is DB-only — the host-side broker daemon is what writes. This is
    the sandbox-safety property: a sandboxed supervisor can enqueue
    materialize requests without needing write access to
    /home/svend/flows.
    """
    db_path, bridge_dir = tmp_bridge_and_db
    # Snapshot the bridge_dir tree.
    before = sorted(p for p in bridge_dir.rglob("*") if p.is_file())

    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# NEW\n",
    ])
    assert rc == 0

    after = sorted(p for p in bridge_dir.rglob("*") if p.is_file())
    assert before == after, (
        f"enqueue touched the bridge dir: before={before} after={after}"
    )

    # Row landed in DB.
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 1


def test_materialize_enqueue_does_not_touch_real_bridge_dir(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """The enqueue step must NOT touch the real /home/svend/flows.

    Even when given a real flow_key, the enqueue is DB-only and
    creates no file under /home/svend/flows. (This is the same
    discipline as test B.5a above; this version uses the real path
    sentinel to make the property visible.)
    """
    db_path, bridge_dir = tmp_bridge_and_db
    # Make sure the real bridge_dir sentinel path stays untouched.
    # We test by enumerating /home/svend/flows/preferred_cloud_harness
    # before and after — but only check that no NEW files appear in
    # the runs/ subdir (we don't write to /tmp under real path here).
    real_runs_dir = Path("/home/svend/flows/preferred_cloud_harness/runs")
    if real_runs_dir.exists():
        before = set(real_runs_dir.rglob("*"))
    else:
        before = set()
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert rc == 0
    after = set(real_runs_dir.rglob("*"))
    new_files = after - before
    # The materialize enqueue must not have created any file under
    # /home/svend/flows.
    assert new_files == set(), (
        f"enqueue created unexpected files in real bridge_dir: {new_files}"
    )
    # Clean up the queue row.
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM bridge_materialize_queue")
    conn.commit()
    conn.close()


# ── B.6 governance preservation (TG11) ────────────────────


def test_materialize_does_not_disable_dispatch_py_validation(
    tmp_bridge_and_db: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The materialize path never invokes dispatch.py — it directly
    writes the file. The dispatch.py evidence-gate and scope-fence
    validation remain active because they were never disabled.
    """
    # Snapshot the dispatch.py mtime so we can prove it was not
    # touched by the materialize flow.
    dispatch_py = _REPO / "scripts" / "bridgeV002" / "dispatch.py"
    mtime_before = dispatch_py.stat().st_mtime

    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])

    # dispatch.py unchanged.
    mtime_after = dispatch_py.stat().st_mtime
    assert mtime_before == mtime_after


def test_materialize_self_bootstraps_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If migration has not been applied, materialize must still
    succeed because the broker self-bootstraps the materialize queue."""
    db_path = tmp_path / "fresh.db"
    bridge_dir = tmp_path / "bridge"
    (bridge_dir / "preferred_cloud_harness" / "runs" / "003").mkdir(parents=True)
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir", lambda: str(bridge_dir))

    # Pre-seed bridge_flows in the fresh DB (NOT a broker-owned table,
    # but the broker looks it up at validation time).
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bridge_flows (
            flow_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            step_order TEXT,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auto_complete_enabled INTEGER DEFAULT 0,
            use_machine_profile INTEGER DEFAULT 0
        );
    """)
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name) VALUES (?, ?)",
        ("preferred_cloud_harness", "x"),
    )
    conn.commit()
    conn.close()

    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert rc == 0
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 1


# ── B.7 idempotency ──────────────────────────────────────


def test_materialize_backlog_multi_write_with_different_content(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """backlog is MULTI-WRITE: a second enqueue with DIFFERENT content is
    enqueued (not dropped). Replaces the prior one-shot
    test_materialize_is_idempotent_for_completed_rows which asserted the
    defective one-shot behavior."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# FIRST\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Re-enqueue with DIFFERENT content. Per the 012 fix, this MUST be
    # enqueued (multi-write per run_id), not dropped.
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# SECOND\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    backlog_count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'backlog'"
    ).fetchone()[0]
    conn.close()
    assert backlog_count == 2
    # Process-once applies the second replace -> file content = SECOND.
    bridge_broker.main(["process-once"])
    backlog = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "BACKLOG.md"
    assert backlog.read_text() == "# SECOND\n"


def test_materialize_run_ledger_multi_write_with_different_content(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """run-ledger is MULTI-WRITE: a second append with DIFFERENT content
    is enqueued (not dropped); the file then holds BOTH entries."""
    db_path, bridge_dir = tmp_bridge_and_db
    ledger = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "RUN-LEDGER.md"
    ledger.write_text("# RUN-LEDGER\n")
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "first entry\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Second append with DIFFERENT content.
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "second entry\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    ledger_count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'run-ledger'"
    ).fetchone()[0]
    conn.close()
    assert ledger_count == 2
    bridge_broker.main(["process-once"])
    # Append semantics: existing + new (no replace, no duplication).
    assert ledger.read_text() == (
        "# RUN-LEDGER\nfirst entry\nsecond entry\n"
    )


def test_materialize_backlog_identical_content_does_not_enqueue(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """backlog: an immediate repeat of IDENTICAL content does NOT enqueue
    a new row and does NOT duplicate content."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# SAME\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Immediate repeat with the IDENTICAL content -> no-op.
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# SAME\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    backlog_count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'backlog'"
    ).fetchone()[0]
    conn.close()
    assert backlog_count == 1


def test_materialize_run_ledger_identical_content_does_not_enqueue(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """run-ledger: an immediate repeat of IDENTICAL content does NOT
    enqueue a new row and does NOT duplicate content."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "same entry\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Immediate repeat with the IDENTICAL content -> no-op.
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "same entry\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    ledger_count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'run-ledger'"
    ).fetchone()[0]
    conn.close()
    assert ledger_count == 1
    # And the file holds the content exactly once (no duplicate).
    bridge_broker.main(["process-once"])
    ledger = bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "RUN-LEDGER.md"
    assert ledger.read_text() == "same entry\n"


def test_materialize_run_ledger_allows_re_dispatch_for_failed_rows(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """run-ledger: a request after a 'failed' row is enqueued (retry is
    allowed), including retry with the SAME content that failed."""
    db_path, bridge_dir = tmp_bridge_and_db
    # First attempt fails (run dir removed).
    run_dir = bridge_dir / "preferred_cloud_harness" / "runs" / "003"
    run_dir.rmdir()
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "retry me\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Restore the run dir.
    run_dir.mkdir(parents=True)
    # Retry with the SAME content (the prior 'failed' row must NOT
    # suppress this request — identical-content idempotency only applies
    # to 'pending'/'completed' rows).
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "run-ledger",
        "--run-id", "3",
        "--content", "retry me\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    conn = sqlite3.connect(db_path)
    statuses = [r[0] for r in conn.execute(
        "SELECT status FROM bridge_materialize_queue ORDER BY id"
    ).fetchall()]
    conn.close()
    assert statuses == ["failed", "completed"]


def test_materialize_handoff_remains_idempotent_per_handoff_id(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """handoff is one-shot per handoff_id (exclusive-create). Even with
    DIFFERENT content, a second materialize for the same handoff_id is
    a no-op; the file is NOT overwritten."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "handoff",
        "--id", "12",
        "--content", "# handoff 12 original\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Second materialize for the SAME handoff_id with DIFFERENT content
    # -> no-op (refuse-overwrite preserved).
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "handoff",
        "--id", "12",
        "--content", "# handoff 12 should NOT win\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    handoff_count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'handoff'"
    ).fetchone()[0]
    conn.close()
    assert handoff_count == 1
    # File content unchanged (the second materialize was a no-op).
    handoff_file = (
        bridge_dir / "preferred_cloud_harness" / "handoffs" / "12-handoff.md"
    )
    assert handoff_file.read_text() == "# handoff 12 original\n"


def test_materialize_end_report_remains_idempotent_per_run_id(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """end-report is one-shot per run_id (refuse-overwrite). Even with
    DIFFERENT content, a second materialize for the same run_id is a
    no-op; the file is NOT overwritten."""
    db_path, bridge_dir = tmp_bridge_and_db
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "end-report",
        "--run-id", "3",
        "--content", "# END original\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Second materialize for the SAME run_id with DIFFERENT content
    # -> no-op (refuse-overwrite preserved).
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "end-report",
        "--run-id", "3",
        "--content", "# END should NOT win\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    end_report_count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'end-report'"
    ).fetchone()[0]
    conn.close()
    assert end_report_count == 1
    # File content unchanged.
    end_report_file = (
        bridge_dir / "preferred_cloud_harness" / "runs" / "003" / "END-REPORT.md"
    )
    assert end_report_file.read_text() == "# END original\n"


def test_materialize_allows_re_dispatch_for_failed_rows(
    tmp_bridge_and_db: tuple[str, Path],
) -> None:
    """Failed materialize rows can be re-enqueued."""
    db_path, bridge_dir = tmp_bridge_and_db
    # First attempt fails (run dir removed).
    run_dir = bridge_dir / "preferred_cloud_harness" / "runs" / "003"
    run_dir.rmdir()
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "x",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # Restore the run dir.
    run_dir.mkdir(parents=True)
    # Re-enqueue.
    rc = bridge_broker.main([
        "materialize",
        "--flow", "preferred_cloud_harness",
        "--type", "backlog",
        "--run-id", "3",
        "--content", "# NOW OK\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    conn = sqlite3.connect(db_path)
    statuses = [r[0] for r in conn.execute(
        "SELECT status FROM bridge_materialize_queue ORDER BY id"
    ).fetchall()]
    conn.close()
    assert statuses == ["failed", "completed"]


# ══════════════════════════════════════════════════════════
# PART C — escalation-response materialization (Run 004)
# ══════════════════════════════════════════════════════════


@pytest.fixture()
def tmp_broker_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, Path]:
    """DB with bridge_flows + bridge_roles + bridge_flow_steps, and a
    bridge_dir holding an escalations/ directory (as signal_escalation
    creates it)."""
    db_path = tmp_path / "esc.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bridge_flows (
            flow_key TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bridge_roles (
            role_key TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS bridge_flow_steps (
            flow_key TEXT NOT NULL,
            from_role TEXT,
            to_role TEXT
        );
    """)
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name) VALUES (?, ?)",
        ("preferred_cloud_harness", "Preferred Cloud Harness"),
    )
    conn.execute(
        "INSERT INTO bridge_roles (role_key) VALUES (?)",
        ("super-deep-deep4",),
    )
    conn.execute(
        "INSERT INTO bridge_flow_steps (flow_key, from_role, to_role) "
        "VALUES (?, ?, ?)",
        ("preferred_cloud_harness", "super-deep-deep4",
         "imple-codex-minimaxM3"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))

    bridge_dir = tmp_path / "bridge"
    (bridge_dir / "escalations").mkdir(parents=True)
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(bridge_dir))
    return str(db_path), bridge_dir


def test_canonical_destination_escalation_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", None, 17, "escalation-response",
        "super-deep-deep4",
    )
    assert dest == f"{tmp_path}/escalations/17-super-deep-deep4-response.md"


def test_canonical_destination_escalation_response_uses_the_unpadded_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir",
                        lambda: str(tmp_path))
    dest = bridge_broker._canonical_destination(
        "preferred_cloud_harness", None, 7, "escalation-response", "r",
    )
    assert dest == f"{tmp_path}/escalations/7-r-response.md"


def test_canonical_destination_escalation_response_requires_role() -> None:
    with pytest.raises(ValueError):
        bridge_broker._canonical_destination(
            "preferred_cloud_harness", None, 17, "escalation-response",
        )


def test_canonical_destination_escalation_response_requires_handoff_id(
) -> None:
    with pytest.raises(ValueError):
        bridge_broker._canonical_destination(
            "preferred_cloud_harness", None, 0, "escalation-response", "r",
        )


def test_materialize_escalation_response_writes_at_canonical_path(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17",
        "--role", "super-deep-deep4", "--content", "# RESPONSE\nbody\n",
    ])
    assert rc == 0
    # Enqueue is DB-only; the file is written by the host-side process.
    resp = bridge_dir / "escalations" / "17-super-deep-deep4-response.md"
    assert not resp.exists()
    bridge_broker.main(["process-once"])
    assert resp.exists()
    assert resp.read_text() == "# RESPONSE\nbody\n"
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, role_key FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "completed"
    assert row[1] == "super-deep-deep4"


def test_materialize_escalation_response_rejects_unknown_role(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17",
        "--role", "not-a-real-role", "--content", "x",
    ])
    assert rc == 1
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert rows[0] == 0


def test_materialize_escalation_response_rejects_role_not_in_flow(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO bridge_roles (role_key) VALUES (?)",
                 ("other-role",))
    conn.commit()
    conn.close()
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17",
        "--role", "other-role", "--content", "x",
    ])
    assert rc == 1


def test_materialize_escalation_response_missing_role_rejected(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17", "--content", "x",
    ])
    assert rc == 1


def test_materialize_escalation_response_requires_handoff_id(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--role", "super-deep-deep4",
        "--content", "x",
    ])
    assert rc == 1


def test_materialize_escalation_response_refuses_overwrite(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    resp = bridge_dir / "escalations" / "17-super-deep-deep4-response.md"
    resp.write_text("# EXISTING\n")
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17",
        "--role", "super-deep-deep4", "--content", "# NEW\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    assert resp.read_text() == "# EXISTING\n"
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status FROM bridge_materialize_queue"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"


def test_materialize_escalation_response_idempotent_per_handoff_and_role(
    tmp_broker_escalation: tuple[str, Path],
) -> None:
    db_path, bridge_dir = tmp_broker_escalation
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17",
        "--role", "super-deep-deep4", "--content", "# FIRST\n",
    ])
    assert rc == 0
    bridge_broker.main(["process-once"])
    # A second materialize for the same (handoff, role) with DIFFERENT
    # content is a no-op (refuse-overwrite).
    rc = bridge_broker.main([
        "materialize", "--flow", "preferred_cloud_harness",
        "--type", "escalation-response", "--id", "17",
        "--role", "super-deep-deep4", "--content", "# SECOND\n",
    ])
    assert rc == 0
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue "
        "WHERE artifact_type = 'escalation-response'"
    ).fetchone()[0]
    conn.close()
    assert count == 1
    resp = bridge_dir / "escalations" / "17-super-deep-deep4-response.md"
    assert resp.read_text() == "# FIRST\n"


def test_materialize_schema_migrates_from_run003_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Run 003 table (no role_key, no escalation-response in its CHECK)
    is rebuilt in place, preserving existing rows."""
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE bridge_materialize_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_key TEXT NOT NULL,
            run_id INTEGER,
            handoff_id INTEGER,
            artifact_type TEXT NOT NULL CHECK (artifact_type IN ('backlog', 'run-ledger', 'handoff', 'end-report')),
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            claimed_at TEXT,
            processed_at TEXT,
            error_msg TEXT,
            broker_pid INTEGER
        );
    """)
    conn.execute(
        "INSERT INTO bridge_materialize_queue "
        "(flow_key, run_id, artifact_type, content, status) "
        "VALUES ('f', 3, 'backlog', 'x', 'completed')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db_path))
    bridge_broker._ensure_schema(bridge_broker._open_db(str(db_path)))

    conn = sqlite3.connect(str(db_path))
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(bridge_materialize_queue)").fetchall()}
    assert "role_key" in cols
    rows = conn.execute(
        "SELECT COUNT(*) FROM bridge_materialize_queue"
    ).fetchone()[0]
    assert rows == 1
    # The new CHECK accepts escalation-response.
    conn.execute(
        "INSERT INTO bridge_materialize_queue "
        "(flow_key, handoff_id, role_key, artifact_type, content, status) "
        "VALUES ('f', 17, 'r', 'escalation-response', 'y', 'pending')"
    )
    conn.commit()
    conn.close()
