-- 046: bring imple01LW onto the OpenCode reset rule (/new).
--
-- 101 now states it: an OpenCode role uses `/new`, a Claude Code role uses
-- `/clear`. The two commands share a name and do different things. Claude
-- Code's clears the conversation; OpenCode's resolves to commands/clear.md,
-- a prompt asking the model to disregard earlier context while the session
-- and all of its tokens continue. It costs window rather than freeing it.
--
-- The rule was already the practice. Measured 2026-08-13 across active agent
-- roles: 25 OpenCode roles on /new, 2 on /clear. The two are drift.
--
--   imple01LW      lightworker       — corrected here
--   Pre-imple-cl   preferred_cloud   — NOT corrected here, deliberately
--
-- preferred_cloud had handoff 035 dispatched and its implementer working
-- when this was written. fresh_session_command takes effect at the next
-- dispatch, so changing it mid-run is a behaviour change the supervisor was
-- never told about — the class of intervention this project has spent a day
-- learning not to make. It is left for the next migration after that run
-- closes, recorded here so it is not lost rather than silently skipped.
--
-- lightworker was PARKed with nothing in flight, so it takes the change now.
--
-- Idempotent: an UPDATE of an existing row; re-running changes nothing.

UPDATE bridge_roles
SET fresh_session_command = '/new',
    updated_at            = CURRENT_TIMESTAMP
WHERE role_key = 'imple01LW'
  AND allocator_client = 'opencode';
