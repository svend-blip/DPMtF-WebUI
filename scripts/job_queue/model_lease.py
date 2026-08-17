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

        # Start when this is the first lease, OR when a lingering lease is
        # masking a dead backend. was_empty is bookkeeping, not proof the
        # GPU is warm: an orphaned lease from a crashed run made was_empty
        # False and the warm was skipped, injecting into a dead server on a
        # free GPU (reveng handoff 068, 2026-08-16). The health probe runs
        # only on the was_empty=False branch (short-circuit), so a normal
        # fresh swap pays nothing and a genuinely running model is reused.
        if was_empty or cls._backend_is_down(alias):
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
            # No more leases — stop the model, and report what actually
            # happened. A False here makes dispatch retry the stop and wait
            # for the GPU instead of warming the next model on faith.
            return cls._stop_model(alias)

        return False

    @classmethod
    def release_all(cls, alias: str, stop_model: bool = True) -> bool:
        """Drop every lease on an alias, then optionally stop the model.

        Leases are keyed by handoff id, but a model's lifetime spans
        handoffs: the lease taken when handoff N's verdict was delivered is
        still open when handoff N+1 dispatches, and release(N+1, alias)
        never matches it. The stale lease then blocked the swap and the
        next model was loaded into a GPU the predecessor still owned.

        Use this only when swapping to a *different* real model. Two models
        cannot share one GPU, so a lease claiming the old one must stay
        resident is bookkeeping that reality has already overruled.
        """
        for lease in cls._load_from_db(alias):
            cls._delete_lease_from_db(lease.job_id, alias)
        cls._leases[alias] = []
        if stop_model:
            return cls._stop_model(alias)
        return False

    @classmethod
    def sweep_orphaned(cls, max_age_seconds: int = None) -> list[Lease]:
        """Delete lease rows older than the age threshold; return what was swept.

        Leases persist in SQLite and outlive their process. A run that
        crashes, gets killed, or (in a cyclic flow) never emits an
        END-REPORT leaves its leases behind forever — release() is keyed by
        handoff id and a later release never matches an earlier handoff's
        row. The result is chronic accumulation (laguna-local from a dead
        llama_SG run, cloud_minimax/opus5 from human dispatches that never
        swap back).

        A handoff holds a lease for minutes, so age is a safe, uniform
        orphan signal for BOTH cloud and local aliases — cloud leases have
        no local server to probe, so backend-health cannot be the test.
        This deletes rows ONLY; it never stops a model. VRAM reclaim stays
        with _stop_other_local_models, and _backend_is_down already makes an
        orphan row harmless to warm-correctness. A wrongly-swept live lease
        degrades gracefully: release() then finds no row and skips the stop,
        and the next dispatch's sweep of resident models catches the weights.

        Age is computed in SQL (julianday) so it matches the stored UTC
        format (datetime('now')) and clock exactly.
        """
        if max_age_seconds is None:
            max_age_seconds = int(os.environ.get("DPMTF_LEASE_MAX_AGE_SEC", "21600"))
        p = cls._get_db_path()
        if not p:
            return []
        import sqlite3
        predicate = "(julianday('now') - julianday(acquired_at)) * 86400.0 > ?"
        try:
            conn = sqlite3.connect(p)
            rows = conn.execute(
                f"SELECT job_id, alias, worker_id, acquired_at "
                f"FROM model_leases WHERE {predicate}",
                (max_age_seconds,),
            ).fetchall()
            if rows:
                conn.execute(
                    f"DELETE FROM model_leases WHERE {predicate}",
                    (max_age_seconds,),
                )
                conn.commit()
            conn.close()
        except Exception:
            return []
        swept = [Lease(job_id=r[0], alias=r[1], worker_id=r[2] or "",
                       acquired_at=r[3] or "") for r in rows]
        # Drop any in-memory mirror of the swept rows so lease_count agrees.
        for lease in swept:
            bucket = cls._leases.get(lease.alias)
            if bucket:
                cls._leases[lease.alias] = [
                    l for l in bucket if l.job_id != lease.job_id]
        return swept

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
        """Start the model via allocator.

        The allocator CLI defaults to a 120s start timeout, and the SGLang
        adapter KILLS the server it just started when that expires. A 30B
        AWQ model needs 3-6 minutes for weight load plus CUDA graph
        capture, so the default guaranteed the role never got a model —
        this is the same defect dispatch.py had, in a second place.
        """
        start_timeout = int(os.environ.get("DPMTF_MODEL_START_TIMEOUT", "900"))
        try:
            result = subprocess.run(
                [ALLOCATOR_SCRIPT, "start", "--alias", alias,
                 "--timeout", str(start_timeout)],
                capture_output=True, text=True, timeout=start_timeout + 60,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                print(f"  WARNING: model start returned {result.returncode} "
                      f"for '{alias}': {detail}", file=sys.stderr)
        except Exception as e:
            print(f"  WARNING: model start failed for '{alias}': {e}", file=sys.stderr)

    @classmethod
    def _backend_is_down(cls, alias: str) -> bool:
        """True only when the alias is a LOCAL backend whose server is dead.

        was_empty (lease bookkeeping) is not proof the GPU is warm. A run
        that dies without releasing leaves an orphaned lease in SQLite; the
        next acquire then sees was_empty=False and — with the old gate —
        skipped _start_model, injecting into a dead backend on a free GPU
        (reveng handoff 068, 2026-08-16: GLM stopped, "Lease acquired"
        printed, no warm, backend down, 32 GB free). This probe is the
        ground-truth backstop.

        Fail-open (return False) on anything unparseable and on cloud
        backends: a cloud alias has no local server to probe, and a false
        "down" would restart a model needlessly. Only ever runs on the
        was_empty=False branch (see acquire), so the fresh-swap path pays
        nothing.
        """
        if not alias:
            return False
        try:
            result = subprocess.run(
                [ALLOCATOR_SCRIPT, "status", "--alias", alias],
                capture_output=True, text=True, timeout=20,
            )
            status = json.loads(result.stdout) if result.stdout.strip() else {}
        except Exception:
            return False
        if not isinstance(status, dict):
            return False
        if status.get("backend") not in ("llama_cpp", "sglang"):
            return False
        return not status.get("running", True)

    @classmethod
    def _stop_model(cls, alias: str) -> bool:
        """Stop the model via allocator. Returns True only if it really stopped.

        The previous version discarded the allocator's exit code, so a
        failed stop was indistinguishable from a successful one. On
        2026-08-05 that silence orphaned an SGLang server: the stop
        reported success, the adapter had already deleted the pid file, and
        the caller warmed the next model into a GPU that was still full.
        A stop that cannot be verified must say so.
        """
        try:
            result = subprocess.run(
                [ALLOCATOR_SCRIPT, "stop", "--alias", alias],
                capture_output=True, text=True, timeout=45,
            )
        except Exception as e:
            print(f"  WARNING: model stop failed for '{alias}': {e}", file=sys.stderr)
            return False

        stopped = result.returncode == 0
        try:
            payload = json.loads(result.stdout or "{}")
            if isinstance(payload, dict) and "stopped" in payload:
                stopped = bool(payload["stopped"])
        except (ValueError, TypeError):
            pass  # non-JSON output — fall back to the exit code

        if not stopped:
            detail = (result.stderr or result.stdout or "").strip()
            print(f"  WARNING: model stop did NOT confirm for '{alias}' "
                  f"(exit {result.returncode}): {detail}", file=sys.stderr)
        return stopped

    @classmethod
    def reset(cls):
        """Clear all leases (for testing)."""
        cls._leases.clear()
