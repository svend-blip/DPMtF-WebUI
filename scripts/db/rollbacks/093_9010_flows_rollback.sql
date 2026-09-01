-- Rollback for 093: remove the 9010 flows, their roles, steps and
-- counters.
--
-- Exact inverse of the forward migration. WHERE clauses match ONLY the
-- keys 093 seeds, so every other flow and role is untouched and
-- re-running after rollback is a no-op (matches the idempotent
-- forward). Governance files and the gate script registrations are
-- untouched — 093 seeds neither.

DELETE FROM bridge_flow_steps
WHERE flow_key IN ('9010-01-PLOOP', '9010-02-ELOOP');

DELETE FROM bridge_id_counters
WHERE flow_key IN ('9010-01-PLOOP', '9010-02-ELOOP');

DELETE FROM bridge_flows
WHERE flow_key IN ('9010-01-PLOOP', '9010-02-ELOOP');

DELETE FROM bridge_roles
WHERE role_key IN
    ('9010-planning-supervisor', '9010-execution-decomposer',
     '9010-implementer', '9010-reviewer', '9010-escalation-supervisor');
