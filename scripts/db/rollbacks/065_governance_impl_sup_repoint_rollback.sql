-- Rollback for migration 065: governance implementor + supervisor repoint.
--
-- Reverses 065_governance_impl_sup_repoint.sql. Scoped to exactly the
-- rows the migration touched:
--   bridge_flow_steps: governance_file IN the two new generic names AND
--     from_role in the same eleven labels the migration listed (eight
--     IDLE implementor labels + three autonomous-supervisor labels).
--   bridge_flows: supervisor_role IN the five seeded values AND flow_key
--     in the same five flow_keys the migration listed.
-- A blanket governance_file match is intentionally avoided -- future
-- handoffs may repoint other steps to the same generic files, and a
-- blanket rollback would clobber their rows. The supervisor_role
-- rollback likewise scopes to the five flows and five roles the
-- migration listed (a blanket flow_key match would clobber any future
-- supervisor_role seeding).
--
-- Sets governance_file back to NULL so the resolver falls through to the
-- role-level fallback (bridge_roles.governance_file, still pointing at
-- the thirteen absorbed originals) -- i.e., post-rollback behavior is
-- identical to the pre-065 state. supervisor_role is set back to NULL
-- so chain_watchdog's _supervisor_wake_up falls back to the
-- supervisor_auto session (pre-061 / pre-065 behavior).
--
-- After clearing the columns, remove the schema_migrations row that
-- migrate.py wrote, so a subsequent `python3 scripts/migrate.py`
-- re-applies 065 cleanly. Mirrors the comment style of
-- rollbacks/064_governance_review_repoint_rollback.sql.
--
-- Do NOT apply this rollback in the normal handoff flow; it is for
-- emergency revert only. The D7 handoff (049) writes the tests that
-- verify this rollback's correctness.

UPDATE bridge_flow_steps
   SET governance_file = NULL
 WHERE governance_file IN ('IMPLEMENTOR.md', 'SUPERVISOR_AUTONOMOUS.md')
   AND from_role IN ('imple01', 'imple01cloud', 'imple01pay', 'imple01sup',
                     'pi_imple01', 'oc_imple01', 'imple01SG', 'Rev_Imple',
                     'supervisor_auto', 'supervisor01_llama', 'Rev_Supervisor');

UPDATE bridge_flows
   SET supervisor_role = NULL
 WHERE flow_key IN ('supervised_review', 'llama_SG', 'reveng',
                    'preferred_cloud', 'preferred_cloud_harness')
   AND supervisor_role IN ('supervisor_auto', 'supervisor01_llama',
                           'Rev_Supervisor', 'Pre-super-cl',
                           'super-deep-deep4');

DELETE FROM schema_migrations WHERE filename = '065_governance_impl_sup_repoint.sql';
