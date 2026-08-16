-- Rollback for migration 052: drop implementation_mode from the three
-- bridge tables.
--
-- SQLite 3.35.0 added ALTER TABLE DROP COLUMN. Detected runtime version
-- is 3.45.1 (well above the threshold), so the real DROP COLUMN path is
-- used here. If this rollback is ever applied on a database compiled
-- against an older SQLite, the statements will fail with
-- "no such column: implementation_mode" (the column doesn't exist) or
-- "near \"DROP\": syntax error" (the engine is too old). Both outcomes
-- are intentional: a silent no-op would leave the schema in a state
-- where the migration is partially reverted, and the dispatch code
-- would crash on the next read.

ALTER TABLE bridge_flows      DROP COLUMN implementation_mode;
ALTER TABLE bridge_flow_steps DROP COLUMN implementation_mode;
ALTER TABLE bridge_roles      DROP COLUMN implementation_mode;

DELETE FROM schema_migrations WHERE filename = '052_implementation_mode.sql';
