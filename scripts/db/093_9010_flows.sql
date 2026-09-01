-- 093: The 9010 flows — 9010-01-PLOOP and 9010-02-ELOOP.
--
-- Human decision 2026-09-01: a sibling of the 9000 pair whose PURPOSE is
-- to prove a fully cloud, two-vendor, two-harness composition:
--   PLOOP  planning supervisor: DeepSeek V4 Pro DIRECT at DeepSeek (not
--          OpenRouter, not a local relay) over the claude-code client —
--          model-allocator alias cloud_deepseek, runtime profile
--          cloud_deepseek_direct (api.deepseek.com/anthropic,
--          live-verified 2026-09-01).
--   ELOOP  decomposer/implementer/reviewer/escalation: MiniMax-M3 over
--          the Codex harness on every role. Codex is a NATIVE harness
--          with no model-allocator adapter, so these roles use
--          default_model_source='harness_provider' with the literal
--          model id — the codex-native form of the cloud_minimax alias;
--          codex's own minimax provider config supplies endpoint+auth
--          (the proven imple-codex-minimaxM3 shape).
--
-- Ships with the install as EXPERIMENTAL (ui_category, migration 088) —
-- unlike the 091 examples it demonstrates a specific vendor/harness
-- composition rather than the on-ramp. Portability follows the 091
-- rules: target_project_path NULL, workdir_mode='father', shared
-- governance generics, no machine paths in this file, supervisor_role
-- explicit on every flow (the NULL fallback routes to supervisor_auto,
-- which fresh databases do not carry). Role keys are distinct from
-- every other flow (100_BRIDGE Security Rule 7). The model-allocator
-- side (roles/models/runtime_profiles, live + .example) lands in
-- model-allocator in the same change set. Requires DEEPSEEK_API_KEY and
-- MINIMAX_API_KEY (plus a codex minimax provider config) at runtime.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, artifact_root, target_project_path,
     is_active, auto_complete_enabled, ui_category, supervisor_role)
VALUES
    ('9010-01-PLOOP', 'Planning Loop (9010 DeepSeek/Codex)',
     'Experimental two-flow pair: planning on DeepSeek V4 Pro DIRECT at DeepSeek over claude-code. Shares artifact root 9010 with the ELOOP.',
     '9010', NULL, 1, 0, 'experimental', '9010-planning-supervisor'),
    ('9010-02-ELOOP', 'Execution Loop (9010 DeepSeek/Codex)',
     'Experimental two-flow pair: decomposer -> implementer -> reviewer on MiniMax-M3 over the Codex harness on every role. Shares artifact root 9010 with the PLOOP.',
     '9010', NULL, 1, 0, 'experimental', '9010-escalation-supervisor');

INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, is_active,
     default_model_source, default_model_alias, allocator_client,
     default_harness_source, default_harness_profile,
     workdir_mode, governance_file, config_dir, fresh_session_command)
VALUES
    ('9010-planning-supervisor', '9010-planning-supervisor', 'agent', 1,
     'model_allocator', 'cloud_deepseek', 'claude-code',
     'claude-code', NULL,
     'father', '500_SUPERVISOR.md', NULL, '/clear'),
    ('9010-execution-decomposer', '9010-execution-decomposer', 'agent', 1,
     'harness_provider', 'MiniMax-M3', 'codex',
     'codex', NULL,
     'father', 'EXECUTION_DECOMPOSER.md', NULL, NULL),
    ('9010-implementer', '9010-implementer', 'agent', 1,
     'harness_provider', 'MiniMax-M3', 'codex',
     'codex', NULL,
     'father', 'IMPLEMENTOR.md', NULL, NULL),
    ('9010-reviewer', '9010-reviewer', 'agent', 1,
     'harness_provider', 'MiniMax-M3', 'codex',
     'codex', NULL,
     'father', 'REVIEW.md', NULL, NULL),
    ('9010-escalation-supervisor', '9010-escalation-supervisor', 'agent', 1,
     'harness_provider', 'MiniMax-M3', 'codex',
     'codex', NULL,
     'father', 'SUPERVISOR_ESCALATION.md', NULL, NULL);

-- PLOOP: Human <-> planning supervisor dialogue (the 090 live shape).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file)
VALUES
    ('9010-01-PLOOP', 'human-planning', 'human', '9010-planning-supervisor',
     '9010/planning', '{ID}-request.md', 1, 1, 'handoff', 0, 0, 'HUMAN.md'),
    ('9010-01-PLOOP', 'planning-human', '9010-planning-supervisor', 'human',
     '9010/goals', '{ID}-GOAL-DRAFT.md', 2, 1, 'callback', 0, 0,
     '500_SUPERVISOR.md');

-- ELOOP: decomposer -> implementer -> reviewer -> decomposer, mirroring
-- 090's live shape (gate-test-impact + README impact on the result step).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file,
     pre_dispatch_script, requires_readme_impact)
VALUES
    ('9010-02-ELOOP', 'decomposer-implementer',
     '9010-execution-decomposer', '9010-implementer',
     '9010/handoffs', '{ID}-handoff.md', 1, 1, 'handoff', 0, 1,
     'EXECUTION_DECOMPOSER.md', NULL, 0),
    ('9010-02-ELOOP', 'implementer-reviewer',
     '9010-implementer', '9010-reviewer',
     '9010/results', '{ID}-result.md', 2, 1, 'callback', 0, 1,
     'IMPLEMENTOR.md', 'gate-test-impact', 1),
    ('9010-02-ELOOP', 'reviewer-decomposer',
     '9010-reviewer', '9010-execution-decomposer',
     '9010/verdicts', '{ID}-verdict.md', 3, 1, 'agent_delivery', 0, 1,
     'REVIEW.md', NULL, 0);

INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
VALUES
    ('9010-01-PLOOP', 1),
    ('9010-02-ELOOP', 1);
