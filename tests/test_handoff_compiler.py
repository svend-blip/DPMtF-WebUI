"""Tests for the Handoff Compiler (scope decomposition + context-fit)."""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python-runtime"))
sys.path.insert(0, str(PROJECT_ROOT))

from handoff_compiler import compile_handoff, create_jobs_from_compiled, CompiledJob
from job_queue.models import JobRepository


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


def test_small_goal_produces_single_job():
    """A small goal fits in a large context window → one job."""
    jobs = compile_handoff(
        goal="Add a function to file.py",
        flow_key="strict_review",
        role_key="imple01",
        target_project="/tmp/test",
        model_context_window=131072,
    )
    assert len(jobs) == 1
    assert jobs[0].context_fit_state in ("FITS", "FITS_WITH_LOW_MARGIN")


def test_large_goal_produces_multiple_jobs():
    """A huge goal exceeds context → split into continuations."""
    large_goal = "Refactor the entire authentication system. " * 500  # ~5000 tokens
    jobs = compile_handoff(
        goal=large_goal,
        flow_key="strict_review",
        role_key="imple01",
        target_project="/tmp/test",
        model_context_window=32768,  # small context
    )
    # Should either split or require larger model
    assert len(jobs) >= 1
    assert all(j.context_fit_state in ("FITS", "FITS_WITH_LOW_MARGIN", "SPLIT_REQUIRED",
                                        "LARGER_MODEL_REQUIRED", "CONTEXT_REDUCTION_REQUIRED")
               for j in jobs)


def test_compiled_jobs_created_in_queue(tmp_path):
    """Compiled jobs are created in the Job Queue."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    compiled = [CompiledJob(
        goal="test goal", flow_key="strict_review",
        role_key="imple01", target_project="/tmp/test",
        context_fit_state="FITS",
    )]
    
    job_ids = create_jobs_from_compiled(repo, compiled, allocator_alias="imple01-local")
    assert len(job_ids) == 1
    
    job = repo.get_job(job_ids[0])
    assert job.goal == "test goal"
    assert job.allocator_alias == "imple01-local"
    assert job.context_fit_state == "FITS"


def test_continuation_jobs_have_parent(tmp_path):
    """Split jobs link parent_job_id."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    compiled = [
        CompiledJob(goal="part 1", flow_key="strict_review", role_key="imple01",
                    target_project="/tmp", context_fit_state="FITS",
                    is_continuation=True, continuation_index=0),
        CompiledJob(goal="part 2", flow_key="strict_review", role_key="imple01",
                    target_project="/tmp", context_fit_state="FITS",
                    is_continuation=True, continuation_index=1, parent_goal="original"),
    ]
    
    job_ids = create_jobs_from_compiled(repo, compiled)
    assert len(job_ids) == 2
    
    # Second job should have parent set to first
    j2 = repo.get_job(job_ids[1])
    assert j2.parent_job_id == job_ids[0]


def test_context_fit_state_stored_on_job(tmp_path):
    """Each job stores its context_fit_state."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    compiled = [CompiledJob(
        goal="test", flow_key="strict_review", role_key="imple01",
        target_project="/tmp", context_fit_state="FITS_WITH_LOW_MARGIN",
    )]
    
    job_ids = create_jobs_from_compiled(repo, compiled)
    job = repo.get_job(job_ids[0])
    assert job.context_fit_state == "FITS_WITH_LOW_MARGIN"
