-- 030: Durable state for the §20 LightWorker protocol.
--
-- Run 007 built routers/lightworkers.py and shipped an InMemoryStore
-- beside it. Mounting that store as-is is "a live endpoint with
-- amnesia": every offer, claim, completion and event vanishes when
-- the WebUI restarts. This migration lays the schema that a
-- SqliteLightWorkerStore (routers/lightworker_store.py) reads and
-- writes instead.
--
-- WHAT THIS SCHEMA IS FOR:
--
-- The store implements the same interface LightWorkerStore declares
-- in routers/lightworkers.py: register, heartbeat, offer, offer_next,
-- claim, execution_heartbeat, record_event, complete, fail,
-- completion_count, failure_count. The columns here are the smallest
-- shape that carries the §20 properties durably.
--
--   execution_id   primary key, the §16.4 path branch
--                  (e.g. EXEC-123-IMPLE01)
--   handoff_id     reference to the upstream handoff that produced
--                  this execution. NOT the key — an execution is keyed
--                  on its own id, the handoff is a reference. This is
--                  run 009's resolution of the design question left
--                  open by run 007.
--   worker_id      the LightWorker the execution is addressed to.
--                  The router only offers an execution to its own
--                  worker; a claim from anyone else is refused.
--   target_role    the role name to execute (e.g. imple01).
--   state          'offered' until offered to a worker
--                  ('delivered'), then 'claimed' on the winning
--                  claim(), then 'completed' on the first
--                  complete() or 'failed' on the first fail().
--                  The §20 atomic-claim property rests on this
--                  column — see claim in the store.
--   attempt_id     the live attempt, NULL until claim, then the
--                  attempt_id of the worker that won. Used to bind
--                  heartbeats and to give complete/fail their key.
--   payload_json   the original execution dict, stored as-is, so
--                  offer_next can return the exact fields the seed
--                  put in. InMemoryStore does the same with a private
--                  _status field; here the status is its own column.
--   created_at / updated_at — timestamps.
--
-- WHY EVENTS ARE A SECOND TABLE, NOT A JSON COLUMN:
--
-- The obvious shortcut is a JSON column on lightworker_executions
-- that grows with each record_event. Every append becomes a
-- read-modify-write — SELECT current, append locally, UPDATE — and
-- that is the precise race this run exists to eliminate. An
-- append-only table makes it one INSERT, which is what the §20
-- protocol's record_event contract actually says. Events are
-- append-only, and so is the table.
--
-- WHY COMPLETIONS AND FAILURES ARE TABLES, NOT FLAGS:
--
-- Idempotency of complete()/fail() per (execution_id, attempt_id) is
-- the §20 property that must hold across process boundaries. The
-- UNIQUE constraint on (execution_id, attempt_id) is what enforces
-- it: INSERT ... ON CONFLICT DO NOTHING returns whether the row
-- changed. A SELECT-then-INSERT is the same defect as a
-- read-then-write claim, one table over, and it loses the race the
-- same way.
--
-- A separate counter column on the completions/failures rows is not
-- worth its weight: the row's existence IS the count. completion_count
-- / failure_count return 0 or 1 from a SELECT COUNT(*) WHERE.
--
-- THE RUN-007 RESOLUTION:
--
-- Run 007's ledger recorded that a *different* attempt_id on an
-- already-completed execution was accepted, leaving two completions
-- with different content and nobody to arbitrate. The schema refuses
-- this: the store reads the row's state='completed' before inserting
-- and raises ExecutionAlreadyCompleted on a different attempt_id.
-- Idempotent replay of the SAME attempt_id returns False without
-- changing state.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT
-- EXISTS everywhere. The store also applies this file on construction
-- so a fresh database bootstraps; several processes may do so at the
-- same time and IF NOT EXISTS keeps that race benign.

CREATE TABLE IF NOT EXISTS lightworker_executions (
    execution_id   TEXT PRIMARY KEY,
    handoff_id     TEXT,
    worker_id      TEXT NOT NULL,
    target_role    TEXT NOT NULL,
    state          TEXT NOT NULL DEFAULT 'offered'
                   CHECK (state IN ('offered', 'delivered', 'claimed', 'completed', 'failed')),
    attempt_id     TEXT,
    payload_json   TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS lightworker_executions_worker_idx
    ON lightworker_executions (worker_id, state);

CREATE INDEX IF NOT EXISTS lightworker_executions_state_idx
    ON lightworker_executions (state);

CREATE TABLE IF NOT EXISTS lightworker_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    worker_id    TEXT NOT NULL,
    event_json   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS lightworker_events_execution_idx
    ON lightworker_events (execution_id, event_id);

CREATE TABLE IF NOT EXISTS lightworker_completions (
    execution_id TEXT NOT NULL,
    attempt_id   TEXT NOT NULL,
    worker_id    TEXT NOT NULL,
    result_json  TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (execution_id, attempt_id)
);

CREATE TABLE IF NOT EXISTS lightworker_failures (
    execution_id TEXT NOT NULL,
    attempt_id   TEXT NOT NULL,
    worker_id    TEXT NOT NULL,
    failure_json TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (execution_id, attempt_id)
);

CREATE TABLE IF NOT EXISTS lightworker_worker_state (
    worker_id      TEXT PRIMARY KEY,
    capabilities_json TEXT NOT NULL,
    heartbeat_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lightworker_execution_heartbeats (
    execution_id TEXT NOT NULL,
    worker_id    TEXT NOT NULL,
    attempt_id   TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (execution_id, worker_id, attempt_id)
);