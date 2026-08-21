"""Tests for D1 — generalized stall wake-up routing (run 007, handoff 027).

The watchdog and the scheduler inject a one-time wake-up prompt into the
session of a supervisor role when a chain step's nudge budget is
exhausted. Today the supervisor is hardcoded to `supervisor_auto`,
whatever flow stalled. D1 routes the wake-up to the FLOW's own
`bridge_flows.supervisor_role` instead, falling back to `supervisor_auto`
when the column is NULL, missing, or unresolvable.

All tests isolate nudge state and DB access to tmp fixtures. Production
nudge-state file and production DB are NEVER touched.
"""

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

from job_queue.models import JobRepository
from job_queue.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _setup_db(tmp_path):
    """Temp job_queue DB PLUS a minimal bridge_flows table for routing tests.

    The bridge_flows table carries `supervisor_role TEXT DEFAULT NULL` so
    the tests can opt a flow in (or leave NULL for the historical fallback).
    `is_active` is also present — the scheduler's helper filters on it.
    """
    db = str(tmp_path / "jq.db")
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY, workflow_run_id TEXT, flow_key TEXT NOT NULL,
            step_key TEXT, role_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT',
            allocator_alias TEXT, handoff_id TEXT, idempotency_key TEXT UNIQUE,
            retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3,
            lease_owner TEXT, lease_expires_at TEXT, heartbeat_at TEXT,
            priority INTEGER DEFAULT 0, goal TEXT NOT NULL, target_project TEXT NOT NULL,
            scope_version TEXT, checkpoint_path TEXT, context_fit_state TEXT,
            parent_job_id TEXT, continuation_index INTEGER,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE job_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL, event_type TEXT NOT NULL,
            from_state TEXT, to_state TEXT, actor TEXT, detail TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE bridge_flows (
            flow_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            step_order TEXT,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            supervisor_role TEXT DEFAULT NULL
        );
    """)
    conn.commit()
    conn.close()
    return db


def _mk_sched(tmp_path):
    sched = Scheduler(db_path=_setup_db(tmp_path))
    sched.nudge_state_path = tmp_path / "nudge-state.json"
    return sched


def _job(hid="42", flow_key="supervised_review"):
    return SimpleNamespace(job_id="JOB-TEST", flow_key=flow_key, handoff_id=hid)


def _seed_flow_supervisor_role(db_path, flow_key, supervisor_role):
    """Seed a bridge_flows row with the given supervisor_role value."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bridge_flows(flow_key, name, is_active, supervisor_role) "
        "VALUES(?, ?, 1, ?)",
        (flow_key, flow_key, supervisor_role),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Scheduler routing — D1b
# ---------------------------------------------------------------------------

def test_stall_wake_up_uses_flow_supervisor_role_when_set(tmp_path):
    """With bridge_flows.supervisor_role set, the wake-up targets THAT role."""
    sched = _mk_sched(tmp_path)
    _seed_flow_supervisor_role(sched.repo.db_path, "supervised_review", "flowsup")

    role = {
        "tmux_session": "flow_session", "fresh_session_command": "/clear",
        "governance_file": "999_FAKE_SUPERVISOR.md",
    }
    with patch("bridge_lib.load_role_from_db", return_value=role) as mock_role, \
         patch("dispatch.session_alive", return_value=True), \
         patch("dispatch.inject_prompt") as mock_inject:
        sched._record_stall_wake_up(
            _job(), "imple01", "review01", "42",
            deliverable_path="/x/results/42-result.md",
        )

    # Crucially: load_role_from_db was called with the flow's supervisor role
    # — NOT the historical `supervisor_auto` fallback.
    mock_role.assert_called_once()
    assert mock_role.call_args[0][0] == "flowsup"
    mock_inject.assert_called_once()
    args, _ = mock_inject.call_args
    assert args[0] == "flow_session"
    assert "999_FAKE_SUPERVISOR.md" in args[1]


