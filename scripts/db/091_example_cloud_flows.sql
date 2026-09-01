-- 091: Shipped example flows — example-cloud, example-01-PLOOP, example-02-ELOOP.
--
-- PLAN-example-flows.md (Human-approved 2026-09-01). Purpose: a fresh
-- git clone on any PC gets a working, cloud-only flow catalogue out of
-- the box — one flow demonstrating the 1-flow principle (a closed
-- supervisor -> implementer -> reviewer chain, the preferred_cloud
-- shape from 028) and a pair demonstrating the 2-flow PLOOP/ELOOP
-- principle (shared artifact root, split authority, the 074/090 shape).
-- databases/dpmtf.db is no longer committed (2026-09-01), so migrations
-- are the only channel by which a fresh database gets flows; these
-- three are deliberately the entire catalogue a new install sees.
--
-- Human decisions (PLAN §6, 2026-09-01):
--   ui_category='standard'  — examples render in the main Flows panel;
--     onboarding discoverability outweighs daily-panel quiet.
--   Model/harness combo: cloud_minimax + opencode on EVERY role — the
--     alias ships in model-allocator's models.example.yaml, so a single
--     MINIMAX_API_KEY env var is the only credential a fresh install
--     needs. The model-allocator side of the contract (roles.example.yaml
--     keys for all eight roles below) lands in model-allocator in the
--     same change set.
--
-- Portability rules (PLAN §3): target_project_path is NULL and every
-- role runs workdir_mode='father', so no external repos are required;
-- deliverable_dir is relative (resolved under config.get_bridge_dir(),
-- default <project root>/flows); governance templates are the SHARED
-- generics — never copies (090 rule); no literal machine paths anywhere
-- in this file. Role keys are distinct from every other flow
-- (100_BRIDGE Security Rule 7). The 'human' role is seeded by
-- init_db.py; the gate scripts referenced by the steps are seeded by
-- migrations 060 (gate-deliverable-evidence) and 085 (gate-test-impact).
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

-- Fresh-install defect fixed in passing: gate-deliverable-evidence was
-- registered in bridge_scripts by hand on 2026-08-05 and never seeded by
-- any migration, so a fresh database lacked the row while 028, 055 and
-- this file all reference it (the script file itself,
-- scripts/bridgeV002/gate-deliverable-evidence.py, ships in the repo).
-- Registered here the way 085 registers gate-test-impact; values mirror
-- the live row.
INSERT OR IGNORE INTO bridge_scripts
    (script_key, name, description, path, stage, params_required, is_active)
VALUES
    ('gate-deliverable-evidence',
     'Deliverable Evidence Gate',
     'Blocks a result or verdict whose claimed file changes are absent from the working tree, and a verdict with no Evidence section. Deterministic — does not depend on a model telling the truth.',
     'scripts/bridgeV002/gate-deliverable-evidence.py',
     'pre',
     '--deliverable-file,--deliverable-dir,--deliverable-pattern,--handoff-id,--flow-key,--from-role,--to-role,--bridge-dir',
     1);

-- supervisor_role is set explicitly on every flow: the NULL fallback
-- routes stall wakeups to 'supervisor_auto', which a fresh database
-- does not carry — the examples must be self-contained.
INSERT OR IGNORE INTO bridge_flows
    (flow_key, name, description, artifact_root, target_project_path,
     is_active, auto_complete_enabled, ui_category, supervisor_role)
VALUES
    ('example-cloud', 'Example: cloud chain (1-flow)',
     'Shipped example of the 1-flow principle: one closed supervisor -> implementer -> reviewer chain on hosted models. Cloud-only, no local GPU; runs against this repo (workdir=father).',
     NULL, NULL, 1, 0, 'standard', 'ex-super-cl'),
    ('example-01-PLOOP', 'Example: Planning Loop (2-flow)',
     'Shipped example of the 2-flow principle: Human <-> planning supervisor dialogue that owns Run IDs and GOAL-DRAFTs. Shares artifact root ''example'' with the ELOOP; writes only under example/planning and example/goals.',
     'example', NULL, 1, 0, 'standard', 'example-planning-supervisor'),
    ('example-02-ELOOP', 'Example: Execution Loop (2-flow)',
     'Shipped example of the 2-flow principle: decomposer -> implementer -> reviewer execution chain owning handoffs, results and verdicts. Shares artifact root ''example'' with the PLOOP.',
     'example', NULL, 1, 0, 'standard', 'example-escalation-supervisor');

-- Roles. One combo everywhere (PLAN §6.2): model-allocator resolves
-- cloud_minimax, OpenCode is the interface. fresh_session_command='/new'
-- is the OpenCode fresh-context convention used by every live OpenCode
-- role. workdir_mode='father' throughout — the examples exercise the
-- machinery against this repo, so a fresh install needs nothing else.
INSERT OR IGNORE INTO bridge_roles
    (role_key, tmux_session, role_type, is_active,
     default_model_source, default_model_alias, allocator_client,
     default_harness_source, default_harness_profile,
     workdir_mode, governance_file, config_dir, fresh_session_command)
