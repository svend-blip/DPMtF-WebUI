-- 044: give pi_test its own OpenCode arm, so the comparison runs in one flow.
--
-- 043 assumed the OpenCode side of the comparison could be run by dispatching
-- the same handoff to imple01sup in supervised_review. That is wrong for two
-- reasons found when it was first attempted, on 2026-08-12:
--
--   * supervised_review's imple01-review01 step has auto_chain_to_next = 1,
--     so the implementer's signal immediately dispatches review01sup.
--   * review01sup runs review01-local, a local Ollama model.
--
-- Together those mean measuring the OpenCode arm would start a second local
-- model on a GPU that was at 31.3 GB of 32.6 GB, held by a live reveng run.
-- A comparison is not worth putting a running chain at risk, and the reading
-- would have been polluted by two reviewers' work anyway.
--
-- oc_imple01 is pi_imple01's twin in every respect that could affect the
-- result:
--
--   pi_imple01   cloud_minimax · 452_SUPERVISED_REVIEW_IMPLE01.md · pi
--   oc_imple01   cloud_minimax · 452_SUPERVISED_REVIEW_IMPLE01.md · opencode
--
-- Same alias, same model, same governance file, same target project, same
-- workdir_mode, human at both ends, no auto-chaining and no reviewers. The
-- only difference is allocator_client, which is the variable under test.
--
-- fresh_session_command differs, and must: /new for OpenCode and Pi both
-- start a genuinely new session, which is what makes each measurement
-- independent of the last. That is a property of the client, not a
-- confound — a comparison where one arm inherits the previous run's context
-- and the other does not would measure nothing.
--
-- The two arms are separate roles rather than one role whose client is
-- flipped between runs, deliberately: both must remain separately
-- observable in trace.log afterwards. A role whose client changed mid-
-- comparison cannot be read back.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, config_dir, default_model_source,
    default_model_alias, allocator_client, fresh_session_command,
    workdir_mode, execution_target
) VALUES (
    'oc_imple01', 'oc_imple01', 1, 'none', '452_SUPERVISED_REVIEW_IMPLE01.md',
    'agent', 'default', 'oc_imple01', 'model_allocator',
    'cloud_minimax', 'opencode', '/new',
    'target_project', NULL
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'pi_test', 'human-oc_imple01', 'human', 'oc_imple01',
    'pi_test/handoffs', '{ID}-handoff.md', 'handoff', 3, 1, 0, 1
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'pi_test', 'oc_imple01-human', 'oc_imple01', 'human',
    'pi_test/results', '{ID}-result.md', 'callback', 4, 1, 0, 1
);
