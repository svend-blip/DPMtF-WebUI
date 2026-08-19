-- Rollback for 057: restore the callback rule's original (wrong) verdict path.
--
-- Only for reverting the migration itself. The path it restores is the defect
-- described in 057 — a reviewer that follows it writes a verdict dispatch
-- cannot see. Do not run this to "fix" anything.
--
-- Idempotent in the same way as the forward migration.

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '{bridge_dir}/{flow_key}/verdicts/{handoff_id}-verdict.md',
        '{bridge_dir}/{flow_key}/reviews/{handoff_id}-review-verdict.md'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'callback'
  AND content_template LIKE '%/verdicts/{handoff_id}-verdict.md%';
