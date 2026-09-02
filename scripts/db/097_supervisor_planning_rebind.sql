-- 097: Bind the planning supervisors to SUPERVISOR_PLANNING.md and make
--      every PLOOP/ELOOP family reach its resident planning supervisor.
--
-- The planning supervisors of the two-flow families — 1000, 1010, 9000,
-- 9010 and the shipped example- pair — were bound to 500_SUPERVISOR.md
-- (role-level via bridge_roles.governance_file AND step-level on the
-- planning-human callback step). 500_SUPERVISOR.md describes the
-- conversational `supervisor` flow: a one-flow role that receives a
-- Human request and hands work to an implementer. That is not what a
-- planning supervisor is. SUPERVISOR_PLANNING.md is the file that
-- describes the RESIDENT planning supervisor of a PLOOP/ELOOP family:
-- a session that stays up across the whole run, drafts GOALs for the
-- Human, and is the wake-up target when the ELOOP stalls.
--
-- Three consequences, each a statement below:
--
-- 1. governance_file -> SUPERVISOR_PLANNING.md on every
--    '%-planning-supervisor' role and every 'planning-human' step
--    that still points at 500_SUPERVISOR.md. The predicate is the
--    file name, not a list of families, so a family added later on
--    the old binding is caught by a re-run; the `supervisor` flow and
--    the example-cloud one-flow example keep 500_SUPERVISOR.md — it
--    is the right file for them.
--
-- 2. bridge_flows.supervisor_role = '<family>-planning-supervisor' on
--    BOTH rows of each family (PLOOP and ELOOP). 103_FLOW_STARTUP
--    Binding Rule 6: the watchdog's stall escalation
--    (chain_watchdog._supervisor_wake_up) and the scheduler's stall
--    wake-up read THIS column to find the session to wake. The ELOOP
--    is where stalls happen, and the session that can decide is the
--    resident planning supervisor — not the per-wakeup escalation
--    supervisor, which is one-shot and holds no session. 9010-02-ELOOP
--    was seeded with '9010-escalation-supervisor' (093); 1000/1010/9000
--    were NULL, which falls back to supervisor_auto — a role fresh
--    databases do not carry. 9010-01-PLOOP already carries the right
--    value and is not touched. The 1010 rows exist only in the live
--    database (created through the WebUI, never migrated — see 090);
--    on a fresh database their UPDATEs match nothing, by design.
--
-- 3. fresh_session_command = NULL on the four claude-code planning
--    supervisors (1000/1010/9000/9010). chain_watchdog.py (~L574-578)
--    and scripts/job_queue/scheduler.py (~L846-877) pass the role's
--    fresh_session_command straight to inject_prompt on a stall
--    wake-up. For these roles it was '/clear' (082): a machine wake-up
--    would wipe the resident session's context — the GOAL it drafted,
--    the Human dialogue, the run it is supervising — before asking it
--    to diagnose. The example-planning-supervisor runs opencode
--    ('/new') and is left alone here; its Human-facing reset is a
--    separate decision.
--
-- Also: cold_start_skill = '9000' on 9000-01-PLOOP (094 added the
-- column; the live 9000-02-ELOOP row carries it, the PLOOP row did
-- not). Guarded so a value set through the UI is never overwritten.
--
-- Idempotent: every UPDATE is predicated on the pre-migration value or
-- on a key whose target value is a fixed point, so a re-run changes
-- nothing. updated_at is bumped the way 080/081/082 do.
--
-- Rollback: rollbacks/097_supervisor_planning_rebind_rollback.sql

-- 1. Governance rebinding, role level.
UPDATE bridge_roles
   SET governance_file = 'SUPERVISOR_PLANNING.md',
       updated_at      = datetime('now')
 WHERE role_key LIKE '%-planning-supervisor'
   AND governance_file = '500_SUPERVISOR.md';

-- 1. Governance rebinding, step level (the planning-human callback).
UPDATE bridge_flow_steps
   SET governance_file = 'SUPERVISOR_PLANNING.md'
 WHERE step_key = 'planning-human'
   AND governance_file = '500_SUPERVISOR.md';

-- 2. Stall wake-up target: the resident planning supervisor, on both
--    rows of each family.
UPDATE bridge_flows
   SET supervisor_role = '1000-planning-supervisor',
       updated_at      = datetime('now')
 WHERE flow_key IN ('1000-01-PLOOP', '1000-02-ELOOP');

UPDATE bridge_flows
   SET supervisor_role = '1010-planning-supervisor',
       updated_at      = datetime('now')
 WHERE flow_key IN ('1010-01-PLOOP', '1010-02-ELOOP');

UPDATE bridge_flows
   SET supervisor_role = '9000-planning-supervisor',
       updated_at      = datetime('now')
 WHERE flow_key IN ('9000-01-PLOOP', '9000-02-ELOOP');

UPDATE bridge_flows
   SET supervisor_role = '9010-planning-supervisor',
       updated_at      = datetime('now')
 WHERE flow_key = '9010-02-ELOOP';

-- 3. A machine wake-up must not /clear a resident session.
UPDATE bridge_roles
   SET fresh_session_command = NULL,
       updated_at            = datetime('now')
 WHERE role_key IN ('1000-planning-supervisor',
                    '1010-planning-supervisor',
                    '9000-planning-supervisor',
                    '9010-planning-supervisor');

-- Cold-start skill on the 9000 PLOOP row (094 column), UI value wins.
UPDATE bridge_flows
   SET cold_start_skill = '9000',
       updated_at       = datetime('now')
 WHERE flow_key = '9000-01-PLOOP'
   AND (cold_start_skill IS NULL OR cold_start_skill = '');
