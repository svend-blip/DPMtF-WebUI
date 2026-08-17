"""Tests for Model Lease Integration (acquire/release semantics)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))

from model_lease import LeaseRegistry, Lease


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path):
    """Point lease persistence at a per-test database.

    acquire() persists leases to SQLite (cross-process refcounting) — the
    tests must never touch the real dpmtf.db.
    """
    old_db = LeaseRegistry._db_path
    LeaseRegistry._db_path = str(tmp_path / "leases.db")
    LeaseRegistry.reset()
    # Default: treat the backend as healthy so the refcount tests never
    # shell out to the allocator. Tests exercising the dead-backend path
    # override this locally.
    with patch.object(LeaseRegistry, "_backend_is_down", return_value=False):
        yield
    LeaseRegistry._db_path = old_db
    LeaseRegistry.reset()


def test_acquire_starts_model():
    """First acquire should start the model."""
    with patch.object(LeaseRegistry, "_start_model") as mock_start:
        LeaseRegistry.acquire("JOB-1", "archi-local")
        mock_start.assert_called_once_with("archi-local")


def test_second_acquire_does_not_restart():
    """Second acquire should NOT start the model again."""
    with patch.object(LeaseRegistry, "_start_model") as mock_start:
        LeaseRegistry.acquire("JOB-1", "archi-local")
        LeaseRegistry.acquire("JOB-2", "archi-local")
        mock_start.assert_called_once()  # only once


def test_acquire_restarts_when_stale_lease_masks_dead_backend():
    """An orphaned lease must not suppress the warm when the server is dead.

    Leases persist in SQLite and outlive the process. A run that dies
    without releasing leaves a lease behind, so the next signal-send sees
    was_empty=False. The old gate (start only when was_empty) then skipped
    _start_model and the dispatch injected into a dead backend on a free
    GPU (reveng handoff 068, 2026-08-16). acquire() must start the model
    whenever the backend is actually down, regardless of lease bookkeeping.
    """
    # A stale lease left in the DB by a prior (now-dead) process.
    stale = Lease(job_id="OLD", alias="qwen-local",
                  acquired_at="2026-08-16T00:00:00Z", worker_id="dead-run")
    LeaseRegistry._save_lease_to_db(stale)
    LeaseRegistry._leases.clear()  # fresh process: nothing in memory

    with patch.object(LeaseRegistry, "_start_model") as mock_start, \
         patch.object(LeaseRegistry, "_backend_is_down", return_value=True):
        LeaseRegistry.acquire("NEW", "qwen-local")
        mock_start.assert_called_once_with("qwen-local")


def test_acquire_skips_restart_when_stale_lease_but_backend_up():
    """A stale lease over a genuinely running model must NOT restart it.

    The refcount optimisation still holds: when the backend is up, a second
    (or orphaned-lease) acquire reuses the loaded weights instead of paying
    for a redundant start that would fail to bind the shared port.
    """
    stale = Lease(job_id="OLD", alias="qwen-local",
                  acquired_at="2026-08-16T00:00:00Z", worker_id="w")
    LeaseRegistry._save_lease_to_db(stale)
    LeaseRegistry._leases.clear()

    with patch.object(LeaseRegistry, "_start_model") as mock_start, \
         patch.object(LeaseRegistry, "_backend_is_down", return_value=False):
        LeaseRegistry.acquire("NEW", "qwen-local")
        mock_start.assert_not_called()


def test_sweep_orphaned_removes_old_and_keeps_fresh():
    """The sweep drops lease rows past the age threshold, keeps recent ones.

    Leases persist across processes and a crashed or cyclic run never
    releases them (laguna-local a day old, cloud_minimax hours old). A
    handoff holds a lease for minutes, so age is a safe, uniform orphan
    signal for both cloud and local aliases.
    """
    import sqlite3
    with patch.object(LeaseRegistry, "_start_model"):
        LeaseRegistry.acquire("FRESH", "qwen-local")
        LeaseRegistry.acquire("OLD", "laguna-local")
    # Backdate OLD's row well past the threshold (the DB owns acquired_at).
    conn = sqlite3.connect(LeaseRegistry._get_db_path())
    conn.execute(
        "UPDATE model_leases SET acquired_at = datetime('now', '-2 days') "
        "WHERE job_id = 'OLD'")
    conn.commit()
    conn.close()

    swept = LeaseRegistry.sweep_orphaned(max_age_seconds=3600)

    swept_jobs = {l.job_id for l in swept}
    assert swept_jobs == {"OLD"}
    assert LeaseRegistry.lease_count("laguna-local") == 0
    assert LeaseRegistry.lease_count("qwen-local") == 1


def test_sweep_orphaned_empty_table_is_noop():
    """Sweeping an empty table returns [] and does not raise."""
    assert LeaseRegistry.sweep_orphaned(max_age_seconds=3600) == []


def test_sweep_orphaned_respects_threshold():
    """A lease younger than the threshold is never swept."""
    with patch.object(LeaseRegistry, "_start_model"):
        LeaseRegistry.acquire("RECENT", "qwen-local")
    swept = LeaseRegistry.sweep_orphaned(max_age_seconds=3600)
    assert swept == []
    assert LeaseRegistry.lease_count("qwen-local") == 1


def test_release_stops_when_no_leases():
    """Release should stop model when no leases remain."""
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model") as mock_stop:
        mock_stop.return_value = True
        LeaseRegistry.acquire("JOB-1", "archi-local")
        stopped = LeaseRegistry.release("JOB-1", "archi-local")
        assert stopped is True
        mock_stop.assert_called_once_with("archi-local")


def test_release_reports_failed_stop():
    """A stop that did not confirm must not be reported as success.

    Returning True on a failed stop orphaned an SGLang server: the caller
    believed the GPU was free and warmed the next model into a full GPU.
    """
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model") as mock_stop:
        mock_stop.return_value = False
        LeaseRegistry.acquire("JOB-1", "archi-local")
        stopped = LeaseRegistry.release("JOB-1", "archi-local")
        assert stopped is False
        mock_stop.assert_called_once_with("archi-local")


def test_release_does_not_stop_when_other_leases():
    """Release should NOT stop model when other jobs still have leases."""
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model") as mock_stop:
        LeaseRegistry.acquire("JOB-1", "archi-local")
        LeaseRegistry.acquire("JOB-2", "archi-local")
        stopped = LeaseRegistry.release("JOB-1", "archi-local")
        assert stopped is False
        mock_stop.assert_not_called()


def test_lease_count():
    """Lease count reflects active leases."""
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model"):
        assert LeaseRegistry.lease_count("archi-local") == 0
        LeaseRegistry.acquire("JOB-1", "archi-local")
        assert LeaseRegistry.lease_count("archi-local") == 1
        LeaseRegistry.acquire("JOB-2", "archi-local")
        assert LeaseRegistry.lease_count("archi-local") == 2
        LeaseRegistry.release("JOB-1", "archi-local")
        assert LeaseRegistry.lease_count("archi-local") == 1


def test_is_loaded():
    """is_loaded reflects whether any leases exist."""
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model"):
        assert not LeaseRegistry.is_loaded("archi-local")
        LeaseRegistry.acquire("JOB-1", "archi-local")
        assert LeaseRegistry.is_loaded("archi-local")
        LeaseRegistry.release("JOB-1", "archi-local")
        assert not LeaseRegistry.is_loaded("archi-local")


def test_different_aliases_independent():
    """Different aliases have independent lease tracking."""
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model"):
        LeaseRegistry.acquire("JOB-1", "archi-local")
        LeaseRegistry.acquire("JOB-2", "imple01-local")
        assert LeaseRegistry.lease_count("archi-local") == 1
        assert LeaseRegistry.lease_count("imple01-local") == 1
        
        # Releasing archi-local doesn't affect imple01-local
        LeaseRegistry.release("JOB-1", "archi-local")
        assert LeaseRegistry.lease_count("archi-local") == 0
        assert LeaseRegistry.lease_count("imple01-local") == 1


def test_release_nonexistent_lease():
    """Releasing a lease that doesn't exist returns False."""
    result = LeaseRegistry.release("NONEXISTENT", "archi-local")
    assert result is False


def test_active_leases():
    """active_leases returns the list of Lease objects."""
    with patch.object(LeaseRegistry, "_start_model"), \
         patch.object(LeaseRegistry, "_stop_model"):
        LeaseRegistry.acquire("JOB-1", "archi-local", worker_id="w1")
        leases = LeaseRegistry.active_leases("archi-local")
        assert len(leases) == 1
        assert leases[0].job_id == "JOB-1"
        assert leases[0].worker_id == "w1"
