-- Rollback of 101: restore the handoff content_template as migration 095 left it.
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
