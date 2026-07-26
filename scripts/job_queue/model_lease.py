"""Model Lease Integration — acquire/release semantics for reference-counted unload.

Problem: _run_allocator_stop() unconditionally stops a model. If two jobs
share an alias, stopping it for one job breaks the other.

Solution: A lease registry tracks active leases per alias. Models are only
unloaded when all leases are released.

Acquire = start model (if not already running) + register lease.
Release = deregister lease + stop model (if no leases remain).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config

ALLOCATOR_SCRIPT = os.path.join(
    config.get_project_path("model-allocator"), "scripts", "model-allocator"
)


@dataclass
class Lease:
    """A model lease owned by a job."""
    job_id: str
    alias: str
    acquired_at: str = ""
    worker_id: str = ""


class LeaseRegistry:
    """Lease registry with SQLite persistence.

    Leases are stored in the DPMtF database so they survive process restarts.
    Falls back to in-memory if the database is unavailable.
    """

    _leases: dict[str, list[Lease]] = {}  # alias → list of active leases (in-memory fallback)
    _db_path: str = None

    @classmethod
    def _get_db_path(cls) -> str:
        if cls._db_path:
            return cls._db_path
        try:
            import config
            p = config.get_db_path()
            import os
            if not os.path.isabs(p):
                p = os.path.join(str(config.get_project_root()), p)
            cls._db_path = p
            return p
        except Exception:
            return 

    @classmethod
    def _ensure_table(cls):
        """Create model_leases table if it doesn't exist."""
        p = cls._get_db_path()
        if not p:
            return
        import sqlite3
        try:
            conn = sqlite3.connect(p)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_leases (
                    lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    worker_id TEXT,
                    acquired_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(job_id, alias)
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    @classmethod
    def _load_from_db(cls, alias: str) -> list[Lease]:
        """Load active leases for an alias from SQLite."""
        cls._ensure_table()
        p = cls._get_db_path()
        if not p:
            return cls._leases.get(alias, [])
        import sqlite3
        try:
            conn = sqlite3.connect(p)
            rows = conn.execute(
                "SELECT job_id, alias, worker_id, acquired_at FROM model_leases WHERE alias = ?",
                (alias,)
            ).fetchall()
            conn.close()
            return [Lease(job_id=r[0], alias=r[1], worker_id=r[2] or "", acquired_at=r[3] or "") for r in rows]
        except Exception:
            return cls._leases.get(alias, [])

    @classmethod
    def _save_lease_to_db(cls, lease: Lease):
        """Persist a lease to SQLite."""
        cls._ensure_table()
        p = cls._get_db_path()
        if not p:
            return
        import sqlite3
        try:
            conn = sqlite3.connect(p)
            conn.execute(
                "INSERT OR IGNORE INTO model_leases (job_id, alias, worker_id) VALUES (?, ?, ?)",
                (lease.job_id, lease.alias, lease.worker_id)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    @classmethod
    def _delete_lease_from_db(cls, job_id: str, alias: str):
        """Remove a lease from SQLite."""
        p = cls._get_db_path()
        if not p:
            return
        import sqlite3
        try:
            conn = sqlite3.connect(p)
            conn.execute(
                "DELETE FROM model_leases WHERE job_id = ? AND alias = ?",
                (job_id, alias)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    @classmethod
    def acquire(cls, job_id: str, alias: str, worker_id: str = "") -> Lease:
        """Acquire a lease on a model alias. Starts the model if no leases exist.

        The lease is persisted to SQLite — every dispatch runs as its own
        process, so an in-memory-only lease was invisible to the release()
        call in the NEXT dispatch process. That made had_lease always False
        and from-role models were never stopped at handoff (models piled up
        in VRAM until Ollama's idle timeout).
        """
        lease = Lease(
            job_id=job_id,
            alias=alias,
            acquired_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            worker_id=worker_id,
        )

        was_empty = (len(cls._leases.get(alias, []))
                     + len(cls._load_from_db(alias))) == 0

        cls._leases.setdefault(alias, []).append(lease)
        cls._save_lease_to_db(lease)

        if was_empty:
            # Start the model — first lease
            cls._start_model(alias)

        return lease

    @classmethod
    def release(cls, job_id: str, alias: str, stop_model: bool = True) -> bool:
        """Release a lease. Stops the model if no leases remain.

        stop_model=False releases the bookkeeping without unloading — used
        when the next role runs the SAME real model under a different alias
        (stopping would unload the model the target just started using).

        Returns True if model was stopped, False if other leases remain.
        """
        # Check if any leases existed before removing
        active_before = cls._load_from_db(alias)
        in_mem_before = cls._leases.get(alias, [])
        had_lease = any(l.job_id == job_id for l in active_before) or any(l.job_id == job_id for l in in_mem_before)
        
        # Remove from in-memory
        if alias in cls._leases:
            cls._leases[alias] = [l for l in cls._leases[alias] if l.job_id != job_id]
        
        # Remove from DB
        cls._delete_lease_from_db(job_id, alias)
        
        # Check remaining leases
        active = cls._load_from_db(alias)
        in_mem = cls._leases.get(alias, [])
        total = len(active) + len(in_mem)
        
        if total == 0 and had_lease and stop_model:
            # No more leases — stop the model
            cls._stop_model(alias)
            return True

        return False

    @classmethod
    def active_leases(cls, alias: str) -> list[Lease]:
        """Return active leases for an alias."""
        return cls._leases.get(alias, [])

    @classmethod
    def lease_count(cls, alias: str) -> int:
        """Number of active leases for an alias."""
        in_mem = len(cls._leases.get(alias, []))
        from_db = len(cls._load_from_db(alias))
        return max(in_mem, from_db)

    @classmethod
    def is_loaded(cls, alias: str) -> bool:
        """Whether a model has any active leases."""
        return cls.lease_count(alias) > 0

    @classmethod
    def _start_model(cls, alias: str):
        """Start the model via allocator."""
        try:
            subprocess.run(
                [ALLOCATOR_SCRIPT, "start", "--alias", alias],
                capture_output=True, text=True, timeout=180,
            )
        except Exception as e:
            print(f"  WARNING: model start failed for '{alias}': {e}", file=sys.stderr)

    @classmethod
    def _stop_model(cls, alias: str):
        """Stop the model via allocator."""
        try:
            subprocess.run(
                [ALLOCATOR_SCRIPT, "stop", "--alias", alias],
                capture_output=True, text=True, timeout=45,
            )
        except Exception as e:
            print(f"  WARNING: model stop failed for '{alias}': {e}", file=sys.stderr)

    @classmethod
    def reset(cls):
        """Clear all leases (for testing)."""
        cls._leases.clear()
