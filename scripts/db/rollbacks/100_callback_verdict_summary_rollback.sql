-- Rollback: callback_verdict_summary
-- Restores the prior callback content_template (without <verdict_summary>).

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

<dispatch_command>
  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role {next_role} --to-role {escalation_role} --id {handoff_id} --action signal-escalation
</dispatch_command>
'
WHERE rule_key = 'callback';
