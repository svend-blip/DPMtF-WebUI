-- Migration 007: Remove deprecated direct model-selection columns.
--
-- These columns are superseded by Model Allocator (default_model_source /
-- default_model_alias on bridge_roles, model_source / model_alias on
-- bridge_flow_steps).
--
-- Dropped from bridge_roles:
--   model_type, cloud_model, ollama_model,
--   default_runtime, default_provider, default_model
--
-- Dropped from bridge_flow_steps:
--   runtime_override, provider_override, model_override
--
-- Prerequisite: migration 006 (documentation-only deprecation).
-- Backup taken before running this migration.

-- bridge_roles: drop deprecated columns
ALTER TABLE bridge_roles DROP COLUMN model_type;
ALTER TABLE bridge_roles DROP COLUMN cloud_model;
ALTER TABLE bridge_roles DROP COLUMN ollama_model;
ALTER TABLE bridge_roles DROP COLUMN default_runtime;
ALTER TABLE bridge_roles DROP COLUMN default_provider;
ALTER TABLE bridge_roles DROP COLUMN default_model;

-- bridge_flow_steps: drop deprecated override columns
ALTER TABLE bridge_flow_steps DROP COLUMN runtime_override;
ALTER TABLE bridge_flow_steps DROP COLUMN provider_override;
ALTER TABLE bridge_flow_steps DROP COLUMN model_override;
