-- Rollback for migration 064: governance review repoint.
--
-- Reverses 064_governance_review_repoint.sql. Scoped to exactly the rows the
-- migration touched: governance_file IN the three new generic names AND
-- from_role in the same nine labels the migration listed. A blanket
-- governance_file match is intentionally avoided -- future handoffs may
-- repoint other steps to the same generic files, and a blanket rollback
-- would clobber their rows.
--
-- Sets governance_file back to NULL so the resolver falls through to the
-- role-level fallback (bridge_roles.governance_file, still pointing at the
-- eleven absorbed originals) -- i.e., post-rollback behavior is identical
-- to the pre-064 state.
--
-- After clearing the column, remove the schema_migrations row that
-- migrate.py wrote, so a subsequent `python3 scripts/migrate.py` re-applies
-- 064 cleanly. Mirrors the comment style of
-- rollbacks/063_governance_pilot_repoint_rollback.sql.
--
-- Do NOT apply this rollback in the normal handoff flow; it is for
-- emergency revert only. The D5 handoff (045) writes the tests that verify
-- this rollback's correctness.

UPDATE bridge_flow_steps
   SET governance_file = NULL
 WHERE governance_file IN ('TECHNICAL_REVIEW.md', 'GOVERNANCE_REVIEW.md', 'REVIEW.md')
   AND from_role IN ('review01', 'review01cloud', 'review01pay', 'review01sup',
                     'review02', 'review02cloud', 'review02pay', 'review02sup',
                     'review01SG');

DELETE FROM schema_migrations WHERE filename = '064_governance_review_repoint.sql';
