-- 019: Give supervisor_auto its own tmux session.
--
-- supervisor_auto (flow `supervised_review`, governance 451) shared the
-- 'supervisor' tmux session with the Human-paired `supervisor` role (flow
-- `supervisor`, governance 500). Migration 017 split the flow's other three
-- roles for the same reason and deliberately left this one alone, because
-- changing it requires a session to exist and an agent to be started in it —
-- an operational step, not a data change.
--
-- Two things were wrong with sharing:
--
-- 1. CONCURRENCY. An autonomous run and a Human-paired supervisor session
--    cannot both use one pane. The autonomous role also carries
--    fresh_session_command '/clear', so a dispatch arriving mid-conversation
--    would wipe a Human-paired discussion. Migration 009 guarded against
--    exactly that by setting the `supervisor` role's own
--    fresh_session_command to NULL; migration 010 then set it back to
--    '/clear' — correctly at the time, because `supervisor` WAS the
--    autonomous role until 011 created `supervisor_auto`. Restoring it is
--    migration 020, which only becomes safe once the sessions are split.
-- 2. AMBIGUOUS TARGETING. Role windows are linked into the flow-* viewer
--    sessions, so a bare role name as a tmux target can resolve to a window
--    that is not the one the flow is driving.
--
-- config_dir moves with it. It is inert for claude-code roles (only
-- start_coding.py's opencode branch reads it, to place opencode.json), but
-- leaving it pointing at another role's directory would be a trap the first
-- time that changes.
--
-- OPERATIONAL follow-up, not covered by this migration:
--     python3 scripts/bridgeV002/start_tmuxflow.py supervised_review
--     python3 scripts/bridgeV002/start_coding.py  supervised_review
-- The first creates the sessions; the second starts the agents in them.
-- Until the second runs, dispatch would inject into a bare shell.
--
-- Idempotent: re-running only re-asserts the same values.

UPDATE bridge_roles
SET tmux_session = 'supervisor_auto',
    config_dir = 'supervisor_auto',
    updated_at = CURRENT_TIMESTAMP
WHERE role_key = 'supervisor_auto';
