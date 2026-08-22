-- 063: Governance pilot repoint — Run 009 (GH-2a) D3.
--
-- Goal (GOAL.md section 1 D3, section 2, section 15):
-- Set bridge_flow_steps.governance_file at STEP level for every active step
-- whose from_role is one of the three architect role labels or the three
-- human role labels. The 4xx originals (401/402/411/412/421/422) are NOT
-- deleted or edited; bridge_roles.governance_file keeps pointing at them as
-- the role-level fallback (the resolver's precedence STEP > ROLE > SYSTEM
-- guarantees the new step-level value wins where it is set).
--
-- Section 15 semantics:
-- Step governance describes the from_role. The predicates below are
-- exclusively from_role-shaped; they do not reference to_role. This is the
-- §15 contract — a to_role-shaped mistake is caught by the D4 tests (TG6
-- carries the contract; rehearsal mutation m2 was caught there).
--
-- Exact predicates and expected row counts (current DB state):
--   3 architect steps (cloud_llm, cloud_pay, strict_review) → ARCHITECT.md
--   4 human steps    (lightworker, pi_test x2, supervisor)  → HUMAN.md
--   Total: 7 rows updated.
--   The named cloud-human role labels (humancloud, humanpay) are terminal
--   to_role labels today and match 0 active from_role rows. The predicate
--   still lists them because GOAL.md binds it that way and to keep the
--   migration correct if those roles ever become from_role.
--
-- Why NO ALTER/CREATE/DROP:
-- Schema is already in place from 062 (governance_file TEXT NULL added on
-- bridge_flow_steps). This migration only writes to that column.
--
-- Why NO UPDATE to bridge_roles:
-- The role-level pointers to the 4xx originals remain in place as the
-- fallback. Removing them is Phase 5 of the spec, out of scope for this
-- run.
--
-- Why no idempotency guard inside this file: scripts/migrate.py records
-- the filename in schema_migrations after a successful apply, so re-running
-- migrate.py is a no-op against this file. Re-running these UPDATEs against
-- rows that already match is harmless (the value is identical), but the
-- runner's schema_migrations check makes the second run a no-op at the file
-- level anyway.

UPDATE bridge_flow_steps
   SET governance_file = 'ARCHITECT.md'
 WHERE is_active = 1
   AND from_role IN ('archi01', 'archi01cloud', 'archi01pay');

UPDATE bridge_flow_steps
   SET governance_file = 'HUMAN.md'
 WHERE is_active = 1
   AND from_role IN ('human', 'humancloud', 'humanpay');
