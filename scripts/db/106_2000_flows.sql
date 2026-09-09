-- Migration: 2000_flows
-- The 2000 flow family (Human 2026-09-09): 2000-01-PLOOP + 2000-02-ELOOP,
-- the same role and step structure as 9000, but EVERY agent role runs on
-- cloud_qwen38flash over simple-harness. It exists to test FlowRunner +
-- Export FlowApp against a cloud model: the DPMtF flow is exported to a
-- FlowApp, run in FlowRunner, and the supervisor and execution-decomposer
-- steps become persistent (continue-session) at export time.
--
-- Deviations from 9000, deliberate for a clean test vehicle (not the role
-- structure, which mirrors 9000): no gate-test-impact pre-dispatch and no
-- requires_readme_impact — 9000-specific tuning that added friction and is
-- unrelated to the roles. No escalation-supervisor (all-simple-harness +
-- the 1020 precedent; not in the flow steps).
--
-- RAW SQL, idempotent (INSERT OR IGNORE), no BEGIN/COMMIT (migrate.py wraps
-- each file), no absolute machine paths. target_project_path is NULL — set
-- live in the DB after apply (portable, no machine path in a committed file).
-- model-allocator roles.yaml carries the matching cloud_qwen38flash entries;
-- cold_start_skill '2000' is created alongside.

INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, step_order, is_default, is_active,
     auto_complete_enabled, use_machine_profile, target_project_path,
     supervisor_role, artifact_root, ui_category, cold_start_skill,
     supervisor_mandate, commit_cadence)
VALUES
    ('2000-01-PLOOP',
     '2000 Planning Loop (FlowRunner export test)',
     'Test flow: cold-start, read a SCOPE, author GOAL-DRAFTs on cloud_qwen38flash over simple-harness. Created to test FlowRunner + Export FlowApp against a cloud model. Shares artifact root 2000 with ELOOP.',
     0, 0, 1, 0, 0, NULL,
     '2000-planning-supervisor', '2000', 'experimental', '2000', NULL, 'none'),
    ('2000-02-ELOOP',
     '2000 Execution Loop (FlowRunner export test)',
     'Test flow: decompose -> implement -> review on cloud_qwen38flash over simple-harness. Exported to FlowRunner to exercise the run and persistent-session lifecycle. Shares artifact root 2000 with PLOOP.',
     0, 0, 1, 0, 0, NULL,
     '2000-planning-supervisor', '2000', 'experimental', '2000', NULL, 'none');

INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, is_active, restart_policy, governance_file,
     role_type, enter_command, config_dir, default_model_source,
     default_model_alias, allocator_client, fresh_session_command,
     workdir_mode, default_harness_source, default_harness_profile, max_turns)
VALUES
    ('2000-planning-supervisor', '2000-planning-supervisor', 1, 'none',
     'SUPERVISOR_PLANNING.md', 'agent', 'default', '', 'model_allocator',
     'cloud_qwen38flash', '', '', 'father', 'simple-harness', '', 40),
    ('2000-execution-decomposer', '2000-execution-decomposer', 1, 'none',
     'EXECUTION_DECOMPOSER.md', 'agent', 'default', '', 'model_allocator',
     'cloud_qwen38flash', '', '', 'target_project', 'simple-harness', '', 40),
    ('2000-implementer', '2000-implementer', 1, 'none',
     'IMPLEMENTOR.md', 'agent', 'default', '', 'model_allocator',
     'cloud_qwen38flash', '', '', 'target_project', 'simple-harness', '', 40),
    ('2000-reviewer', '2000-reviewer', 1, 'none',
     'REVIEW.md', 'agent', 'default', '', 'model_allocator',
     'cloud_qwen38flash', '', '', 'target_project', 'simple-harness', '', 40);

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file,
     requires_readme_impact)
VALUES
    ('2000-01-PLOOP', 'human-planning', 'human', '2000-planning-supervisor',
     '2000/planning', '{ID}-request.md', 1, 1, 'handoff', 0, 0, 'HUMAN.md', 0),
    ('2000-01-PLOOP', 'planning-human', '2000-planning-supervisor', 'human',
     '2000/goals', '{ID}-GOAL-DRAFT.md', 2, 1, 'callback', 0, 0,
     'SUPERVISOR_PLANNING.md', 0),
    ('2000-02-ELOOP', 'decomposer-implementer', '2000-execution-decomposer',
     '2000-implementer', '2000/handoffs', '{ID}-handoff.md', 1, 1, 'handoff',
     0, 1, 'EXECUTION_DECOMPOSER.md', 0),
    ('2000-02-ELOOP', 'implementer-reviewer', '2000-implementer',
     '2000-reviewer', '2000/results', '{ID}-result.md', 2, 1, 'callback',
     0, 1, 'IMPLEMENTOR.md', 0),
    ('2000-02-ELOOP', 'reviewer-decomposer', '2000-reviewer',
     '2000-execution-decomposer', '2000/verdicts', '{ID}-verdict.md', 3, 1,
     'agent_delivery', 0, 1, 'REVIEW.md', 0);
