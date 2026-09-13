-- Rollback: 110_knowledge_status_constraint.sql
-- Reverse the deferred status constraint on knowledge_indexes.
--
-- Drops both status triggers and deletes the schema_migrations row for 110,
-- so migrate.py can apply the migration again after a fresh forward run.

DROP TRIGGER IF EXISTS knowledge_indexes_status_check_insert;
DROP TRIGGER IF EXISTS knowledge_indexes_status_check_update;

DELETE FROM schema_migrations WHERE filename = '110_knowledge_status_constraint.sql';
