-- Rollback for migration 070: undo the model_source 'harness' ->
-- 'harness_provider' flip for the two migrated roles (super-deep-deep4,
-- imple-codex-minimaxM3) using the marker table as the source of truth
-- for the prior values.
--
-- Why a marker table: the migration's UPDATE is scoped to the two roles
-- by name (a blanket model_source match is unsafe). The marker table
-- captures the exact prior value for every row the migration touched,
-- so the rollback can restore byte-exact prior values even if a future
-- migration changes the same rows in between. The marker-table CREATE
-- and INSERT sit outside the migration's trigger-bound UPDATE, so they
-- survive a guard abort — the rollback must still be able to read them.
--
-- After restoring the prior values and dropping the marker table,
-- remove the schema_migrations row that migrate.py wrote, so a
-- subsequent `python3 scripts/migrate.py` re-applies 070 cleanly.
--
-- mirrors the comment style of rollbacks/067_harness_source_backfill_rollback.sql
-- and rollbacks/062_step_execution_config_rollback.sql.

UPDATE bridge_roles
SET default_model_source = (
    SELECT prior_model_source
    FROM _migration_070_prior_model_source
    WHERE _migration_070_prior_model_source.role_key = bridge_roles.role_key
)
WHERE role_key IN (SELECT role_key FROM _migration_070_prior_model_source);

DROP TABLE IF EXISTS _migration_070_prior_model_source;

DELETE FROM schema_migrations WHERE filename = '070_model_source_harness_provider.sql';
