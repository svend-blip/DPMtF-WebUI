-- Rollback: 113_knowledge_grant_dsh.sql
-- Reverse the DeepSeek Harness dpmtf-webui grant seed (GOAL-DRAFT-033 WORK 1).

DELETE FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui' AND agent_role = 'dsh' AND flow_key IS NULL;

DELETE FROM schema_migrations WHERE filename = '113_knowledge_grant_dsh.sql';
