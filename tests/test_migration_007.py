"""Test migration 007: Job Queue tables."""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config


def _db_path():
    p = config.get_db_path()
    import os
    if not os.path.isabs(p):
        p = os.path.join(str(PROJECT_ROOT), p)
    return p


def test_jobs_table_exists():
    conn = sqlite3.connect(_db_path())
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
    ).fetchone()
    conn.close()
    assert row is not None


def test_job_events_table_exists():
    conn = sqlite3.connect(_db_path())
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='job_events'"
    ).fetchone()
    conn.close()
    assert row is not None


def test_jobs_columns():
    conn = sqlite3.connect(_db_path())
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    conn.close()
    required = {
        "job_id", "workflow_run_id", "flow_key", "step_key", "role_key",
        "status", "allocator_alias", "handoff_id", "idempotency_key",
        "retry_count", "max_retries", "lease_owner", "lease_expires_at",
        "heartbeat_at", "priority", "goal", "target_project",
        "scope_version", "checkpoint_path", "context_fit_state",
        "parent_job_id", "continuation_index", "created_at", "updated_at",
    }
    assert required <= cols, f"Missing columns: {required - cols}"


def test_indexes_exist():
    conn = sqlite3.connect(_db_path())
    indexes = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()}
    conn.close()
    assert "idx_jobs_status" in indexes
    assert "idx_jobs_lease" in indexes
    assert "idx_jobs_flow" in indexes
    assert "idx_job_events_job" in indexes


def test_job_lifecycle_states_work():
    """Verify job status transitions work end-to-end."""
    conn = sqlite3.connect(_db_path())
    conn.execute(
        "INSERT INTO jobs (job_id, flow_key, role_key, goal, target_project, idempotency_key) "
        "VALUES ('TEST-007', 'strict_review', 'archi01', 'test', '/tmp/test', 'idem-test-007')"
    )
    conn.execute(
        "UPDATE jobs SET status='AWAITING_APPROVAL' WHERE job_id='TEST-007'"
    )
    conn.execute(
        "UPDATE jobs SET status='APPROVED' WHERE job_id='TEST-007'"
    )
    conn.execute(
        "INSERT INTO job_events (job_id, event_type, from_state, to_state, actor) "
        "VALUES ('TEST-007', 'transition', 'DRAFT', 'AWAITING_APPROVAL', 'test')"
    )
    row = conn.execute("SELECT status FROM jobs WHERE job_id='TEST-007'").fetchone()
    events = conn.execute("SELECT COUNT(*) FROM job_events WHERE job_id='TEST-007'").fetchone()
    # Cleanup
    conn.execute("DELETE FROM job_events WHERE job_id='TEST-007'")
    conn.execute("DELETE FROM jobs WHERE job_id='TEST-007'")
    conn.commit()
    conn.close()
    
    assert row[0] == "APPROVED"
    assert events[0] == 1
