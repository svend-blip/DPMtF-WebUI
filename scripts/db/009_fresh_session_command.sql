-- 009: Tool-independent context reset at new-task dispatch.
--
-- The reset that gives a role an empty context (and frees client-side KV)
-- is client-specific (/new in OpenCode, /clear in Claude Code) — but the
-- dispatch code must be tool-independent. The command is per-role
-- configuration: dispatch sends bridge_roles.fresh_session_command into
-- the role's pane before a new-task prompt when set; NULL opts out.
--
-- Defaults: opencode roles -> '/new', claude-code roles -> '/clear',
-- except 'supervisor' (human-paired session — an auto-/clear could wipe an
-- ongoing discussion when a handoff arrives).

ALTER TABLE bridge_roles ADD COLUMN fresh_session_command TEXT DEFAULT NULL;

UPDATE bridge_roles SET fresh_session_command = '/new'
WHERE (allocator_client = 'opencode' OR allocator_client IS NULL)
  AND role_type != 'human';

UPDATE bridge_roles SET fresh_session_command = '/clear'
WHERE allocator_client = 'claude-code' AND role_type != 'human';

UPDATE bridge_roles SET fresh_session_command = NULL
WHERE role_key = 'supervisor';
