-- 100 — Allow 'goal-draft' as a bridge_materialize_queue artifact_type.
--
-- bridge_broker.py lists 'goal-draft' as a materialize type, but the
-- bridge_materialize_queue.artifact_type CHECK omitted it, so
-- `materialize --type goal-draft` was rejected and every planning draft
-- has been written host-side. SQLite cannot ALTER a CHECK, so the table is
-- recreated with 'goal-draft' added; all rows are preserved. (No BEGIN/COMMIT
-- or PRAGMA: migrate.py wraps each migration in its own transaction.)
CREATE TABLE bridge_materialize_queue_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    run_id INTEGER,
    handoff_id INTEGER,
    role_key TEXT,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN
        ('backlog', 'run-ledger', 'handoff', 'end-report', 'escalation-response', 'goal-draft')),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    processed_at TEXT,
    error_msg TEXT,
    broker_pid INTEGER
);
INSERT INTO bridge_materialize_queue_new
    SELECT id, flow_key, run_id, handoff_id, role_key, artifact_type, content,
           status, created_at, claimed_at, processed_at, error_msg, broker_pid
    FROM bridge_materialize_queue;
DROP TABLE bridge_materialize_queue;
ALTER TABLE bridge_materialize_queue_new RENAME TO bridge_materialize_queue;
CREATE INDEX bridge_materialize_queue_status_idx ON bridge_materialize_queue(status, id);
CREATE INDEX bridge_materialize_queue_flow_idx ON bridge_materialize_queue(flow_key, status, id);
