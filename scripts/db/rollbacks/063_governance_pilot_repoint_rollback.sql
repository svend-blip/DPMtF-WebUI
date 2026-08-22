-- Rollback for migration 063: governance pilot repoint.
--
-- Reverses 063_governance_pilot_repoint.sql. Scoped to exactly the rows the
-- migration touched: governance_file IN ('ARCHITECT.md', 'HUMAN.md') AND
-- from_role in the same six labels the migration listed. A blanket
-- governance_file match is intentionally avoided — future handoffs may
-- repoint other steps to the same generic files, and a blanket rollback
-- would clobber their rows.
--
-- Sets governance_file back to NULL so the resolver falls through to the
-- role-level fallback (bridge_roles.governance_file, still pointing at the
-- 4xx originals) — i.e., post-rollback behavior is identical to the
-- pre-063 state.
--
-- After clearing the column, remove the schema_migrations row that
-- migrate.py wrote, so a subsequent `python3 scripts/migrate.py` re-applies
-- 063 cleanly. Mirrors the comment style of
-- rollbacks/062_step_execution_config_rollback.sql.
--
-- Do NOT apply this rollback in the normal handoff flow; it is for
-- emergency revert only. The D4 handoff (038) writes the tests that verify
-- this rollback's correctness.

UPDATE bridge_flow_steps
   SET governance_file = NULL
 WHERE governance_file IN ('ARCHITECT.md', 'HUMAN.md')
   AND from_role IN ('archi01', 'archi01cloud', 'archi01pay',
                     'human', 'humancloud', 'humanpay');

DELETE FROM schema_migrations WHERE filename = '063_governance_pilot_repoint.sql';
