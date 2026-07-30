-- 020: Stop auto-/clear on the Human-paired supervisor session.
--
-- Migration 009 set `supervisor`.fresh_session_command to NULL on purpose:
-- "human-paired session — an auto-/clear could wipe an ongoing discussion
-- when a handoff arrives."
--
-- Migration 010 then set it to '/clear'. That was correct at the time:
-- `supervisor` WAS the autonomous role that the supervised_review flow
-- dispatched to, and a stateless wake-up needs an empty context. Migration
-- 011 created `supervisor_auto` to take that job, but nobody restored
-- `supervisor` — so the Human-paired role has carried an auto-/clear ever
-- since, for a reason that stopped applying three migrations ago.
--
-- It could not be fixed while the two roles shared one tmux session: a
-- dispatch to that pane had to clear it. Migration 019 split the sessions,
-- which is what makes this safe now.
--
-- Idempotent: re-running only re-asserts the same value.

UPDATE bridge_roles
SET fresh_session_command = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE role_key = 'supervisor';
