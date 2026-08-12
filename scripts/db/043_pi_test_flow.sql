-- 043: `pi_test` — a two-step flow for measuring Pi as a code frontend.
--
-- WHAT THIS IS FOR. Pi (@earendil-works/pi-coding-agent) joins Claude Code
-- and OpenCode as a third frontend. It is a frontend only: which model runs,
-- and whether its server is up, stays owned by model-allocator. This flow
-- exists to answer one question with evidence instead of impression — does
-- the same model behave differently under a different client?
--
-- THE COMPARISON IS CONTROLLED, AND THAT IS THE ENTIRE DESIGN.
--
--   pi_imple01   cloud_minimax · 452_SUPERVISED_REVIEW_IMPLE01.md · pi
--   imple01sup   cloud_minimax · 452_SUPERVISED_REVIEW_IMPLE01.md · opencode
--
-- Same alias, same model, same runtime, same governance file, same kind of
-- handoff. The only difference is the client. Anything that shows up in one
-- and not the other is attributable to the frontend, which is not true of
-- any comparison this project has been able to make until now.
--
-- WHY IT IS WORTH MEASURING. OpenCode driving MiniMax-M3 returned a textual
-- imitation of a tool call instead of a structured one — five of seven
-- completed turns on 2026-08-12, ending each turn with finish "stop", no
-- tool run, no deliverable and no error anywhere. The same behaviour is
-- documented upstream for MiniMax-M2.7, so the cause could be the model, the
-- harness, or the pair. Pi reaches MiniMax through its own built-in provider
-- rather than a generic openai-compatible block, so it is a real second
-- reading rather than the same code path twice.
--
-- A first manual probe on 2026-08-12 is encouraging but is one trial, not a
-- result: Pi/MiniMax ran a python3 heredoc through bash, wrote a file with
-- the write tool and verified it with cat — the exact multi-tool shape that
-- leaked under OpenCode. This flow is how that gets repeated enough times to
-- mean something.
--
-- RUNNING THE OTHER ARM. Dispatch the same handoff text to imple01sup in
-- supervised_review. Do NOT flip pi_imple01's allocator_client back and
-- forth to do it: the two arms must be separately observable afterwards, and
-- a role whose client changed mid-comparison cannot be read from the trace.
--
-- SCOPE. Two steps, human at both ends, because a comparison needs a person
-- to read both results. No supervisor, no auto-chaining: this measures a
-- worker, not a chain.
--
-- Target project is the allocator repo, which is a real codebase the role
-- can be given real work in without touching a live run's evidence.
--
-- Idempotent: INSERT OR IGNORE throughout; re-running changes nothing.

INSERT OR IGNORE INTO bridge_flows (flow_key, name, description, target_project_path, is_active)
VALUES (
    'pi_test',
    'Pi Frontend Test',
    'Single-worker flow for measuring the Pi code frontend against OpenCode on an identical model, runtime and governance file.',
    '/home/svend/model-allocator',
    1
);

INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES ('pi_test', 1);

-- Governance is deliberately 452, the same file imple01sup runs under.
-- Giving Pi its own contract would make the comparison measure two things.
INSERT OR IGNORE INTO bridge_roles (
    role_key, tmux_session, is_active, restart_policy, governance_file,
    role_type, enter_command, config_dir, default_model_source,
    default_model_alias, allocator_client, fresh_session_command,
    workdir_mode, execution_target
) VALUES (
    'pi_imple01', 'pi_imple01', 1, 'none', '452_SUPERVISED_REVIEW_IMPLE01.md',
    'agent', 'default', 'pi_imple01', 'model_allocator',
    'cloud_minimax', 'pi', '/new',
    'target_project', NULL
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'pi_test', 'human-pi_imple01', 'human', 'pi_imple01',
    'pi_test/handoffs', '{ID}-handoff.md', 'handoff', 1, 1, 0, 1
);

INSERT OR IGNORE INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, rule_key, sort_order, is_active,
    auto_chain_to_next, validation_required
) VALUES (
    'pi_test', 'pi_imple01-human', 'pi_imple01', 'human',
    'pi_test/results', '{ID}-result.md', 'callback', 2, 1, 0, 1
);
