-- 101 — The handoff prompt names the RESULT sections and the README Impact block.
--
-- The `handoff` content_template told the implementer that its "callback file
-- must include <role>, <task>, <constraint>, <deliverable>" — the sections of
-- the HANDOFF it received — and never mentioned the README Impact block the
-- broker enforces (readme_impact.py: a section headed `## README Impact` with
-- `README impact: yes|no` and `Reason:`). Measured 2026-09-03 on both ELOOP
-- families: results refused with README_IMPACT_BLOCK_MISSING, verdicts without
-- the four result sections. The row was corrected in the live database that
-- night; this migration mirrors it so init_db/migrations and the live row agree.
--
-- Rollback: rollbacks/101_handoff_template_result_sections_rollback.sql
UPDATE bridge_convention_rules
SET content_template = 'The architect has prepared a handoff. Read and execute the referenced file.

## Previous Deliverable
Handoff ID: {handoff_id}
Source Role: {source_role}

## Required Sections
Your RESULT file (the deliverable you write) must start with these XML sections:
- <handoff_id>: the id of the handoff you executed
- <source_role>: your own role name, exactly as dispatched
- <deliverable_input>: the path(s) you read (the handoff file)
- <deliverable_output>: the path(s) you produced (result and notification)
It must also carry the README impact block, which the broker enforces — a section
headed exactly `## README Impact` containing:
- a line `README impact: yes` or `README impact: no`
- a line `Reason: ...` explaining why
(`yes` with `updated: no` is a contradiction; if the README needs a change, make it.)
The <role>/<task>/<constraint>/<deliverable> sections belong to the handoff you received, not to your result.
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
