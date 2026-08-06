-- 028_preferred_cloud_flow.sql
-- Add the preferred_cloud flow: three roles, one chain, cloud models only.
--
-- The same shape as llama_SG — supervisor drives, implementer builds, reviewer
-- verifies against the working tree — with hosted models instead of local
-- ones. Governance: 471, 472, 473.
--
--   Pre-super-cl   Claude Opus 5   (opus5)          claude-code
--   Pre-imple-cl   MiniMax M3      (cloud_minimax)  opencode
--   Pre-review-cl  Claude Sonnet 5 (sonnet5)        claude-code
--
-- Pre-imple-cl runs OpenCode rather than Claude Code because the allocator's
-- Claude Code adapter rejects provider=minimax outright (claude_code.py).
-- MiniMax does expose an Anthropic-shaped endpoint, but it is not wired, so
-- the OpenAI-compatible path is the supported route. Human decision, recorded
-- here so it is not read as an oversight.
--
-- No pre/post dispatch scripts for model lifecycle. All three aliases carry
-- lifecycle_policy: cloud_noop, where start and stop are credential checks
-- rather than loads — there is no card to take turns on and nothing to evict.
-- That is the one structural difference from llama_SG, and it removes the
-- whole class of swap failures with it.
--
-- deliverable_dir is relative to the bridge directory; dispatch resolves it
-- with os.path.join(bridge_dir, …).

-- Roles
INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, governance_file,
     default_model_source, default_model_alias, allocator_client,
     workdir_mode, fresh_session_command)
VALUES
  ('Pre-super-cl',  'Pre-super-cl',  'agent', '471_PREFERRED_CLOUD_SUPERVISOR.md',
   'model_allocator', 'opus5',         'claude-code', 'father',         '/clear'),
  ('Pre-imple-cl',  'Pre-imple-cl',  'agent', '472_PREFERRED_CLOUD_IMPLE01.md',
   'model_allocator', 'cloud_minimax', 'opencode',    'target_project', '/clear'),
  ('Pre-review-cl', 'Pre-review-cl', 'agent', '473_PREFERRED_CLOUD_REVIEW01.md',
   'model_allocator', 'sonnet5',       'claude-code', 'target_project', '/clear');

-- Flow
INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, auto_complete_enabled)
VALUES ('preferred_cloud', 'Preferred cloud autonomous review',
        'Autonomous supervisor-driven chain on hosted models: Opus 5 -> MiniMax M3 -> Sonnet 5',
        0);

-- Steps. The evidence gate runs before the two deliverable-carrying callbacks,
-- exactly as in llama_SG: it compares the claims in a result or verdict
-- against the working tree, which is the check that stopped a fabricated
-- implementation report from being approved.
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active,
     auto_chain_to_next, validation_required, pre_dispatch_script)
VALUES
  ('preferred_cloud', 'supervisor-imple01', 'Pre-super-cl', 'Pre-imple-cl',
   'preferred_cloud/handoffs', '{ID}-handoff.md', 'handoff',
   1, 1, 1, 1, NULL),
  ('preferred_cloud', 'imple01-review01', 'Pre-imple-cl', 'Pre-review-cl',
   'preferred_cloud/results', '{ID}-result.md', 'callback',
   2, 1, 1, 1, 'gate-deliverable-evidence'),
  ('preferred_cloud', 'review01-supervisor', 'Pre-review-cl', 'Pre-super-cl',
   'preferred_cloud/verdicts', '{ID}-verdict.md', 'agent_delivery',
   3, 1, 1, 1, 'gate-deliverable-evidence');

-- Flow counter
INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
VALUES ('preferred_cloud', 1);
