-- 119 — The core flows are part of a fresh install.
--
-- strict_review, cloud_llm and cloud_pay are the flows governance files
-- 40x/41x/42x describe, and the 1010 family is the simple-harness loop. All
-- five were made by hand in the production database (the seed script that
-- once wrote the first three no longer exists), so a fresh install had the
-- governance for flows it did not have. Found 2026-09-20.
--
-- It also had flows without their Human: the role `human` existed only in
-- production, and 20 steps in 10 migrated flows (supervisor, lightworker,
-- pi_test and every PLOOP since migration 074) name it as sender or receiver.
--
-- Copied from the production rows on 2026-09-20: 5 flows, 17 steps,
-- 20 roles, and a counter at 1 for each flow. Every statement is INSERT
-- OR IGNORE: on a database that has these rows — with its own target paths,
-- models, mandates and counters — nothing changes.
--
-- What is NOT copied: target_project_path. In production cloud_pay and the
-- 1010 family point at directories under the author's home; here every flow
-- is installed with NULL, which bridge_lib reads as "works in Father". Set
-- the path per installation in the flow editor. Model aliases are copied:
-- they are names in model-allocator's configuration, as in every flow
-- migration before this one, and a role whose alias the local allocator
-- does not know says so when it is started.
--
-- Not included: the trade_cockpit flows and their twelve roles (they belong
-- to the trade project's installation), ft_imple01, and two zzverify_* test
-- roles.
--
-- Rollback: rollbacks/119_core_flows_rollback.sql

-- Roles first: a step that names a role nobody created is what this corrects.
INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, setup_script, teardown_script, deliver_error_msg, is_active, restart_policy, governance_file, role_type, enter_command, config_dir, primary_output_type, default_model_source, default_model_alias, trade_mcp_push_mode, max_output_tokens, allocator_client, fresh_session_command, workdir_mode, execution_target, implementation_mode, default_harness_source, default_harness_profile, codex_fresh_context_policy, max_turns, context_budget)
VALUES
    ('1010-escalation-supervisor', '1010-escalation-supervisor', NULL, NULL, NULL, 1, 'none', 'SUPERVISOR_ESCALATION.md', 'agent', 'default', NULL, NULL, 'harness_provider', NULL, NULL, NULL, NULL, NULL, 'father', NULL, NULL, 'dsh', 'headless', NULL, NULL, NULL),
    ('1010-execution-decomposer', '1010-execution-decomposer', NULL, NULL, NULL, 1, 'none', 'EXECUTION_DECOMPOSER.md', 'agent', 'default', '1010-execution-decomposer', NULL, 'model_allocator', 'cloud_minimax', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('1010-implementer', '1010-implementer', NULL, NULL, NULL, 1, 'none', 'IMPLEMENTOR.md', 'agent', 'default', '1010-implementer', NULL, 'model_allocator', 'cloud_minimax', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('1010-planning-supervisor', '1010-planning-supervisor', NULL, NULL, NULL, 1, 'none', 'SUPERVISOR_PLANNING.md', 'agent', 'default', '1010-planning-supervisor', NULL, 'model_allocator', 'opus5', NULL, NULL, 'claude-code', NULL, 'father', NULL, NULL, 'claude-code', NULL, NULL, NULL, NULL),
    ('1010-reviewer', '1010-reviewer', NULL, NULL, NULL, 1, 'none', 'REVIEW.md', 'agent', 'default', '1010-reviewer', NULL, 'model_allocator', 'sonnet5', NULL, NULL, 'claude-code', '/clear', 'target_project', NULL, NULL, 'claude-code', NULL, NULL, NULL, NULL),
    ('archi01', 'archi01', NULL, NULL, NULL, 1, 'none', 'ARCHITECT.md', 'agent', 'default', NULL, NULL, 'model_allocator', 'archi-local', NULL, NULL, 'opencode', '/new', 'father', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('archi01cloud', 'archi01cloud', NULL, NULL, NULL, 1, 'none', 'ARCHITECT.md', 'agent', 'default', NULL, NULL, 'model_allocator', 'archi-local', NULL, NULL, 'opencode', '/new', 'father', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('archi01pay', 'archi01pay', NULL, NULL, NULL, 1, 'none', 'ARCHITECT.md', 'agent', 'default', 'archi01pay', NULL, 'model_allocator', 'archi-pay', NULL, NULL, 'claude-code', '/clear', 'father', NULL, NULL, 'claude-code', NULL, NULL, NULL, NULL),
    ('human', 'human', NULL, NULL, NULL, 1, 'none', 'HUMAN.md', 'human', 'default', NULL, NULL, NULL, NULL, NULL, NULL, 'opencode', NULL, 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('humancloud', 'humancloud', NULL, NULL, NULL, 1, 'none', 'HUMAN.md', 'human', 'default', NULL, NULL, NULL, NULL, NULL, NULL, 'opencode', NULL, 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('humanpay', 'humanpay', NULL, NULL, NULL, 1, 'none', 'HUMAN.md', 'human', 'default', NULL, NULL, NULL, NULL, NULL, NULL, 'opencode', NULL, 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('imple01', 'imple01', NULL, NULL, NULL, 1, 'none', 'IMPLEMENTOR.md', 'agent', 'default', 'imple01', NULL, 'model_allocator', 'imple01-local', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('imple01cloud', 'imple01cloud', NULL, NULL, NULL, 1, 'none', 'IMPLEMENTOR.md', 'agent', 'c-m', NULL, NULL, 'model_allocator', 'freebuff-cli', NULL, NULL, 'freebuff', '/new', 'target_project', NULL, NULL, 'freebuff', NULL, NULL, NULL, NULL),
    ('imple01pay', 'imple01pay', NULL, NULL, NULL, 1, 'none', 'IMPLEMENTOR.md', 'agent', 'default', 'imple01pay', NULL, 'model_allocator', 'imple-pay', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('review01', 'review01', NULL, NULL, NULL, 1, 'none', 'TECHNICAL_REVIEW.md', 'agent', 'default', 'review01', NULL, 'model_allocator', 'review01-local', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('review01cloud', 'review01cloud', NULL, NULL, NULL, 1, 'none', 'TECHNICAL_REVIEW.md', 'agent', 'default', 'review01cloud', NULL, 'model_allocator', 'review02-local', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('review01pay', 'review01pay', NULL, NULL, NULL, 1, 'none', 'TECHNICAL_REVIEW.md', 'agent', 'default', 'review01pay', NULL, 'model_allocator', 'review02-local', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('review02', 'review02', NULL, NULL, NULL, 1, 'none', 'GOVERNANCE_REVIEW.md', 'agent', 'default', 'review02', NULL, 'model_allocator', 'review02-local', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('review02cloud', 'review02cloud', NULL, NULL, NULL, 1, 'none', 'GOVERNANCE_REVIEW.md', 'agent', 'default', 'review02cloud', NULL, 'model_allocator', 'review-cloud', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL),
    ('review02pay', 'review02pay', NULL, NULL, NULL, 1, 'none', 'GOVERNANCE_REVIEW.md', 'agent', 'default', 'review02pay', NULL, 'model_allocator', 'review-cloud', NULL, NULL, 'opencode', '/new', 'target_project', NULL, NULL, 'opencode', NULL, NULL, NULL, NULL);

INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, is_default, is_active, auto_complete_enabled, use_machine_profile, target_project_path, implementation_mode, supervisor_role, artifact_root, ui_category, cold_start_skill, supervisor_mandate, commit_cadence)
VALUES
    ('strict_review', 'Standard development flow', 'human/archi01/imple01/review01/review02/human', 0, 1, 0, 0, NULL, NULL, NULL, NULL, 'standard', NULL, NULL, 'none'),
    ('cloud_llm', 'Using Cloud Freebuff', 'Freebuff', 0, 1, 0, 0, NULL, NULL, NULL, NULL, 'standard', NULL, NULL, 'none'),
    ('cloud_pay', 'Cloud Pay', 'Using Anthropic API via proxy', 0, 1, 0, 0, NULL, NULL, NULL, NULL, 'standard', NULL, NULL, 'none'),
    ('1010-01-PLOOP', 'Planning Loop (1010)', 'Planning: Run allocation, GOAL-DRAFT authoring, Human-approved promotion to GOAL. All-cloud twin of 1000-01-PLOOP. Shares artifact root 1010 with ELOOP.', 0, 1, 0, 0, NULL, NULL, '1010-planning-supervisor', '1010', 'standard', NULL, NULL, 'none'),
    ('1010-02-ELOOP', 'Execution Loop (1010)', 'Autonomous execution of approved Runs: decomposer -> implementer -> reviewer, all cloud models. Shares artifact root 1010 with PLOOP.', 0, 1, 0, 0, NULL, NULL, '1010-planning-supervisor', '1010', 'standard', NULL, NULL, 'none');

INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern, pre_dispatch_script, post_dispatch_script, error_msg, sort_order, is_active, rule_key, auto_chain_to_next, validation_required, model_source, model_alias, implementation_mode, auto_dispatch, governance_file, harness_source, harness_profile, requires_readme_impact)
VALUES
    ('strict_review', 'archi01-imple01', 'archi01', 'imple01', 'strict_review/handoffs', '{ID}-handoff.md', NULL, 'post-dispatch-common', 'Failed to deliver handoff to {to_role}.', 1, 1, 'handoff', 1, 1, NULL, NULL, NULL, NULL, 'ARCHITECT.md', NULL, NULL, 0),
    ('strict_review', 'imple01-review01', 'imple01', 'review01', 'strict_review/results', '{ID}-result.md', NULL, 'post-dispatch-common', 'Failed to deliver callback to {to_role}.', 2, 1, 'technical_review', 1, 1, NULL, NULL, NULL, NULL, 'IMPLEMENTOR.md', NULL, NULL, 0),
    ('strict_review', 'review01-review02', 'review01', 'review02', 'strict_review/reviews', '{ID}-review01.md', NULL, 'post-dispatch-common', 'Failed to deliver callback to {to_role}.', 3, 1, 'verdict', 1, 1, NULL, NULL, NULL, NULL, 'TECHNICAL_REVIEW.md', NULL, NULL, 0),
    ('strict_review', 'review02-human', 'review02', 'human', 'strict_review/verdicts', '{ID}-verdict.md', NULL, 'post-dispatch-common', 'Failed to deliver verdict. Present to {to_role} manually.', 4, 1, 'human_delivery', 0, 0, NULL, NULL, NULL, NULL, 'GOVERNANCE_REVIEW.md', NULL, NULL, 0),
    ('cloud_llm', 'archi01-imple01', 'archi01cloud', 'imple01cloud', 'cloud_llm/handoffs', '{ID}-handoff.md', NULL, 'post-dispatch-common', 'Failed to deliver handoff to {to_role}.', 1, 1, 'handoff', 0, 1, NULL, NULL, NULL, NULL, 'ARCHITECT.md', NULL, NULL, 0),
    ('cloud_llm', 'imple01-review01', 'imple01cloud', 'review01cloud', 'cloud_llm/results', '{ID}-result.md', NULL, 'post-dispatch-common', 'Failed to deliver technical review to {to_role}.', 2, 1, 'technical_review', 0, 1, NULL, NULL, NULL, NULL, 'IMPLEMENTOR.md', NULL, NULL, 0),
    ('cloud_llm', 'review01-review02', 'review01cloud', 'review02cloud', 'cloud_llm/reviews', '{ID}-review01.md', NULL, 'post-dispatch-common', 'Failed to deliver callback to {to_role}.', 3, 1, 'verdict', 0, 1, NULL, NULL, NULL, NULL, 'TECHNICAL_REVIEW.md', NULL, NULL, 0),
    ('cloud_llm', 'review02-human', 'review02cloud', 'humancloud', 'cloud_llm/verdicts', '{ID}-verdict.md', NULL, 'post-dispatch-common', 'Failed to deliver verdict to Human. Present manually.', 4, 1, 'human_delivery', 0, 0, NULL, NULL, NULL, NULL, 'GOVERNANCE_REVIEW.md', NULL, NULL, 0),
    ('cloud_pay', 'archi01-imple01', 'archi01pay', 'imple01pay', 'cloud_pay/handoffs', '{ID}-handoff.md', NULL, 'post-dispatch-common', 'Failed to deliver handoff to {to_role}.', 1, 1, 'handoff', 0, 1, NULL, NULL, NULL, NULL, 'ARCHITECT.md', NULL, NULL, 0),
    ('cloud_pay', 'imple01-review01', 'imple01pay', 'review01pay', 'cloud_pay/results', '{ID}-result.md', NULL, 'post-dispatch-common', 'Failed to deliver callback to {to_role}.', 2, 1, 'technical_review', 0, 1, NULL, NULL, NULL, NULL, 'IMPLEMENTOR.md', NULL, NULL, 0),
    ('cloud_pay', 'review01-review02', 'review01pay', 'review02pay', 'cloud_pay/reviews', '{ID}-review01.md', NULL, 'post-dispatch-common', 'Failed to deliver callback to {to_role}.', 3, 1, 'verdict', 0, 1, NULL, NULL, NULL, NULL, 'TECHNICAL_REVIEW.md', NULL, NULL, 0),
    ('cloud_pay', 'review02-human', 'review02pay', 'humanpay', 'cloud_pay/verdicts', '{ID}-verdict.md', NULL, 'post-dispatch-common', 'Failed to deliver verdict. Present to {to_role} manually.', 4, 1, 'human_delivery', 0, 0, NULL, NULL, NULL, NULL, 'GOVERNANCE_REVIEW.md', NULL, NULL, 0),
    ('1010-01-PLOOP', 'human-planning', 'human', '1010-planning-supervisor', '1010/planning', '{ID}-request.md', NULL, NULL, NULL, 1, 1, 'handoff', 0, 0, NULL, NULL, NULL, NULL, 'HUMAN.md', NULL, NULL, 0),
    ('1010-01-PLOOP', 'planning-human', '1010-planning-supervisor', 'human', '1010/goals', '{ID}-GOAL-DRAFT.md', NULL, NULL, NULL, 2, 1, 'callback', 0, 0, NULL, NULL, NULL, NULL, 'SUPERVISOR_PLANNING.md', NULL, NULL, 0),
    ('1010-02-ELOOP', 'decomposer-implementer', '1010-execution-decomposer', '1010-implementer', '1010/handoffs', '{ID}-handoff.md', NULL, NULL, NULL, 1, 1, 'handoff', 0, 1, NULL, NULL, NULL, NULL, 'EXECUTION_DECOMPOSER.md', NULL, NULL, 0),
    ('1010-02-ELOOP', 'implementer-reviewer', '1010-implementer', '1010-reviewer', '1010/results', '{ID}-result.md', 'gate-test-impact', NULL, NULL, 2, 1, 'callback', 0, 1, NULL, NULL, NULL, NULL, 'IMPLEMENTOR.md', NULL, NULL, 1),
    ('1010-02-ELOOP', 'reviewer-decomposer', '1010-reviewer', '1010-execution-decomposer', '1010/verdicts', '{ID}-verdict.md', NULL, NULL, NULL, 3, 1, 'agent_delivery', 0, 1, NULL, NULL, NULL, NULL, 'REVIEW.md', NULL, NULL, 0);

INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES
    ('strict_review', 1),
    ('cloud_llm', 1),
    ('cloud_pay', 1),
    ('1010-01-PLOOP', 1),
    ('1010-02-ELOOP', 1);
