-- 107_knowledge_tables.sql
-- Durable storage for the knowledge layer (SCOPE addendum §3, §4, §8).
--
-- GOAL-DRAFT-002. Three tables, nothing else:
--
--   knowledge_indexes        which repository scopes have an index, through
--                            which provider, and how big it is (§4).
--   knowledge_exclusions     repository-specific rules for what MUST NOT be
--                            indexed (§3).
--   knowledge_retrieval_log  one row per retrieval, the observability record
--                            §8 requires so "with retrieval" can be compared
--                            against "without" (§8, success criterion 7).
--
-- WHY THE SHAPE IS THIS AND NOT SOMETHING RICHER:
--
-- The logical separation between repository scopes is mandatory (addendum §4);
-- the physical layout is explicitly implementation-specific. So `scope` is the
-- only key that matters here and `location` is an opaque string the provider
-- chooses for itself. Nothing in this schema names a retrieval engine: the
-- provider column is a label recorded from config.get_knowledge_provider(), and
-- a future backend replaces it by writing a different string, not by a
-- migration. That is the provider-neutral requirement (addendum §2) expressed
-- in storage.
--
-- knowledge_indexes carries one row PER SCOPE (scope is UNIQUE). An index that
-- is rebuilt updates its own row; the history of rebuilds is not this table's
-- job, and `updated_at` plus `status` answer the questions the indexer asks
-- ("is this scope's index fresh enough to search?").
--
-- knowledge_exclusions is per-scope on purpose. Addendum §3 makes exclusion
-- rules repository-specific, and draft 003 keeps the *defaults* in code as
-- constants — a row here is an operator's addition or removal for one scope,
-- which is why `enabled` exists rather than deletion: a disabled rule keeps
-- the record of what was ruled out and when it was created.
--
-- knowledge_retrieval_log is APPEND-ONLY. It has no UNIQUE constraint and no
-- natural key, because its whole purpose is a record of every retrieval: two
-- identical searches are two rows, and the comparison in §8 counts them. A
-- later draft (007) reads this table to produce the measurement; it never
-- writes it.
--
-- NO SEED DATA: the migration creates schema only. Default exclusion patterns
-- are code constants in the indexer (draft 003), so seeding them here would put
-- one run's opinion about caches and secrets into durable state another run may
-- need to override per scope.
--
-- `status` on knowledge_indexes is deliberately NOT a CHECK constraint. The
-- GOAL names the column but not its vocabulary, and the vocabulary belongs to
-- whichever provider writes it (draft 003/004). Constraining it here would
-- guess a lifecycle no contract has approved yet; a later run that settles it
-- can add the constraint in its own migration.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS
-- throughout, no DROP, no DELETE, no ALTER, no BEGIN/COMMIT (migrate.py wraps
-- each file in a transaction), and no absolute machine paths.

-- ── Per-scope index registry (addendum §4) ─────────────────────────────

CREATE TABLE IF NOT EXISTS knowledge_indexes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Repository scope, e.g. the project this index belongs to. One row per
    -- scope: the UNIQUE constraint is what makes "does this scope have an
    -- index?" a single lookup instead of a scan.
    scope          TEXT NOT NULL UNIQUE,
    -- Which provider built it. Free text by design — see the header note on
    -- provider neutrality.
    provider       TEXT NOT NULL,
    -- Opaque, provider-chosen location of the index on disk. No path is
    -- interpreted here; the config layer resolves where indexes live.
    location       TEXT NOT NULL DEFAULT '',
    -- How many documents the index currently holds. 0 means "built but empty",
    -- which is a different state from "no row at all".
    document_count INTEGER NOT NULL DEFAULT 0 CHECK (document_count >= 0),
    -- Index state as its provider reports it ('unknown' until a provider that
    -- reports exists).
    status         TEXT NOT NULL DEFAULT 'unknown',
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_knowledge_indexes_provider
    ON knowledge_indexes (provider);

-- ── Repository-specific exclusion rules (addendum §3) ──────────────────

CREATE TABLE IF NOT EXISTS knowledge_exclusions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The scope this rule applies to. Exclusions are never global by
    -- implication: a rule for one repository must not silently change what
    -- another repository indexes.
    scope      TEXT NOT NULL,
    -- The pattern itself, interpreted according to `kind`.
    pattern    TEXT NOT NULL,
    -- Three kinds, matching the three ways content gets excluded: by path, by
    -- file name, or by what the file contains (secrets and private keys are
    -- content, not names — addendum §9).
    kind       TEXT NOT NULL CHECK (kind IN ('path', 'name', 'content')),
    -- 1 = active. A rule switched off keeps its row so the record shows what
    -- was ruled out and when it stopped being ruled out.
    enabled    INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- One rule per (scope, pattern): re-registering the same exclusion is an
    -- update to `enabled`, not a second row.
    UNIQUE (scope, pattern)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_exclusions_scope
    ON knowledge_exclusions (scope, enabled);

-- ── Append-only retrieval log (addendum §8) ────────────────────────────

CREATE TABLE IF NOT EXISTS knowledge_retrieval_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    provider              TEXT NOT NULL,
    scope                 TEXT NOT NULL,
    query                 TEXT NOT NULL,
    -- Number of results the provider returned for this query.
    result_count          INTEGER NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    -- Source references of the returned results, as a JSON array written by
    -- the caller. Kept as text so the log stays one row per retrieval.
    sources               TEXT NOT NULL DEFAULT '[]',
    -- Tokens the retrieval put into context, and how long it took: the two
    -- numbers §8's with-vs-without comparison is actually about.
    retrieved_token_count INTEGER NOT NULL DEFAULT 0 CHECK (retrieved_token_count >= 0),
    retrieval_duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (retrieval_duration_ms >= 0),
    -- Who asked, and which unit of work it belongs to. Nullable: a retrieval
    -- can happen outside a role context, and the log must still take the row.
    agent_role            TEXT,
    run_id                TEXT,
    handoff_id            TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-scope retrieval history, oldest first — the shape a report reads.
CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_log_scope_time
    ON knowledge_retrieval_log (scope, created_at);

-- The join key for the execution records the evaluation harness compares
-- against (draft 007).
CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_log_run
    ON knowledge_retrieval_log (run_id, handoff_id);
