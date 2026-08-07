-- 034: Escalation commands must name the flow's own escalation target.
--
-- The `callback` and `technical_review` convention rules are step-TYPE
-- templates shared by every flow, and both hardcoded
-- `--to-role archi01` -- strict_review's architect -- in the escalation
-- command they inject into a role's prompt. preferred_cloud run 010 found
-- it the live way:
--
--   2026-08-07T09:04Z | Pre-review-cl->archi01 | escalation_failed
--
-- No archi01 session exists in that flow; the escalation fell back to the
-- supervisor and the run was closed by hand.
--
-- `{escalation_role}` is rendered by dispatch at injection time as the
-- from_role of the flow's first active step: archi01 for strict_review
-- (behaviour unchanged), Pre-super-cl for preferred_cloud, the human for
-- human-supervised flows.
--
-- The technical_review rule also said `--db-flow FLOW` -- a literal FLOW,
-- not a placeholder. Same fix, same reason: a role pasting that command
-- verbatim got a broken invocation.

UPDATE bridge_convention_rules
   SET content_template = REPLACE(content_template,
       '--to-role archi01', '--to-role {escalation_role}'),
       updated_at = datetime('now')
 WHERE rule_key IN ('callback', 'technical_review')
   AND content_template LIKE '%--to-role archi01%';

UPDATE bridge_convention_rules
   SET content_template = REPLACE(content_template,
       '--db-flow FLOW ', '--db-flow {flow_key} '),
       updated_at = datetime('now')
 WHERE rule_key = 'technical_review'
   AND content_template LIKE '%--db-flow FLOW %';
