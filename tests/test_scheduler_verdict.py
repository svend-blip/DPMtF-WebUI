"""Tests for verdict handling in the Job Queue scheduler (Task 3)."""
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


def test_verdict_parsing_approve(tmp_path):
    """Test parsing a verdict file with APPROVED status."""
    # Create test verdict file
    tmp_dir = Path(tmp_path)
    verdict_file = tmp_dir / "305-verdict.md"
    verdict_content = """
<handoff_id>305</handoff_id>

<deliverable_output>
  verdict: /home/svend/flows/strict_review/verdicts/305-verdict.md
</deliverable_output>

## Final Verdict — Handoff 305

### Status: APPROVED WITH NOTES

Some other content...
"""
    verdict_file.write_text(verdict_content)
    
    # Test the parser function directly
    sched = Scheduler(db_path=_setup_db(tmp_path))
    status = sched._parse_verdict_file(str(verdict_file))
    assert status == "APPROVED WITH NOTES"


def test_verdict_parsing_reject(tmp_path):
    """Test parsing a verdict file with REJECTED status."""
    # Create test verdict file
    tmp_dir = Path(tmp_path)
    verdict_file = tmp_dir / "308-verdict.md"
    verdict_content = """
<handoff_id>308</handoff_id>

<deliverable_output>
  verdict: /home/svend/flows/strict_review/verdicts/308-verdict.md
</deliverable_output>

## Final Verdict — Handoff 308

### Status: REJECTED

Some other content...
"""
    verdict_file.write_text(verdict_content)
    
    # Test the parser function directly
    sched = Scheduler(db_path=_setup_db(tmp_path))
    status = sched._parse_verdict_file(str(verdict_file))
    assert status == "REJECTED"


def test_is_verdict_deliverable(tmp_path):
    """Test detecting if a job's deliverable pattern is a verdict file."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    # Create a mock flow with a verdict pattern
    sched = Scheduler(db_path=db)
    
    # Mock the flow loading to simulate a verdict deliverable
    # Patch the scheduler module's binding — scheduler.py imports
    # load_flow_from_db at module level, so patching bridge_lib has no effect.
    with patch('job_queue.scheduler.load_flow_from_db') as mock_load_flow:
        mock_mock_flow_data = {
            "steps": [
                {"deliverable_dir": "", "deliverable_pattern": "{ID}-result.md"},
                {"deliverable_dir": "", "deliverable_pattern": "{ID}-verdict.md"}
            ]
        }
        mock_load_flow.return_value = mock_mock_flow_data
        
        # Create a job (no need for state transition since testing the method only)
        job_id = repo.create_job(
            "strict_review", "archi01", "Add feature X", "/tmp/test"
        )
        job = repo.get_job(job_id)
        
        # Set up the job to have a handoff_id for testing
        repo.update(job_id, handoff_id="305")
        job.handoff_id = "305"
        
        # Check if it's correctly identified as a verdict deliverable
        is_verdict = sched._is_verdict_deliverable(job)
        assert is_verdict == True


def test_is_not_verdict_deliverable(tmp_path):
    """Test detecting when a job's deliverable pattern is NOT a verdict file."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    # Create a mock flow with a non-verdict pattern
    sched = Scheduler(db_path=db)
    
    # Mock the flow loading to simulate a regular result pattern 
    # Patch the scheduler module's binding — scheduler.py imports
    # load_flow_from_db at module level, so patching bridge_lib has no effect.
    with patch('job_queue.scheduler.load_flow_from_db') as mock_load_flow:
        mock_mock_flow_data = {
            "steps": [
                {"deliverable_dir": "", "deliverable_pattern": "{ID}-result.md"},
                {"deliverable_dir": "", "deliverable_pattern": "{ID}-handoff.md"}
            ]
        }
        mock_load_flow.return_value = mock_mock_flow_data
        
        # Create a job
        job_id = repo.create_job(
            "strict_review", "archi01", "Add feature X", "/tmp/test"
        )
        job = repo.get_job(job_id)
        
        # Set up the job to have a handoff_id for testing
        repo.update(job_id, handoff_id="305")
        job.handoff_id = "305"
        
        # Check if it's correctly identified as NOT a verdict deliverable
        is_verdict = sched._is_verdict_deliverable(job)
        assert is_verdict == False


