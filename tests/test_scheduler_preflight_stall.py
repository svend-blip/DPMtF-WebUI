"""Tests for the scheduler invariant preflight and stall wake-up (handoff 323).

The preflight guards every tick: app health, DB connectivity, and a
non-decreasing jobs row count (a decrease means production rows were
deleted — the 2026-07-27 incident class). The stall wake-up injects a
one-time prompt into the supervisor_auto session when a chain step's
nudge budget is exhausted.

All tests isolate nudge state to tmp_path — NEVER the production file.
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


def _setup_db(tmp_path):
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
    """)
    conn.commit()
    conn.close()
    return db


def _mk_sched(tmp_path):
    """Scheduler on a temp DB with ISOLATED nudge state."""
    sched = Scheduler(db_path=_setup_db(tmp_path))
    sched.nudge_state_path = tmp_path / "nudge-state.json"
    return sched


def _healthy_response():
    resp = MagicMock()
    resp.status_code = 200
    return resp


# ---------------------------------------------------------------------------
# Preflight — direct checks
# ---------------------------------------------------------------------------

def test_preflight_passes_when_healthy(tmp_path):
    sched = _mk_sched(tmp_path)
    with patch("requests.get", return_value=_healthy_response()):
        result = sched._preflight()
    assert result["passed"] is True


def test_preflight_fails_when_health_endpoint_unreachable(tmp_path):
    sched = _mk_sched(tmp_path)
    with patch("requests.get", side_effect=Exception("Connection refused")):
        result = sched._preflight()
    assert result["passed"] is False
    assert "unreachable" in result["reason"]


def test_preflight_fails_on_bad_health_status(tmp_path):
    sched = _mk_sched(tmp_path)
    resp = MagicMock()
    resp.status_code = 500
    with patch("requests.get", return_value=resp):
        result = sched._preflight()
    assert result["passed"] is False
    assert "500" in result["reason"]


def test_preflight_fails_when_jobs_count_decreases(tmp_path):
    """A row-count drop means something deleted production rows."""
    sched = _mk_sched(tmp_path)
    sched._write_nudge_state({"last_jobs_count": 10})
    # Temp DB has 0 jobs — a decrease from the persisted 10.
    with patch("requests.get", return_value=_healthy_response()):
        result = sched._preflight()
    assert result["passed"] is False
    assert "decreased" in result["reason"]


def test_preflight_persists_jobs_count_on_pass(tmp_path):
    sched = _mk_sched(tmp_path)
    repo = JobRepository(db_path=sched.repo.db_path)
    repo.create_job("flowX", "role1", "Task", "/tmp/test")
    with patch("requests.get", return_value=_healthy_response()):
        result = sched._preflight()
    assert result["passed"] is True
    assert sched._read_nudge_state().get("last_jobs_count") == 1


def test_preflight_passes_when_count_grows(tmp_path):
    sched = _mk_sched(tmp_path)
    sched._write_nudge_state({"last_jobs_count": 0})
    repo = JobRepository(db_path=sched.repo.db_path)
    repo.create_job("flowX", "role1", "Task", "/tmp/test")
    with patch("requests.get", return_value=_healthy_response()):
        result = sched._preflight()
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Preflight — tick gating
# ---------------------------------------------------------------------------

def test_tick_blocked_on_preflight_failure(tmp_path):
    """A failed preflight must prevent ANY claim or dispatch this tick."""
    sched = _mk_sched(tmp_path)
    repo = JobRepository(db_path=sched.repo.db_path)
    job_id = repo.create_job("flowX", "role1", "Task", "/tmp/test")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    with patch.object(Scheduler, "_preflight",
                      return_value={"passed": False, "reason": "health down"}):
        result = sched.tick()

    assert result["claimed"] is False
    assert result["outcome"].startswith("preflight_failed:")
    assert "health down" in result["outcome"]
    # The APPROVED job must NOT have been touched.
    assert repo.get_job(job_id).status == "APPROVED"


def test_tick_proceeds_when_preflight_passes(tmp_path):
    """Regression: a passing preflight must not block normal claiming."""
    sched = _mk_sched(tmp_path)
    repo = JobRepository(db_path=sched.repo.db_path)
    job_id = repo.create_job("flowX", "role1", "Task", "/tmp/test")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    with patch.object(Scheduler, "_preflight",
                      return_value={"passed": True, "reason": ""}):
        result = sched.tick()

    assert result["claimed"] is True
    assert result["job_id"] == job_id


