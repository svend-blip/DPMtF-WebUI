-- Rollback for 119. Nothing is deleted: on the production database these
-- flows, roles and steps predate the migration and carry its run history, and
-- the rows 119 inserted cannot be told from the rows it found. Only the
-- bookkeeping is undone, so the migration can be applied again; every
-- statement in it is INSERT OR IGNORE.

DELETE FROM schema_migrations WHERE filename = '119_core_flows.sql';
