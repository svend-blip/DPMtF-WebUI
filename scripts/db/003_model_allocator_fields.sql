-- Migration 003: add nullable Model Allocator source/alias columns to bridgeV002.
--
-- Adds the opt-in fields required for the V1B allocator pilot (handoff 66):
--   - bridge_roles.default_model_source
--   - bridge_roles.default_model_alias
--   - bridge_flow_steps.model_source
--   - bridge_flow_steps.model_alias
--
-- All columns are nullable with default NULL so existing `direct_*` roles and
-- steps continue to work unchanged. The model_allocator source is opt-in per
-- role/step; no global switch is introduced.
--
-- Idempotency: this migration is recorded in schema_migrations. Re-running
-- scripts/migrate.py skips already-applied migrations. If a column already
-- exists outside the migration table, SQLite will error — that situation
-- should be reconciled manually.

ALTER TABLE bridge_roles ADD COLUMN default_model_source TEXT;
ALTER TABLE bridge_roles ADD COLUMN default_model_alias TEXT;

ALTER TABLE bridge_flow_steps ADD COLUMN model_source TEXT;
ALTER TABLE bridge_flow_steps ADD COLUMN model_alias TEXT;
