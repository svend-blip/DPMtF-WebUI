-- 025_llama_sg_flow.sql
-- Add llama_SG flow with 3 roles and 3 steps
--
-- Numbered 025, not 005, because the INSERT below writes three columns that
-- later migrations create: allocator_client (008), fresh_session_command
-- (009) and workdir_mode (023). The runner sorts by filename, so at 005 this
-- ran before all three existed and aborted every fresh install on
-- "table bridge_roles has no column named allocator_client". Existing
-- databases never noticed: they had already applied 001-024 before this file
-- was written, so the column was there when it first ran.
--
-- Every statement is INSERT OR IGNORE against a PRIMARY KEY or UNIQUE
-- constraint, so re-running it on a database that already has the llama_SG
-- flow changes nothing — in particular it does not reset bridge_id_counters
-- or overwrite a tuned model alias.

-- Roles
INSERT OR IGNORE INTO bridge_roles (role_key, tmux_session, role_type, governance_file, default_model_source, default_model_alias, allocator_client, workdir_mode, fresh_session_command)
VALUES
  ('supervisor01_llama', 'supervisor01_llama', 'agent', '461_LLAMA_SG_SUPERVISOR.md', 'model_allocator', 'laguna-local', 'claude-code', 'father', '/clear'),
  ('imple01SG', 'imple01SG', 'agent', '462_LLAMA_SG_IMPLE01.md', 'model_allocator', 'qwen-shared-sglang', 'opencode', 'target_project', '/clear'),
  ('review01SG', 'review01SG', 'agent', '463_LLAMA_SG_REVIEW01.md', 'model_allocator', 'qwen-shared-sglang', 'opencode', 'target_project', '/clear');

-- Flow
INSERT OR IGNORE INTO bridge_flows (flow_key, name, description, auto_complete_enabled)
VALUES ('llama_SG', 'Laguna + SGLang autonomous review',
        'Autonomous supervisor-driven chain: Laguna (architect) -> SGLang/Qwen (imple+review)',
        0);

-- Flow steps
INSERT OR IGNORE INTO bridge_flow_steps (flow_key, step_key, from_role, to_role, sort_order, auto_chain_to_next, pre_dispatch_script, post_dispatch_script)
VALUES
  ('llama_SG', 'supervisor-imple01', 'supervisor01_llama', 'imple01SG', 1, 1,
   'model-allocator start --alias qwen-shared-sglang',
   'model-allocator stop --alias laguna-local'),
  ('llama_SG', 'imple01-review01', 'imple01SG', 'review01SG', 2, 1, NULL, NULL),
  ('llama_SG', 'review01-supervisor', 'review01SG', 'supervisor01_llama', 3, 1,
   'model-allocator start --alias laguna-local',
   'model-allocator stop --alias qwen-shared-sglang');

-- Flow counter
INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES ('llama_SG', 1);
