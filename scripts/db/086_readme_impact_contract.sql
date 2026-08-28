-- 086: README Impact deliverable contract — per-step activation flag.
--
-- Governance: docs/governance-templates-v2/31_README_STANDARD.md.
-- Mirrors 085's wiring pattern: a step that has not opted in is untouched,
-- and deliverables from before activation are never retroactively
-- invalidated. dispatch refuses a delivery on an activated step whose
-- deliverable fails scripts/bridgeV002/readme_impact.py.
--
-- TWO statements, both required:
--
-- 1. The column. Default 0 = not activated (historical behaviour).
ALTER TABLE bridge_flow_steps ADD COLUMN requires_readme_impact INTEGER NOT NULL DEFAULT 0;

-- 2. Activate on the single implementation-result step of 1000-02-ELOOP.
UPDATE bridge_flow_steps
   SET requires_readme_impact = 1
 WHERE flow_key = '1000-02-ELOOP'
   AND step_key = 'implementer-reviewer';
