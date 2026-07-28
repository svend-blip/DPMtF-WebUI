"""Tests for the Job Queue scheduler (Task 3)."""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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


def test_tick_no_jobs(tmp_path):
    """Scheduler with no APPROVED jobs returns claimed=False."""
    db = _setup_db(tmp_path)
    sched = Scheduler(db_path=db)
    result = sched.tick()
    assert result["claimed"] is False
    assert result["recovered"] == 0


def test_tick_claims_and_dispatches(tmp_path):
    """Scheduler claims an APPROVED job and dispatches it."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job(
        "strict_review", "archi01", "Add feature X", "/tmp/test"
    )
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db)
    # Mock the internal methods to avoid real dispatch
    with patch.object(sched, '_preflight', return_value={'passed': True, 'reason': ''}), \
         patch.object(sched, '_dispatch', return_value={"status": "dispatched"}), \
          patch.object(sched, '_check_completion', return_value=True), \
          patch.object(sched, '_resolve_alias', return_value="archi-local"), \
          patch.object(sched, '_compile_handoff'), \
          patch.object(sched, '_resolve_context_window', return_value=131072):
        result = sched.tick()

    assert result["claimed"] is True
    assert result["outcome"] == "completed"
    
    job = repo.get_job(job_id)
    assert job.status == "COMPLETED"
    assert job.allocator_alias == "archi-local"


def test_tick_blocks_oversized_handoff(tmp_path):
    """Scheduler blocks a job that requires split."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    large_goal = "x" * 25000  # > 5000 tokens
    job_id = repo.create_job("strict_review", "archi01", large_goal, "/tmp/test")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db)
    with patch.object(sched, '_preflight', return_value={'passed': True, 'reason': ''}), \
         patch.object(sched, '_resolve_context_window', return_value=16000), \
          patch.object(sched, '_auto_split'), \
          patch.object(sched, '_resolve_alias', return_value='archi-local'):
        result = sched.tick()
    
    assert result["claimed"] is True
    assert result["outcome"] == "split"
    
    job = repo.get_job(job_id)
    assert job.status == "BLOCKED"
    assert job.context_fit_state == "SPLIT_REQUIRED"


def test_tick_writes_checkpoint(tmp_path):
    """Completed job has a checkpoint file."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "test goal", "/tmp/test")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db)
    with patch.object(sched, '_preflight', return_value={'passed': True, 'reason': ''}), \
         patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
          patch.object(sched, '_check_completion', return_value=True), \
          patch.object(sched, '_resolve_alias', return_value="archi-local"), \
          patch.object(sched, '_compile_handoff'), \
          patch.object(sched, '_resolve_context_window', return_value=131072):
        sched.tick()

    job = repo.get_job(job_id)
    assert job.checkpoint_path
    import json
    checkpoint = json.loads(Path(job.checkpoint_path).read_text())
    assert checkpoint["job_id"] == job_id
    assert checkpoint["flow_key"] == "strict_review"
    assert checkpoint["model_alias"] == "archi-local"


def test_tick_records_events(tmp_path):
    """Scheduler transitions produce job_events."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db)
    with patch.object(sched, '_preflight', return_value={'passed': True, 'reason': ''}), \
         patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
          patch.object(sched, '_check_completion', return_value=True), \
          patch.object(sched, '_resolve_alias', return_value=""), \
          patch.object(sched, '_compile_handoff'), \
          patch.object(sched, '_resolve_context_window', return_value=131072):
        sched.tick()

    events = repo.get_events(job_id)
    # create + AWAITING_APPROVAL + APPROVED + claim + RUNNING + VERIFYING + COMPLETED
    assert len(events) >= 6


def test_tick_fails_on_exception(tmp_path):
    """Scheduler transitions to FAILED on unexpected error."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    job_id = repo.create_job("strict_review", "archi01", "test", "/tmp")
    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db)
    with patch.object(sched, '_preflight', return_value={'passed': True, 'reason': ''}), \
         patch.object(sched, '_dispatch', side_effect=RuntimeError("boom")):
        result = sched.tick()

    assert "error" in result["outcome"]
    job = repo.get_job(job_id)
    assert job.status == "FAILED"
