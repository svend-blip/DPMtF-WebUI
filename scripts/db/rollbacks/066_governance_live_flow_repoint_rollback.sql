-- 066 rollback: Governance live-flow repoint -- Run 012 (GH-2d).
--
-- Restores DB state only: sets bridge_flow_steps.governance_file back to
-- NULL for the six live-flow roles repointed by 066 (part a + part b).
--
-- FULL HOST RECOVERY (GOAL.md section 2 rollback coupling): this SQL
-- rollback PLUS git-revert of the rename commit (the three D4 exception
-- renames from handoff 050). The DB restore and the git restore are two
-- separate steps; neither alone is a full recovery.

UPDATE bridge_flow_steps SET governance_file = NULL
 WHERE is_active = 1
   AND from_role IN ('Pre-imple-cl', 'Pre-super-cl', 'Pre-review-cl',
                     'imple-codex-minimaxM3', 'super-deep-deep4',
                     'review-claude-sonnet5');
