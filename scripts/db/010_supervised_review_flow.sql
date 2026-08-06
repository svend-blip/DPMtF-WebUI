-- 010: Supervised review flow — autonomous supervisor-driven review chain.
--
-- Implements the supervised_review flow that allows a supervisor role to
-- author handoffs to imple01 and receive the final verdict back as a real
-- dispatch (supervisor is role_type='agent', so it must NOT be skipped like
-- human deliveries are). The flow mirrors strict_review but with a supervisor
-- as the first step and a specific verdict delivery pattern.

-- Update the supervisor role to have fresh_session_command = '/clear'
UPDATE bridge_roles SET fresh_session_command = '/clear' WHERE role_key = 'supervisor';

-- Create the supervised_review flow
INSERT OR IGNORE INTO bridge_flows (flow_key, name, description, is_active)
VALUES ('supervised_review', 'Supervised Review',
        'Autonomous supervisor-driven review chain: supervisor -> imple01 -> review01 -> review02 -> supervisor',
        1);

-- Add the 4 steps for supervised_review flow
-- deliverable_dir is stored relative to the bridge directory.
-- dispatch.py resolves it with os.path.join(bridge_dir, …) when it is
-- not absolute, which is the convention llama_SG has used since it was
-- added. Writing the author's own /home/svend/flows/… here gave every
-- fresh install a database pointing at another person's directories.

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active, auto_chain_to_next)
VALUES ('supervised_review', 'supervisor-imple01', 'supervisor', 'imple01',
        'supervised_review/handoffs', '{ID}-handoff.md',
        'handoff', 1, 1, 1);

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active, auto_chain_to_next)
VALUES ('supervised_review', 'imple01-review01', 'imple01', 'review01',
        'supervised_review/results', '{ID}-result.md',
        'technical_review', 2, 1, 1);

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active, auto_chain_to_next)
VALUES ('supervised_review', 'review01-review02', 'review01', 'review02',
        'supervised_review/reviews', '{ID}-review01.md',
        'verdict', 3, 1, 1);

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active, auto_chain_to_next)
VALUES ('supervised_review', 'review02-supervisor', 'review02', 'supervisor',
        'supervised_review/verdicts', '{ID}-verdict.md',
        'agent_delivery', 4, 1, 0);

-- Add the counter for supervised_review flow
INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
VALUES ('supervised_review', 1);