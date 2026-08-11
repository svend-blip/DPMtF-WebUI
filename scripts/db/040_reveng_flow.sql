-- 040: The `reveng` (RevEngineer) flow — retro-game reverse engineering.
--
-- A three-role supervise/implement/review chain for reverse-engineering old
-- games into modern, runnable form (decomp / source-port / remaster-style
-- work). Same shape as supervised_review but with a single reviewer.
--
-- ROLE NAMES / MODELS. The keys Rev_Supervisor / Rev_Imple / Rev_Review MUST
-- match model-allocator's roles.yaml exactly, or the allocator binding is
-- silently ignored and the role falls back to the direct path. Wired
-- 2026-08-11:
--   Rev_Supervisor -> cloud_deepseek (deepseek-v4-pro:cloud via Ollama's
--                     Anthropic endpoint, claude-code)
--   Rev_Imple      -> cloud_minimax  (MiniMax-M3, opencode)
--   Rev_Review     -> sonnet5        (claude-sonnet-5, claude-code)
--
-- TARGET PROJECT. Left NULL — set per run (via the WebUI dispatch or a later
-- migration) to the specific game-RE repository being worked. The dispatch
-- Target Project block yields to the run's own scope when unset.
--
-- Governance: 491/492/493 in docs/governance-templates-v2/, modelled on the
-- 47x preferred_cloud series (the closest analog: autonomous supervisor +
-- single cloud implementer + single cloud reviewer). Step rules mirror it:
-- handoff / callback / agent_delivery, all auto-chaining and validated.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows (flow_key, name, description, target_project_path, is_active)
VALUES (
    'reveng',
    'RevEngineer',
    'Retro-game reverse engineering: supervise/implement/review chain for modernizing old games',
    NULL,
    1
);

INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES ('reveng', 1);

-- Supervisor runs on Father (workdir_mode=father), like supervised_review's
-- supervisor_auto. deepseek-v4-pro via the claude-code client.
INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'Rev_Supervisor', 'Rev_Supervisor', 1, 'none', '491_REVENG_SUPERVISOR.md',
    'agent', 'default', 'model_allocator', 'cloud_deepseek',
    'claude-code', '/clear', 'father', NULL
);

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'Rev_Imple', 'Rev_Imple', 1, 'none', '492_REVENG_IMPLE.md',
    'agent', 'default', 'model_allocator', 'cloud_minimax',
    'opencode', '/clear', 'target_project', NULL
);

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'Rev_Review', 'Rev_Review', 1, 'none', '493_REVENG_REVIEW.md',
    'agent', 'default', 'model_allocator', 'sonnet5',
    'claude-code', '/clear', 'target_project', NULL
);

-- Chain: supervisor -> imple -> review -> supervisor. Deliverable dirs are
-- flow-relative (resolved against the bridge root at runtime); never absolute.
INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'reveng', 'supervisor-imple', 'Rev_Supervisor', 'Rev_Imple',
    'reveng/handoffs', '{ID}-handoff.md', 'handoff', 1, 1, 1, 1
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'reveng', 'imple-review', 'Rev_Imple', 'Rev_Review',
    'reveng/results', '{ID}-result.md', 'callback', 2, 1, 1, 1
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'reveng', 'review-supervisor', 'Rev_Review', 'Rev_Supervisor',
    'reveng/verdicts', '{ID}-verdict.md', 'agent_delivery', 3, 1, 1, 1
);