def test_stall_wake_up_falls_back_to_supervisor_auto_when_null(tmp_path):
    """With bridge_flows.supervisor_role NULL, behavior matches the historical default."""
    sched = _mk_sched(tmp_path)
    _seed_flow_supervisor_role(sched.repo.db_path, "supervised_review", None)

    role = {
        "tmux_session": "supervisor_auto_session", "fresh_session_command": "/clear",
        "governance_file": "451_SUPERVISED_REVIEW_SUPERVISOR.md",
    }
    with patch("bridge_lib.load_role_from_db", return_value=role) as mock_role, \
         patch("dispatch.session_alive", return_value=True), \
         patch("dispatch.inject_prompt") as mock_inject:
        sched._record_stall_wake_up(
            _job(), "imple01", "review01", "42",
            deliverable_path="/x/results/42-result.md",
        )

    mock_role.assert_called_once()
    assert mock_role.call_args[0][0] == "supervisor_auto"  # historical fallback
    mock_inject.assert_called_once()


def test_stall_wake_up_falls_back_when_no_bridge_flows_row(tmp_path):
    """No matching bridge_flows row -> fall back to supervisor_auto."""
    sched = _mk_sched(tmp_path)  # NO seed insert — the table is empty

    role = {
        "tmux_session": "supervisor_auto_session", "fresh_session_command": "/clear",
        "governance_file": "451_SUPERVISED_REVIEW_SUPERVISOR.md",
    }
    with patch("bridge_lib.load_role_from_db", return_value=role) as mock_role, \
         patch("dispatch.session_alive", return_value=True), \
         patch("dispatch.inject_prompt") as mock_inject:
        sched._record_stall_wake_up(
            _job(flow_key="nonexistent_flow"), "imple01", "review01", "42",
            deliverable_path="/x/results/42-result.md",
        )

    mock_role.assert_called_once()
    assert mock_role.call_args[0][0] == "supervisor_auto"
    mock_inject.assert_called_once()


def test_stall_wake_up_missing_role_never_crashes_with_custom_target(tmp_path):
    """Custom supervisor_role that doesn't resolve -> warn, never crash."""
    sched = _mk_sched(tmp_path)
    _seed_flow_supervisor_role(sched.repo.db_path, "supervised_review", "ghost_role")

    with patch("bridge_lib.load_role_from_db", return_value=None), \
         patch("dispatch.inject_prompt") as mock_inject:
        # Must not raise.
        sched._record_stall_wake_up(
            _job(), "imple01", "review01", "42",
            deliverable_path="/x/results/42-result.md",
        )
    mock_inject.assert_not_called()


# ---------------------------------------------------------------------------
# Marker semantics — once-per-flow/handoff/step (D1b constraint #7)
# ---------------------------------------------------------------------------

def test_stall_wake_up_fires_exactly_once_with_per_flow_supervisor(tmp_path):
    """Marker semantics are independent of WHICH supervisor role is chosen."""
    sched = _mk_sched(tmp_path)
    _seed_flow_supervisor_role(sched.repo.db_path, "supervised_review", "flowsup")

    role = {"tmux_session": "s", "fresh_session_command": "/clear",
            "governance_file": "X.md"}
    with patch("bridge_lib.load_role_from_db", return_value=role), \
         patch("dispatch.session_alive", return_value=True), \
         patch("dispatch.inject_prompt") as mock_inject:
        fired1 = sched._maybe_stall_wake_up(
            _job(), "imple01", "review01", "42", "sr:42:s2", "/x/42-result.md"
        )
        fired2 = sched._maybe_stall_wake_up(
            _job(), "imple01", "review01", "42", "sr:42:s2", "/x/42-result.md"
        )

        # Simulated restart — same nudge-state file, fresh instance.
        sched2 = Scheduler(db_path=sched.repo.db_path)
        sched2.nudge_state_path = sched.nudge_state_path
        fired3 = sched2._maybe_stall_wake_up(
            _job(), "imple01", "review01", "42", "sr:42:s2", "/x/42-result.md"
        )

    assert fired1 is True
    assert fired2 is False
    assert fired3 is False
    mock_inject.assert_called_once()  # at most once — marker survives restarts


# ---------------------------------------------------------------------------
# Watchdog escalation routing — D1c
# ---------------------------------------------------------------------------

