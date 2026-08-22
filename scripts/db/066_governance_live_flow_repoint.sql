-- 066: Governance live-flow repoint -- Run 012 (GH-2d) D1 + D2.
--
-- Goal (GOAL.md section 1 D1 + D2, section 2, section 15):
-- Set bridge_flow_steps.governance_file at STEP level for every active step
-- whose from_role is one of the three preferred_cloud live-flow roles (D1,
-- part a) or one of the three preferred_cloud_harness live-flow roles (D2,
-- part b). These are the two LIVE flows every earlier run (009/010/011)
-- deliberately excluded.
--
-- The 4xx/5xx originals (471/472/473/511/512/513) are NOT deleted or
-- edited; bridge_roles.governance_file keeps pointing at them as the
-- role-level fallback (the resolver's precedence STEP > ROLE > SYSTEM
-- guarantees the new step-level value wins where it is set).
--
-- Section 15 semantics:
-- Step governance describes the from_role. The predicates below are
-- exclusively from_role-shaped; they do not reference to_role.
--
-- TWO-PART APPLICATION (binding -- GOAL.md section 2 "Sequencing"):
--   Part a (preferred_cloud -- the idle flow) is applied FIRST, in
--     handoff 051, only while NO preferred_cloud run is open (GOAL.md
--     section 1 D1 precondition).
--   Part b (preferred_cloud_harness -- the EXECUTING flow) is applied
--     LAST, in handoff 052, so the maximum number of this run's own
--     deliveries exercise the new step-level resolution (the live
--     acceptance TG8 measures in trace.log).
--   Because migrate.py applies a whole file at once, the two parts are
--     applied by direct sqlite3 in the run -- NOT via migrate.py. On a
--     fresh database (or after this run), migrate.py applies the whole
--     file idempotently: every UPDATE is already true, so re-running is
--     harmless.
--
-- Rollback coupling (GOAL.md section 2 / rehearsal finding):
--   The 066 rollback restores DB state only. Full host recovery is the
--   SQL rollback PLUS git-revert of the rename commit (the D4 renames
--   from handoff 050). The migration and rollback headers both state
--   this.
--
-- Why NO ALTER/CREATE/DROP:
-- Schema is already in place from 062 (governance_file TEXT NULL added
-- on bridge_flow_steps). This migration only writes to that column.
--
-- Why NO UPDATE to bridge_roles:
-- The role-level pointers to the 4xx/5xx originals remain in place as
-- the fallback. Removing them is Phase 5 of the spec, out of scope for
-- this run.

-- Part a -- preferred_cloud (idle flow; applied FIRST, handoff 051):
UPDATE bridge_flow_steps SET governance_file = 'IMPLEMENTOR.md'
 WHERE is_active = 1 AND from_role = 'Pre-imple-cl';
UPDATE bridge_flow_steps SET governance_file = 'SUPERVISOR_AUTONOMOUS.md'
 WHERE is_active = 1 AND from_role = 'Pre-super-cl';
UPDATE bridge_flow_steps SET governance_file = 'REVIEW.md'
 WHERE is_active = 1 AND from_role = 'Pre-review-cl';

-- Part b -- preferred_cloud_harness (the executing flow; applied LAST, handoff 052):
UPDATE bridge_flow_steps SET governance_file = 'IMPLEMENTOR.md'
 WHERE is_active = 1 AND from_role = 'imple-codex-minimaxM3';
UPDATE bridge_flow_steps SET governance_file = 'SUPERVISOR_AUTONOMOUS.md'
 WHERE is_active = 1 AND from_role = 'super-deep-deep4';
UPDATE bridge_flow_steps SET governance_file = 'REVIEW.md'
 WHERE is_active = 1 AND from_role = 'review-claude-sonnet5';
