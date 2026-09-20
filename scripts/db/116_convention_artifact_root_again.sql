-- 116 — Convention rules: the artifact root as path root, again.
--
-- Migration 084 replaced {bridge_dir}/{flow_key}/ with
-- {bridge_dir}/{artifact_root}/ in five content templates, so that a
-- shared-root family (1000-01-PLOOP and 1000-02-ELOOP share root 1000)
-- resolves to the shared root instead of the flow key.
--
-- scripts/init_db.py then rewrote three of them — technical_review, verdict,
-- human_delivery — with the old text, unconditionally, on every run; it runs
-- the migrations first and its own statements afterwards, and the validation
-- checklist has it run routinely. tests/test_artifact_root_prompt.py TG1/TG2
-- had been red since the first run after 2026-08-31. init_db.py was corrected
-- on 2026-09-20; 084 is recorded as applied and does not run again, so the
-- rows are put right here.
--
-- No step of a shared-root flow used the three rules when this was written
-- (their twelve active steps all belong to flows whose root is their own
-- key, where both placeholders resolve to the same directory), so nothing
-- was ever delivered to a wrong path. The defect was waiting for the first
-- shared-root flow to use one of them.
--
-- handoff and json_output are NOT touched, as in 084: their {flow_key} is a
-- --flow command-line argument, not a path. The statement is a no-op on a
-- database that is already right.
--
-- Rollback: rollbacks/116_convention_artifact_root_again_rollback.sql

UPDATE bridge_convention_rules
SET content_template = REPLACE(content_template, '{bridge_dir}/{flow_key}/', '{bridge_dir}/{artifact_root}/')
WHERE rule_key IN ('agent_delivery', 'callback', 'verdict', 'technical_review', 'human_delivery')
  AND content_template LIKE '%{bridge_dir}/{flow_key}/%';
