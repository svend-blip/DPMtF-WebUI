-- 101 — Callback <stop> must not forbid the reviewer's evidence-gathering.
--
-- The callback content_template (result->reviewer dispatch, every flow) carried
-- "<stop> ... do not read the repository; at most 6 tool calls </stop>". Reviewers
-- that obeyed it skipped git status/diff and the closing test measure, producing
-- invalid verdicts (verdict 115 on run 060 did exactly this; 114 overrode it —
-- non-deterministic, chain-wide). Rewrite the clause so it keeps the focus/cost
-- intent while explicitly allowing the evidence a role's Evidence Rules require.
UPDATE bridge_convention_rules
SET content_template = REPLACE(
        content_template,
        'you have every fact you need; do not read the repository; at most 6 tool calls',
        'you have every fact you need; do not read the repository beyond what your role''s Evidence Rules require, and keep tool calls to the minimum those rules need'
    )
WHERE content_template LIKE '%do not read the repository; at most 6 tool calls%';
