-- 084: Convention rules — replace {flow_key} path root with {artifact_root}
--
-- The five rules that use {flow_key} in a path must use {artifact_root}
-- so that shared-root flows (1000-01-PLOOP, 1000-02-ELOOP) resolve to
-- the shared root instead of the flow key.
--
-- handoff and json_output are NOT touched — their {flow_key} is a --flow
-- command-line argument, not a path.

UPDATE bridge_convention_rules
SET content_template = REPLACE(content_template, '{bridge_dir}/{flow_key}/', '{bridge_dir}/{artifact_root}/')
WHERE rule_key IN ('agent_delivery', 'callback', 'verdict', 'technical_review', 'human_delivery');
