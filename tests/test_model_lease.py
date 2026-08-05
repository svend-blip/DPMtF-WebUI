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
