-- Rollback for 060: remove the evidence gate from reveng rows 701 and 702.
--
-- Only for reverting the migration itself. The state it restores is
-- the exact pre-D3 defect — a reveng deliverable that can pass without
-- the evidence check every other supervisor flow runs. Do not run this
-- to "fix" anything.
--
-- Idempotent in the same way as the forward migration: WHERE matches
-- only rows whose pre_dispatch_script IS the gate value, so re-running
-- after rollback is a no-op.

UPDATE bridge_flow_steps
SET pre_dispatch_script = ''
WHERE id IN (701, 702)
  AND flow_key = 'reveng'
  AND pre_dispatch_script = 'gate-deliverable-evidence';
