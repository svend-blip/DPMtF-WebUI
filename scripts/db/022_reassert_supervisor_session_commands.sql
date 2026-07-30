-- 022: Defense-in-depth re-assert of the two supervisor session commands.
--
-- The values are already correct in the live database; this migration
-- exists for the rebuild-from-migrations scenario (which is not
-- theoretical here — see the 2026-07-04 DB-loss incident, where the
-- database was reconstructed and subtle role config was lost).
--
-- Why these two values are load-bearing:
--
-- 1. supervisor_auto.fresh_session_command = '/clear' is what
--    451_SUPERVISED_REVIEW_SUPERVISOR.md's statelessness rests on: the
--    autonomous supervisor rebuilds from durable files on EVERY wake-up.
--    A rebuild that loses the '/clear' produces a supervisor whose
--    context grows across wake-ups — a silent corruption of the design,
--    invisible until the context overflows mid-run. Migration 011 set
--    it; nothing after 011 re-asserts it (migrations 019/020 touch the
--    same role/area without restating it).
--
-- 2. supervisor.fresh_session_command = NULL is the Human-paired
--    session's protection against a dispatch clearing an ongoing
--    conversation (the 009 → 010 → 020 history; see migration 020's
--    header for the full account).
--
-- Idempotent: both statements re-assert values migration 020 left in
-- place; re-running changes nothing.

UPDATE bridge_roles
SET fresh_session_command = '/clear'
WHERE role_key = 'supervisor_auto'
  AND (fresh_session_command IS NULL OR fresh_session_command <> '/clear');

UPDATE bridge_roles
SET fresh_session_command = NULL
WHERE role_key = 'supervisor'
  AND fresh_session_command IS NOT NULL;
