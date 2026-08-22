-- 064: Governance review repoint -- Run 010 (GH-2b) D4.
--
-- Goal (GOAL.md section 1 D4, section 2, section 15):
-- Set bridge_flow_steps.governance_file at STEP level for every active step
-- whose from_role is one of the nine reviewer labels that absorbed into the
-- three generic review files (handoffs 041/042/043/044). The eleven
-- absorbed originals are NOT deleted or edited; bridge_roles.governance_file
-- keeps pointing at them as the role-level fallback (the resolver's
-- precedence STEP > ROLE > SYSTEM guarantees the new step-level value wins
-- where it is set).
--
-- Section 15 semantics:
-- Step governance describes the from_role. The predicates below are
-- exclusively from_role-shaped; they do not reference to_role. This is the
-- §15 contract -- a to_role-shaped mistake is caught by the D5 tests (the
-- invariant group carries the contract; rehearsal mutation m2 was caught
-- there in Run 009, and the same shape is mirrored here).
--
-- Exact predicates and expected row counts (current DB state at authoring):
--   4 technical-review steps (strict_review, cloud_llm, cloud_pay,
--     supervised_review)               -> TECHNICAL_REVIEW.md
--   4 governance-review steps (strict_review, cloud_llm, cloud_pay,
--     supervised_review)               -> GOVERNANCE_REVIEW.md
--   1 single-layer review step (llama_SG) -> REVIEW.md
--   Total: 9 rows updated.
--
-- Deliberate deferral (NOT in any UPDATE predicate this run):
--   'Pre-review-cl' (preferred_cloud) and 'review-claude-sonnet5'
--   (this very flow's reviewer -- preferred_cloud_harness) are deliberately
--   NOT repointed this run. They keep their role-level files
--   (473_PREFERRED_CLOUD_REVIEW01.md and 513_PREFERRED_CLOUD_HARNESS_REVIEW01.md)
--   via bridge_roles.governance_file. A later run repoints them after this
--   run has held in production (Pre-review-cl drives daily production work;
--   repointing the very flow that is executing the migration would create a
--   mid-run split-brain). Neither label may appear in any UPDATE predicate.
--   The D5 live_flows_deferred test group pins this deferral at both the
--   resolver level AND the migration-text level (so a future mutation that
--   "fixes" the deferral by adding the labels to the predicates is caught
--   at test time).
--
-- Why NO ALTER/CREATE/DROP:
-- Schema is already in place from 062 (governance_file TEXT NULL on
-- bridge_flow_steps). This migration only writes to that column.
--
-- Why NO UPDATE to bridge_roles:
-- The role-level pointers to the eleven absorbed originals remain in place
-- as the fallback. Removing them is Phase 5 of the spec, out of scope for
-- this run.
--
-- Why no idempotency guard inside this file: scripts/migrate.py records
-- the filename in schema_migrations after a successful apply, so re-running
-- migrate.py is a no-op against this file. Re-running these UPDATEs against
-- rows that already match is harmless (the value is identical), but the
-- runner's schema_migrations check makes the second run a no-op at the file
-- level anyway.

UPDATE bridge_flow_steps
   SET governance_file = 'TECHNICAL_REVIEW.md'
 WHERE is_active = 1
   AND from_role IN ('review01', 'review01cloud', 'review01pay', 'review01sup');

UPDATE bridge_flow_steps
   SET governance_file = 'GOVERNANCE_REVIEW.md'
 WHERE is_active = 1
   AND from_role IN ('review02', 'review02cloud', 'review02pay', 'review02sup');

UPDATE bridge_flow_steps
   SET governance_file = 'REVIEW.md'
 WHERE is_active = 1
   AND from_role IN ('review01SG');
