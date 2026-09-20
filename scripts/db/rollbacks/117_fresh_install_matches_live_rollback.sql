-- Rollback for 117. The corrections are deliberately NOT undone: putting back
-- a label bound twice, a System Setup heading that reads "Default Model
-- Source", or an escalation line that names archi01 for every flow would
-- restore defects. Only the bookkeeping is undone, so the migration can be
-- applied again; every statement in it is a no-op on data already corrected.

DELETE FROM schema_migrations WHERE filename = '117_fresh_install_matches_live.sql';
