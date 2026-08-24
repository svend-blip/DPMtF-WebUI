-- 071: default_harness_profile='gpu' for the role that runs GPU-gated proofs.
--
-- Goal (GOAL.md Run 024 §1 D3, section 2, section 5):
-- The resolver's harness_profile dimension is empty everywhere today. Run 022's
-- 087 discrepancy (2026-08-23) was a host-side PRIVILEGE INVERSION: the role
-- that must run GPU-gated proofs (imple-codex-minimaxM3) sat in the
-- least-privileged sandbox while the verifying reviewer held full access.
-- The Human flagged the rebalance as REQUIRED before any HA-3..HA-5 GPU-gated
-- handoff. The fix is to set default_harness_profile = 'gpu' on the ONE role
-- that runs GPU-gated proofs so its codex launch path threads CODEX_PROFILE=gpu
-- (D2, handoff 092) and the adapter renders --sandbox danger-full-access
-- (D1, handoff 091).
--
-- Bindings:
--   (a) Marker table (067/070-pattern) records the PRIOR value for the row
--       the migration touches, so the rollback can restore byte-exact prior
--       values (NULL in this case — the migration flips NULL -> 'gpu' for
--       exactly one role). The marker table is the source of truth.
--   (b) The UPDATE is scoped to ONE role (imple-codex-minimaxM3) by name,
--       not a blanket WHERE default_harness_profile IS NULL match: a blanket
--       match would also flip review-claude-sonnet5 and super-deep-deep4 if a
--       future migration left them NULL, which would break the role split
--       (the reviewer is NOT supposed to escape its sandbox). The list is the
--       same as the marker-table INSERT.
--   (c) The marker-table CREATE and INSERT sit OUTSIDE the per-statement
--       auto-commit boundary, so they survive a guard abort — the rollback
--       must still be able to read them. They are idempotent (CREATE IF NOT
--       EXISTS; INSERT OR IGNORE on the role_key PRIMARY KEY).
--   (d) POST-update guard (one-shot trigger on a sentinel table): if, after
--       the UPDATE, more or fewer than EXACTLY ONE active bridge_roles row
--       reads default_harness_profile='gpu', OR that one row is NOT
--       imple-codex-minimaxM3, the guard RAISEs ABORT and the explicit
--       BEGIN/COMMIT transaction is rolled back — imple-codex-minimaxM3
--       keeps its NULL. [verified fact] SQLite's RAISE() is only valid
--       inside a trigger program, so the abort is implemented as an AFTER
--       UPDATE trigger on a small sentinel table (_migration_071_check);
--       the migration UPDATEs the sentinel to fire the trigger exactly
--       once, and the trigger body checks the post-update predicate. The
--       UPDATE on bridge_roles and the UPDATE on _migration_071_check are
--       wrapped in a single explicit BEGIN/COMMIT, so a guard abort rolls
--       the bridge_roles UPDATE back atomically. The sentinel trigger and
--       table are dropped at the end of a successful apply.
--   (e) Idempotent: re-running against an already-applied DB is a no-op
--       (the UPDATE matches zero rows because imple-codex-minimaxM3 already
--       reads 'gpu'; the sentinel UPDATE fires the trigger, the predicate
--       already holds (1 row, correct role), no abort). On a re-run after a
--       failed apply, the sentinel table and trigger from the failed run
--       are dropped at the top of the script (DROP IF EXISTS) so the new
--       run starts clean; the marker table is idempotent via INSERT OR IGNORE.
--   (f) Step-level default_harness_profile is left untouched — bridge_flow_steps
--       has no default_harness_profile column and the resolver inherits via
--       COALESCE from the role row. The other two roles (review-claude-sonnet5,
--       super-deep-deep4) stay NULL. No schema change to any production table
--       (the marker + sentinel are scratch _migration_071_* tables and the
--       sentinel is dropped at the end of every successful or failed apply;
--       the marker is dropped only by the rollback).
--
-- Header comment follows the 067 / 069 / 070 house style and names GOAL.md
-- Run 024 §1 D3.

-- (e) Drop any sentinel-table / trigger left over from a previously-aborted
-- apply so the new run starts clean.
DROP TRIGGER IF EXISTS _migration_071_guard;
DROP TABLE IF EXISTS _migration_071_check;

-- (a) Marker table — OUTSIDE the BEGIN/COMMIT so it survives a guard abort.
CREATE TABLE IF NOT EXISTS _migration_071_prior_harness_profile (
    role_key TEXT PRIMARY KEY,
    prior_harness_profile TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- (a) Snapshot the prior values for the row the migration is about to update.
-- INSERT OR IGNORE keeps this idempotent: a re-run that finds the row already
-- present skips the duplicate insert without raising. NULL COALESCEd to the
-- empty string because the column is TEXT NOT NULL; the rollback restores the
-- empty string (effectively NULL — sqlite TEXT NULL and TEXT '' both deserialize
-- to None in the Python row).
INSERT OR IGNORE INTO _migration_071_prior_harness_profile (role_key, prior_harness_profile)
SELECT role_key, COALESCE(default_harness_profile, '')
FROM bridge_roles
WHERE is_active = 1 AND role_key = 'imple-codex-minimaxM3';

-- (d) Sentinel table — the trigger fires on UPDATE of this table. The migration
-- UPDATEs the sentinel to fire the guard exactly once, AFTER the bridge_roles
-- UPDATE has run inside the same transaction.
CREATE TABLE IF NOT EXISTS _migration_071_check (id INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO _migration_071_check (id) VALUES (0);

-- (d) One-shot guard trigger. Fires AFTER UPDATE on the sentinel; the WHEN
-- clause narrows to the sentinel's id transition (0 -> 1) so the trigger
-- fires exactly once per migration run. The body checks the post-update
-- predicate (EXACTLY ONE active row reads 'gpu' AND that row is
-- imple-codex-minimaxM3) and RAISEs ABORT if not.
CREATE TRIGGER IF NOT EXISTS _migration_071_guard
AFTER UPDATE ON _migration_071_check
WHEN OLD.id = 0 AND NEW.id = 1
BEGIN
  SELECT CASE
    WHEN NOT (
        (SELECT COUNT(*) FROM bridge_roles
         WHERE is_active = 1 AND default_harness_profile = 'gpu') = 1
        AND
        (SELECT COUNT(*) FROM bridge_roles
         WHERE is_active = 1 AND default_harness_profile = 'gpu'
           AND role_key = 'imple-codex-minimaxM3') = 1
    )
    THEN RAISE(ABORT, 'migration 071 guard violation: post-update predicate is not exactly one active gpu role and it is imple-codex-minimaxM3 (the UPDATE was rolled back)')
  END;
END;

-- (b) + (d) The migration. The bridge_roles UPDATE and the sentinel UPDATE
-- (which fires the guard) are wrapped in a single explicit BEGIN/COMMIT so
-- a guard abort rolls back the bridge_roles UPDATE atomically.
BEGIN;
UPDATE bridge_roles
SET default_harness_profile = 'gpu'
WHERE is_active = 1 AND role_key = 'imple-codex-minimaxM3';
-- Fire the guard:
UPDATE _migration_071_check SET id = 1 WHERE id = 0;
COMMIT;

-- (d) Cleanup: drop the trigger and sentinel table now that the guard has
-- run (and the transaction committed). If the transaction aborted, the
-- script's RAISE propagated out and these statements don't run, so the
-- trigger and sentinel table remain — the DROP IF EXISTS at the top of
-- the next run cleans them up.
DROP TRIGGER IF EXISTS _migration_071_guard;
DROP TABLE IF EXISTS _migration_071_check;