VALUES
    ('ex-super-cl', 'ex-super-cl', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', '500_SUPERVISOR.md', NULL, '/new'),
    ('ex-imple-cl', 'ex-imple-cl', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', 'IMPLEMENTOR.md', NULL, '/new'),
    ('ex-review-cl', 'ex-review-cl', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', 'REVIEW.md', NULL, '/new'),
    ('example-planning-supervisor', 'example-planning-supervisor', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', '500_SUPERVISOR.md', NULL, '/new'),
    ('example-execution-decomposer', 'example-execution-decomposer', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', 'EXECUTION_DECOMPOSER.md', NULL, '/new'),
    ('example-implementer', 'example-implementer', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', 'IMPLEMENTOR.md', NULL, '/new'),
    ('example-reviewer', 'example-reviewer', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', 'REVIEW.md', NULL, '/new'),
    ('example-escalation-supervisor', 'example-escalation-supervisor', 'agent', 1,
     'model_allocator', 'cloud_minimax', 'opencode',
     'opencode', NULL,
     'father', 'SUPERVISOR_ESCALATION.md', NULL, '/new');

-- example-cloud steps: the 028 shape. The evidence gate runs before the
-- two deliverable-carrying callbacks — it compares the claims in a
-- result or verdict against the working tree.
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, rule_key, sort_order, is_active,
     auto_chain_to_next, validation_required, pre_dispatch_script,
     governance_file)
VALUES
    ('example-cloud', 'supervisor-imple', 'ex-super-cl', 'ex-imple-cl',
     'example-cloud/handoffs', '{ID}-handoff.md', 'handoff',
     1, 1, 1, 1, NULL, '500_SUPERVISOR.md'),
    ('example-cloud', 'imple-review', 'ex-imple-cl', 'ex-review-cl',
     'example-cloud/results', '{ID}-result.md', 'callback',
     2, 1, 1, 1, 'gate-deliverable-evidence', 'IMPLEMENTOR.md'),
    ('example-cloud', 'review-supervisor', 'ex-review-cl', 'ex-super-cl',
     'example-cloud/verdicts', '{ID}-verdict.md', 'agent_delivery',
     3, 1, 1, 1, 'gate-deliverable-evidence', 'REVIEW.md');

-- PLOOP: Human <-> planning supervisor dialogue (the 090 live shape).
-- Steps write ONLY under example/planning and example/goals — a
-- deliberate non-handoffs directory, so the planning flow cannot
-- allocate an implementation handoff filename even by accident.
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file)
VALUES
    ('example-01-PLOOP', 'human-planning',
     'human', 'example-planning-supervisor',
     'example/planning', '{ID}-request.md', 1, 1, 'handoff', 0, 0, 'HUMAN.md'),
    ('example-01-PLOOP', 'planning-human',
     'example-planning-supervisor', 'human',
     'example/goals', '{ID}-GOAL-DRAFT.md', 2, 1, 'callback', 0, 0,
     '500_SUPERVISOR.md');

-- ELOOP: decomposer -> implementer -> reviewer -> decomposer, mirroring
-- 090's live shape (gate-test-impact + README impact on the result step).
INSERT OR IGNORE INTO bridge_flow_steps
    (flow_key, step_key, from_role, to_role, deliverable_dir,
     deliverable_pattern, sort_order, is_active, rule_key,
     auto_chain_to_next, validation_required, governance_file,
     pre_dispatch_script, requires_readme_impact)
VALUES
    ('example-02-ELOOP', 'decomposer-implementer',
     'example-execution-decomposer', 'example-implementer',
     'example/handoffs', '{ID}-handoff.md', 1, 1, 'handoff', 0, 1,
     'EXECUTION_DECOMPOSER.md', NULL, 0),
    ('example-02-ELOOP', 'implementer-reviewer',
     'example-implementer', 'example-reviewer',
     'example/results', '{ID}-result.md', 2, 1, 'callback', 0, 1,
     'IMPLEMENTOR.md', 'gate-test-impact', 1),
    ('example-02-ELOOP', 'reviewer-decomposer',
     'example-reviewer', 'example-execution-decomposer',
     'example/verdicts', '{ID}-verdict.md', 3, 1, 'agent_delivery', 0, 1,
     'REVIEW.md', NULL, 0);

-- Flow counters (bridge_lib self-heals a missing row, but explicit is clear).
INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id)
VALUES
    ('example-cloud', 1),
    ('example-01-PLOOP', 1),
    ('example-02-ELOOP', 1);
