-- Migration 005: Unified Model Allocator — set default_model_source for all non-human, non-Freebuff roles
-- This migration makes model-allocator the sole source of truth for model selection.
-- Old columns (default_runtime, default_provider, default_model) are NOT dropped —
-- they are deprecated and ignored when default_model_source = 'model_allocator'.
--
-- Excluded:
--   - All human roles (human, humancloud, humanpay, humantrade) — no model
--   - imple01cloud — Freebuff is a separate execution runtime, not a model backend
--
-- Rollback: see 005_unified_allocator_migration_rollback.sql

-- Already on allocator: imple01 (no change needed)

-- strict_review core
UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'archi-local'
WHERE role_key = 'archi01' AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'review01-local'
WHERE role_key = 'review01' AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'review02-local'
WHERE role_key = 'review02' AND is_active = 1;

-- imple01pay: change alias from imple01-local to imple-pay (OpenRouter backend)
UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'imple-pay'
WHERE role_key = 'imple01pay' AND is_active = 1;

-- Cloud variants (all use local Ollama despite names)
UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'archi-local'
WHERE role_key = 'archi01cloud' AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'review02-local'
WHERE role_key IN ('review01cloud', 'review01pay') AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'review-cloud'
WHERE role_key IN ('review02cloud', 'review02pay') AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'archi-pay'
WHERE role_key = 'archi01pay' AND is_active = 1;

-- Trade roles
UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'archi-local'
WHERE role_key IN ('analyst01_trade', 'sim01_trade') AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'trend-local'
WHERE role_key = 'trend01_trade' AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'coder-96k-local'
WHERE role_key IN ('market01_trade', 'portfolio01_trade') AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'coder-48k-local'
WHERE role_key IN ('risk01_trade', 'score01_trade') AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'learn-local'
WHERE role_key = 'learn01_trade' AND is_active = 1;

UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'review02-local'
WHERE role_key = 'review01_trade' AND is_active = 1;
-- NOTE: migrate.py records this filename in schema_migrations automatically.
