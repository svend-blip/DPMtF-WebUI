-- Rollback for migration 071: undo the default_harness_profile = 'gpu' flip
-- on imple-codex-minimaxM3 using the marker table as the source of truth for
-- the prior value.
--
-- Why a marker table: the migration's UPDATE is scoped to ONE role by name
-- (a blanket default_harness_profile IS NULL match would be unsafe — it
-- could touch review-claude-sonnet5 or super-deep-deep4 if a future
-- migration left them NULL). The marker table captures the exact prior
-- value for the one row the migration touched, so the rollback can restore
-- byte-exact prior values even if a future migration changes the same row
-- in between. The marker-table CREATE and INSERT sit outside the
-- migration's trigger-bound UPDATE, so they survive a guard abort — the
-- rollback must still be able to read them.
--
-- After restoring the prior values and dropping the marker table, remove
-- the schema_migrations row that migrate.py wrote, so a subsequent
-- `python3 scripts/migrate.py` re-applies 071 cleanly.
--
-- Mirrors the comment style of rollbacks/070_model_source_harness_provider_rollback.sql
-- and rollbacks/067_harness_source_backfill_rollback.sql.

UPDATE bridge_roles
SET default_harness_profile = (
    SELECT prior_harness_profile
    FROM _migration_071_prior_harness_profile
    WHERE _migration_071_prior_harness_profile.role_key = bridge_roles.role_key
)
WHERE role_key IN (SELECT role_key FROM _migration_071_prior_harness_profile);

DROP TABLE IF EXISTS _migration_071_prior_harness_profile;

DELETE FROM schema_migrations WHERE filename = '071_imple_gpu_harness_profile.sql';
