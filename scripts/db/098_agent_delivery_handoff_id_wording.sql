-- 098 — The agent_delivery convention names the handoff id, not a "run ID".
--
-- The verdict-callback prompt told the decomposer to "Allocate a new run ID
-- from the flow's id counter if you dispatch a new handoff". A Run number is
-- the planning flow's to allocate (SUPERVISOR_PLANNING.md §Authority Split;
-- EXECUTION_DECOMPOSER.md: "You NEVER open a Run"); what the decomposer needs
-- after a verdict is the NEXT HANDOFF id, which the flow counter allocates
-- when it signals. The old sentence read as a licence to open the next Run,
-- and the callback prompt carries no computed "## Signal Completion" section,
-- so it also said nothing about which signal to send for the new handoff.
-- Measured on 9000-02-ELOOP 2026-09-01/02: decomposers that stood down
-- without signalling, or reasoned about Run numbers on a verdict wake-up.
--
-- Rollback: rollbacks/098_agent_delivery_handoff_id_wording_rollback.sql
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
4. If the verdict leaves work in this Run, write the NEXT handoff under the next
   HANDOFF id (the flow''s id counter allocates it when you signal; never a Run
   number, never a hand-picked id) and signal it ONCE with the verb your governance
   gives for that step (signal-send naming the receiving role when auto_dispatch
   is unset). Writing the file is not delivery; the signal is.
5. Send NO completion signal for the delivery itself
6. If the verdict closes the Run''s last work item: END-REPORT and one ledger
   entry through the broker, then stand down. The next Run waits for its own
   kickoff; you never open one.

Do not send a signal_complete with the same handoff_id - this causes infinite loops.',
    updated_at = CURRENT_TIMESTAMP
WHERE rule_key = 'agent_delivery';
