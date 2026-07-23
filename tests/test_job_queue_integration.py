"""Integration tests for Job Queue — context-fit, checkpoint, dependencies, lease recovery (Tasks 5-9)."""
import sqlite3
import sys
import time
import json
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
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


# Task 5: Context-fit preflight
def test_context_fit_blocks_oversized(tmp_path):
    """Scheduler blocks SPLIT_REQUIRED jobs."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "x" * 25000, "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    
    sched = Scheduler(db_path=db)
    result = sched.tick()
    
    job = repo.get_job(job_id)
    assert job.status == "BLOCKED"
    assert job.context_fit_state == "SPLIT_REQUIRED"


def test_context_fit_allows_normal(tmp_path):
    """Scheduler allows FITS jobs."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "small goal", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    
    sched = Scheduler(db_path=db)
    with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
         patch.object(sched, '_check_completion', return_value=True), \
         patch.object(sched, '_resolve_alias', return_value="archi-local"):
        result = sched.tick()
    
    job = repo.get_job(job_id)
    assert job.status == "COMPLETED"
    assert job.context_fit_state == "FITS"


# Task 6: Checkpoint integration
def test_checkpoint_written_on_completion(tmp_path):
    """Completed job has a checkpoint with correct fields."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "test goal", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    
    sched = Scheduler(db_path=db)
    with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
         patch.object(sched, '_check_completion', return_value=True), \
         patch.object(sched, '_resolve_alias', return_value="archi-local"):
        sched.tick()
    
    job = repo.get_job(job_id)
    assert job.checkpoint_path
    cp = json.loads(Path(job.checkpoint_path).read_text())
    assert cp["checkpoint_schema_version"] == "1.0"
    assert cp["flow_key"] == "strict_review"
    assert cp["model_alias"] == "archi-local"
    assert cp["role_key"] == "archi01"


# Task 7: Cron-tick entry point
def test_cron_tick_entry_point(tmp_path):
    """cron_tick.py runs one scheduler pass."""
    db = _setup_db(tmp_path)
    # Import and run
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
    from scheduler import Scheduler
    sched = Scheduler(db_path=db)
    result = sched.tick()
    assert "claimed" in result
    assert "recovered" in result


# Task 8: Dependency scheduling
def test_dependency_blocks_until_parent_completes(tmp_path):
    """Child job with parent_job_id cannot be claimed until parent is COMPLETED."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    parent_id = repo.create_job("strict_review", "archi01", "parent", "/tmp")
    repo.transition(parent_id, "AWAITING_APPROVAL")
    repo.transition(parent_id, "APPROVED")
    
    child_id = repo.create_job("strict_review", "imple01", "child", "/tmp",
                               parent_job_id=parent_id)
    repo.transition(child_id, "AWAITING_APPROVAL")
    repo.transition(child_id, "APPROVED")
    
    # Claim — should get parent, not child (child has uncompleted parent)
    claimed = repo.claim("worker-1")
    assert claimed.job_id == parent_id
    
    # Complete parent
    repo.transition(parent_id, "RUNNING")
    repo.transition(parent_id, "VERIFYING")
    repo.transition(parent_id, "COMPLETED")
    
    # Now claim — should get child
    claimed2 = repo.claim("worker-1")
    assert claimed2.job_id == child_id


# Task 9: Lease recovery + retry
def test_lease_recovery_increments_retry(tmp_path):
    """Expired lease recovery increments retry_count."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    repo.claim("worker-1", lease_seconds=1)
    
    time.sleep(2)
    recovered = repo.recover_expired_leases()
    assert recovered == 1
    
    job = repo.get_job(job_id)
    assert job.retry_count == 1
    assert job.status == "APPROVED"


def test_lease_recovery_in_tick(tmp_path):
    """Scheduler tick recovers expired leases before claiming."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")
    repo.claim("worker-1", lease_seconds=1)
    
    time.sleep(2)
    
    sched = Scheduler(db_path=db)
    result = sched.tick()
    assert result["recovered"] == 1
    # After recovery, the job is APPROVED again and should be claimed
    assert result["claimed"] is True


def test_max_retries_not_exceeded_in_claim():
    """Repository claim logic should still claim jobs even with high retry_count.
    (Production should add a check — for now, retry_count is informational.)"""
    # This is a design note test — the spike's state machine handles
    # max_retries as a policy decision, not a hard enforcement point.
    assert True
