-- Migration: callback_verdict_summary
-- Adds <verdict_summary>, <next_action>, and <stop> blocks to the callback
-- content_template so the execution-decomposer receives structured verdict
-- context on wake-up. Only touches rule_key='callback'; the 'handoff' row
-- carries a separate migration debt and must not be overwritten here.

UPDATE bridge_convention_rules
SET content_template = '<handoff_id>{handoff_id}</handoff_id>

<source_role>{source_role}</source_role>

<deliverable_input>
  {bridge_dir}/{artifact_root}/results/{handoff_id}-result.md
  {bridge_dir}/{artifact_root}/results/{handoff_id}-notification.md
</deliverable_input>

<deliverable_output>
  verdict: {bridge_dir}/{artifact_root}/verdicts/{handoff_id}-verdict.md
  commit_msg (if APPROVED): {bridge_dir}/{artifact_root}/verdicts/{handoff_id}-commit-message.md
</deliverable_output>

<verdict_summary>
status: {verdict_status}
{verdict_lines}
work_item: {work_item}
</verdict_summary>

<next_action>
{next_action}
</next_action>

<stop>
you have every fact you need; do not read the repository; at most 6 tool calls
</stop>

<dispatch_command>
  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role {next_role} --to-role {escalation_role} --id {handoff_id} --action signal-escalation
</dispatch_command>
'
WHERE rule_key = 'callback';
