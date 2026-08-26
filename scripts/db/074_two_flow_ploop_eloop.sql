-- 074: The two-flow setup — 1000-01-PLOOP and 1000-02-ELOOP.
--
-- TWO-FLOW-PLOOP-ELOOP.md (Human-approved 2026-08-26), sections 1, 5-8, 13.
-- Two orchestration flows sharing one artifact root: artifact_root = '1000'
-- on both rows, resolved by bridge_lib.get_effective_artifact_root
-- (migration 073). The flow keys are orchestration identities; the durable
-- structure is shared.
--
-- AUTHORITY SPLIT (spec §5/§7, binding):
--   PLOOP owns Run IDs, GOAL-DRAFT and (via host-side promote-goal) GOAL.
--   ELOOP owns handoff ids, handoffs, results, verdicts.
--   PLOOP's steps therefore write ONLY under 1000/planning/ — a dialogue
--   directory for the Human<->supervisor exchange, deliberately NOT
--   1000/handoffs/, so the flow cannot allocate implementation handoff
--   filenames even by accident. The Run contract itself never travels as a
--   step deliverable: it is broker-materialized (goal-draft) and promoted.
--
-- ROLES (spec §13). Role keys are distinct from every other flow so the
-- trace role-pair remains unambiguous (100_BRIDGE Security Rules 7).
-- Governance is shared where the authority boundary is shared:
-- IMPLEMENTOR.md and REVIEW.md are reused; only the genuinely new
-- boundaries get new files (EXECUTION_DECOMPOSER.md,
-- SUPERVISOR_ESCALATION.md). The model-allocator side of the contract
-- (roles.yaml keys 1000-planning-supervisor, 1000-reviewer) landed as
-- model-allocator commit 0dcf334.
--
-- qwen HARNESS STATUS (spec §13): adapter-proven, NOT flow-proven. The
-- decomposer and implementer rows are seeded is_active=0 until the phase-3
-- proof (one governed handoff through pi_test's ft_imple01) has run. The
-- reviewer, planning supervisor and escalation supervisor are proven shapes
-- and seed active.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, artifact_root, target_project_path, is_active, auto_complete_enabled)
VALUES
    ('1000-01-PLOOP', 'Planning Loop (1000)',
     'Planning: Run allocation, GOAL-DRAFT authoring, Human-approved promotion to GOAL. Shares artifact root 1000 with ELOOP.',
     '1000', NULL, 1, 0),
    ('1000-02-ELOOP', 'Execution Loop (1000)',
     'Autonomous execution of approved Runs: decomposer -> implementer -> reviewer. Shares artifact root 1000 with PLOOP.',
     '1000', NULL, 1, 0);

INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, is_active,
     default_model_source, default_model_alias, allocator_client,
     default_harness_source, default_harness_profile,
     workdir_mode, governance_file, config_dir)
VALUES
    ('1000-planning-supervisor', '1000-planning-supervisor', 'agent', 1,
     'model_allocator', 'opus5', 'claude-code',
     'claude-code', NULL,
     'father', '500_SUPERVISOR.md', '1000-planning-supervisor'),
    ('1000-execution-decomposer', '1000-execution-decomposer', 'agent', 0,
     'model_allocator', 'freetoken-qwen36-35b-a3b', NULL,
     'qwen', NULL,
     'target_project', 'EXECUTION_DECOMPOSER.md', NULL),
    ('1000-implementer', '1000-implementer', 'agent', 0,
     'model_allocator', 'freetoken-qwen36-35b-a3b', NULL,
     'qwen', NULL,
     'target_project', 'IMPLEMENTOR.md', NULL),
    ('1000-reviewer', '1000-reviewer', 'agent', 1,
     'model_allocator', 'Qwen38-Standard', 'opencode',
     'opencode', NULL,
     'target_project', 'REVIEW.md', '1000-reviewer'),
    ('1000-escalation-supervisor', '1000-escalation-supervisor', 'agent', 1,
     'harness_provider', NULL, NULL,
     'dsh', 'headless',
     'father', 'SUPERVISOR_ESCALATION.md', NULL);

-- PLOOP: Human <-> planning supervisor dialogue. 1000/planning is the
-- deliberate NOT-handoffs directory (see header).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file)
VALUES
    ('1000-01-PLOOP', 'human-planning', 'human', '1000-planning-supervisor',
     '1000/planning', '{ID}-request.md', 1, 1, 'handoff', 0, 0, 'HUMAN.md'),
    ('1000-01-PLOOP', 'planning-human', '1000-planning-supervisor', 'human',
     '1000/planning', '{ID}-plan.md', 2, 1, 'callback', 0, 0, '500_SUPERVISOR.md');

-- ELOOP: decomposer -> implementer -> reviewer -> decomposer, mirroring the
-- proven preferred_cloud_harness step shapes.
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file)
VALUES
    ('1000-02-ELOOP', 'decomposer-implementer',
     '1000-execution-decomposer', '1000-implementer',
     '1000/handoffs', '{ID}-handoff.md', 1, 1, 'handoff', 0, 1,
     'EXECUTION_DECOMPOSER.md'),
    ('1000-02-ELOOP', 'implementer-reviewer',
     '1000-implementer', '1000-reviewer',
     '1000/results', '{ID}-result.md', 2, 1, 'callback', 0, 1,
     'IMPLEMENTOR.md'),
    ('1000-02-ELOOP', 'reviewer-decomposer',
     '1000-reviewer', '1000-execution-decomposer',
     '1000/verdicts', '{ID}-verdict.md', 3, 1, 'agent_delivery', 0, 1,
     'REVIEW.md');
