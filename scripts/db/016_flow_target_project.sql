-- 016: Per-flow target project.
--
-- A flow does not necessarily operate on Father. `cloud_pay` targets
-- /home/svend/trade-ui, `supervised_review` has targeted
-- /home/svend/music-video-orchestrator since run goal-001, and Father
-- itself is only the target of `strict_review`.
--
-- Until now nothing in the database recorded that. The governance files
-- carried `cd {project_path}`, a placeholder dispatch.py never replaced
-- (it replaces {bridge_dir}, {flow_key}, {handoff_id}, {deliverable_dir},
-- {deliverable_file}, {output_file}, {model_name} and
-- {previous_deliverable_path} — and no {project_path}). Roles therefore
-- read it as literal text, never changed directory, and ran Father's
-- checks against whatever the real target was.
--
-- Measured consequence in run goal-009 (2026-07-30): review01 reviewed
-- handoff 32 inside Father on master and rejected it for "the files do
-- not exist" and "235 tests not 315" — both true of Father, neither true
-- of the target. The same blind checklist APPROVED handoffs 30 and 31,
-- one of them in 55 seconds. False positives and false negatives from a
-- single root cause.
--
-- The target belongs to the FLOW, not to the role: roles are shared
-- across flows (imple01 serves both strict_review and supervised_review),
-- so a per-role column could not express two targets at once. Keying it
-- per flow also lets several flows run against different projects
-- simultaneously.
--
-- NULL means "this flow targets Father", which is the historical
-- behaviour and stays the default for every flow not named below.
--
-- Idempotent: re-running only re-asserts the same values.

ALTER TABLE bridge_flows ADD COLUMN target_project_path TEXT DEFAULT NULL;

UPDATE bridge_flows
SET target_project_path = '/home/svend/music-video-orchestrator',
    updated_at = CURRENT_TIMESTAMP
WHERE flow_key = 'supervised_review';
