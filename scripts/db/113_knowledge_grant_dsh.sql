-- 113_knowledge_grant_dsh.sql
-- GOAL-DRAFT-033 WORK 1: seed the DeepSeek Harness dpmtf-webui grant.
--
-- One row, exactly the triple the GOAL names: the DeepSeek Harness role
-- 'dsh' gets the internal dpmtf-webui scope as a wildcard-flow grant
-- (flow_key NULL). A DSH session has no flow key -- it sends its workspace
-- as flow_key -- so the grant must be wildcard on flow. The table's UNIQUE
-- (scope, agent_role, flow_key) constraint plus INSERT OR IGNORE makes this
-- re-runnable without duplicates. No other roles; no other scopes; no
-- DROP/DELETE/ALTER; no BEGIN/COMMIT (migrate.py wraps the file in a
-- transaction).

INSERT OR IGNORE INTO knowledge_scope_grants (scope, agent_role, flow_key)
VALUES ('dpmtf-webui', 'dsh', NULL);
