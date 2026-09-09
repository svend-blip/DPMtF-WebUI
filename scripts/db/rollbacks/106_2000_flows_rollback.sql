-- Rollback: 2000_flows (migration 106)
-- Remove the 2000 flow family.
DELETE FROM bridge_flow_steps WHERE flow_key IN ('2000-01-PLOOP', '2000-02-ELOOP');
DELETE FROM bridge_flows WHERE flow_key IN ('2000-01-PLOOP', '2000-02-ELOOP');
DELETE FROM bridge_roles WHERE role_key IN
    ('2000-planning-supervisor', '2000-execution-decomposer',
     '2000-implementer', '2000-reviewer');
