-- 065: Governance implementor + supervisor repoint -- Run 011 (GH-2c) D4.
--
-- Goal (GOAL.md section 1 D4, section 2, section 15):
-- Set bridge_flow_steps.governance_file at STEP level for every active step
-- whose from_role is one of the eight IDLE implementor labels (binding to
-- IMPLEMENTOR.md) or one of the three autonomous-supervisor labels (binding
-- to SUPERVISOR_AUTONOMOUS.md). The thirteen absorbed originals are NOT
-- deleted or edited; bridge_roles.governance_file keeps pointing at them
-- as the role-level fallback (the resolver's precedence STEP > ROLE >
-- SYSTEM guarantees the new step-level value wins where it is set).
--
-- Then seed bridge_flows.supervisor_role for the five autonomous flows.
-- The 061 column was added with all-NULL values (opt-in); this migration
-- flips it on for the five flows that have an autonomous supervisor in the
-- chain. Seeding activates the generalized stall wake-up (chain_watchdog's
-- _supervisor_wake_up reads this column) for those five flows in
-- production, deliberately.
--
-- Section 15 semantics:
-- Step governance describes the from_role. The predicates below are
-- exclusively from_role-shaped; they do not reference to_role. This is
-- the section 15 contract -- a to_role-shaped mistake is caught by the
-- D7 tests (the invariant group carries the contract; rehearsal mutation
-- m2 from Run 009 was caught the same way).
--
-- Exact predicates and expected row counts (current DB state at authoring):
--   8 implementor steps                                 -> IMPLEMENTOR.md
--   3 supervisor steps                                   -> SUPERVISOR_AUTONOMOUS.md
--   Total: 11 step rows updated.
--
--   bridge_flows.supervisor_role seeded for 5 autonomous flows:
--     supervised_review        -> supervisor_auto
--     llama_SG                 -> supervisor01_llama
--     reveng                   -> Rev_Supervisor
--     preferred_cloud          -> Pre-super-cl
--     preferred_cloud_harness  -> super-deep-deep4
--
-- Deliberate exclusion (NOT in any bridge_flow_steps UPDATE predicate this
-- run; a later run repoints the live-flow actors after this run has held
-- in production):
--   'Pre-imple-cl'    -- preferred_cloud implementor, drives daily production
--   'Pre-super-cl'    -- preferred_cloud supervisor, drives daily production
--   'imple-codex-minimaxM3'  -- the remote worker for this executing flow
--   'super-deep-deep4'       -- the autonomous supervisor for this flow
--   'imple01LW'       -- the remote-worker exception (481 stays authoritative)
-- NONE of these five labels may appear in any bridge_flow_steps UPDATE
-- predicate. Note that 'Pre-super-cl' and 'super-deep-deep4' DO appear as
-- VALUES in the bridge_flows supervisor_role seeding below -- the deferral
-- is about step-level governance binding, not about flow-level seeding.
-- The D7 live_flows_deferred test group pins the deferral at the step-
-- UPDATE-predicate level only (where it is meaningful).
--
-- Why NO ALTER/CREATE/DROP:
-- Schema is already in place. bridge_flow_steps.governance_file TEXT NULL
-- was added by migration 062 (Run 007); bridge_flows.supervisor_role
-- TEXT NULL was added by migration 061 (Run 007). This migration only
-- writes to those columns.
--
-- Why NO UPDATE to bridge_roles:
-- The role-level pointers to the thirteen absorbed originals remain in
-- place as the fallback. Removing them is Phase 5 of the spec, out of
-- scope for this run.
--
-- Why no idempotency guard inside this file: scripts/migrate.py records
-- the filename in schema_migrations after a successful apply, so
-- re-running migrate.py is a no-op against this file. Re-running these
-- UPDATEs against rows that already match is harmless (the value is
-- identical), but the runner's schema_migrations check makes the second
-- run a no-op at the file level anyway.
--
-- Why two UPDATE statements for bridge_flow_steps and five for
-- bridge_flows:
-- The two bridge_flow_steps UPDATEs target disjoint from_role sets (the
-- eight IDLE implementor labels vs. the three autonomous-supervisor
-- labels). Splitting them keeps each predicate narrow and the row counts
-- separately auditable (the D7 test counts the repointed rows per group,
-- not in aggregate). The five bridge_flows UPDATEs are per-flow by
-- design -- each one is the explicit opt-in the section 2 contract binds.

UPDATE bridge_flow_steps
   SET governance_file = 'IMPLEMENTOR.md'
 WHERE is_active = 1
   AND from_role IN ('imple01', 'imple01cloud', 'imple01pay', 'imple01sup',
                     'pi_imple01', 'oc_imple01', 'imple01SG', 'Rev_Imple');

UPDATE bridge_flow_steps
   SET governance_file = 'SUPERVISOR_AUTONOMOUS.md'
 WHERE is_active = 1
   AND from_role IN ('supervisor_auto', 'supervisor01_llama',
                     'Rev_Supervisor');

UPDATE bridge_flows SET supervisor_role = 'supervisor_auto' WHERE flow_key = 'supervised_review' AND is_active = 1;
UPDATE bridge_flows SET supervisor_role = 'supervisor01_llama' WHERE flow_key = 'llama_SG' AND is_active = 1;
UPDATE bridge_flows SET supervisor_role = 'Rev_Supervisor' WHERE flow_key = 'reveng' AND is_active = 1;
UPDATE bridge_flows SET supervisor_role = 'Pre-super-cl' WHERE flow_key = 'preferred_cloud' AND is_active = 1;
UPDATE bridge_flows SET supervisor_role = 'super-deep-deep4' WHERE flow_key = 'preferred_cloud_harness' AND is_active = 1;
