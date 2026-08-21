-- 059: broker is the only role-facing signal path (Run 006 D2).
--
-- Four convention rules in bridge_convention_rules still instructed a
-- DIRECT `dispatch.py … --signal-*` call in their content_template. A
-- direct call can be lost on a killed shell exactly the way the broker
-- was built to prevent (preferred_cloud run 004 dispatch row 19 sat
-- 'pending' for 41 minutes on 2026-07-21). The signal path is now
-- uniform: every role invokes the broker, and only the broker invokes
-- dispatch.py.
--
-- This migration changes ONLY the signal-invocation block inside each
-- rule's content_template. Everything else (deliverable paths, verdict
-- destinations, role placeholders, log-redirect filenames, surrounding
-- prose) is byte-preserved. The 'verdict' and 'agent_delivery' rules
-- are untouched (they already use the broker or have no signal line).
--
-- Per-rule change summary:
--
--   handoff         signal-complete: dispatch.py → bridge_broker.py enqueue
--                   --from-role {next_role} --to-role {next_role}
--                   (from=to convention — GOAL.md §2).
--                   Log-redirect filename /tmp/bridge-signal-{flow_run_id}.log
--                   is BYTE-IDENTICAL (surrounding prose references it).
--
--   json_output     identical change to handoff.
--
--   callback        signal-escalation: dispatch.py → bridge_broker.py enqueue,
--                   GAINING --id {handoff_id}.
--                   Existing --to-role {escalation_role} value byte-preserved.
--
--   technical_review signal-escalation: dispatch.py → bridge_broker.py enqueue,
--                   GAINING --id {handoff_id}.
--                   Existing --to-role archi01 AND literal --db-flow FLOW
--                   byte-preserved (pre-existing, OUT OF SCOPE — do NOT
--                   "fix" them; the literal `FLOW` would otherwise read
--                   as an unresolved placeholder to a casual reader).
--
-- Implementation note 1: the patterns include literal shell
-- line-continuation backslashes (each `\` is immediately followed by
-- a newline inside the content_template). SQLite string literals
-- treat `\` as a regular character; the patterns build them up via
-- char(92) || char(10) so no escaping is needed inside the SQL.
--
-- Implementation note 2: the replacement broker invocation puts
-- `bridge_broker.py enqueue` on the SAME line (no `\` between them).
-- This is what makes the TG4 supervisor check pass — the canonical
-- substring `bridge_broker.py enqueue` must appear contiguously in
-- the stored content_template for the criterion query to find it.
-- The remaining broker flags still use `<backslash><newline>`
-- continuations because they are long.
--
-- Idempotent: each UPDATE's WHERE clause matches only the unfixed text,
-- so re-running is a no-op.

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '    nohup python3 {project_root}/scripts/bridgeV002/dispatch.py '
            || char(92) || char(10)
            || '      --db-flow {flow_key} '
            || char(92) || char(10)
            || '      --signal-complete --from-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &',
        '    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue '
            || char(92) || char(10)
            || '      --flow {flow_key} --from-role {next_role} --to-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} --action signal-complete '
            || char(92) || char(10)
            || '      > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'handoff'
  AND content_template LIKE '%bridgeV002/dispatch.py%'
  AND content_template LIKE '%--signal-complete%'
  AND content_template NOT LIKE '%bridge_broker.py enqueue%';

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '    nohup python3 {project_root}/scripts/bridgeV002/dispatch.py '
            || char(92) || char(10)
            || '      --db-flow {flow_key} '
            || char(92) || char(10)
            || '      --signal-complete --from-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &',
        '    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue '
            || char(92) || char(10)
            || '      --flow {flow_key} --from-role {next_role} --to-role {next_role} '
            || char(92) || char(10)
            || '      --id {flow_run_id} --action signal-complete '
            || char(92) || char(10)
            || '      > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'json_output'
  AND content_template LIKE '%bridgeV002/dispatch.py%'
  AND content_template LIKE '%--signal-complete%'
  AND content_template NOT LIKE '%bridge_broker.py enqueue%';

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '  escalation: python3 dispatch.py --db-flow {flow_key} --signal-escalation --from-role {next_role} --to-role {escalation_role}',
        '  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role {next_role} --to-role {escalation_role} --id {handoff_id} --action signal-escalation'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'callback'
  AND content_template LIKE '%python3 dispatch.py --db-flow {flow_key} --signal-escalation%'
  AND content_template NOT LIKE '%bridge_broker.py enqueue%';

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '  escalation: python3 dispatch.py --db-flow FLOW --signal-escalation --from-role {next_role} --to-role archi01',
        '  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow FLOW --from-role {next_role} --to-role archi01 --id {handoff_id} --action signal-escalation'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'technical_review'
  AND content_template LIKE '%python3 dispatch.py --db-flow FLOW --signal-escalation%'
  AND content_template NOT LIKE '%bridge_broker.py enqueue%';
