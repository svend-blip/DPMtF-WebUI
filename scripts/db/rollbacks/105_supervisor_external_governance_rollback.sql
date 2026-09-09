-- Rollback: supervisor_external_governance (migration 105)
-- Rebind the conversational `supervisor` role's governance from
-- EXTERNAL_SUPERVISOR.md back to 500_SUPERVISOR.md.

UPDATE bridge_roles
SET governance_file = '500_SUPERVISOR.md'
WHERE role_key = 'supervisor'
  AND governance_file = 'EXTERNAL_SUPERVISOR.md';
