-- Rollback for 095: restore the hardcoded signal-complete block.
UPDATE bridge_convention_rules
SET content_template = 'The architect has prepared a handoff. Read and execute the referenced file.

## Previous Deliverable
Handoff ID: {handoff_id}
Source Role: {source_role}

## Required Sections
Your callback file must include these XML sections:
- <role>: The target role for this handoff
- <task>: What needs to be accomplished
- <constraint>: Any constraints that apply
- <deliverable>: What you will produce
<chain_advancement>
After writing your deliverable, you MUST signal completion so the bridge
dispatches the next role in the chain. Run this exact command:

    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue \
      --flow {flow_key} --from-role {next_role} --to-role {next_role} \
      --id {flow_run_id} --action signal-complete \
      > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &

{flow_key}, {next_role}, and {flow_run_id} are already resolved for you —
substitute nothing. The command runs in the background (nohup + &) so your turn ends
immediately — dispatch.py''s post-dispatch step can hang and must never
block you. Progress is written to /tmp/bridge-signal-{flow_run_id}.log.
Do NOT skip this step — without signal-complete, the next role is never
dispatched and the chain stalls.
</chain_advancement>',
    updated_at = CURRENT_TIMESTAMP
WHERE rule_key = 'handoff';
