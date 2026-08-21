-- 061: Per-flow supervisor_role for stall wake-up routing.
--
-- Today the exhausted-nudge-budget stall wake-up is hardcoded to inject
-- into the `supervisor_auto` session, whatever flow stalled. A flow that
-- has its own supervisor role should have the wake-up land in that
-- flow's own supervisor session instead. NULL must preserve today's
-- behavior exactly.
--
-- The column is opt-in: no UPDATE statements. Every existing flow keeps
-- NULL, which routes to `supervisor_auto` (today's behavior). Opting any
-- flow in is a separate decision, made by the run that wants it, and is
-- not in the fence of this handoff.
--
-- Idempotency: schema_migrations (managed by scripts/migrate.py) records
-- this filename after a successful apply, so re-running migrate.py is a
-- no-op against the column add.

ALTER TABLE bridge_flows ADD COLUMN supervisor_role TEXT DEFAULT NULL;
