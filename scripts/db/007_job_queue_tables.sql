-- Migration 007: Job Queue tables
-- Durable job lifecycle with atomic claims, leases, retries, and dependency scheduling.
-- Based on verified spike (Task 4.2 GO, 12 tests green).

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    workflow_run_id TEXT,
    flow_key TEXT NOT NULL,
    step_key TEXT,
    role_key TEXT NOT NULL,
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
    goal TEXT NOT NULL,
    target_project TEXT NOT NULL,
    scope_version TEXT,
    checkpoint_path TEXT,
    context_fit_state TEXT,
    parent_job_id TEXT,
    continuation_index INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
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
CREATE INDEX IF NOT EXISTS idx_jobs_flow ON jobs(flow_key, status);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id);
