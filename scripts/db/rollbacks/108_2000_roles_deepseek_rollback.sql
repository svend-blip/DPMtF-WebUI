-- Rollback: 2000_roles_deepseek (migration 108)
-- Restore the 106 seed binding for the two roles.
UPDATE bridge_roles
   SET default_model_alias = 'cloud_qwen38flash',
       updated_at = datetime('now')
 WHERE role_key IN ('2000-implementer', '2000-reviewer');
