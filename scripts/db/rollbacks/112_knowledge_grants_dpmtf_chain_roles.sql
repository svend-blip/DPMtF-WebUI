-- Rollback: 112_knowledge_grants_dpmtf_chain_roles.sql
-- Reverse exactly the rows migration 112 inserted (GOAL-DRAFT-028 WORK 1),
-- then remove the applied-marker row.
--
-- The DELETE uses the SAME predicate as the migration, expressed as an
-- EXISTS subquery over bridge_flow_steps joined to bridge_flows: an active,
-- non-example step whose bridge_flows.target_project_path is NULL, empty, or
-- LIKE '%DPMtF-WebUI%'. The run-024 operator grant ('dpmtf-webui', 'human',
-- NULL) has no matching bridge_flow_steps (to_role, flow_key) pair, so the
-- EXISTS leaves it in place by construction.

DELETE FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui'
  AND EXISTS (
        SELECT 1
        FROM bridge_flow_steps AS s
        JOIN bridge_flows AS f ON f.flow_key = s.flow_key
        WHERE s.to_role = knowledge_scope_grants.agent_role
          AND s.flow_key = knowledge_scope_grants.flow_key
          AND s.is_active = 1
          AND s.flow_key NOT LIKE 'example%'
          AND (
                f.target_project_path IS NULL
                OR f.target_project_path = ''
                OR f.target_project_path LIKE '%DPMtF-WebUI%'
              )
      );

DELETE FROM schema_migrations WHERE filename = '112_knowledge_grants_dpmtf_chain_roles.sql';
