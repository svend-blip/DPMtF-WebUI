-- Update agent_delivery content template to prevent infinite loop and directory overwrite
-- Migration 013: Fix agent_delivery template for autonomous wakeups

UPDATE bridge_convention_rules 
SET content_template = 'Read the delivered verdict file for handoff {handoff_id}.
Then, read your own governance file and follow your wake-up protocol.
Act on the verdict outcome accordingly.

The verdict file is located at: {previous_deliverable_path}

Your tasks:
1. Process the verdict file in "{previous_deliverable_path}"
2. Follow the wake-up protocol in your governance file
3. Write run bookkeeping (ledger updates, END-REPORT when the run ends) to your own 
   run directory under {bridge_dir}/supervisor/runs/ instead of any chain deliverable directory
4. Allocate a new run ID from the flow''s id counter if you dispatch a new handoff
5. Send NO completion signal for the delivery itself

Do not send a signal_complete with the same handoff_id - this causes infinite loops.'
WHERE rule_key = 'agent_delivery';