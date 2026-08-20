-- 055_preferred_cloud_harness_flow.sql
-- Add the preferred_cloud_harness flow: the preferred_cloud chain shape
-- (supervisor -> implementer -> reviewer -> supervisor) with an explicit
-- coding harness assigned per role.
--
--   super-deep-deep4      DeepSeek Harness (dsh)   deepseek-v4-pro
--   imple-codex-minimaxM3 Codex CLI (codex)        MiniMax-M3
--   review-claude-sonnet5 Claude Code (claude-code) sonnet5
--
-- Governance: 511, 512, 513 in docs/governance-templates-v2/.
-- Cold-start skill: .claude/skills/PRECLOUDHARNESS/SKILL.md.
--
-- WHY TWO ROLES USE default_model_source = 'harness'. The model allocator
-- has no client adapter for DeepSeek Harness or Codex CLI, so their launch
-- command is built by scripts/bridgeV002/harness.py, not `model-allocator
-- run`. The model identity stays in default_model_alias and the harness
-- identity in allocator_client -- two columns, never collapsed. The
-- reviewer reuses the existing model_allocator 'sonnet5' alias exactly as
-- preferred_cloud's Pre-review-cl does (028): no second Sonnet 5 runtime
-- configuration is created.
--
-- STEPS MIRROR preferred_cloud (028). The evidence gate runs before the two
-- deliverable-carrying callbacks, and no pre/post model-lifecycle scripts
-- exist on any step because none of the three roles owns a local server.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'super-deep-deep4', 'super-deep-deep4', 1, 'none', '511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md',
    'agent', 'default', 'harness', 'deepseek-v4-pro',
    'dsh', NULL, 'father', NULL
);

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'imple-codex-minimaxM3', 'imple-codex-minimaxM3', 1, 'none', '512_PREFERRED_CLOUD_HARNESS_IMPLE01.md',
    'agent', 'default', 'harness', 'MiniMax-M3',
    'codex', NULL, 'target_project', NULL
);

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'review-claude-sonnet5', 'review-claude-sonnet5', 1, 'none', '513_PREFERRED_CLOUD_HARNESS_REVIEW01.md',
    'agent', 'default', 'model_allocator', 'sonnet5',
    'claude-code', '/clear', 'target_project', NULL
);

-- Flow
INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, auto_complete_enabled)
VALUES ('preferred_cloud_harness', 'Preferred Cloud Harness',
        'Autonomous supervisor-driven chain on explicit coding harnesses: DeepSeek Harness (DeepSeek V4 Pro) -> Codex (MiniMax M3) -> Claude Code (Sonnet 5)',
        0);

-- Steps. The evidence gate runs before the two deliverable-carrying callbacks,
-- exactly as in preferred_cloud (028).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active,
     auto_chain_to_next, validation_required, pre_dispatch_script)
VALUES
  ('preferred_cloud_harness', 'supervisor-imple01', 'super-deep-deep4', 'imple-codex-minimaxM3',
   'preferred_cloud_harness/handoffs', '{ID}-handoff.md', 'handoff',
   1, 1, 1, 1, NULL),
  ('preferred_cloud_harness', 'imple01-review01', 'imple-codex-minimaxM3', 'review-claude-sonnet5',
   'preferred_cloud_harness/results', '{ID}-result.md', 'callback',
   2, 1, 1, 1, 'gate-deliverable-evidence'),
  ('preferred_cloud_harness', 'review01-supervisor', 'review-claude-sonnet5', 'super-deep-deep4',
   'preferred_cloud_harness/verdicts', '{ID}-verdict.md', 'agent_delivery',
   3, 1, 1, 1, 'gate-deliverable-evidence');

-- Flow counter
INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
VALUES ('preferred_cloud_harness', 1);
