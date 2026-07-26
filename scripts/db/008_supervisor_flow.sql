-- 008: Supervisor flow — Human-paired senior engineering session.
--
-- 1. bridge_roles.allocator_client: which model-allocator client starts the
--    role's coding frontend (opencode | claude-code). Removes the hardcoded
--    'opencode' in start_coding.py — client choice is now per-role DB config.
-- 2. Seed the 'supervisor' role (Claude Code with the fable5 alias in tmux
--    session 'supervisor') and a two-step flow: human -> supervisor
--    (handoff) and supervisor -> human (result delivery).

ALTER TABLE bridge_roles ADD COLUMN allocator_client TEXT DEFAULT 'opencode';

INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, governance_file, enter_command,
     config_dir, default_model_source, default_model_alias,
     allocator_client, is_active)
VALUES ('supervisor', 'supervisor', 'agent', '500_SUPERVISOR.md', 'default',
        'supervisor', 'model_allocator', 'fable5', 'claude-code', 1);

INSERT OR IGNORE INTO bridge_flows (flow_key, name, description, is_active)
VALUES ('supervisor', 'Supervisor',
        'Human-paired senior engineering session: discuss issues and apply fixes (Claude Code / Fable 5)',
        1);

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active, validation_required)
VALUES ('supervisor', 'human-supervisor', 'human', 'supervisor',
        '/home/svend/flows/supervisor/handoffs', '{ID}-handoff.md',
        'handoff', 1, 1, 0);

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active, validation_required)
VALUES ('supervisor', 'supervisor-human', 'supervisor', 'human',
        '/home/svend/flows/supervisor/results', '{ID}-result.md',
        'human_delivery', 2, 1, 0);

INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
VALUES ('supervisor', 1);
