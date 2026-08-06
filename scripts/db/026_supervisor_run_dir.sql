-- 026_supervisor_run_dir.sql
-- Point the supervisor's bookkeeping at the flow's own run directory.
--
-- Migration 013 told the supervisor to write ledger updates and END-REPORTs
-- to {bridge_dir}/supervisor/runs/, while the LLAMASG cold-start procedure
-- looks for them under {bridge_dir}/{flow_key}/runs/{run_id}/. Two
-- instructions, two locations, and the supervisor obeyed both: on 2026-08-06
-- run 009 it ran `mkdir -p /home/svend/flows/supervisor/runs/llama_SG-009`
-- and mirrored everything, having first spent nearly two minutes reading
-- previous runs to work out the format.
--
-- The flow's run directory wins. It is where GOAL.md lives, where the
-- procedure looks, and where "the newest run without an END-REPORT" is
-- resolved — a report written anywhere else leaves the run looking open
-- forever.
--
-- Targeted replace rather than a rewrite of the whole template: the rest of
-- the agent_delivery text is unrelated and should not be restated here, where
-- it would silently become a second copy to drift from.
--
-- No {run_id} placeholder: dispatch substitutes bridge_dir, flow_key,
-- handoff_id, flow_run_id, project_path and nine others, but not run_id — it
-- would reach the role as literal text. The supervisor resolves the active
-- run itself (supervisor_state.py, or the newest directory without an
-- END-REPORT), so the instruction names the parent and lets it choose.

UPDATE bridge_convention_rules
SET content_template = REPLACE(
        content_template,
        'your own ' || char(10) || '   run directory under {bridge_dir}/supervisor/runs/ instead of any chain deliverable directory',
        'the active run''s' || char(10) ||
        '   directory under {bridge_dir}/{flow_key}/runs/ — never a chain deliverable' || char(10) ||
        '   directory, and never {bridge_dir}/supervisor/runs/'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'agent_delivery'
  AND content_template LIKE '%supervisor/runs/%';
