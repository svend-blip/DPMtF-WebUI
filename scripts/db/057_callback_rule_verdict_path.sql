-- 057: the callback convention rule told reviewers the wrong verdict path.
--
-- Found by Pre-review-cl in preferred_cloud run 034, handoff 102 (2026-08-19),
-- and confirmed by the supervisor. The dispatch envelope its reviewer received
-- named two different destinations for the same file:
--
--   <deliverable_output>
--     verdict: {bridge_dir}/{flow_key}/reviews/{handoff_id}-review-verdict.md
--
-- while bridge_flow_steps for the next step (review01-supervisor) says
-- preferred_cloud/verdicts + {ID}-verdict.md, and governance 473 says the same
-- and adds why it matters: "That exact filename. A verdict written as anything
-- else is invisible to dispatch." (473:105-108)
--
-- That reviewer followed governance over the envelope and the chain worked. A
-- reviewer that trusts the envelope writes its verdict where dispatch does not
-- look, reports success, and the run stalls with nobody aware — the failure is
-- silent on both sides.
--
-- The 'callback' rule is the imple01->review01 step of every supervisor-shaped
-- flow, and all four of them agree on the destination:
--
--   llama_SG                 review01-supervisor  -> llama_SG/verdicts/{ID}-verdict.md
--   preferred_cloud          review01-supervisor  -> preferred_cloud/verdicts/{ID}-verdict.md
--   preferred_cloud_harness  review01-supervisor  -> preferred_cloud_harness/verdicts/{ID}-verdict.md
--   reveng                   review-supervisor    -> reveng/verdicts/{ID}-verdict.md
--
-- pi_test also uses 'callback', for two implementer->human steps with no
-- verdict step after them; the corrected path is inert there rather than wrong.
--
-- The 'reviews/{ID}-review01.md' shape is NOT a mistake in general — it is the
-- real deliverable of the two-stage review flows (strict_review, cloud_llm,
-- cloud_pay, supervised_review), which reach it through the 'technical_review'
-- and 'verdict' rules. Only 'callback' carried it wrongly, as a leftover from
-- that shape. The 'verdict' rule's own template is already correct and is not
-- touched here.
--
-- Observed while fixing this and deliberately NOT changed, because it is a
-- different question and this migration should stay the size of the defect it
-- repairs: the same template's "commit_msg (if APPROVED)" line points at
-- {flow_key}/verdicts/{ID}-commit-message.md, which is a real deliverable in
-- the strict_review / cloud_llm family but is named by none of the four
-- supervisor flows' governance files. The directory is correct, the line is
-- conditional, and it misdirects nobody — it may simply be unnecessary here.
--
-- Idempotent: the WHERE clause matches only the unfixed text, so re-running
-- this migration is a no-op.

UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '{bridge_dir}/{flow_key}/reviews/{handoff_id}-review-verdict.md',
        '{bridge_dir}/{flow_key}/verdicts/{handoff_id}-verdict.md'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'callback'
  AND content_template LIKE '%/reviews/{handoff_id}-review-verdict.md%';
