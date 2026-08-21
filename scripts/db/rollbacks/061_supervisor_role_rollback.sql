-- Rollback for migration 061: drop supervisor_role from bridge_flows.
--
-- SQLite 3.35.0 added ALTER TABLE DROP COLUMN. Detected runtime version
-- on this project is 3.45.1 (well above the threshold), so the real
-- DROP COLUMN path is used here. If this rollback is ever applied on a
-- database compiled against an older SQLite, the statement will fail
-- with "no such column: supervisor_role" (the column doesn't exist) or
-- "near \"DROP\": syntax error" (the engine is too old). Both outcomes
-- are intentional: a silent no-op would leave the schema in a state
-- where the migration is partially reverted, and the dispatch code
-- would crash on the next read.

ALTER TABLE bridge_flows DROP COLUMN supervisor_role;

DELETE FROM schema_migrations WHERE filename = '061_supervisor_role.sql';
