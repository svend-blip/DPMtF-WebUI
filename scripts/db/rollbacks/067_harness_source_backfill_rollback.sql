-- Rollback for migration 067: undo the backfill of default_harness_source
-- from allocator_client, but ONLY for the rows the marker table captured.
--
-- Why a marker table: the backfill UPDATE is "WHERE default_harness_source
-- IS NULL AND allocator_client IS NOT NULL". An independent post-backfill
-- write (e.g. a role whose default_harness_source was set by another path
-- AFTER 067 was applied) would NOT be in the marker table and would
-- survive the rollback. The resolver reads default_harness_source either
-- way; the mirror in allocator_client is the durable copy.
--
-- After nulling the backfilled rows and dropping the marker table, remove
-- the schema_migrations row that migrate.py wrote, so a subsequent
-- `python3 scripts/migrate.py` re-applies 067 cleanly.
--
-- mirrors the comment style of rollbacks/062_step_execution_config_rollback.sql
-- and rollbacks/061_supervisor_role_rollback.sql.

UPDATE bridge_roles
SET default_harness_source = NULL
WHERE role_key IN (SELECT role_key FROM _migration_067_backfilled_roles);

DROP TABLE IF EXISTS _migration_067_backfilled_roles;

DELETE FROM schema_migrations WHERE filename = '067_harness_source_backfill.sql';
