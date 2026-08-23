-- 070: model_source='harness' -> 'harness_provider' for the two migrated roles.
--
-- Goal (GOAL.md Run 021 §1 D2, section 2, section 5):
-- Retire the legacy model_source='harness' value by flipping the EXACTLY TWO
-- active roles that still carry it: super-deep-deep4 and imple-codex-minimaxM3
-- (the executing chain's own supervisor and implementer). The replacement
-- value 'harness_provider' is Human-approved and the dual acceptance at the
-- two enumerated comparison sites (start_coding.py:491, supervisor_state.py:337)
-- was already landed in 081 — this migration is the value flip those sites
-- already accept.
--
-- Bindings:
--   (a) Marker table (067-pattern) records the PRIOR value for each row the
--       migration touches, so the rollback can restore byte-exact prior values
--       (not a blanket 'harness' write — the marker table is the source of truth).
--   (b) The UPDATE is scoped to EXACTLY the two roles (a blanket model_source
--       match would be unsafe — it would also flip any future role that has
--       been added on the legacy value before dual acceptance is rolled back
--       everywhere else). The list is the same as the marker-table INSERT.
--   (c) The marker-table CREATE and INSERT sit OUTSIDE the per-statement
--       auto-commit boundary, so they survive a guard abort — the rollback
--       must still be able to read them. They are idempotent (CREATE IF NOT
--       EXISTS; INSERT OR IGNORE on the role_key PRIMARY KEY).
--   (d) POST-update guard (one-shot trigger on a sentinel table): if, after
--       the UPDATE, any active bridge_roles row OR any active bridge_flow_steps
--       row still reads 'harness', the guard RAISEs ABORT and the explicit
--       BEGIN/COMMIT transaction is rolled back — the two migrated roles
--       keep 'harness'. [verified fact] SQLite's RAISE() is only valid
--       inside a trigger program, so the abort is implemented as an AFTER
--       UPDATE trigger on a small sentinel table (_migration_070_check);
--       the migration UPDATEs the sentinel to fire the trigger exactly once,
--       and the trigger body checks the post-update predicate. The UPDATE on
--       bridge_roles and the UPDATE on _migration_070_check are wrapped in
--       a single explicit BEGIN/COMMIT, so a guard abort rolls the
--       bridge_roles UPDATE back atomically. The sentinel trigger and table
--       are dropped at the end of a successful apply.
--   (e) Idempotent: re-running against an already-applied DB is a no-op
--       (the UPDATE matches zero rows because the two roles already read
--       'harness_provider'; the sentinel UPDATE fires the trigger, the
--       count is 0, no abort). On a re-run after a failed apply, the
--       sentinel table and trigger from the failed run are dropped at the
--       top of the script (DROP IF EXISTS) so the new run starts clean;
--       the marker table is idempotent via INSERT OR IGNORE.
--   (f) The legacy literal 'harness' is NOT removed anywhere (dead-value
--       tolerance; start_coding.py / supervisor_state.py / execution_config.py
--       still accept it for already-rolled-back DBs and for any third role
--       a future migration has not yet flipped). Step-level model_source is
--       all NULL today and is NOT touched. No schema change to any
--       production table (the marker table and sentinel table are the
--       scratch _migration_070_* tables and the rollback drops the marker
--       table; the sentinel table is dropped at the end of every successful
--       or failed apply attempt).
--
-- Header comment follows the 067 / 069 house style and names GOAL.md Run 021
-- section 1 D2.

-- (e) Drop any sentinel-table / trigger left over from a previously-aborted
-- apply so the new run starts clean.
DROP TRIGGER IF EXISTS _migration_070_guard;
DROP TABLE IF EXISTS _migration_070_check;

-- (a) Marker table — OUTSIDE the BEGIN/COMMIT so it survives a guard abort.
CREATE TABLE IF NOT EXISTS _migration_070_prior_model_source (
    role_key TEXT PRIMARY KEY,
    prior_model_source TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- (a) Snapshot the prior values for the rows the migration is about to update.
-- INSERT OR IGNORE keeps this idempotent: a re-run that finds the rows already
-- present skips the duplicate insert without raising.
INSERT OR IGNORE INTO _migration_070_prior_model_source (role_key, prior_model_source)
SELECT role_key, default_model_source
FROM bridge_roles
WHERE is_active = 1 AND default_model_source = 'harness'
  AND role_key IN ('super-deep-deep4', 'imple-codex-minimaxM3');

-- (d) Sentinel table — the trigger fires on UPDATE of this table. The migration
-- UPDATEs the sentinel to fire the guard exactly once, AFTER the bridge_roles
-- UPDATE has run inside the same transaction.
CREATE TABLE IF NOT EXISTS _migration_070_check (id INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO _migration_070_check (id) VALUES (0);

-- (d) One-shot guard trigger. Fires AFTER UPDATE on the sentinel; the WHEN
-- clause narrows to the sentinel's id transition (0 -> 1) so the trigger
-- fires exactly once per migration run. The body checks the post-update
-- predicate (zero active rows must read 'harness') and RAISEs ABORT if not.
CREATE TRIGGER IF NOT EXISTS _migration_070_guard
AFTER UPDATE ON _migration_070_check
WHEN OLD.id = 0 AND NEW.id = 1
BEGIN
  SELECT CASE
    WHEN (
        SELECT COUNT(*) FROM bridge_roles
        WHERE is_active = 1 AND default_model_source = 'harness'
      ) + (
        SELECT COUNT(*) FROM bridge_flow_steps
        WHERE is_active = 1 AND model_source = 'harness'
      ) > 0
    THEN RAISE(ABORT, 'migration 070 guard violation: post-update predicate is non-empty (a legacy harness row remains in bridge_roles or bridge_flow_steps); the UPDATE was rolled back')
  END;
END;

-- (b) + (d) The migration. The bridge_roles UPDATE and the sentinel UPDATE
-- (which fires the guard) are wrapped in a single explicit BEGIN/COMMIT so
-- a guard abort rolls back the bridge_roles UPDATE atomically.
BEGIN;
UPDATE bridge_roles
SET default_model_source = 'harness_provider'
WHERE is_active = 1 AND default_model_source = 'harness'
  AND role_key IN ('super-deep-deep4', 'imple-codex-minimaxM3');
-- Fire the guard:
UPDATE _migration_070_check SET id = 1 WHERE id = 0;
COMMIT;

-- (d) Cleanup: drop the trigger and sentinel table now that the guard has
-- run (and the transaction committed). If the transaction aborted, the
-- script's RAISE propagated out and these statements don't run, so the
-- trigger and sentinel table remain — the DROP IF EXISTS at the top of
-- the next run cleans them up.
DROP TRIGGER IF EXISTS _migration_070_guard;
DROP TABLE IF EXISTS _migration_070_check;
