-- 109_knowledge_scope_grants.sql
-- Per-scope grants for DPMtF-internal development memory (GOAL-DRAFT-009).
--
-- GOAL-DRAFT-009 adds explicit scope permissions so repository boundaries are
-- enforced at the knowledge layer, not merely assumed by the provider. This
-- migration stores the grants themselves; the provider-neutral guard that
-- reads them lives in knowledge/scope_guard.py and is the only reader.
--
-- One table, nothing else. A row is an explicit Human grant for one exact
-- (scope, agent_role, flow_key) triple: the UNIQUE constraint makes "does
-- this exact triple have a grant?" a single lookup, and makes re-recording
-- the same grant a conflict rather than a second row.
--
-- WHY THIS SHAPE AND NOT SOMETHING RICHER:
--
-- agent_role and flow_key are both nullable on purpose. A grant is keyed by
-- exactly the identity the caller can provide; absent means "unknown / not
-- provided", and the guard treats an absent value as a value that must match
-- a stored NULL — never as a wildcard that matches every row. That is
-- default-deny expressed in storage: a caller that does not name a role or a
-- flow gets a grant only for the exact triple (scope, NULL, NULL), which the
-- Human records explicitly.
--
-- There is deliberately no authentication table, no user identity, and no UI
-- here. Draft 009 is scope enforcement only; identity systems are out of
-- scope, and grants are maintained with plain SQL by the operator (the Human).
--
-- No provider is named anywhere in this schema. scope is an opaque string the
-- caller passes through; the guard's is_internal_scope() decides whether the
-- scope needs a grant at all, so a future provider or scope vocabulary does
-- not require a migration.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS only, no DROP, no DELETE, no ALTER,
-- no seed rows, and no BEGIN/COMMIT (migrate.py wraps each file in a
-- transaction).

CREATE TABLE IF NOT EXISTS knowledge_scope_grants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The internal scope this grant opens, e.g. 'dpmtf-webui'.
    scope      TEXT NOT NULL,
    -- Which agent role the grant is for. NULL means the caller did not
    -- provide a role; it is not a wildcard.
    agent_role TEXT,
    -- Which flow the grant is for. NULL means the caller did not provide a
    -- flow; it is not a wildcard.
    flow_key   TEXT,
    -- When the Human recorded the grant.
    granted_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- One grant per exact (scope, agent_role, flow_key) triple. Re-recording
    -- the same triple is a conflict, not a duplicate row.
    UNIQUE (scope, agent_role, flow_key)
);
