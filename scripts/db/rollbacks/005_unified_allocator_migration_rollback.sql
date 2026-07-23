-- Rollback for migration 005: Revert all roles to direct model path
-- This sets default_model_source back to NULL (empty) for all roles
-- that were migrated by 005, restoring the direct/command_builder path.

UPDATE bridge_roles SET default_model_source = '', default_model_alias = ''
WHERE role_key IN (
  'archi01', 'review01', 'review02', 'imple01pay',
  'archi01cloud', 'review01cloud', 'review01pay', 'review02cloud', 'review02pay', 'archi01pay',
  'analyst01_trade', 'sim01_trade', 'trend01_trade',
  'market01_trade', 'portfolio01_trade',
  'risk01_trade', 'score01_trade', 'learn01_trade',
  'review01_trade'
) AND is_active = 1;

-- imple01 stays on allocator (was already there before migration 005)
UPDATE bridge_roles SET default_model_source = 'model_allocator', default_model_alias = 'imple01-local'
WHERE role_key = 'imple01' AND is_active = 1;

DELETE FROM schema_migrations WHERE filename = "005_unified_allocator_migration.sql";
