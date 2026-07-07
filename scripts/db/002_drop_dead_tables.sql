-- Migration 002: retroactively encode Fase F dead-table drops (handoffs 59+60).
--
-- The 13 tables below were confirmed dead by a reachability audit:
--   - Frontend (static/js/dpmtf-app.js) calls only /api/prompt-compiler/compile,
--     /api/prompt-compiler/assign-handoff-id, and /api/prompt-compiler/dispatch.
--   - No mcp-light consumer, no shell/cronjob/scripts consumer, and no internal
--     Python caller for the removed endpoints.
--   - Data was seed-only or old dev-test writes.
--
-- They were originally dropped ad-hoc via scripts/migrate_c3_drop_dead_tables.py
-- before the versioned migration system existed (Fase E-2 / handoff 61). This
-- migration records those drops in schema_migrations history so the evolution is
-- tracked and reproducible.
--
-- This migration is a NO-OP on the live DB (tables already dropped) and on a
-- fresh DB (001_baseline.sql creates only the 37 live tables, not these 13).
-- It supersedes scripts/migrate_c3_drop_dead_tables.py, which is retired.

-- Children-first drop order for the dead-table cluster:
DROP TABLE IF EXISTS generated_prompts;
DROP TABLE IF EXISTS prompt_sequence_steps;
DROP TABLE IF EXISTS project_plans;
DROP TABLE IF EXISTS prompt_compiler_field_options;
DROP TABLE IF EXISTS prompt_sequences;
DROP TABLE IF EXISTS prompt_compiler_fields;
DROP TABLE IF EXISTS prompt_runs;
DROP TABLE IF EXISTS prompt_templates;
DROP TABLE IF EXISTS prompt_hitrates;
DROP TABLE IF EXISTS template_model_hitrates;
DROP TABLE IF EXISTS implementation_patterns;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS reference_projects;
