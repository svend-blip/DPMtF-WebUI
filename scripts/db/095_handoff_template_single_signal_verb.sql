-- 095 — The handoff convention states one signal verb: the one dispatch computes.
--
-- The `handoff` content_template carried a hardcoded <chain_advancement> block
-- telling the receiving role to run `bridge_broker.py enqueue ... --from-role
-- {next_role} --to-role {next_role} --action signal-complete`. dispatch.py has,
-- since run 009, APPENDED a "## Signal Completion" section to the same prompt
-- with the verb computed from the NEXT step's auto_dispatch (0 -> signal-send
-- naming the receiver; otherwise signal-complete). A role therefore read two
-- signal commands per dispatch, and its governance a third rule in prose.
-- Measured on 9000-02-ELOOP 2026-09-01/02: roles ran their signal twice
-- (duplicates suppressed only since fea4c00), used the wrong verb on a
-- callback, or addressed a step key as a role. The template block is the
-- stale copy; the computed section is the truth. Keep the section pointer,
-- drop the command.
--
-- Rollback: rollbacks/095_handoff_template_single_signal_verb_rollback.sql
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
After writing your deliverable you MUST signal, exactly once, with the command
given in the "## Signal Completion" section at the end of this prompt. That
command is computed from the flow''s step configuration (auto_dispatch) and
names the correct verb, roles and id — substitute nothing, and do not run any
other signal command you find in a handoff, a governance file or a previous
deliverable. Without that signal the next role is never dispatched and the
chain stalls.
</chain_advancement>',
    updated_at = CURRENT_TIMESTAMP
WHERE rule_key = 'handoff';
