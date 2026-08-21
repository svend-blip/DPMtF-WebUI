-- 062: Step-key execution schema -- bound storage for the unified resolver.
--
-- Goal (GOAL.md section 1, section 2; spec section 1-8, 15, 17):
-- Governance today is bound only to bridge_roles; model selection is partly
-- at step level. The unified resolver needs step-key bound storage so the
-- precedence STEP -> ROLE DEFAULT -> SYSTEM/LEGACY can be expressed once
-- for governance, model, and harness, identically. This migration adds the
-- storage; the resolver lives in scripts/bridgeV002/execution_config.py.
--
-- bridge_flow_steps gains three nullable TEXT columns:
--   governance_file   -- step-level governance override (Phase 3 will
--                        deduplicate file content; this migration does not
--                        touch any governance file)
--   harness_source    -- step-level harness override (e.g. 'codex', 'opencode')
--   harness_profile   -- step-level harness profile/preset
--
-- bridge_roles gains two nullable TEXT columns:
--   default_harness_source  -- role-level harness default. Until Phase 4
--                              migrates it, the resolver falls back to the
--                              legacy allocator_client column for the role
--                              default (COALESCE semantics, GOAL.md section 1 D2).
--                              Both columns are LOAD-BEARING for the
--                              preferred_cloud_harness chain -- read them,
--                              never rewrite them.
--   default_harness_profile -- role-level harness profile default.
--
-- bridge_flow_steps already has model_source/model_alias/implementation_mode;
-- bridge_roles already has governance_file/allocator_client/
-- default_model_source/default_model_alias/implementation_mode. This
-- migration does NOT touch those existing columns -- it ONLY adds the five
-- new nullable columns.
--
-- Why all DEFAULT NULL: every existing row stays NULL, so every existing
-- flow resolves identically to the legacy behavior (zero behavior change,
-- GOAL.md section 1; mechanically guarded by TG10 in a later handoff). Opting any
-- step or role into a non-NULL value is a separate decision, made by the
-- run that wants it, and is not in the fence of this handoff.
--
-- Why NO UPDATE statements: same reason -- opting in is a separate decision.
-- This migration only adds storage.
--
-- Why NO pragma / idempotency guard inside this file: scripts/migrate.py
-- records the filename in schema_migrations after a successful apply, so
-- re-running migrate.py is a no-op against the column adds. Re-adding a
-- column that already exists raises "duplicate column name" -- that is the
-- intended failure mode (better than silently promoting a partial apply).

ALTER TABLE bridge_flow_steps ADD COLUMN governance_file TEXT DEFAULT NULL;
ALTER TABLE bridge_flow_steps ADD COLUMN harness_source  TEXT DEFAULT NULL;
ALTER TABLE bridge_flow_steps ADD COLUMN harness_profile TEXT DEFAULT NULL;
ALTER TABLE bridge_roles      ADD COLUMN default_harness_source  TEXT DEFAULT NULL;
ALTER TABLE bridge_roles      ADD COLUMN default_harness_profile TEXT DEFAULT NULL;
