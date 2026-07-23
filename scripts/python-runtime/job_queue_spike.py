#!/usr/bin/env python3
"""Job Queue spike — tests durable job lifecycle, atomic claims, and state transitions.

Compares two approaches:
1. Extending workflow_runs table
2. Separate jobs table linked to workflow_runs

This is a SPIKE — it tests concepts, not a production scheduler.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# ── Job lifecycle states and legal transitions ──────────────────

STATES = [
    "DRAFT",
    "AWAITING_APPROVAL",
    "APPROVED",
    "QUEUED",
    "WAITING_FOR_RESOURCES",
    "RUNNING",
    "VERIFYING",
    "REVIEW_REQUIRED",
    "COMPLETED",
    "CHANGES_REQUESTED",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
    "HUMAN_ACTION_REQUIRED",
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


def is_legal_transition(from_state: str, to_state: str) -> bool:
    return to_state in LEGAL_TRANSITIONS.get(from_state, [])


# ── Schema for separate jobs table ───────────────────────────────

JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    workflow_run_id TEXT,
    flow_key TEXT NOT NULL,
    step_key TEXT,
    role_key TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    allocator_alias TEXT,
    handoff_id TEXT,
    idempotency_key TEXT UNIQUE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    lease_owner TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    priority INTEGER DEFAULT 0,
    goal TEXT,
    target_project TEXT,
    scope_version TEXT,
    checkpoint_path TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(run_id)
);

CREATE TABLE IF NOT EXISTS job_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    actor TEXT,
    detail TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(lease_owner, lease_expires_at);
"""


# ── Transition service — rejects illegal transitions ─────────────

class IllegalTransitionError(Exception):
    pass


def transition_job(conn: sqlite3.Connection, job_id: str, to_state: str, actor: str = "system"):
    """Transition a job to a new state, recording an event.

    Rejects illegal transitions atomically.
    """
    conn.execute("BEGIN")
    try:
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
            "INSERT INTO job_events (job_id, event_type, from_state, to_state, actor) "
            "VALUES (?, 'transition', ?, ?, ?)",
            (job_id, from_state, to_state, actor)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Atomic claim — two workers cannot claim the same job ─────────

def claim_job(conn: sqlite3.Connection, worker_id: str, lease_seconds: int = 300) -> Optional[str]:
    """Atomically claim the oldest APPROVED job.

    Uses a single transaction with row locking (SQLite BEGIN IMMEDIATE).
    Returns job_id if claimed, None if no eligible job.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT job_id FROM jobs WHERE status = 'APPROVED' "
            "ORDER BY priority DESC, created_at ASC LIMIT 1"
        ).fetchone()
        if not row:
            conn.rollback()
            return None
        
        job_id = row[0]
        expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + lease_seconds))
        conn.execute(
            "UPDATE jobs SET status = 'QUEUED', lease_owner = ?, lease_expires_at = ?, "
            "heartbeat_at = datetime('now'), updated_at = datetime('now') WHERE job_id = ?",
            (worker_id, expires, job_id)
        )
        conn.execute(
            "INSERT INTO job_events (job_id, event_type, from_state, to_state, actor) "
            "VALUES (?, 'claim', 'APPROVED', 'QUEUED', ?)",
            (job_id, worker_id)
        )
        conn.commit()
        return job_id
    except Exception:
        conn.rollback()
        raise


# ── Lease recovery — expired leases get re-queued ───────────────

def recover_expired_leases(conn: sqlite3.Connection) -> int:
    """Reclaim jobs with expired leases.

    Moves them back to APPROVED (incrementing retry_count).
    Returns count of recovered jobs.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rows = conn.execute(
            "SELECT job_id FROM jobs WHERE lease_expires_at < ? "
            "AND status IN ('QUEUED', 'WAITING_FOR_RESOURCES', 'RUNNING')",
            (now,)
        ).fetchall()
        for row in rows:
            job_id = row[0]
            conn.execute(
                "UPDATE jobs SET status = 'APPROVED', lease_owner = NULL, "
                "lease_expires_at = NULL, retry_count = retry_count + 1, "
                "updated_at = datetime('now') WHERE job_id = ?",
                (job_id,)
            )
            conn.execute(
                "INSERT INTO job_events (job_id, event_type, from_state, to_state, actor, detail) "
                "VALUES (?, 'lease_expired', 'RUNNING', 'APPROVED', 'system', 'auto-recovery')",
                (job_id,)
            )
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise


# ── Heartbeat ────────────────────────────────────────────────────

def heartbeat(conn: sqlite3.Connection, job_id: str, worker_id: str, lease_seconds: int = 300):
    """Update heartbeat and extend lease."""
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + lease_seconds))
    conn.execute(
        "UPDATE jobs SET heartbeat_at = datetime('now'), lease_expires_at = ? "
        "WHERE job_id = ? AND lease_owner = ?",
        (expires, job_id, worker_id)
    )
    conn.commit()


# ── Create test DB ───────────────────────────────────────────────

def create_test_db(db_path: str):
    """Create a fresh test database with the jobs schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(JOBS_SCHEMA)
    
    # Also create a minimal workflow_runs table for FK reference
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_runs (
            run_id TEXT PRIMARY KEY,
            phase_key TEXT,
            target_project TEXT,
            status TEXT DEFAULT 'prompt_compiled'
        )
    """)
    conn.commit()
    return conn


def create_job(conn, job_id="JOB-001", flow_key="strict_review", goal="test goal",
               target_project="/tmp/test", allocator_alias="archi-local"):
    """Create a job in DRAFT state."""
    conn.execute(
        "INSERT INTO jobs (job_id, flow_key, goal, target_project, allocator_alias, idempotency_key) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, flow_key, goal, target_project, allocator_alias, f"idem-{job_id}")
    )
    conn.commit()
    return job_id
