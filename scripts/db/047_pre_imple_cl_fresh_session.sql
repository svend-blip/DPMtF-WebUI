-- 047: Pre-imple-cl takes the OpenCode reset rule — the last role that had not.
--
-- 046 corrected imple01LW and deliberately left this one, because
-- preferred_cloud had handoff 035 dispatched and its implementer working.
-- fresh_session_command takes effect at the next dispatch, so changing it
-- mid-run would have been a behaviour change the supervisor was never told
-- about. The Human has taken the flow down, which is what makes this safe.
--
-- With this applied, every active OpenCode role uses /new and every Claude
-- Code role uses /clear, as 101 requires. The rule and the data now agree,
-- which they did not when the rule was written.
--
-- The reason, restated once because it is the whole point: OpenCode's
-- /clear is not a context clear. It resolves to commands/clear.md, a prompt
-- asking the model to disregard earlier context while the session and every
-- token of its history continue — appended to the history it asks the model
-- to ignore. Pre-imple-cl runs MiniMax-M3, the model measured degrading
-- into prose tool calls past roughly half its window (492), so this role in
-- particular should not be accumulating across a run.
--
-- Idempotent: an UPDATE of an existing row; re-running changes nothing.

UPDATE bridge_roles
SET fresh_session_command = '/new',
    updated_at            = CURRENT_TIMESTAMP
WHERE role_key = 'Pre-imple-cl'
  AND allocator_client = 'opencode';
