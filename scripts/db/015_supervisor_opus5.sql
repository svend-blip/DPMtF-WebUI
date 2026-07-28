-- Migration 015: run supervisor_auto on Claude Opus 5 instead of Claude Fable 5
--
-- Fable 5 costs $10/$50 per MTok; Opus 5 costs $5/$25 for work of this shape.
-- The supervisor is stateless per wake-up (501_SUPERVISOR_AUTONOMOUS.md) and
-- rebuilds its state from GOAL.md / RUN-LEDGER.md / BACKLOG.md, so it does not
-- need Fable 5's long-horizon context retention.
--
-- The alias name must match model-allocator's models.yaml, and roles.yaml must
-- point supervisor_auto at the same alias: start_coding.py resolves the actual
-- claude-code model through `model-allocator run --role supervisor_auto`.
--
-- Idempotent: re-running only re-asserts the same values.

UPDATE bridge_roles
SET default_model_source = 'model_allocator',
    default_model_alias = 'opus5',
    updated_at = CURRENT_TIMESTAMP
WHERE role_key = 'supervisor_auto';
