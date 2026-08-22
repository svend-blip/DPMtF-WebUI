-- 067: Harness Source Unification — backfill default_harness_source from
--       allocator_client for every active role that has no current value.
--
-- Goal (GOAL.md section 1, section 2; spec section 9/Phase 4):
-- End the two-competing-concepts state where allocator_client and
-- default_harness_source both carry the harness key. allocator_client
-- stays in the schema and in every row (no DROP COLUMN, no rename,
-- no value rewrite — frozen mirror). default_harness_source becomes
-- the single authoritative role-level harness source for the readers
-- the next handoffs will switch.
--
-- This migration ONLY writes the OTHER column (default_harness_source)
-- where it is NULL. Rows with a non-NULL default_harness_source are
-- left UNTOUCHED (an independent write by another path wins; the
-- resolver reads default_harness_source either way).
--
-- Idempotency: the marker table is created with IF NOT EXISTS, the
-- row insert is INSERT OR IGNORE (role_key is UNIQUE), and the UPDATE's
-- NULL predicate excludes rows already backfilled. Re-running this file
-- against an already-applied database is a no-op (zero rows updated,
-- marker table already exists with the original rows).
--
-- Safety under partial apply: the marker table records WHICH rows were
-- backfilled in this apply, so the rollback can null ONLY those rows
-- and leave any independent post-backfill write intact.
--
-- The two model_source='harness' roles (super-deep-deep4, imple-codex-minimaxM3)
-- are NOT special-cased: their default_model_source is 'harness' (untouched),
-- and this migration only touches default_harness_source. They will be
-- backfilled like any other role.
--
-- Why no pragma / no schema change: migration 062 already added the
-- default_harness_source column. This migration only writes data.

CREATE TABLE IF NOT EXISTS _migration_067_backfilled_roles (
    role_key TEXT PRIMARY KEY,
    backfilled_harness_source TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Snapshot rows that are about to be backfilled (pre-update state).
-- INSERT OR IGNORE keeps this idempotent: a re-run that finds the
-- row already present skips the duplicate insert without raising.
INSERT OR IGNORE INTO _migration_067_backfilled_roles (role_key, backfilled_harness_source)
SELECT role_key, allocator_client
FROM bridge_roles
WHERE is_active = 1
  AND default_harness_source IS NULL
  AND allocator_client IS NOT NULL;

-- Backfill default_harness_source from allocator_client for the rows
-- the snapshot captured. The IS NULL predicate makes the UPDATE a
-- no-op on rows already backfilled (independent post-backfill writes
-- survive this migration).
UPDATE bridge_roles
SET default_harness_source = allocator_client
WHERE is_active = 1
  AND default_harness_source IS NULL
  AND allocator_client IS NOT NULL;
