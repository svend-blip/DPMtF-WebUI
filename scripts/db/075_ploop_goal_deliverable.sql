-- 075: PLOOP's callback deliverable becomes the GOAL draft (hybrid channel).
--
-- Human decision 2026-08-26: the planning supervisor delivers the Run
-- contract draft as an ORDINARY step deliverable — 1000/goals/{ID}-GOAL-DRAFT.md
-- — and the deliverable's id becomes the Run id, so spec §5's "only PLOOP
-- allocates Run IDs" is enforced by the flow's own id counter rather than by
-- convention. Promotion (host-side promote-goal, with the parse gate) moves
-- an approved draft to runs/NNN/GOAL.md; GOAL.md itself still has no
-- dispatch path. Discarded drafts leave gaps in the run numbering, which
-- rule 6 already declares normal.
--
-- Idempotent: a plain UPDATE keyed on the seeded values; re-running matches
-- zero rows the second time or rewrites identical values.
UPDATE bridge_flow_steps
SET deliverable_dir = '1000/goals',
    deliverable_pattern = '{ID}-GOAL-DRAFT.md'
WHERE flow_key = '1000-01-PLOOP'
  AND step_key = 'planning-human';
