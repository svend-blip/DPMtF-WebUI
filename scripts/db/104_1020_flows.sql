-- 104: The 1020 flows — 1020-01-PLOOP and 1020-02-ELOOP.
--
-- Human decision 2026-09-07: a fully-cloud two-flow pair for a NEW project
-- (AI_AdvisoryBoard). Mirrors the 9000 pair's shape:
--   PLOOP  1020-planning-supervisor: a copy of 9000-01-PLOOP's planning
--          supervisor — opus5 (Claude subscription, cloud) over claude-code,
--          governance SUPERVISOR_PLANNING.md.
--   ELOOP  decomposer -> implementer -> reviewer: ALL on the simple-harness
--          interface with cloud_deepseek_v4pro_direct (deepseek-v4-pro DIRECT
--          at api.deepseek.com — pure cloud, no local model, no Token Plan).
--   No escalation role (Human 2026-09-07: not needed).
--
-- Portability: target_project_path is NULL here (no machine path in a
-- committed migration — auto-fail rule + test_governance_no_hardcoded_paths).
-- The concrete target path is set live in the DB after apply
-- after apply, the same way flow config is set through the UI. Role keys are
-- distinct from every other flow (100_BRIDGE Security Rule 7). The model-
-- allocator side (roles.yaml entries for the four 1020 roles) lands in
-- model-allocator in the same change set. Requires DEEPSEEK_API_KEY at
-- runtime (opus5 uses the Claude subscription). cold_start_skill '1020'.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, artifact_root, target_project_path,
     is_active, auto_complete_enabled, ui_category, supervisor_role,
     cold_start_skill, commit_cadence)
VALUES
    ('1020-01-PLOOP', '1020 Planning Loop (AI AdvisoryBoard)',
     'Pure-cloud two-flow pair for the AI_AdvisoryBoard project: planning on opus5 over claude-code. Copy of 9000-01-PLOOP. Shares artifact root 1020 with ELOOP.',
     '1020', NULL, 1, 0, 'experimental', '1020-planning-supervisor',
     '1020', 'none'),
    ('1020-02-ELOOP', '1020 Execution Loop (AI AdvisoryBoard)',
     'Pure-cloud two-flow pair: decomposer -> implementer -> reviewer on the simple-harness interface with cloud_deepseek_v4pro_direct (deepseek-v4-pro DIRECT). Shares artifact root 1020 with PLOOP.',
     '1020', NULL, 1, 0, 'experimental', '1020-planning-supervisor',
     '1020', 'per_run');

INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, is_active,
     default_model_source, default_model_alias, allocator_client,
     default_harness_source, default_harness_profile,
     workdir_mode, governance_file, config_dir, fresh_session_command)
VALUES
    ('1020-planning-supervisor', '1020-planning-supervisor', 'agent', 1,
     'model_allocator', 'opus5', 'claude-code',
     'claude-code', NULL,
     'father', 'SUPERVISOR_PLANNING.md', '1020-planning-supervisor', NULL),
    ('1020-execution-decomposer', '1020-execution-decomposer', 'agent', 1,
     'model_allocator', 'cloud_deepseek_v4pro_direct', NULL,
     'simple-harness', NULL,
     'target_project', 'EXECUTION_DECOMPOSER.md', NULL, NULL),
    ('1020-implementer', '1020-implementer', 'agent', 1,
     'model_allocator', 'cloud_deepseek_v4pro_direct', NULL,
     'simple-harness', NULL,
     'target_project', 'IMPLEMENTOR.md', NULL, NULL),
    ('1020-reviewer', '1020-reviewer', 'agent', 1,
     'model_allocator', 'cloud_deepseek_v4pro_direct', NULL,
     'simple-harness', NULL,
     'target_project', 'REVIEW.md', NULL, NULL);

-- PLOOP: Human <-> planning supervisor dialogue (the 9000 shape).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file)
VALUES
    ('1020-01-PLOOP', 'human-planning', 'human', '1020-planning-supervisor',
     '1020/planning', '{ID}-request.md', 1, 1, 'handoff', 0, 0, 'HUMAN.md'),
    ('1020-01-PLOOP', 'planning-human', '1020-planning-supervisor', 'human',
     '1020/goals', '{ID}-GOAL-DRAFT.md', 2, 1, 'callback', 0, 0,
     'SUPERVISOR_PLANNING.md'),
    ('1020-02-ELOOP', 'decomposer-implementer', '1020-execution-decomposer', '1020-implementer',
     '1020/handoffs', '{ID}-handoff.md', 1, 1, 'handoff', 0, 1, 'EXECUTION_DECOMPOSER.md'),
    ('1020-02-ELOOP', 'implementer-reviewer', '1020-implementer', '1020-reviewer',
     '1020/results', '{ID}-result.md', 2, 1, 'callback', 0, 1, 'IMPLEMENTOR.md'),
    ('1020-02-ELOOP', 'reviewer-decomposer', '1020-reviewer', '1020-execution-decomposer',
     '1020/verdicts', '{ID}-verdict.md', 3, 1, 'agent_delivery', 0, 1, 'REVIEW.md');
