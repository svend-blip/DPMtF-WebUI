-- Rollback: 111_knowledge_grants_dpmtf_webui.sql
-- Reverse the dpmtf-webui grant seed (GOAL-DRAFT-024 WORK 1).

DELETE FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui' AND agent_role = 'human' AND flow_key IS NULL;

DELETE FROM schema_migrations WHERE filename = '111_knowledge_grants_dpmtf_webui.sql';