# ---------------------------------------------------------------------------
# Stall wake-up
# ---------------------------------------------------------------------------

def _job(hid="42"):
    return SimpleNamespace(job_id="JOB-TEST", flow_key="supervised_review",
                           handoff_id=hid)


def test_stall_wake_up_injects_into_supervisor_session(tmp_path):
    sched = _mk_sched(tmp_path)
    role = {"tmux_session": "supervisor", "fresh_session_command": "/clear",
            "governance_file": "501_SUPERVISOR_AUTONOMOUS.md"}
    with patch("bridge_lib.load_role_from_db", return_value=role) as mock_role, \
         patch("dispatch.session_alive", return_value=True), \
         patch("dispatch.inject_prompt") as mock_inject:
        sched._record_stall_wake_up(_job(), "imple01", "review01", "42",
                                    deliverable_path="/x/results/42-result.md")

    mock_role.assert_called_once()
    assert mock_role.call_args[0][0] == "supervisor_auto"
    mock_inject.assert_called_once()
    args, kwargs = mock_inject.call_args
    assert args[0] == "supervisor"                    # target session
    prompt = args[1]
    assert "42" in prompt                             # handoff id
    assert "/x/results/42-result.md" in prompt        # actual deliverable path
    assert "501_SUPERVISOR_AUTONOMOUS.md" in prompt   # governance reference
    assert kwargs.get("fresh_session_command") == "/clear"


def test_stall_wake_up_fires_exactly_once(tmp_path):
    """The persisted marker must survive across calls AND instances."""
    sched = _mk_sched(tmp_path)
    role = {"tmux_session": "supervisor", "fresh_session_command": "/clear",
            "governance_file": "501_SUPERVISOR_AUTONOMOUS.md"}
    with patch("bridge_lib.load_role_from_db", return_value=role), \
         patch("dispatch.session_alive", return_value=True), \
         patch("dispatch.inject_prompt") as mock_inject:
        fired1 = sched._maybe_stall_wake_up(_job(), "imple01", "review01",
                                            "42", "sr:42:s2", "/x/42-result.md")
        fired2 = sched._maybe_stall_wake_up(_job(), "imple01", "review01",
                                            "42", "sr:42:s2", "/x/42-result.md")
        # New instance, same state file — marker must survive "restarts".
        sched2 = Scheduler(db_path=sched.repo.db_path)
        sched2.nudge_state_path = sched.nudge_state_path
        fired3 = sched2._maybe_stall_wake_up(_job(), "imple01", "review01",
                                             "42", "sr:42:s2", "/x/42-result.md")

    assert fired1 is True
    assert fired2 is False
    assert fired3 is False
    mock_inject.assert_called_once()


def test_stall_wake_up_dead_session_never_crashes(tmp_path):
    sched = _mk_sched(tmp_path)
    role = {"tmux_session": "supervisor", "fresh_session_command": "/clear",
            "governance_file": "501_SUPERVISOR_AUTONOMOUS.md"}
    with patch("bridge_lib.load_role_from_db", return_value=role), \
         patch("dispatch.session_alive", return_value=False), \
         patch("dispatch.inject_prompt") as mock_inject:
        sched._record_stall_wake_up(_job(), "imple01", "review01", "42",
                                    deliverable_path="/x/42-result.md")
    mock_inject.assert_not_called()


def test_stall_wake_up_missing_role_never_crashes(tmp_path):
    sched = _mk_sched(tmp_path)
    with patch("bridge_lib.load_role_from_db", return_value=None), \
         patch("dispatch.inject_prompt") as mock_inject:
        sched._record_stall_wake_up(_job(), "imple01", "review01", "42",
                                    deliverable_path="/x/42-result.md")
    mock_inject.assert_not_called()


# ---------------------------------------------------------------------------
# Nudge state persistence (isolated path)
# ---------------------------------------------------------------------------

def test_nudge_state_persistence(tmp_path):
    sched = _mk_sched(tmp_path)
    assert isinstance(sched._read_nudge_state(), dict)
    sched._record_nudge("test_key")
    assert sched._read_nudge_state().get("test_key") == 1
    sched._record_nudge("test_key")
    assert sched._read_nudge_state().get("test_key") == 2
