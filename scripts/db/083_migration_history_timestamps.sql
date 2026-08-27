-- 083: Restore the true application times for migrations 079-082.
--
-- Migrations 079, 080 and 081 took effect in the database but were never
-- recorded in schema_migrations. 082 was applied by hand during run 002 and
-- was the fourth. All four were recorded on 2026-08-27 by running
-- scripts/migrate.py, which is the right mechanism — each is idempotent, and a
-- before/after snapshot of every row they touch was identical.
--
-- But the runner stamps applied_at with datetime('now'), so all four came out
-- reading 10:31:28Z. The row was then true about WHETHER each migration was
-- applied and false about WHEN. Human instruction: the history must be correct.
--
-- Each timestamp below is EVIDENCE, not reconstruction. The four sources are
-- independent of one another, and each is corroborated by the commit that
-- carried the migration file:
--
--   079  2026-08-26 22:03:57Z   ui_labels.created_at for LBL-1000511. The
--                               migration is INSERT OR IGNORE, so re-running
--                               it did NOT overwrite the original row's
--                               created_at.        commit 29ce8df  +23 s
--
--   080  2026-08-27 01:27:37Z   bridge_roles.updated_at for
--                               1000-execution-decomposer and
--                               1000-implementer, read before anything in
--                               this session was changed.
--                                                  commit 5701009  +26 s
--
--   081  2026-08-27 09:28:42Z   bridge_roles.updated_at for 1000-reviewer,
--                               read in the same untouched state.
--                                                  commit 55e7431  +30 s
--
--   082  2026-08-27 10:28:18Z   bridge_roles.updated_at in the .backup taken
--                               after 082 was applied and before migrate.py
--                               re-ran it.         commit 512878e  +28 s
--
-- The same apply-then-commit-within-half-a-minute pattern appears in all four,
-- from four different sources. That agreement is the reason these are written
-- as fact rather than estimate.
--
-- Written to SECOND precision deliberately. The existing rows carry
-- microseconds because datetime.now() produced them; the evidence here does
-- not, and inventing sub-second digits to match the format would be false
-- precision in the one table whose purpose is to be believed.
--
-- What this does NOT change: the 79 rows recorded 001-078 by the runner at the
-- time they genuinely ran. Only the four repaired rows are touched.
--
-- Idempotent: each UPDATE sets a literal keyed on filename, so re-running
-- asserts the same value.

UPDATE schema_migrations SET applied_at = '2026-08-26T22:03:57+00:00'
 WHERE filename = '079_artifact_root_placeholder_label.sql';

UPDATE schema_migrations SET applied_at = '2026-08-27T01:27:37+00:00'
 WHERE filename = '080_eloop_roles_opencode.sql';

UPDATE schema_migrations SET applied_at = '2026-08-27T09:28:42+00:00'
 WHERE filename = '081_reviewer_freetoken.sql';

UPDATE schema_migrations SET applied_at = '2026-08-27T10:28:18+00:00'
 WHERE filename = '082_1000_fresh_session_command.sql';
