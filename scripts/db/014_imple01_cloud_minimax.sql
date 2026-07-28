-- Migration 014: run imple01 on the MiniMax cloud model
--
-- imple01 ran on the local Ollama alias 'imple01-local'
-- (qwen3-coder-30b-96k). The role now resolves to model-allocator's
-- 'cloud_minimax' alias (MiniMax-M3 over the OpenAI-compatible endpoint).
--
-- The alias name must match model-allocator's models.yaml, and roles.yaml
-- must point imple01 at the same alias: start_coding.py resolves the actual
-- OpenCode model through `model-allocator run --role imple01`, which reads
-- roles.yaml, while this column drives warm-up/teardown and idle checks.
--
-- Idempotent: re-running only re-asserts the same values.

UPDATE bridge_roles
SET default_model_source = 'model_allocator',
    default_model_alias = 'cloud_minimax',
    updated_at = CURRENT_TIMESTAMP
WHERE role_key = 'imple01';