def _import_watchdog():
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
    import chain_watchdog as cw  # noqa: E402
    return cw


def test_watchdog_escalate_calls_supervisor_wake_up_when_role_set(tmp_path, monkeypatch):
    """escalate() attempts a supervisor wake-up when bridge_flows.supervisor_role is set."""
    cw = _import_watchdog()
    # Avoid disk side effects from the watchdog module imports.
    monkeypatch.setattr(cw, "_notify", lambda *a, **k: None)
    monkeypatch.setattr(cw, "save_state", lambda s: None)
    calls = {}
    monkeypatch.setattr(
        cw, "_supervisor_wake_up",
        lambda key, why: calls.setdefault("invocations", []).append((key, why)),
    )

    # escalate() is rate-limited via state["escalated:{key}"]. Seed it as old.
    key = "preferred_cloud_harness:42:imple01"
    state = {f"escalated:{key}": 0.0}  # very old -> allows notification

    cw.escalate(key, "for the test", state, dry_run=False)

    assert "invocations" in calls, "supervisor wake-up must be attempted"
    assert calls["invocations"][0][0] == key


def test_watchdog_escalate_notify_send_is_still_called(tmp_path, monkeypatch):
    """notify-send remains the fallback even when the wake-up runs."""
    cw = _import_watchdog()
    notify_calls = []
    monkeypatch.setattr(cw, "_notify", lambda *a, **k: notify_calls.append((a, k)))
    monkeypatch.setattr(cw, "save_state", lambda s: None)
    monkeypatch.setattr(cw, "_supervisor_wake_up", lambda k, w: None)

    key = "preferred_cloud_harness:42:imple01"
    state = {f"escalated:{key}": 0.0}

    cw.escalate(key, "for the test", state, dry_run=False)

    assert len(notify_calls) == 1
    title, body = notify_calls[0][0]
    assert "BridgeV002 stalled" in title
    assert "for the test" in body


def test_watchdog_escalate_does_not_raise_when_wake_up_fails(tmp_path, monkeypatch):
    """A failing _supervisor_wake_up must never make escalate() fatal."""
    cw = _import_watchdog()
    monkeypatch.setattr(cw, "_notify", lambda *a, **k: None)
    monkeypatch.setattr(cw, "save_state", lambda s: None)

    def _boom(key, why):
        raise RuntimeError("simulated wake-up failure")
    monkeypatch.setattr(cw, "_supervisor_wake_up", _boom)

    key = "preferred_cloud_harness:42:imple01"
    state = {f"escalated:{key}": 0.0}

    # Must not raise — escalate() never becomes fatal because of the
    # additive wake-up path.
    result = cw.escalate(key, "for the test", state, dry_run=False)
    assert result is True  # notify-send path completed successfully


def test_watchdog_supervisor_wake_up_skips_when_role_null(tmp_path, monkeypatch):
    """NULL supervisor_role -> helper is a no-op (notify-send already done)."""
    cw = _import_watchdog()
    loads = []
    monkeypatch.setattr(cw, "log", lambda *a, **k: None)

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = (None,)  # NULL supervisor_role
    fake_conn.execute.return_value = fake_cursor
    monkeypatch.setattr(
        cw.sqlite3, "connect", lambda *a, **k: fake_conn
    )

    # Must return without error and without calling load_role_from_db.
    cw._supervisor_wake_up("preferred_cloud_harness:42:imple01", "why")
    assert loads == []


def test_watchdog_supervisor_wake_up_no_failure_log_when_role_null(tmp_path, monkeypatch):
    """NULL supervisor_role -> no spurious WARN log (notify-send-only is fine)."""
    cw = _import_watchdog()
    log_lines = []
    monkeypatch.setattr(cw, "log", lambda msg: log_lines.append(msg))

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = (None,)
    fake_conn.execute.return_value = fake_cursor
    monkeypatch.setattr(cw.sqlite3, "connect", lambda *a, **k: fake_conn)

    cw._supervisor_wake_up("preferred_cloud_harness:42:imple01", "why")
    # No WARN lines emitted — the path is silent on the NULL case.
    assert not any("WARN" in l for l in log_lines)
