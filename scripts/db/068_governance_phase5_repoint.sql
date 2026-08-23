-- 068: Governance phase-5 repoint -- Run 017 (Phase 5) D1.
--
-- Goal (GOAL.md section 1 D1, section 2, section 7):
-- Set bridge_roles.governance_file at ROLE level for every active role whose
-- pointer names an absorbed original. Step-level repoints (063/064/065/066)
-- were completed in runs 009-012; this migration finishes the repoint at
-- the role-level FALLBACK so that deleting the 30 absorbed-original files in
-- the later D3 handoff does not leave any active role dangling on a missing
-- filename.
--
-- Section 15 semantics:
-- The role-level pointer names the role. The predicates below are
-- exclusively role_key-shaped. Where two roles share an absorbed file
-- (e.g. archi01/archi01cloud/archi01pay all map to ARCHITECT.md), one
-- UPDATE per group is sufficient — the predicate lists every role_key
-- in the group, scoped to is_active = 1 so retired roles are untouched.
--
-- Exact predicates and expected row counts (current DB state at authoring):
--   HUMAN.md                 <- human, humancloud, humanpay                          (3)
--   ARCHITECT.md             <- archi01, archi01cloud, archi01pay                    (3)
--   IMPLEMENTOR.md           <- imple01, imple01cloud, imple01pay, imple01sup,
--                               pi_imple01, oc_imple01, imple01SG, Rev_Imple,
--                               Pre-imple-cl, imple-codex-minimaxM3                 (10)
--   TECHNICAL_REVIEW.md      <- review01, review01cloud, review01pay, review01sup    (4)
--   GOVERNANCE_REVIEW.md     <- review02, review02cloud, review02pay, review02sup    (4)
--   REVIEW.md                <- review01SG, Pre-review-cl, review-claude-sonnet5      (3)
--   SUPERVISOR_AUTONOMOUS.md <- supervisor_auto, supervisor01_llama, Rev_Supervisor,
--                               Pre-super-cl, super-deep-deep4                        (5)
--   IMPLEMENTOR_REMOTE_WORKER.md   <- imple01LW                                       (1)
--   REVIEW_REMOTE_WORKER.md        <- review01LW                                      (1)
--   REVERSE_ENGINEERING_REVIEW.md  <- Rev_Review                                      (1)
--   Total: 32 + 3 = 35 rows updated (the 32 generic repoints + 3 idempotent
--   exception-file data fixes carried for any DB rebuilt from the committed
--   copy + migrations; production received these three as direct UPDATEs in
--   run 012, so the 068 apply is a no-op against those three rows on the
--   live DB).
--
-- Deliberate deferral (NOT in any UPDATE predicate):
--   supervisor                -> 500_SUPERVISOR.md     (kept: standalone spec file)
--   trade roles (43x)         -> 43x_TRADE_*.md        (kept: trade is its own spec)
--   humantrade                -> NULL                  (kept: empty is intentional)
--   every role already at its generic or exception target (no-ops naturally
--   because the value is identical).
--
-- POST-UPDATE ABORT GUARD (data-dependent, NOT a pre-count):
-- After all UPDATEs above, a TEMP TRIGGER is created on bridge_roles. A
-- forced no-op UPDATE on every active row evaluates the WHEN clause
-- (is_active=1 AND governance_file IN (the 30 retired absorbed-original
-- names)). If any active role still references a retired name, the
-- trigger raises ABORT and the migration fails. Otherwise the trigger
-- sees no matching row and the UPDATE proceeds; DROP TRIGGER cleans up.
--
-- Why POST-update and NOT a pre-count guard: a pre-count guard ("all 32
-- role_keys must exist before the UPDATEs") breaks scratch DBs that seed
-- only a subset of roles (the migrated_db fixture in
-- tests/test_preferred_cloud_harness.py is exactly such a DB). A post-
-- update guard only fires when the migration's own data-dependent
-- invariant is violated.
--
-- [verified] SQLite RAISE() is only valid inside a trigger-program, so a
-- bare SELECT ... RAISE(ABORT, ...) fails at prepare time. The trigger
-- + no-op UPDATE dance is the equivalent data-dependent error.
--
-- Idempotency: every UPDATE is scoped to role_keys whose current value
-- matches the source group, so re-running the UPDATEs against an
-- already-applied DB writes identical values (a no-op for SQLite's
-- row-update semantics). migrate.py records the filename in
-- schema_migrations after a successful apply, so a second migrate.py
-- run skips the file entirely. The trigger is TEMP and lives only for
-- the duration of the migration script.

-- ── generic repoints (32 rows) ─────────────────────────────────────

UPDATE bridge_roles
   SET governance_file = 'HUMAN.md'
 WHERE is_active = 1
   AND role_key IN ('human', 'humancloud', 'humanpay');

UPDATE bridge_roles
   SET governance_file = 'ARCHITECT.md'
 WHERE is_active = 1
   AND role_key IN ('archi01', 'archi01cloud', 'archi01pay');

UPDATE bridge_roles
   SET governance_file = 'IMPLEMENTOR.md'
 WHERE is_active = 1
   AND role_key IN ('imple01', 'imple01cloud', 'imple01pay', 'imple01sup',
                    'pi_imple01', 'oc_imple01', 'imple01SG', 'Rev_Imple',
                    'Pre-imple-cl', 'imple-codex-minimaxM3');

UPDATE bridge_roles
   SET governance_file = 'TECHNICAL_REVIEW.md'
 WHERE is_active = 1
   AND role_key IN ('review01', 'review01cloud', 'review01pay', 'review01sup');

UPDATE bridge_roles
   SET governance_file = 'GOVERNANCE_REVIEW.md'
 WHERE is_active = 1
   AND role_key IN ('review02', 'review02cloud', 'review02pay', 'review02sup');

UPDATE bridge_roles
   SET governance_file = 'REVIEW.md'
 WHERE is_active = 1
   AND role_key IN ('review01SG', 'Pre-review-cl', 'review-claude-sonnet5');

UPDATE bridge_roles
   SET governance_file = 'SUPERVISOR_AUTONOMOUS.md'
 WHERE is_active = 1
   AND role_key IN ('supervisor_auto', 'supervisor01_llama', 'Rev_Supervisor',
                    'Pre-super-cl', 'super-deep-deep4');

-- ── exception-file data fixes (3 rows; idempotent on production) ────
-- These three renames were applied as direct UPDATEs in run 012 (no
-- migration written at the time). 068 carries them idempotently so any
-- DB rebuilt from the committed copy + applied migrations reaches the
-- same state as production. On production, the values already match
-- the SET clause and the UPDATEs are no-ops.

UPDATE bridge_roles
   SET governance_file = 'IMPLEMENTOR_REMOTE_WORKER.md'
 WHERE is_active = 1
   AND role_key = 'imple01LW';

UPDATE bridge_roles
   SET governance_file = 'REVIEW_REMOTE_WORKER.md'
 WHERE is_active = 1
   AND role_key = 'review01LW';

UPDATE bridge_roles
   SET governance_file = 'REVERSE_ENGINEERING_REVIEW.md'
 WHERE is_active = 1
   AND role_key = 'Rev_Review';

-- ── POST-UPDATE abort guard ─────────────────────────────────────────
-- If any active role still references a retired absorbed-original name
-- after the UPDATEs above, abort. The 30 retired names are the exact
-- set the D3 handoff will delete from docs/governance-templates-v2/.
--
-- Mechanism: TEMP TRIGGER (session-scoped, no persistent schema
-- change) + a forced no-op UPDATE on every active row that evaluates
-- the WHEN clause. If a bad row exists, the trigger fires RAISE(ABORT,
-- ...) and the migration fails BEFORE schema_migrations is updated.
-- migrate.py catches the failure and rolls back the transaction.

CREATE TEMP TRIGGER _068_guard AFTER UPDATE ON bridge_roles
WHEN NEW.is_active = 1 AND NEW.governance_file IN (
  '401_STRICT_REVIEW_HUMAN.md',
  '402_STRICT_REVIEW_ARCHI01.md',
  '403_STRICT_REVIEW_IMPLE01.md',
  '404_STRICT_REVIEW_REVIEW01.md',
  '405_STRICT_REVIEW_REVIEW02.md',
  '411_CLOUD_LLM_HUMANCLOUD.md',
  '412_CLOUD_LLM_ARCHI01CLOUD.md',
  '413_CLOUD_LLM_IMPLE01CLOUD.md',
  '414_CLOUD_LLM_REVIEW01CLOUD.md',
  '415_CLOUD_LLM_REVIEW02CLOUD.md',
  '421_CLOUD_PAY_HUMANPAY.md',
  '422_CLOUD_PAY_ARCHI01PAY.md',
  '423_CLOUD_PAY_IMPLE01PAY.md',
  '424_CLOUD_PAY_REVIEW01PAY.md',
  '425_CLOUD_PAY_REVIEW02PAY.md',
  '451_SUPERVISED_REVIEW_SUPERVISOR.md',
  '452_SUPERVISED_REVIEW_IMPLE01.md',
  '453_SUPERVISED_REVIEW_REVIEW01.md',
  '454_SUPERVISED_REVIEW_REVIEW02.md',
  '461_LLAMA_SG_SUPERVISOR.md',
  '462_LLAMA_SG_IMPLE01.md',
  '463_LLAMA_SG_REVIEW01.md',
  '471_PREFERRED_CLOUD_SUPERVISOR.md',
  '472_PREFERRED_CLOUD_IMPLE01.md',
  '473_PREFERRED_CLOUD_REVIEW01.md',
  '491_REVENG_SUPERVISOR.md',
  '492_REVENG_IMPLE.md',
  '511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md',
  '512_PREFERRED_CLOUD_HARNESS_IMPLE01.md',
  '513_PREFERRED_CLOUD_HARNESS_REVIEW01.md'
)
BEGIN
  SELECT RAISE(ABORT, '068 guard: post-update active role still references retired absorbed-original name');
END;

-- Forced no-op UPDATE: triggers the guard if any active row has a
-- retired governance_file. If the post-update state is clean (every
-- active role has a generic or exception-file value), the WHEN clause
-- never matches and the UPDATE is a benign row-touch.
UPDATE bridge_roles SET role_key = role_key WHERE is_active = 1;

DROP TRIGGER _068_guard;
