"""Tests for the Job Queue spike (Task 4.2)."""
import sqlite3
import sys
import os
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))

from job_queue_spike import (
    create_test_db, create_job, transition_job, claim_job,
    recover_expired_leases, heartbeat, is_legal_transition,
    IllegalTransitionError, STATES, LEGAL_TRANSITIONS, TERMINAL_STATES,
)


def test_legal_transitions():
    """Legal transitions must follow the state machine."""
    assert is_legal_transition("DRAFT", "AWAITING_APPROVAL")
    assert is_legal_transition("AWAITING_APPROVAL", "APPROVED")
    assert is_legal_transition("APPROVED", "QUEUED")
    assert is_legal_transition("QUEUED", "RUNNING")
    assert is_legal_transition("RUNNING", "VERIFYING")
    assert is_legal_transition("VERIFYING", "COMPLETED")


def test_illegal_transitions_rejected():
    """Illegal transitions must be rejected."""
    assert not is_legal_transition("DRAFT", "RUNNING")
    assert not is_legal_transition("DRAFT", "COMPLETED")
    assert not is_legal_transition("RUNNING", "DRAFT")
    assert not is_legal_transition("COMPLETED", "RUNNING")


def test_transition_service_records_event(tmp_path):
    """Transition service must update status and record an event."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    
    transition_job(conn, "JOB-001", "AWAITING_APPROVAL")
    
    job = conn.execute("SELECT status FROM jobs WHERE job_id='JOB-001'").fetchone()
    assert job[0] == "AWAITING_APPROVAL"
    
    events = conn.execute("SELECT * FROM job_events WHERE job_id='JOB-001'").fetchall()
    assert len(events) == 1
    assert events[0]["to_state"] == "AWAITING_APPROVAL"
    conn.close()


def test_illegal_transition_raises(tmp_path):
    """Illegal transition must raise and not change state."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    
    try:
        transition_job(conn, "JOB-001", "RUNNING")
        assert False, "Should have raised"
    except IllegalTransitionError:
        pass
    
    # State unchanged
    job = conn.execute("SELECT status FROM jobs WHERE job_id='JOB-001'").fetchone()
    assert job[0] == "DRAFT"
    conn.close()


def test_atomic_claim_single_worker(tmp_path):
    """One worker claims the oldest APPROVED job."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    create_job(conn, "JOB-002")
    
    # Move both to APPROVED
    transition_job(conn, "JOB-001", "AWAITING_APPROVAL")
    transition_job(conn, "JOB-001", "APPROVED")
    transition_job(conn, "JOB-002", "AWAITING_APPROVAL")
    transition_job(conn, "JOB-002", "APPROVED")
    
    # Claim — should get JOB-001 (oldest)
    claimed = claim_job(conn, "worker-1")
    assert claimed == "JOB-001"
    
    # JOB-001 is now QUEUED
    job = conn.execute("SELECT status, lease_owner FROM jobs WHERE job_id='JOB-001'").fetchone()
    assert job[0] == "QUEUED"
    assert job[1] == "worker-1"
    
    # JOB-002 is still APPROVED
    job2 = conn.execute("SELECT status FROM jobs WHERE job_id='JOB-002'").fetchone()
    assert job2[0] == "APPROVED"
    conn.close()


def test_atomic_claim_two_workers_no_double_claim(tmp_path):
    """Two workers cannot claim the same job."""
    db_path = str(tmp_path / "jq.db")
    conn = create_test_db(db_path)
    create_job(conn, "JOB-001")
    transition_job(conn, "JOB-001", "AWAITING_APPROVAL")
    transition_job(conn, "JOB-001", "APPROVED")
    conn.close()
    
    # Use separate connections — SQLite BEGIN IMMEDIATE serializes access
    results = {"worker-1": None, "worker-2": None}
    errors = {"worker-1": None, "worker-2": None}
    
    def claim(worker_id):
        try:
            wconn = sqlite3.connect(db_path, timeout=5)
            results[worker_id] = claim_job(wconn, worker_id)
            wconn.close()
        except Exception as e:
            errors[worker_id] = e
    
    t1 = threading.Thread(target=claim, args=("worker-1",))
    t2 = threading.Thread(target=claim, args=("worker-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Exactly one worker should have claimed the job
    claims = [r for r in results.values() if r is not None]
    assert len(claims) == 1, f"Expected 1 claim, got {claims}"
    assert claims[0] == "JOB-001"


def test_lease_recovery(tmp_path):
    """Expired leases are recovered and re-queued."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    transition_job(conn, "JOB-001", "AWAITING_APPROVAL")
    transition_job(conn, "JOB-001", "APPROVED")
    
    # Claim with 1 second lease
    claimed = claim_job(conn, "worker-1", lease_seconds=1)
    assert claimed == "JOB-001"
    
    # Wait for lease to expire
    time.sleep(2)
    
    # Recover
    recovered = recover_expired_leases(conn)
    assert recovered == 1
    
    # Job is back to APPROVED
    job = conn.execute("SELECT status, retry_count FROM jobs WHERE job_id='JOB-001'").fetchone()
    assert job[0] == "APPROVED"
    assert job[1] == 1
    conn.close()


def test_heartbeat_extends_lease(tmp_path):
    """Heartbeat extends the lease."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    transition_job(conn, "JOB-001", "AWAITING_APPROVAL")
    transition_job(conn, "JOB-001", "APPROVED")
    claim_job(conn, "worker-1", lease_seconds=10)
    
    # Get original lease expiry
    job = conn.execute("SELECT lease_expires_at FROM jobs WHERE job_id='JOB-001'").fetchone()
    original = job[0]
    
    # Heartbeat with longer lease
    heartbeat(conn, "JOB-001", "worker-1", lease_seconds=300)
    
    job = conn.execute("SELECT lease_expires_at FROM jobs WHERE job_id='JOB-001'").fetchone()
    extended = job[0]
    
    assert extended > original
    conn.close()


def test_idempotency_key_prevents_duplicates(tmp_path):
    """Same idempotency key cannot create duplicate jobs."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    
    try:
        create_job(conn, "JOB-001")  # Same job_id / idempotency key
        assert False, "Should have raised"
    except sqlite3.IntegrityError:
        pass
    conn.close()


def test_full_lifecycle(tmp_path):
    """Full lifecycle: DRAFT → AWAITING_APPROVAL → APPROVED → QUEUED → RUNNING → VERIFYING → COMPLETED."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001")
    
    for to_state in ["AWAITING_APPROVAL", "APPROVED", "QUEUED", "RUNNING", "VERIFYING", "COMPLETED"]:
        transition_job(conn, "JOB-001", to_state)
    
    job = conn.execute("SELECT status FROM jobs WHERE job_id='JOB-001'").fetchone()
    assert job[0] == "COMPLETED"
    
    events = conn.execute("SELECT * FROM job_events WHERE job_id='JOB-001' ORDER BY event_id").fetchall()
    assert len(events) == 6  # 6 transitions
    conn.close()


def test_allocator_alias_stored_on_job(tmp_path):
    """Jobs must store the allocator alias for model resolution."""
    conn = create_test_db(str(tmp_path / "jq.db"))
    create_job(conn, "JOB-001", allocator_alias="archi-local")
    
    job = conn.execute("SELECT allocator_alias FROM jobs WHERE job_id='JOB-001'").fetchone()
    assert job[0] == "archi-local"
    conn.close()


def test_terminal_states_have_no_outgoing_transitions():
    """Terminal states must not have outgoing transitions."""
    for state in TERMINAL_STATES:
        assert LEGAL_TRANSITIONS.get(state, []) == [], f"{state} should be terminal"
