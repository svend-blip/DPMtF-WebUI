-- Rollback for 059: restore the four convention rules' original direct
-- `dispatch.py --signal-*` invocation.
--
-- Only for reverting the migration itself. The shape it restores is
-- the exact pre-D2 defect — a direct dispatch.py call that can be lost
-- on a killed shell, bypassing the broker queue. Do not run this to
-- "fix" anything.
--
-- Idempotent in the same way as the forward migration: each UPDATE's
-- WHERE clause matches only the broker-form text, so re-running is a
-- no-op once the rollback has been applied.

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue '
            || char(92) || char(10)
            || '      --flow {flow_key} --from-role {next_role} --to-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} --action signal-complete '
            || char(92) || char(10)
            || '      > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &',
        '    nohup python3 {project_root}/scripts/bridgeV002/dispatch.py '
            || char(92) || char(10)
            || '      --db-flow {flow_key} '
            || char(92) || char(10)
            || '      --signal-complete --from-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'handoff'
  AND content_template LIKE '%bridge_broker.py enqueue%'
  AND content_template LIKE '%--action signal-complete%';

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue '
            || char(92) || char(10)
            || '      --flow {flow_key} --from-role {next_role} --to-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} --action signal-complete '
            || char(92) || char(10)
            || '      > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &',
        '    nohup python3 {project_root}/scripts/bridgeV002/dispatch.py '
            || char(92) || char(10)
            || '      --db-flow {flow_key} '
            || char(92) || char(10)
            || '      --signal-complete --from-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'json_output'
  AND content_template LIKE '%bridge_broker.py enqueue%'
  AND content_template LIKE '%--action signal-complete%';

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role {next_role} --to-role {escalation_role} --id {handoff_id} --action signal-escalation',
        '  escalation: python3 dispatch.py --db-flow {flow_key} --signal-escalation --from-role {next_role} --to-role {escalation_role}'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'callback'
  AND content_template LIKE '%bridge_broker.py enqueue --flow {flow_key}%'
  AND content_template LIKE '%--to-role {escalation_role}%';

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow FLOW --from-role {next_role} --to-role archi01 --id {handoff_id} --action signal-escalation',
        '  escalation: python3 dispatch.py --db-flow FLOW --signal-escalation --from-role {next_role} --to-role archi01'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'technical_review'
  AND content_template LIKE '%bridge_broker.py enqueue --flow FLOW%'
  AND content_template LIKE '%--to-role archi01%';
