-- Rollback for 116. The rows are deliberately NOT put back to
-- {bridge_dir}/{flow_key}/: that root is the defect 084 and 116 correct, and a
-- rollback that restored it would be a second defect. Only the bookkeeping is
-- undone, so the migration can be applied again.

DELETE FROM schema_migrations WHERE filename = '116_convention_artifact_root_again.sql';
