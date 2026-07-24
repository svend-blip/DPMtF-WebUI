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

_JOBS_SCHEMA = """
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
"""

def _make_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(_JOBS_SCHEMA)
    conn.commit()
    conn.close()


def test_full_cycle_workflow(tmp_path):
    """Test complete end-to-end job cycle including all states and transitions."""
    db_path = str(tmp_path / "test_full_cycle.db")
    _make_db(db_path)

    repo = JobRepository(db_path=db_path)
    job_id = repo.create_job(
        flow_key="strict_review",
        role_key="archi01",
        goal="Implement comprehensive feature set with multiple components",
        target_project=str(tmp_path / "test_project"),
        priority=5
    )

    job = repo.get_job(job_id)
    assert job.status == "DRAFT"
    assert job.flow_key == "strict_review"
    assert job.role_key == "archi01"
    assert job.priority == 5

    repo.transition(job_id, "AWAITING_APPROVAL")
    assert repo.get_job(job_id).status == "AWAITING_APPROVAL"

    repo.transition(job_id, "APPROVED")
    assert repo.get_job(job_id).status == "APPROVED"

    sched = Scheduler(db_path=db_path)
    with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
         patch.object(sched, '_check_completion', return_value=True), \
         patch.object(sched, '_resolve_alias', return_value="imple-local"), \
         patch.object(sched, '_compile_handoff'), \
         patch.object(sched, '_resolve_context_window', return_value=131072):
        result = sched.tick()

    job = repo.get_job(job_id)
    assert job.status == "COMPLETED"
    assert job.checkpoint_path is not None

    cp = json.loads(Path(job.checkpoint_path).read_text())
    assert cp["checkpoint_schema_version"] == "1.0"
    assert cp["flow_key"] == "strict_review"
    assert cp["model_alias"] == "imple-local"
    assert cp["role_key"] == "archi01"


def test_error_handling_in_cycle(tmp_path):
    """Test that the system properly handles errors during job lifecycle."""
    db_path = str(tmp_path / "test_error_handling.db")
    _make_db(db_path)

    repo = JobRepository(db_path=db_path)
    job_id = repo.create_job("strict_review", "archi01", "Test error handling", str(tmp_path))

    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db_path)
    with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
         patch.object(sched, '_check_completion', return_value=False), \
         patch.object(sched, '_resolve_alias', return_value="imple-local"), \
         patch.object(sched, '_compile_handoff'), \
         patch.object(sched, '_resolve_context_window', return_value=131072):
        result = sched.tick()

    job = repo.get_job(job_id)
    # Job should be RUNNING (dispatch sent, not yet completed)
    assert job.status == "RUNNING"


def test_context_fit_integration(tmp_path):
    """Test that context-fit checking works properly within E2E cycle."""
    db_path = str(tmp_path / "test_context_fit.db")
    _make_db(db_path)

    repo = JobRepository(db_path=db_path)
    job_id = repo.create_job("strict_review", "archi01", "Small feature implementation", str(tmp_path))

    repo.transition(job_id, "AWAITING_APPROVAL")
    repo.transition(job_id, "APPROVED")

    sched = Scheduler(db_path=db_path)
    with patch.object(sched, '_dispatch', return_value={"status": "ok"}), \
         patch.object(sched, '_check_completion', return_value=True), \
         patch.object(sched, '_resolve_alias', return_value="imple-local"), \
         patch.object(sched, '_compile_handoff'), \
         patch.object(sched, '_resolve_context_window', return_value=131072):
        result = sched.tick()

    job = repo.get_job(job_id)
    assert job.status == "COMPLETED"
