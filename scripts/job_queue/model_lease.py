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
    """In-memory lease registry. Production would use SQLite."""

    _leases: dict[str, list[Lease]] = {}  # alias → list of active leases

    @classmethod
    def acquire(cls, job_id: str, alias: str, worker_id: str = "") -> Lease:
        """Acquire a lease on a model alias. Starts the model if no leases exist."""
        lease = Lease(
            job_id=job_id,
            alias=alias,
            acquired_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            worker_id=worker_id,
        )
        
        was_empty = alias not in cls._leases or len(cls._leases[alias]) == 0
        
        cls._leases.setdefault(alias, []).append(lease)
        
        if was_empty:
            # Start the model — first lease
            cls._start_model(alias)
        
        return lease

    @classmethod
    def release(cls, job_id: str, alias: str) -> bool:
        """Release a lease. Stops the model if no leases remain.
        
        Returns True if model was stopped, False if other leases remain.
        """
        if alias not in cls._leases:
            return False
        
        # Remove this job's lease
        before = len(cls._leases[alias])
        cls._leases[alias] = [l for l in cls._leases[alias] if l.job_id != job_id]
        after = len(cls._leases[alias])
        
        if after == 0 and before > 0:
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
        return len(cls._leases.get(alias, []))

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
