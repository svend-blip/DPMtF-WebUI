-- Rollback for 069: remove the codex-context-release pre-dispatch from
-- the preferred_cloud_harness supervisor-imple01 step and unregister the
-- bridge_scripts row.
--
-- Exact inverse of the forward migration. WHERE matches ONLY rows whose
-- pre_dispatch_script IS 'codex-context-release', so re-running after
-- rollback is a no-op (matches the idempotent forward).
--
-- Only for reverting 069 itself. The state this restores is the
-- pre-069 defect — a codex-bound step with no pre-dispatch at all, so
-- the context-release contract never runs in production. Do not run
-- this to "fix" anything.

UPDATE bridge_flow_steps
SET pre_dispatch_script = NULL
WHERE flow_key = 'preferred_cloud_harness'
  AND step_key = 'supervisor-imple01'
  AND pre_dispatch_script = 'codex-context-release';

DELETE FROM bridge_scripts WHERE script_key = 'codex-context-release';