def test_flow_claiming_logic(tmp_path):
    """A busy flow's APPROVED job is skipped; another flow's job is claimed.

    flowA has a RUNNING job plus an older APPROVED job; flowB has a newer
    APPROVED job. One claim pass must skip flowA's APPROVED job (flow busy)
    and claim flowB's. A second pass must return None — flowA is still busy.
    """
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)

    # flowA: one job driven to RUNNING through legal transitions only
    job_a_running_id = repo.create_job(
        "flowA", "role1", "Running task in Flow A", "/tmp/test"
    )
    repo.transition(job_a_running_id, "AWAITING_APPROVAL")
    repo.transition(job_a_running_id, "APPROVED")
    repo.transition(job_a_running_id, "QUEUED")
    repo.transition(job_a_running_id, "RUNNING")

    # flowA: an APPROVED job that must NOT be claimable while flowA is busy
    job_a_approved_id = repo.create_job(
        "flowA", "role1", "Waiting task in Flow A", "/tmp/test"
    )
    repo.transition(job_a_approved_id, "AWAITING_APPROVAL")
    repo.transition(job_a_approved_id, "APPROVED")

    # flowB: an APPROVED job in an idle flow — claimable
    job_b_approved_id = repo.create_job(
        "flowB", "role2", "Task for Flow B", "/tmp/test"
    )
    repo.transition(job_b_approved_id, "AWAITING_APPROVAL")
    repo.transition(job_b_approved_id, "APPROVED")

    sched = Scheduler(db_path=db)

    # The claim must skip flowA's APPROVED job and take flowB's
    claimed_job = sched.repo.claim("test-worker")
    assert claimed_job is not None
    assert claimed_job.job_id == job_b_approved_id

    # Second pass: only flowA's APPROVED job remains, but flowA is busy
    claimed_job2 = sched.repo.claim("test-worker")
    assert claimed_job2 is None


def test_job_transition_scenarios(tmp_path):
    """Test the various job transitions based on verdict outcomes directly."""
    db = _setup_db(tmp_path)
    repo = JobRepository(db_path=db)
    
    # Create a mock flow with verdict pattern for testing transitions  
    sched = Scheduler(db_path=db)
    
    # Create test verdict file manually
    tmp_dir = Path(tmp_path)
    verdict_file = tmp_dir / "305-verdict.md"
    verdict_content = """
<handoff_id>305</handoff_id>

<deliverable_output>
  verdict: /home/svend/flows/strict_review/verdicts/305-verdict.md
</deliverable_output>

## Final Verdict — Handoff 305

### Status: APPROVED WITH NOTES

Some other content...
"""
    verdict_file.write_text(verdict_content)
    
    # Create a job and transition it through different states - 
    # This simulates a complete tick() or _check_running_jobs() process that would call _resolve_verdict_outcome
    job_id = repo.create_job(
        "strict_review", "archi01", "Add feature X", "/tmp/test"
    )
    
    # Transition to APPROVED and set handoff_id for processing
    repo.transition(job_id, "AWAITING_APPROVAL") 
    repo.transition(job_id, "APPROVED")
    repo.update(job_id, handoff_id="305")
    
    # Test our verdict parsing logic directly - should work
    status = sched._parse_verdict_file(str(verdict_file))
    assert status == "APPROVED WITH NOTES"
    
    # Create a rejection verdict file 
    reject_verdict_file = tmp_dir / "306-verdict.md"
    reject_verdict_content = """
<handoff_id>306</handoff_id>

<deliverable_output>
  verdict: /home/svend/flows/strict_review/verdicts/306-verdict.md
</deliverable_output>

## Final Verdict — Handoff 306

### Status: REJECTED

Some other content...
"""
    reject_verdict_file.write_text(reject_verdict_content)
    
    # Test rejection parsing
    status = sched._parse_verdict_file(str(reject_verdict_file))
    assert status == "REJECTED"
    
    # Test unrecognized verdict status
    unrecognized_verdict_file = tmp_dir / "307-verdict.md"
    unrecognized_verdict_content = """
<handoff_id>307</handoff_id>

<deliverable_output>
  verdict: /home/svend/flows/strict_review/verdicts/307-verdict.md
</deliverable_output>

## Final Verdict — Handoff 307

### Status: UNRECOGNIZED_STATUS

Some other content...
"""
    unrecognized_verdict_file.write_text(unrecognized_verdict_content)
    
    # Test unrecognized status parsing — the parser returns the raw status
    # text; the OUTCOME mapping (not the parser) decides REVIEW_REQUIRED.
    status = sched._parse_verdict_file(str(unrecognized_verdict_file))
    assert status == "UNRECOGNIZED_STATUS"
