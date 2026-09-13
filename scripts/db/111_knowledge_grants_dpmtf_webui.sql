-- 111_knowledge_grants_dpmtf_webui.sql
-- GOAL-DRAFT-024 WORK 1: seed the operator's own dpmtf-webui grant (D-024-2).
--
-- One row, exactly the triple the GOAL names: the operator's own API use as
-- agent_role 'human', any flow (flow_key NULL). The table's UNIQUE
-- (scope, agent_role, flow_key) constraint plus INSERT OR IGNORE makes this
-- re-runnable without duplicates. No wildcard agent_role; no other scopes;
-- no DROP/DELETE/ALTER; no BEGIN/COMMIT (migrate.py wraps the file in a
-- transaction).

INSERT OR IGNORE INTO knowledge_scope_grants (scope, agent_role, flow_key)
VALUES ('dpmtf-webui', 'human', NULL);
