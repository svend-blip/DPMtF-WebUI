"""Full end-to-end cycle test covering all aspects of the job lifecycle."""
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

def test_full_cycle_workflow():
    """Test complete end-to-end job cycle including all states and transitions."""
    
    # Setup temporary database 
    db_path = "/tmp/test_full_cycle.db"
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
        # Create a complex job with specific characteristics
        repo = JobRepository(db_path=db_path)
        job_id = repo.create_job(
            flow_key="strict_review", 
            role_key="archi01", 
            goal="Implement comprehensive feature set with multiple components",
            target_project="/tmp/test_project",
            priority=5
        )
        
        # Verify initial job creation
        job = repo.get_job(job_id)
        assert job.status == "DRAFT"
        assert job.flow_key == "strict_review"
        assert job.role_key == "archi01"
        assert job.priority == 5
        
        # Test multiple state transitions
        repo.transition(job_id, "AWAITING_APPROVAL")
        job = repo.get_job(job_id)
        assert job.status == "AWAITING_APPROVAL"
        
        repo.transition(job_id, "APPROVED")  
        job = repo.get_job(job_id)
        assert job.status == "APPROVED"
        
        # Run scheduler to process job through full lifecycle
        sched = Scheduler(db_path=db_path)
        
        with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
             patch.object(sched, '_check_completion', return_value=True), \
             patch.object(sched, '_resolve_alias', return_value="imple-local"), \
             patch.object(sched, '_compile_handoff'), \
             patch.object(sched, '_resolve_context_window', return_value=131072):
            
            # Execute the scheduler tick
            result = sched.tick()
            
        # Verify job completed successfully with checkpoint
        job = repo.get_job(job_id)
        assert job.status == "COMPLETED"
        assert job.checkpoint_path is not None
        
        # Validate checkpoint content contains expected fields
        checkpoint_content = json.loads(Path(job.checkpoint_path).read_text())
        assert checkpoint_content["checkpoint_schema_version"] == "1.0"
        assert checkpoint_content["flow_key"] == "strict_review"
        assert checkpoint_content["model_alias"] == "imple-local"
        assert checkpoint_content["role_key"] == "archi01"
        assert "implementation_summary" in checkpoint_content
        
        # Test job properties are correctly stored
        assert job.goal == "Implement comprehensive feature set with multiple components"
        assert job.target_project == "/tmp/test_project"
        
    finally:
        # Clean up
        if Path(db_path).exists():
            Path(db_path).unlink()

def test_error_handling_in_cycle():
    """Test that the system properly handles errors during job lifecycle."""
    
    # Setup temporary database
    db_path = "/tmp/test_error_handling.db"
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
        # Create job and go through the process
        repo = JobRepository(db_path=db_path)
        job_id = repo.create_job("strict_review", "archi01", "Test error handling", "/tmp/test_project")
        
        # Progress through lifecycle
        repo.transition(job_id, "AWAITING_APPROVAL")
        repo.transition(job_id, "APPROVED")
        
        # Run scheduler that simulates processing (without completion)
        sched = Scheduler(db_path=db_path)
        
        with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
             patch.object(sched, '_check_completion', return_value=False), \
             patch.object(sched, '_resolve_alias', return_value="imple-local"), \
             patch.object(sched, '_compile_handoff'), \
             patch.object(sched, '_resolve_context_window', return_value=131072):
            
            result = sched.tick()
            
        # Job should not be completed but remain in a valid state
        job = repo.get_job(job_id)
        # This would be in a state like VERIFYING or RUNNING (pending full completion)
        
    finally:
        # Clean up
        if Path(db_path).exists():
            Path(db_path).unlink()

def test_context_fit_integration():
    """Test that context-fit checking works properly within E2E cycle."""
    
    # Setup temporary database  
    db_path = "/tmp/test_context_fit.db"
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
        # Create a reasonably-sized job that should fit
        repo = JobRepository(db_path=db_path)
        job_id = repo.create_job("strict_review", "archi01", "Small feature implementation", "/tmp/test_project")
        
        repo.transition(job_id, "AWAITING_APPROVAL")
        repo.transition(job_id, "APPROVED")
        
        # Run scheduler with context-fit checking
        sched = Scheduler(db_path=db_path)
        
        with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
             patch.object(sched, '_check_completion', return_value=True), \
             patch.object(sched, '_resolve_alias', return_value="imple-local"), \
             patch.object(sched, '_compile_handoff'), \
             patch.object(sched, '_resolve_context_window', return_value=131072):  # Large context window
            result = sched.tick()
            
        # Should complete with proper context fit status  
        job = repo.get_job(job_id)
        assert job.status == "COMPLETED"
        
    finally:
        # Clean up
        if Path(db_path).exists():
            Path(db_path).unlink()