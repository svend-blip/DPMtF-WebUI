-- 069: Codex context-release pre-dispatch on supervisor-imple01 (Run 018 D3).
--
-- Run 018 wires the codex_context_release pre-dispatch script to the
-- preferred_cloud_harness chain's first step (supervisor -> implementer).
-- The receiver is the codex role; with the fresh-context policy at its
-- default 'off' every subsequent live dispatch to the codex role
-- exercises the script's no-op path in production (console-evidenced
-- in handoff 071's landing step).
--
-- TWO statements, both required:
--
-- (1) Register the script key in bridge_scripts. resolve_script_key
--     resolves through this table; an unregistered key returns None
--     and dispatch silently skips — observed on the reference worktree
--     when the step value was set without the registration row.
--
-- (2) Set pre_dispatch_script on the codex-bound step ONLY. The two
--     review-bound steps keep gate-deliverable-evidence (TG7 contract:
--     exactly two rows carry gate-deliverable-evidence, both review
--     steps).
--
-- Idempotent: INSERT OR IGNORE on the bridge_scripts row (registration
-- is a one-time setup); UPDATE on bridge_flow_steps matches only the
-- unfixed state (pre_dispatch_script IS NULL OR ''). Re-running is a
-- no-op.

INSERT OR IGNORE INTO bridge_scripts
    (script_key, name, description, path, stage, params_required, is_active)
VALUES
    ('codex-context-release',
     'Codex Context Release',
     'Per-work-unit Codex context release: no-op unless the receiving harness is codex with fresh-context policy work_unit, then verified stop + relaunch + re-anchor.',
     'scripts/bridgeV002/codex_context_release.py',
     'pre',
     '--flow-key,--to-role',
     1);

UPDATE bridge_flow_steps
SET pre_dispatch_script = 'codex-context-release'
WHERE flow_key = 'preferred_cloud_harness'
  AND step_key = 'supervisor-imple01'
  AND (pre_dispatch_script IS NULL OR pre_dispatch_script = '');
