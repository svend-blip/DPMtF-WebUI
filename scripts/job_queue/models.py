"""Job Queue models — state machine, repository, transition service.

Ported from the verified spike (scripts/python-runtime/job_queue_spike.py,
12 tests green) and productionized with a JobRepository class that owns
all DB interactions.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config


# ── States and legal transitions ─────────────────────────────────

STATES = [
    "DRAFT", "AWAITING_APPROVAL", "APPROVED", "QUEUED",
    "WAITING_FOR_RESOURCES", "RUNNING", "VERIFYING",
    "REVIEW_REQUIRED", "COMPLETED", "CHANGES_REQUESTED",
    "BLOCKED", "FAILED", "CANCELLED", "HUMAN_ACTION_REQUIRED",
]

LEGAL_TRANSITIONS = {
    "DRAFT": ["AWAITING_APPROVAL", "CANCELLED"],
    "AWAITING_APPROVAL": ["APPROVED", "BLOCKED", "CANCELLED", "HUMAN_ACTION_REQUIRED"],
    "APPROVED": ["QUEUED", "CANCELLED"],
    "QUEUED": ["WAITING_FOR_RESOURCES", "RUNNING", "BLOCKED", "CANCELLED"],
    "WAITING_FOR_RESOURCES": ["RUNNING", "BLOCKED", "CANCELLED"],
    "RUNNING": ["VERIFYING", "BLOCKED", "FAILED", "CANCELLED"],
    "VERIFYING": ["REVIEW_REQUIRED", "COMPLETED", "CHANGES_REQUESTED", "FAILED"],
    "REVIEW_REQUIRED": ["COMPLETED", "CHANGES_REQUESTED", "BLOCKED", "HUMAN_ACTION_REQUIRED"],
    "COMPLETED": [],
    "CHANGES_REQUESTED": ["AWAITING_APPROVAL", "CANCELLED"],
    "BLOCKED": ["AWAITING_APPROVAL", "CANCELLED", "HUMAN_ACTION_REQUIRED"],
    "FAILED": ["AWAITING_APPROVAL", "CANCELLED"],
    "CANCELLED": [],
    "HUMAN_ACTION_REQUIRED": ["AWAITING_APPROVAL", "CANCELLED"],
}

TERMINAL_STATES = {"COMPLETED", "CANCELLED"}
EXECUTABLE_STATES = {"FITS", "FITS_WITH_LOW_MARGIN"}


def is_legal_transition(from_state: str, to_state: str) -> bool:
    return to_state in LEGAL_TRANSITIONS.get(from_state, [])


class IllegalTransitionError(Exception):
    pass


# ── Job dataclass ────────────────────────────────────────────────

@dataclass
class Job:
    job_id: str = ""
    workflow_run_id: str = ""
    flow_key: str = ""
    step_key: str = ""
    role_key: str = ""
    status: str = "DRAFT"
    allocator_alias: str = ""
    handoff_id: str = ""
    idempotency_key: str = ""
    retry_count: int = 0
    max_retries: int = 3
    lease_owner: str = ""
    lease_expires_at: str = ""
    heartbeat_at: str = ""
    priority: int = 0
    goal: str = ""
    target_project: str = ""
    scope_version: str = ""
    checkpoint_path: str = ""
    context_fit_state: str = ""
    parent_job_id: str = ""
    continuation_index: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Job":
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})


# ── Job Repository ──────────────────────────────────────────────

class JobRepository:
    """CRUD + transitions + claims + leases for jobs."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            p = config.get_db_path()
            if not Path(p).is_absolute():
                p = str(Path(config.get_project_root()) / p)
            db_path = p
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_job(self, flow_key: str, role_key: str, goal: str,
                   target_project: str, allocator_alias: str = "",
                   step_key: str = "", priority: int = 0,
                   parent_job_id: str = "", idempotency_key: str = "") -> str:
        """Create a job in DRAFT state. Returns job_id."""
        job_id = f"JOB-{uuid.uuid4().hex[:12].upper()}"
        if not idempotency_key:
            idempotency_key = f"idem-{job_id}"
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO jobs (job_id, flow_key, role_key, goal, target_project,
                   allocator_alias, step_key, priority, parent_job_id, idempotency_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, flow_key, role_key, goal, target_project,
                 allocator_alias, step_key, priority, parent_job_id, idempotency_key)
            )
            conn.execute(
                """INSERT INTO job_events (job_id, event_type, to_state, actor, detail)
                   VALUES (?, 'create', 'DRAFT', 'system', ?)""",
                (job_id, goal[:200])
            )
            conn.commit()
            return job_id
        except sqlite3.IntegrityError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[Job]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
        return Job.from_row(row) if row else None

    def list_jobs(self, status: str = None, flow_key: str = None) -> list[Job]:
        conn = self._conn()
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if flow_key:
            query += " AND flow_key = ?"
            params.append(flow_key)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [Job.from_row(r) for r in rows]

    def transition(self, job_id: str, to_state: str, actor: str = "system",
                   detail: str = "") -> Job:
        """Transition a job to a new state. Raises IllegalTransitionError."""
        conn = self._conn()
        try:
            conn.execute("BEGIN")
            row = conn.execute(
                "SELECT status FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not row:
                conn.rollback()
                raise ValueError(f"Job {job_id} not found")
            from_state = row[0]
            if not is_legal_transition(from_state, to_state):
                conn.rollback()
                raise IllegalTransitionError(
                    f"Illegal transition: {from_state} → {to_state}"
                )
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE job_id = ?",
                (to_state, job_id)
            )
            conn.execute(
                """INSERT INTO job_events (job_id, event_type, from_state, to_state, actor, detail)
                   VALUES (?, 'transition', ?, ?, ?, ?)""",
                (job_id, from_state, to_state, actor, detail)
            )
            conn.commit()
        except (IllegalTransitionError, ValueError):
            if conn:
                conn.rollback()
            raise
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_job(job_id)

    def claim(self, worker_id: str, lease_seconds: int = 900) -> Optional[Job]:
        """Atomically claim the oldest APPROVED job. Returns Job or None.

        Excludes jobs that have exhausted their retry budget (retry_count >= max_retries).
        
        For flow serial claims: only claim APPROVED jobs from a flow if no other
        job in that flow is in RUNNING or VERIFYING state.
        
        This implementation iterates through ALL APPROVED jobs ordered by priority and creation time,
        checking each one's flow is available before claiming it. This ensures that if
        one flow has an active job, jobs from other flows can still be claimed in the same tick.
        """
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Get all APPROVED jobs ordered by priority and creation time
            rows = conn.execute(
                """SELECT job_id, flow_key FROM jobs WHERE status = 'APPROVED'
                   AND retry_count < max_retries
                   AND (parent_job_id IS NULL OR parent_job_id = ''
                        OR parent_job_id IN (SELECT job_id FROM jobs WHERE status = 'COMPLETED'))
                   ORDER BY priority DESC, created_at ASC"""
            ).fetchall()
            
            if not rows:
                conn.rollback()
                return None
            
            # Try each approved job until we find one with an available flow
            for row in rows:
                job_id = row[0]
                job_flow_key = row[1] 
                
                # Check if any job in this flow is currently RUNNING or VERIFYING
                existing_running_job = conn.execute(
                    """SELECT 1 FROM jobs WHERE flow_key = ? AND status IN ('RUNNING', 'VERIFYING')
                       LIMIT 1""", (job_flow_key,)
                ).fetchone()
                
                if not existing_running_job:
                    # No running job in this flow - claim this one
                    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + lease_seconds))
                    conn.execute(
                        """UPDATE jobs SET status = 'QUEUED', lease_owner = ?,
                           lease_expires_at = ?, heartbeat_at = datetime('now'),
                           updated_at = datetime('now') WHERE job_id = ?""",
                        (worker_id, expires, job_id)
                    )
                    conn.execute(
                        """INSERT INTO job_events (job_id, event_type, from_state, to_state, actor)
                           VALUES (?, 'claim', 'APPROVED', 'QUEUED', ?)""",
                        (job_id, worker_id)
                    )
                    conn.commit()
                    return self.get_job(job_id)
            
            # No eligible jobs found
            conn.rollback()
            return None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def heartbeat(self, job_id: str, worker_id: str, lease_seconds: int = 900):
        """Extend lease."""
        expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + lease_seconds))
        conn = self._conn()
        conn.execute(
            """UPDATE jobs SET heartbeat_at = datetime('now'), lease_expires_at = ?
               WHERE job_id = ? AND lease_owner = ?""",
            (expires, job_id, worker_id)
        )
        conn.commit()
        conn.close()

    def recover_expired_leases(self) -> int:
        """Reclaim jobs with expired leases. Returns count recovered.

        Jobs that still have retry budget are reset to APPROVED.
        Jobs that have exhausted retries (retry_count >= max_retries) are
        transitioned to FAILED — they will not be retried again.
        """
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            rows = conn.execute(
                """SELECT job_id FROM jobs WHERE lease_expires_at < ?
                   AND status IN ('QUEUED', 'WAITING_FOR_RESOURCES', 'RUNNING')""",
                (now,)
            ).fetchall()
            for row in rows:
                job_id = row[0]
                # Increment retry_count first
                conn.execute(
                    """UPDATE jobs SET retry_count = retry_count + 1,
                       lease_owner = NULL, lease_expires_at = NULL,
                       updated_at = datetime('now') WHERE job_id = ?""",
                    (job_id,)
                )
                # Check if retries exhausted
                check = conn.execute(
                    "SELECT retry_count, max_retries FROM jobs WHERE job_id = ?",
                    (job_id,)
                ).fetchone()
                rc = check["retry_count"] if check else 0
                mr = check["max_retries"] if check else 3
                if rc >= mr:
                    # Exhausted retries — transition to FAILED
                    conn.execute(
                        """UPDATE jobs SET status = 'FAILED',
                           updated_at = datetime('now') WHERE job_id = ?""",
                        (job_id,)
                    )
                    conn.execute(
                        """INSERT INTO job_events (job_id, event_type, from_state, to_state, actor, detail)
                           VALUES (?, 'lease_expired', 'RUNNING', 'FAILED', 'system', ?)""",
                        (job_id, f"retry exhausted ({rc}/{mr})")
                    )
                else:
                    # Still have budget — reset to APPROVED for retry
                    conn.execute(
                        """UPDATE jobs SET status = 'APPROVED',
                           updated_at = datetime('now') WHERE job_id = ?""",
                        (job_id,)
                    )
                    conn.execute(
                        """INSERT INTO job_events (job_id, event_type, from_state, to_state, actor, detail)
                           VALUES (?, 'lease_expired', 'RUNNING', 'APPROVED', 'system', ?)""",
                        (job_id, f"auto-recovery ({rc}/{mr})")
                    )
            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_events(self, job_id: str) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY event_id", (job_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update(self, job_id: str, **fields):
        """Update specific fields on a job.

        Field names are interpolated into the SQL, so they are validated
        against the Job dataclass first — values stay parameterized either
        way, but an unvalidated key would let a caller reach arbitrary
        column expressions."""
        unknown = set(fields) - set(Job.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown job fields: {sorted(unknown)}")
        conn = self._conn()
        sets = [f"{k} = ?" for k in fields]
        vals = list(fields.values())
        sets.append("updated_at = datetime('now')")
        vals.append(job_id)
        conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", vals)
        conn.commit()
        conn.close()
