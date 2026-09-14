-- 112_knowledge_grants_dpmtf_chain_roles.sql
-- GOAL-DRAFT-028 WORK 1: grant the internal dpmtf-webui scope to every active
-- chain role whose flow targets Father (this DPMtF checkout).
--
-- Predicate: one grant ('dpmtf-webui', s.to_role, s.flow_key) for every
-- bridge_flow_steps row whose flow targets Father — bridge_flows
-- .target_project_path is NULL, empty, or names the DPMtF checkout
-- (LIKE '%DPMtF-WebUI%') — and whose flow_key does not start with 'example'.
-- The compiler passes the step's to_role key as agent_role
-- (routers/prompt_compiler.py, role_name = to_role_key), so to_role is
-- exactly the string the guard compares. One grant per (role, flow) pair:
-- SELECT DISTINCT plus the table's UNIQUE (scope, agent_role, flow_key)
-- constraint and INSERT OR IGNORE keep this re-runnable without duplicates.
-- No wildcard flow_key, no wildcard agent_role; no seed rows for foreign or
-- example flows; no DROP/DELETE/ALTER; no BEGIN/COMMIT (migrate.py wraps the
-- file in a transaction).

INSERT OR IGNORE INTO knowledge_scope_grants (scope, agent_role, flow_key)
SELECT DISTINCT 'dpmtf-webui', s.to_role, s.flow_key
FROM bridge_flow_steps AS s
JOIN bridge_flows AS f ON f.flow_key = s.flow_key
WHERE s.is_active = 1
  AND s.flow_key NOT LIKE 'example%'
  AND (
        f.target_project_path IS NULL
        OR f.target_project_path = ''
        OR f.target_project_path LIKE '%DPMtF-WebUI%'
      );
