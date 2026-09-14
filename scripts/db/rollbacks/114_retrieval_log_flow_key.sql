-- Rollback: 114_retrieval_log_flow_key.sql
-- Remove flow_key from knowledge_retrieval_log and delete the 114
-- schema_migrations row so migrate.py can apply the migration again.
--
-- SQLite cannot drop a column in every version the checkout runs on, so
-- this rollback uses the copy-table pattern: create the pre-114 table
-- under a temporary name, copy every row, drop the post-114 table, rename
-- the copy into place, and recreate the two indexes 107 defines.

CREATE TABLE knowledge_retrieval_log_new (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    provider              TEXT NOT NULL,
    scope                 TEXT NOT NULL,
    query                 TEXT NOT NULL,
    result_count          INTEGER NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    sources               TEXT NOT NULL DEFAULT '[]',
    retrieved_token_count INTEGER NOT NULL DEFAULT 0 CHECK (retrieved_token_count >= 0),
    retrieval_duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (retrieval_duration_ms >= 0),
    agent_role            TEXT,
    run_id                TEXT,
    handoff_id            TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO knowledge_retrieval_log_new (id, provider, scope, query,
    result_count, sources, retrieved_token_count, retrieval_duration_ms,
    agent_role, run_id, handoff_id, created_at)
SELECT id, provider, scope, query, result_count, sources,
    retrieved_token_count, retrieval_duration_ms, agent_role, run_id,
    handoff_id, created_at FROM knowledge_retrieval_log;

DROP TABLE knowledge_retrieval_log;

ALTER TABLE knowledge_retrieval_log_new RENAME TO knowledge_retrieval_log;

CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_log_scope_time
    ON knowledge_retrieval_log (scope, created_at);

CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_log_run
    ON knowledge_retrieval_log (run_id, handoff_id);

DELETE FROM schema_migrations WHERE filename = '114_retrieval_log_flow_key.sql';
