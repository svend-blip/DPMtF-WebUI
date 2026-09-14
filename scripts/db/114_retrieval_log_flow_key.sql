-- 114_retrieval_log_flow_key.sql
-- Record the caller's flow key on the knowledge retrieval log.
--
-- GOAL-DRAFT-034. knowledge_retrieval_log gains flow_key so usage is
-- auditable per workspace. The column is nullable: pre-114 rows and
-- retrievals that happen outside a flow context stay NULL.

ALTER TABLE knowledge_retrieval_log ADD COLUMN flow_key TEXT DEFAULT NULL;
