"""Tests for Job Queue models (Task 2)."""
import sqlite3
import sys
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

from job_queue.models import (
    Job, JobRepository, is_legal_transition, IllegalTransitionError,
    STATES, LEGAL_TRANSITIONS, TERMINAL_STATES,
)


def _repo(tmp_path):
    """Create a fresh test DB with jobs + job_events tables."""
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
    return JobRepository(db_path=db)


def test_create_and_get_job(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job(
        flow_key="strict_review", role_key="archi01",
        goal="Add feature X", target_project="/tmp/test"
    )
    job = repo.get_job(job_id)
    assert job is not None
    assert job.status == "DRAFT"
    assert job.goal == "Add feature X"


def test_legal_transitions():
    assert is_legal_transition("DRAFT", "AWAITING_APPROVAL")
    assert is_legal_transition("APPROVED", "QUEUED")
    assert is_legal_transition("RUNNING", "VERIFYING")


def test_illegal_transition_rejected():
    assert not is_legal_transition("DRAFT", "RUNNING")
    assert not is_legal_transition("COMPLETED", "RUNNING")


def test_transition_records_event(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL", actor="human")
    
    events = repo.get_events(job_id)
    assert len(events) == 2  # create + transition
    assert events[1]["to_state"] == "AWAITING_APPROVAL"


def test_illegal_transition_raises(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    try:
        repo.transition(job_id, "RUNNING")
        assert False, "Should raise"
    except IllegalTransitionError:
        pass
    # State unchanged
    assert repo.get_job(job_id).status == "DRAFT"


def test_claim_picks_oldest_approved(tmp_path):
    repo = _repo(tmp_path)
    j1 = repo.create_job("strict_review", "archi01", "g1", "/tmp")
    j2 = repo.create_job("strict_review", "archi01", "g2", "/tmp")
    repo.transition(j1, "AWAITING_APPROVAL")
    repo.transition(j1, "APPROVED")
    repo.transition(j2, "AWAITING_APPROVAL")
    repo.transition(j2, "APPROVED")
    
    claimed = repo.claim("worker-1")
    assert claimed is not None
    assert claimed.job_id == j1  # oldest first


def test_claim_returns_none_when_empty(tmp_path):
    repo = _repo(tmp_path)
    assert repo.claim("worker-1") is None


def test_atomic_claim_two_workers(tmp_path):
    db = str(tmp_path / "jq.db")
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    
    results = {"w1": None, "w2": None}
    def claim(wid):
        r = JobRepository(db_path=db)
        try:
            results[wid] = r.claim(wid)
        except Exception:
            results[wid] = None
    
    t1 = threading.Thread(target=claim, args=("w1",))
    t2 = threading.Thread(target=claim, args=("w2",))
    t1.start(); t2.start()
    t1.join(); t2.join()
    
    claims = [r for r in results.values() if r is not None]
    assert len(claims) == 1


def test_lease_recovery(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    repo.claim("worker-1", lease_seconds=1)
    
    time.sleep(2)
    recovered = repo.recover_expired_leases()
    assert recovered == 1
    job = repo.get_job(job_id)
    assert job.status == "APPROVED"
    assert job.retry_count == 1


def test_heartbeat_extends_lease(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    repo.claim("worker-1", lease_seconds=10)
    
    job_before = repo.get_job(job_id)
    repo.heartbeat(job_id, "worker-1", lease_seconds=300)
    job_after = repo.get_job(job_id)
    assert job_after.lease_expires_at > job_before.lease_expires_at


def test_idempotency_key_prevents_duplicates(tmp_path):
    repo = _repo(tmp_path)
    repo.create_job("strict_review", "archi01", "g1", "/tmp", idempotency_key="key-1")
    try:
        repo.create_job("strict_review", "archi01", "g2", "/tmp", idempotency_key="key-1")
        assert False
    except sqlite3.IntegrityError:
        pass


def test_full_lifecycle(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    for to in ["AWAITING_APPROVAL", "APPROVED", "QUEUED", "RUNNING", "VERIFYING", "COMPLETED"]:
        repo.transition(job_id, to)
    assert repo.get_job(job_id).status == "COMPLETED"
    events = repo.get_events(job_id)
    assert len(events) == 7  # create + 6 transitions


def test_update_fields(tmp_path):
    repo = _repo(tmp_path)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.update(job_id, allocator_alias="archi-local", context_fit_state="FITS")
    job = repo.get_job(job_id)
    assert job.allocator_alias == "archi-local"
    assert job.context_fit_state == "FITS"


def test_list_jobs_by_status(tmp_path):
    repo = _repo(tmp_path)
    j1 = repo.create_job("strict_review", "archi01", "g1", "/tmp")
    j2 = repo.create_job("strict_review", "archi01", "g2", "/tmp")
    repo.transition(j1, "AWAITING_APPROVAL")
    repo.transition(j1, "APPROVED")
    
    approved = repo.list_jobs(status="APPROVED")
    drafts = repo.list_jobs(status="DRAFT")
    assert len(approved) == 1
    assert len(drafts) == 1


def test_terminal_states_empty():
    for s in TERMINAL_STATES:
        assert LEGAL_TRANSITIONS.get(s, []) == []
