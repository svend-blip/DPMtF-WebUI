"""Complete end-to-end integration test that validates the full create-to-completion workflow."""
import sys
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
sys.path.insert(0, str(PROJECT_ROOT))

from job_queue.models import JobRepository
from job_queue.scheduler import Scheduler

import pytest


@pytest.fixture(autouse=True)
def _preflight_ok():
    """These tests exercise claiming/completion, not the invariant preflight.
    The real preflight needs a live health endpoint — bypass it here; the
    preflight itself is covered by test_scheduler_preflight_stall.py."""
    with patch.object(Scheduler, "_preflight",
                      return_value={"passed": True, "reason": ""}):
        yield

def test_full_create_to_completion_workflow(tmp_path):
    """Test the complete end-to-end workflow from job creation to completion."""

    # Setup temporary database
    db_path = str(tmp_path / "test_complete_e2e.db")
    conn = sqlite3.connect(db_path)
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
    
    try:
        # Create a job for imple01 in strict_review flow
        repo = JobRepository(db_path=db_path)
        job_id = repo.create_job("strict_review", "archi01", "Implement feature X", "/tmp/test_project")
        
        # Verify job was created with correct initial state and details
        job = repo.get_job(job_id)
        assert job.status == "DRAFT"
        assert job.flow_key == "strict_review"
        assert job.role_key == "archi01"
        assert job.goal == "Implement feature X"
        
        # Transition to AWAITING_APPROVAL
        repo.transition(job_id, "AWAITING_APPROVAL")
        job = repo.get_job(job_id)
        assert job.status == "AWAITING_APPROVAL"
        
        # Transition to APPROVED 
        repo.transition(job_id, "APPROVED")
        job = repo.get_job(job_id)
        assert job.status == "APPROVED"
        
        # Run scheduler tick to dispatch and complete the job
        sched = Scheduler(db_path=db_path)
        
        # Mock key functions for a successful completion with proper transitions
        with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
             patch.object(sched, '_check_completion', return_value=True), \
             patch.object(sched, '_resolve_alias', return_value="imple-local"), \
             patch.object(sched, '_compile_handoff'), \
             patch.object(sched, '_resolve_context_window', return_value=131072):
            result = sched.tick()
            
        # Verify job completed successfully 
        job = repo.get_job(job_id)
        assert job.status == "COMPLETED"
        assert job.checkpoint_path is not None
        
        # Validate checkpoint content
        cp = json.loads(Path(job.checkpoint_path).read_text())
        assert cp["checkpoint_schema_version"] == "1.0"
        assert cp["flow_key"] == "strict_review"
        assert cp["model_alias"] == "imple-local"
        assert cp["role_key"] == "archi01"
        

        
    finally:
        pass  # tmp_path auto-cleans

def test_multiple_jobs_workflow(tmp_path):
    """Test multiple jobs in sequence to verify complete workflow."""

    # Setup temporary database
    db_path = str(tmp_path / "test_multiple_jobs.db")
    conn = sqlite3.connect(db_path)
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
    
    try:
        # Create multiple jobs
        repo = JobRepository(db_path=db_path)
        
        # Create first job
        job1_id = repo.create_job("strict_review", "archi01", "First task", "/tmp/test_project")
        repo.transition(job1_id, "AWAITING_APPROVAL")
        repo.transition(job1_id, "APPROVED")
        
        # Create second job
        job2_id = repo.create_job("strict_review", "archi01", "Second task", "/tmp/test_project") 
        repo.transition(job2_id, "AWAITING_APPROVAL")
        repo.transition(job2_id, "APPROVED")
        
        # Run scheduler to complete first job
        sched = Scheduler(db_path=db_path)
        
        with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
             patch.object(sched, '_check_completion', return_value=True), \
             patch.object(sched, '_resolve_alias', return_value="imple-local"), \
             patch.object(sched, '_compile_handoff'), \
             patch.object(sched, '_resolve_context_window', return_value=131072):
            
            # Complete first job
            result1 = sched.tick()
            assert result1["claimed"]  # First job should be claimed
            
            # Complete second job
            result2 = sched.tick()  
            assert result2["claimed"]  # Second job should be claimed
            
        # Verify both jobs completed
        job1 = repo.get_job(job1_id)
        job2 = repo.get_job(job2_id)
        assert job1.status == "COMPLETED"
        assert job2.status == "COMPLETED"
        
    finally:
        pass  # tmp_path auto-cleans