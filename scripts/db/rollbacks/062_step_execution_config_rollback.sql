-- Rollback for migration 062: drop the five step-execution columns.
--
-- SQLite 3.35.0 added ALTER TABLE DROP COLUMN. Detected runtime version
-- on this project is 3.45.1 (well above the threshold), so the real
-- DROP COLUMN path is used here. If this rollback is ever applied on a
-- database compiled against an older SQLite, the statements will fail
-- with "no such column: <name>" (the column doesn't exist) or
-- "near \"DROP\": syntax error" (the engine is too old). Both outcomes
-- are intentional: a silent no-op would leave the schema in a state
-- where the migration is partially reverted, and the resolver would
-- crash on the next read because some columns would be present and
-- others missing.
--
-- After dropping the columns, remove the schema_migrations row that
-- migrate.py wrote, so a subsequent `python3 scripts/migrate.py`
-- re-applies 062 cleanly. mirrors the comment style of
-- rollbacks/061_supervisor_role_rollback.sql and
-- rollbacks/052_implementation_mode_rollback.sql.

ALTER TABLE bridge_flow_steps DROP COLUMN governance_file;
ALTER TABLE bridge_flow_steps DROP COLUMN harness_source;
ALTER TABLE bridge_flow_steps DROP COLUMN harness_profile;
ALTER TABLE bridge_roles      DROP COLUMN default_harness_source;
ALTER TABLE bridge_roles      DROP COLUMN default_harness_profile;

DELETE FROM schema_migrations WHERE filename = '062_step_execution_config.sql';
