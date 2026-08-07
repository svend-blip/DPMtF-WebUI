-- 033: The step that gets a handoff INTO the lightworker chain.
--
-- 031 defined imple01LW -> review01LW and review01LW -> human, which is the
-- chain once it is moving. Nothing delivers to imple01LW, so
-- `--signal-send --to-role imple01LW` fails with "No step matching
-- human->imple01LW" and the flow cannot be started at all.
--
-- Every other flow hides this because its first role receives from a
-- supervisor or an architect that is itself a role. Here the implementer IS
-- the first role, so the sender is the Human — the same shape trade_cockpit
-- uses for its human-originated steps.
--
-- sort_order 0 puts it ahead of the two 031 defined. The deliverable is the
-- compiled handoff, which dispatch reads to build the §13 envelope: for a
-- role with an execution_target, this step's deliverable becomes
-- envelope.handoff.content rather than a tmux injection.

INSERT INTO bridge_flow_steps (
    flow_key, step_key, from_role, to_role, deliverable_dir,
    deliverable_pattern, sort_order, is_active, validation_required
)
SELECT
    'lightworker', 'human-imple01LW', 'human', 'imple01LW',
    'lightworker/handoffs', '{ID}-handoff.md', 0, 1, 1
WHERE NOT EXISTS (
    SELECT 1 FROM bridge_flow_steps
     WHERE flow_key = 'lightworker' AND step_key = 'human-imple01LW'
);
