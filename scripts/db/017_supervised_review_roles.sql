-- 017: Give supervised_review its own roles and its own governance decade.
--
-- Every other flow minted unique roles and a unique governance decade:
--   40x  strict_review   archi01, imple01, review01, review02
--   41x  cloud_llm       *cloud
--   42x  cloud_pay       *pay
--   43x-44x trade        *_trade
--   50x  supervisor      supervisor (Human-paired)
--
-- supervised_review was the exception. It borrowed strict_review's
-- imple01/review01/review02 wholesale, and its one bespoke role
-- (supervisor_auto) was documented as 501 — inside the supervisor flow's
-- decade. So the flow had zero files in a decade of its own.
--
-- Three consequences, all measured:
--
-- 1. MODEL CHOICE. A role carries one default_model_alias, and
--    start_coding.py renders each opencode role's config from the ROLE
--    default (bridge_flow_steps overrides apply at dispatch, not at
--    session start). Sharing imple01 therefore forced both flows onto the
--    same model.
-- 2. TMUX COLLISION. Shared roles mean shared tmux_session, so
--    strict_review and supervised_review could not run at the same time —
--    they would inject into each other's panes.
-- 3. GOVERNANCE FIT. 403/404/405 are written for a Human-paired flow
--    against Father: a Human commit gate that does not exist here, and a
--    checklist assuming app.py / static/js / innerHTML / lbl(). Against a
--    Python CLI target they ask the wrong questions.
--
-- The new roles keep the model aliases the old ones used, so this
-- migration changes WHO is dispatched, not WHAT model runs. Retuning the
-- aliases per flow is now possible and is deliberately left to the Human.
--
-- supervisor_auto keeps its role_key (it is already unique to this flow and
-- is referenced by scheduler.py and model-allocator's roles.yaml); only its
-- governance_file moves 501 -> 451. Its tmux_session is deliberately NOT
-- changed here: it still shares the 'supervisor' session with the
-- Human-paired supervisor role, which is a separate decision that requires
-- a session to be created and restarted while the Human is present.
--
-- Idempotent: INSERT OR IGNORE + UPDATE, safe to re-run.

-- ── The three new agent roles ──────────────────────────────
INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, config_dir,
    default_model_source, default_model_alias,
    allocator_client, fresh_session_command
) VALUES
    ('imple01sup',   'imple01sup',   1, 'none', '452_SUPERVISED_REVIEW_IMPLE01.md',
     'agent', 'default', 'imple01sup',   'model_allocator', 'cloud_minimax',
     'opencode', '/new'),
    ('review01sup',  'review01sup',  1, 'none', '453_SUPERVISED_REVIEW_REVIEW01.md',
     'agent', 'default', 'review01sup',  'model_allocator', 'review01-local',
     'opencode', '/new'),
    ('review02sup',  'review02sup',  1, 'none', '454_SUPERVISED_REVIEW_REVIEW02.md',
     'agent', 'default', 'review02sup',  'model_allocator', 'review02-local',
     'opencode', '/new');

-- Re-assert the governance files in case the rows already existed.
UPDATE bridge_roles SET governance_file = '452_SUPERVISED_REVIEW_IMPLE01.md',
       updated_at = CURRENT_TIMESTAMP WHERE role_key = 'imple01sup';
UPDATE bridge_roles SET governance_file = '453_SUPERVISED_REVIEW_REVIEW01.md',
       updated_at = CURRENT_TIMESTAMP WHERE role_key = 'review01sup';
UPDATE bridge_roles SET governance_file = '454_SUPERVISED_REVIEW_REVIEW02.md',
       updated_at = CURRENT_TIMESTAMP WHERE role_key = 'review02sup';

-- ── supervisor_auto follows the decade ─────────────────────
UPDATE bridge_roles
SET governance_file = '451_SUPERVISED_REVIEW_SUPERVISOR.md',
    updated_at = CURRENT_TIMESTAMP
WHERE role_key = 'supervisor_auto';

-- ── Repoint the flow's steps at the new roles ──────────────
UPDATE bridge_flow_steps SET to_role = 'imple01sup'
WHERE flow_key = 'supervised_review' AND to_role = 'imple01';

UPDATE bridge_flow_steps SET from_role = 'imple01sup'
WHERE flow_key = 'supervised_review' AND from_role = 'imple01';

UPDATE bridge_flow_steps SET to_role = 'review01sup'
WHERE flow_key = 'supervised_review' AND to_role = 'review01';

UPDATE bridge_flow_steps SET from_role = 'review01sup'
WHERE flow_key = 'supervised_review' AND from_role = 'review01';

UPDATE bridge_flow_steps SET to_role = 'review02sup'
WHERE flow_key = 'supervised_review' AND to_role = 'review02';

UPDATE bridge_flow_steps SET from_role = 'review02sup'
WHERE flow_key = 'supervised_review' AND from_role = 'review02';
