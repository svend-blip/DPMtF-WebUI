-- Rollback for 097: return the planning supervisors to their pre-097
-- bindings.
--
-- Exact inverse of the forward migration, statement for statement:
--   governance_file        -> 500_SUPERVISOR.md on the same predicates
--                             (only rows 097 moved, i.e. those now on
--                             SUPERVISOR_PLANNING.md);
--   supervisor_role        -> NULL on the six 1000/1010/9000 rows and
--                             back to '9010-escalation-supervisor' on
--                             9010-02-ELOOP (093's seed). 9010-01-PLOOP
--                             was not touched forward and is not here;
--   fresh_session_command  -> '/clear' on the four claude-code planning
--                             supervisors (082's value);
--   cold_start_skill       -> NULL on 9000-01-PLOOP;
--   schema_migrations      -> the 097 ledger row removed so the runner
--                             re-applies the forward file on demand.
--
-- The example-* rows' supervisor_role and the example-planning-
-- supervisor's fresh_session_command were not changed forward and are
-- not changed here. Re-running after rollback is a no-op.

UPDATE bridge_roles
   SET governance_file = '500_SUPERVISOR.md',
       updated_at      = datetime('now')
 WHERE role_key LIKE '%-planning-supervisor'
   AND governance_file = 'SUPERVISOR_PLANNING.md';

UPDATE bridge_flow_steps
   SET governance_file = '500_SUPERVISOR.md'
 WHERE step_key = 'planning-human'
   AND governance_file = 'SUPERVISOR_PLANNING.md';

UPDATE bridge_flows
   SET supervisor_role = NULL,
       updated_at      = datetime('now')
 WHERE flow_key IN ('1000-01-PLOOP', '1000-02-ELOOP',
                    '1010-01-PLOOP', '1010-02-ELOOP',
                    '9000-01-PLOOP', '9000-02-ELOOP');

UPDATE bridge_flows
   SET supervisor_role = '9010-escalation-supervisor',
       updated_at      = datetime('now')
 WHERE flow_key = '9010-02-ELOOP';

UPDATE bridge_roles
   SET fresh_session_command = '/clear',
       updated_at            = datetime('now')
 WHERE role_key IN ('1000-planning-supervisor',
                    '1010-planning-supervisor',
                    '9000-planning-supervisor',
                    '9010-planning-supervisor');

UPDATE bridge_flows
   SET cold_start_skill = NULL,
       updated_at       = datetime('now')
 WHERE flow_key = '9000-01-PLOOP';

DELETE FROM schema_migrations
 WHERE filename = '097_supervisor_planning_rebind.sql';
