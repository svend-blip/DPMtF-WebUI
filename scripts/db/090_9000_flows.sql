-- 090: The 9000 test flows — 9000-01-PLOOP and 9000-02-ELOOP.
--
-- Human decision 2026-08-30 (alignment task, item 7): a copy of the 1010
-- two-flow shape whose PURPOSE is to prove the full allocator composition:
-- model-allocator resolves every model, harness-allocator launches every
-- interface. The planning supervisor runs claude-code; the three chain
-- roles run the simple-harness interface (native launch, ninth supported
-- harness) with cloud_minimax resolved by model-allocator — the
-- combination the 2026-08-30 wiring commits (harness-allocator 784b97d,
-- DPMtF f573195) made launchable.
--
-- Unlike 1010 (created through the WebUI, rows only in the live DB), 9000
-- is seeded by migration so fresh databases carry it. Steps mirror 1010's
-- LIVE shape (23 closed runs) including the gate-test-impact pre-dispatch
-- gate and the README-impact requirement on implementer->reviewer.
-- Role keys are distinct from every other flow (100_BRIDGE Security Rule
-- 7); governance templates are SHARED, not copied.
--
-- target_project_path: /home/svend/9000-sandbox — a dedicated throwaway
-- git repo (created alongside this migration), NOT a real project: these
-- flows exist to exercise wiring, and their roles must not edit anything
-- that matters. ui_category='experimental': test flows are atypical and
-- render in the Experimental Flows panel (migration 088).
--
-- The model-allocator side of the contract (roles.yaml keys + the
-- simple-harness client on the cloud_minimax alias) lands in
-- model-allocator in the same change set.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, artifact_root, target_project_path,
     is_active, auto_complete_enabled, ui_category)
VALUES
    ('9000-01-PLOOP', 'Planning Loop (9000 test)',
     'Test flow: Run allocation and GOAL-DRAFT authoring. Exists to prove model-allocator + harness-allocator composition. Shares artifact root 9000 with ELOOP.',
     '9000', '/home/svend/9000-sandbox', 1, 0, 'experimental'),
    ('9000-02-ELOOP', 'Execution Loop (9000 test)',
     'Test flow: decomposer -> implementer -> reviewer on the simple-harness interface with model-allocator-resolved models. Shares artifact root 9000 with PLOOP.',
     '9000', '/home/svend/9000-sandbox', 1, 0, 'experimental');

INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, is_active,
     default_model_source, default_model_alias, allocator_client,
     default_harness_source, default_harness_profile,
     workdir_mode, governance_file, config_dir, fresh_session_command)
VALUES
    ('9000-planning-supervisor', '9000-planning-supervisor', 'agent', 1,
     'model_allocator', 'opus5', 'claude-code',
     'claude-code', NULL,
     'father', '500_SUPERVISOR.md', '9000-planning-supervisor', '/clear'),
    ('9000-execution-decomposer', '9000-execution-decomposer', 'agent', 1,
     'model_allocator', 'cloud_minimax', NULL,
     'simple-harness', NULL,
     'target_project', 'EXECUTION_DECOMPOSER.md', NULL, NULL),
    ('9000-implementer', '9000-implementer', 'agent', 1,
     'model_allocator', 'cloud_minimax', NULL,
     'simple-harness', NULL,
     'target_project', 'IMPLEMENTOR.md', NULL, NULL),
    ('9000-reviewer', '9000-reviewer', 'agent', 1,
     'model_allocator', 'cloud_minimax', NULL,
     'simple-harness', NULL,
     'target_project', 'REVIEW.md', NULL, NULL),
    ('9000-escalation-supervisor', '9000-escalation-supervisor', 'agent', 1,
     'harness_provider', NULL, NULL,
     'dsh', 'headless',
     'father', 'SUPERVISOR_ESCALATION.md', NULL, NULL);

-- PLOOP: Human <-> planning supervisor dialogue (1010's live shape).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file)
VALUES
    ('9000-01-PLOOP', 'human-planning', 'human', '9000-planning-supervisor',
     '9000/planning', '{ID}-request.md', 1, 1, 'handoff', 0, 0, 'HUMAN.md'),
    ('9000-01-PLOOP', 'planning-human', '9000-planning-supervisor', 'human',
     '9000/goals', '{ID}-GOAL-DRAFT.md', 2, 1, 'callback', 0, 0, '500_SUPERVISOR.md');

-- ELOOP: decomposer -> implementer -> reviewer -> decomposer, mirroring
-- 1010's live shape (gate-test-impact + README impact on the result step).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file,
     pre_dispatch_script, requires_readme_impact)
VALUES
    ('9000-02-ELOOP', 'decomposer-implementer',
     '9000-execution-decomposer', '9000-implementer',
     '9000/handoffs', '{ID}-handoff.md', 1, 1, 'handoff', 0, 1,
     'EXECUTION_DECOMPOSER.md', NULL, 0),
    ('9000-02-ELOOP', 'implementer-reviewer',
     '9000-implementer', '9000-reviewer',
     '9000/results', '{ID}-result.md', 2, 1, 'callback', 0, 1,
     'IMPLEMENTOR.md', 'gate-test-impact', 1),
    ('9000-02-ELOOP', 'reviewer-decomposer',
     '9000-reviewer', '9000-execution-decomposer',
     '9000/verdicts', '{ID}-verdict.md', 3, 1, 'agent_delivery', 0, 1,
     'REVIEW.md', NULL, 0);
