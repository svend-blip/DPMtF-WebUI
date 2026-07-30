-- 023: Per-role working-directory mode for coding sessions.
--
-- start_coding.py has always launched every role's coding interface with
-- `cd <Father>` — measured: start_coding.py line ~254, `cwd = project_root`.
-- With per-flow target projects (migration 016) that is wrong for chain
-- workers: an implementer serving a flow that targets
-- /home/svend/music-video-orchestrator should START there, not in Father.
--
-- WHERE a role works is a property of the ROLE, not of its allocator
-- client: a claude-code implementer would still work in the target, and
-- an opencode architect would still work in Father. Hardcoding the client
-- type as the discriminator (the obvious shortcut) encodes today's
-- coincidence, so the mode is data:
--
--   workdir_mode = 'target_project'  → cd to the flow's resolved target
--                                      (get_flow_target_project: falls
--                                      back to Father when the flow sets
--                                      no target — behaviour-preserving
--                                      for every Father-targeting flow)
--   workdir_mode = 'father'          → cd to Father regardless of flow
--
-- 'father' is seeded for the roles whose own procedures assume Father's
-- cwd (they author handoffs, run dispatch.py, and their cold-start skills
-- use Father-relative paths like databases/dpmtf.db):
--   - supervisor / supervisor_auto (500/451 governance)
--   - the architects: archi01, archi01cloud, archi01pay (40x/41x/42x)
--
-- Everything else defaults to 'target_project'. The prompt side needs no
-- change: dispatch injects absolute governance paths and the Target
-- Project block (016), so prompts are cwd-independent.
--
-- Idempotent: ADD COLUMN runs once via schema_migrations; the UPDATE
-- re-asserts the same values on re-run.

ALTER TABLE bridge_roles
    ADD COLUMN workdir_mode TEXT NOT NULL DEFAULT 'target_project';

UPDATE bridge_roles
SET workdir_mode = 'father'
WHERE role_key IN (
    'supervisor', 'supervisor_auto',
    'archi01', 'archi01cloud', 'archi01pay'
);
