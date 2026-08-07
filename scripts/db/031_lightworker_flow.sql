-- 031: The `lightworker` flow — one role on svend3060, one on Father.
--
-- The first flow where a role does not run on this machine. Two roles is the
-- smallest thing that proves §41: an implementer executing remotely, and a
-- reviewer here to judge what came back. A supervisor can be added once the
-- two-step chain has run.
--
-- ROLE NAMES. `imple01` and `review01` already exist and belong to
-- strict_review. The suffix follows the house convention — imple01SG,
-- imple01cloud, imple01pay — and the names must be unique for a second
-- reason: the worker's Model Allocator resolves `--role <target_role>`
-- against its own roles.yaml, so the key there must match role_key here
-- exactly. `model-allocator run` has no --alias form (preferred_cloud run
-- 002, §43 Phase 0), which is why the mirroring exists at all.
--
-- TARGET PROJECT. DPMtF-LightWorker, chosen because it is the only repository
-- the worker is MEASURED to be able to clone: `git ls-remote` over HTTPS
-- succeeds there from svend3060, while SSH to GitHub does not. Its origin is
-- a read-only URL, which is what §16.2 asks for, and the worker builds a
-- disposable worktree from it rather than touching the checkout. One column
-- to change if a different project is wanted.
--
-- MODEL. imple01LW carries `imple01-3060` — an alias the WORKER can resolve,
-- not one of Father's. This is the trap the envelope builder exposed: a
-- worker-routed role sending Father's own alias would have the worker fail on
-- a name it has never heard. Measured on the card: qwen2.5-coder 14B at 8k
-- context, 10 GB, 100% GPU. 16k spills 12% to CPU and 32k spills 30%.
--
-- review01LW runs on Father with the usual local setup.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows (flow_key, description, target_project_path, is_active)
VALUES (
    'lightworker',
    'Remote execution on svend3060 with review on Father (GOAL.md §41)',
    '/home/svend/DPMtF-LightWorker',
    1
);

-- The implementer executes elsewhere. execution_target is what routes it:
-- dispatch offers a §13 envelope instead of injecting into tmux, and there is
-- no session on this host for it to inject into.
INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'imple01LW', 'imple01LW', 1, 'none', '481_LIGHTWORKER_IMPLE01LW.md',
    'agent', 'default', 'model_allocator', 'imple01-3060',
    'opencode', '/clear', 'target_project', 'svend3060'
);

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, default_model_source, default_model_alias,
    allocator_client, fresh_session_command, workdir_mode, execution_target
) VALUES (
    'review01LW', 'review01LW', 1, 'none', '482_LIGHTWORKER_REVIEW01LW.md',
    'agent', 'default', 'model_allocator', 'sonnet5',
    'claude-code', '/clear', 'target_project', NULL
);

-- Deliverable dirs are flow-relative, resolved against the bridge root at
-- runtime — the convention migration 027 established. Never absolute.
INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, sort_order, is_active, validation_required
) VALUES (
    'lightworker', 'imple01LW-review01LW', 'imple01LW', 'review01LW',
    'lightworker/results', '{ID}-result.md', 1, 1, 1
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, sort_order, is_active, validation_required
) VALUES (
    'lightworker', 'review01LW-human', 'review01LW', 'human',
    'lightworker/verdicts', '{ID}-verdict.md', 2, 1, 1
);

INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES ('lightworker', 1);
