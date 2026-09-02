-- Rollback for 098: restore the previous agent_delivery wording.
UPDATE bridge_convention_rules
SET content_template = 'Read the delivered verdict file for handoff {handoff_id}.
Then, read your own governance file and follow your wake-up protocol.
Act on the verdict outcome accordingly.

The verdict file is located at: {previous_deliverable_path}

Your tasks:
1. Process the verdict file in "{previous_deliverable_path}"
2. Follow the wake-up protocol in your governance file
3. Write run bookkeeping (ledger updates, END-REPORT when the run ends) to the active run''s
   directory under {bridge_dir}/{artifact_root}/runs/ — never a chain deliverable
   directory, and never {bridge_dir}/supervisor/runs/
4. Allocate a new run ID from the flow''s id counter if you dispatch a new handoff
5. Send NO completion signal for the delivery itself

Do not send a signal_complete with the same handoff_id - this causes infinite loops.',
    updated_at = CURRENT_TIMESTAMP
WHERE rule_key = 'agent_delivery';
DELETE FROM schema_migrations WHERE filename = '098_agent_delivery_handoff_id_wording.sql';
