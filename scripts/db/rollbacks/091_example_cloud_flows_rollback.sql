-- Rollback for 091: remove the shipped example flows, their roles,
-- steps and counters.
--
-- Exact inverse of the forward migration. WHERE clauses match ONLY the
-- keys 091 seeds, so live flows and roles are untouched and re-running
-- after rollback is a no-op (matches the idempotent forward).
--
-- Only for reverting 091 itself. Governance files are untouched — 091
-- seeds no files, it only references the shared generics.
--
-- The gate-deliverable-evidence bridge_scripts row is deliberately NOT
-- deleted: on databases older than 091 the row predates this migration
-- (hand-registered 2026-08-05) and is shared by the preferred_cloud and
-- preferred_cloud_harness flows.

DELETE FROM bridge_flow_steps
WHERE flow_key IN ('example-cloud', 'example-01-PLOOP', 'example-02-ELOOP');

DELETE FROM bridge_id_counters
WHERE flow_key IN ('example-cloud', 'example-01-PLOOP', 'example-02-ELOOP');

DELETE FROM bridge_flows
WHERE flow_key IN ('example-cloud', 'example-01-PLOOP', 'example-02-ELOOP');

DELETE FROM bridge_roles
WHERE role_key IN
    ('ex-super-cl', 'ex-imple-cl', 'ex-review-cl',
     'example-planning-supervisor', 'example-execution-decomposer',
     'example-implementer', 'example-reviewer',
     'example-escalation-supervisor');
