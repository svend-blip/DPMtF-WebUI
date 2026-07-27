-- 011: Supervisor autonomous wiring part 1 of 2 (DB only; scheduler code follows in the next handoff).
--
-- Creates supervisor_auto role for autonomous wake-ups, updates supervised_review flow steps to use it,
-- and adds agent_delivery convention rule for automated verdict delivery.

-- Create new bridge_roles row 'supervisor_auto' with same tmux_session as 'supervisor'
INSERT OR IGNORE INTO bridge_roles (
    role_key, is_active, created_at, updated_at,
    tmux_session, role_type, default_model_source, default_model_alias,
    config_dir, governance_file, allocator_client, fresh_session_command
) 
SELECT 
    'supervisor_auto' as role_key,
    1 as is_active,
    datetime('now') as created_at,
    datetime('now') as updated_at,
    tmux_session, -- same session as supervisor
    'agent' as role_type,
    default_model_source, -- copy from supervisor
    default_model_alias, -- copy from supervisor
    config_dir, -- copy from supervisor
    '501_SUPERVISOR_AUTONOMOUS.md' as governance_file,
    allocator_client, -- copy from supervisor
    '/clear' as fresh_session_command
FROM bridge_roles 
WHERE role_key = 'supervisor';

-- Update supervised_review flow steps to use the new supervisor_auto role
-- Step 1: Change from_role from 'supervisor' to 'supervisor_auto'
UPDATE bridge_flow_steps 
SET from_role = 'supervisor_auto' 
WHERE flow_key = 'supervised_review' AND step_key = 'supervisor-imple01';

-- Step 4: Change to_role from 'supervisor' to 'supervisor_auto' 
UPDATE bridge_flow_steps 
SET to_role = 'supervisor_auto' 
WHERE flow_key = 'supervised_review' AND step_key = 'review02-supervisor';

-- Insert new convention rule 'agent_delivery' mirroring 'human_delivery' but for agents
INSERT OR IGNORE INTO bridge_convention_rules (
    rule_key, step_type, dir_template, pattern_template,
    error_template, created_at, updated_at, content_template, validation_schema
)
SELECT 
    'agent_delivery' as rule_key,
    'AgentDelivery' as step_type,
    'verdicts' as dir_template,
    '{ID}-verdict.md' as pattern_template,
    'Failed to deliver verdict.' as error_template,
    datetime('now') as created_at,
    datetime('now') as updated_at,
    'Read the delivered verdict file for handoff {handoff_id}.
Then, read your own governance file and follow your wake-up protocol.
Act on the verdict outcome accordingly.' as content_template,
    '{"type": "object", "properties": {"verdict": {"type": "string"}}, "required": ["verdict"]}' as validation_schema
FROM bridge_convention_rules 
WHERE rule_key = 'human_delivery';

-- Bump the strict_review row in bridge_id_counters so next_id is at least 323
-- Use idempotent UPDATE that never lowers the value (will be 323 already from previous handoffs)
UPDATE bridge_id_counters 
SET next_id = MAX(next_id, 323) 
WHERE flow_key = 'strict_review';