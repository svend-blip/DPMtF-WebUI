-- 068 rollback: Governance phase-5 repoint -- Run 017 (Phase 5) D1.
--
-- Restores bridge_roles.governance_file for the 32 generic repoints back
-- to their original 4xx/5xx absorbed-original names, and restores the 3
-- exception-file roles back to their pre-068 originals.
--
-- Exact rollback mapping (the inverse of 068):
--   HUMAN.md                 -> 401/411/421  (human, humancloud, humanpay)
--   ARCHITECT.md             -> 402/412/422  (archi01, archi01cloud, archi01pay)
--   IMPLEMENTOR.md           -> 403/413/423/452/462/492/472/512
--                                            (imple01, imple01cloud,
--                                             imple01pay, imple01sup,
--                                             pi_imple01, oc_imple01,
--                                             imple01SG, Rev_Imple,
--                                             Pre-imple-cl,
--                                             imple-codex-minimaxM3)
--   TECHNICAL_REVIEW.md      -> 404/414/424/453 (review01, review01cloud,
--                                                 review01pay, review01sup)
--   GOVERNANCE_REVIEW.md     -> 405/415/425/454 (review02, review02cloud,
--                                                 review02pay, review02sup)
--   REVIEW.md                -> 463/473/513     (review01SG, Pre-review-cl,
--                                                 review-claude-sonnet5)
--   SUPERVISOR_AUTONOMOUS.md -> 451/461/491/471/511
--                                            (supervisor_auto,
--                                             supervisor01_llama,
--                                             Rev_Supervisor,
--                                             Pre-super-cl,
--                                             super-deep-deep4)
--   IMPLEMENTOR_REMOTE_WORKER.md  -> 481_LIGHTWORKER_IMPLE01LW.md (imple01LW)
--   REVIEW_REMOTE_WORKER.md       -> 482_LIGHTWORKER_REVIEW01LW.md (review01LW)
--   REVERSE_ENGINEERING_REVIEW.md -> 493_REVENG_REVIEW.md (Rev_Review)
--
-- Scope discipline: each UPDATE is scoped to the exact role_key +
-- post-068 governance_file pair the migration set, so a blanket match
-- on a single governance_file would clobber rows that a future handoff
-- repoints to the same generic name. The role_key predicate is the
-- authoritative tie-breaker.
--
-- FULL HOST RECOVERY (GOAL.md section 2 rollback coupling): this SQL
-- rollback PLUS git-revert of the later D3 deletion commit (the 35
-- files the Phase-5 deletion handoff removes). The DB restore and the
-- git restore are two separate steps; neither alone is a full recovery.
-- Without the git-revert, the restored names (401_/402_/...) point at
-- files that no longer exist on disk.
--
-- After clearing the columns, remove the schema_migrations row that
-- migrate.py wrote, so a subsequent `python3 scripts/migrate.py`
-- re-applies 068 cleanly. Mirrors the comment style of
-- rollbacks/063_governance_pilot_repoint_rollback.sql.
--
-- Do NOT apply this rollback in the normal handoff flow; it is for
-- emergency revert only. The D4 handoff (068) writes the tests that
-- verify this rollback's correctness.

UPDATE bridge_roles
   SET governance_file = '401_STRICT_REVIEW_HUMAN.md'
 WHERE is_active = 1 AND role_key = 'human'
   AND governance_file = 'HUMAN.md';

UPDATE bridge_roles
   SET governance_file = '411_CLOUD_LLM_HUMANCLOUD.md'
 WHERE is_active = 1 AND role_key = 'humancloud'
   AND governance_file = 'HUMAN.md';

UPDATE bridge_roles
   SET governance_file = '421_CLOUD_PAY_HUMANPAY.md'
 WHERE is_active = 1 AND role_key = 'humanpay'
   AND governance_file = 'HUMAN.md';

UPDATE bridge_roles
   SET governance_file = '402_STRICT_REVIEW_ARCHI01.md'
 WHERE is_active = 1 AND role_key = 'archi01'
   AND governance_file = 'ARCHITECT.md';

UPDATE bridge_roles
   SET governance_file = '412_CLOUD_LLM_ARCHI01CLOUD.md'
 WHERE is_active = 1 AND role_key = 'archi01cloud'
   AND governance_file = 'ARCHITECT.md';

UPDATE bridge_roles
   SET governance_file = '422_CLOUD_PAY_ARCHI01PAY.md'
 WHERE is_active = 1 AND role_key = 'archi01pay'
   AND governance_file = 'ARCHITECT.md';

UPDATE bridge_roles
   SET governance_file = '403_STRICT_REVIEW_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'imple01'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '413_CLOUD_LLM_IMPLE01CLOUD.md'
 WHERE is_active = 1 AND role_key = 'imple01cloud'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '423_CLOUD_PAY_IMPLE01PAY.md'
 WHERE is_active = 1 AND role_key = 'imple01pay'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '452_SUPERVISED_REVIEW_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'imple01sup'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '452_SUPERVISED_REVIEW_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'pi_imple01'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '452_SUPERVISED_REVIEW_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'oc_imple01'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '462_LLAMA_SG_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'imple01SG'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '492_REVENG_IMPLE.md'
 WHERE is_active = 1 AND role_key = 'Rev_Imple'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '472_PREFERRED_CLOUD_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'Pre-imple-cl'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '512_PREFERRED_CLOUD_HARNESS_IMPLE01.md'
 WHERE is_active = 1 AND role_key = 'imple-codex-minimaxM3'
   AND governance_file = 'IMPLEMENTOR.md';

UPDATE bridge_roles
   SET governance_file = '404_STRICT_REVIEW_REVIEW01.md'
 WHERE is_active = 1 AND role_key = 'review01'
   AND governance_file = 'TECHNICAL_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '414_CLOUD_LLM_REVIEW01CLOUD.md'
 WHERE is_active = 1 AND role_key = 'review01cloud'
   AND governance_file = 'TECHNICAL_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '424_CLOUD_PAY_REVIEW01PAY.md'
 WHERE is_active = 1 AND role_key = 'review01pay'
   AND governance_file = 'TECHNICAL_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '453_SUPERVISED_REVIEW_REVIEW01.md'
 WHERE is_active = 1 AND role_key = 'review01sup'
   AND governance_file = 'TECHNICAL_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '405_STRICT_REVIEW_REVIEW02.md'
 WHERE is_active = 1 AND role_key = 'review02'
   AND governance_file = 'GOVERNANCE_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '415_CLOUD_LLM_REVIEW02CLOUD.md'
 WHERE is_active = 1 AND role_key = 'review02cloud'
   AND governance_file = 'GOVERNANCE_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '425_CLOUD_PAY_REVIEW02PAY.md'
 WHERE is_active = 1 AND role_key = 'review02pay'
   AND governance_file = 'GOVERNANCE_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '454_SUPERVISED_REVIEW_REVIEW02.md'
 WHERE is_active = 1 AND role_key = 'review02sup'
   AND governance_file = 'GOVERNANCE_REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '463_LLAMA_SG_REVIEW01.md'
 WHERE is_active = 1 AND role_key = 'review01SG'
   AND governance_file = 'REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '473_PREFERRED_CLOUD_REVIEW01.md'
 WHERE is_active = 1 AND role_key = 'Pre-review-cl'
   AND governance_file = 'REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '513_PREFERRED_CLOUD_HARNESS_REVIEW01.md'
 WHERE is_active = 1 AND role_key = 'review-claude-sonnet5'
   AND governance_file = 'REVIEW.md';

UPDATE bridge_roles
   SET governance_file = '451_SUPERVISED_REVIEW_SUPERVISOR.md'
 WHERE is_active = 1 AND role_key = 'supervisor_auto'
   AND governance_file = 'SUPERVISOR_AUTONOMOUS.md';

UPDATE bridge_roles
   SET governance_file = '461_LLAMA_SG_SUPERVISOR.md'
 WHERE is_active = 1 AND role_key = 'supervisor01_llama'
   AND governance_file = 'SUPERVISOR_AUTONOMOUS.md';

UPDATE bridge_roles
   SET governance_file = '491_REVENG_SUPERVISOR.md'
 WHERE is_active = 1 AND role_key = 'Rev_Supervisor'
   AND governance_file = 'SUPERVISOR_AUTONOMOUS.md';

UPDATE bridge_roles
   SET governance_file = '471_PREFERRED_CLOUD_SUPERVISOR.md'
 WHERE is_active = 1 AND role_key = 'Pre-super-cl'
   AND governance_file = 'SUPERVISOR_AUTONOMOUS.md';

UPDATE bridge_roles
   SET governance_file = '511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md'
 WHERE is_active = 1 AND role_key = 'super-deep-deep4'
   AND governance_file = 'SUPERVISOR_AUTONOMOUS.md';

-- Exception-file data-fix rollback (the three direct UPDATEs from run 012).
UPDATE bridge_roles
   SET governance_file = '481_LIGHTWORKER_IMPLE01LW.md'
 WHERE is_active = 1 AND role_key = 'imple01LW'
   AND governance_file = 'IMPLEMENTOR_REMOTE_WORKER.md';

UPDATE bridge_roles
   SET governance_file = '482_LIGHTWORKER_REVIEW01LW.md'
 WHERE is_active = 1 AND role_key = 'review01LW'
   AND governance_file = 'REVIEW_REMOTE_WORKER.md';

UPDATE bridge_roles
   SET governance_file = '493_REVENG_REVIEW.md'
 WHERE is_active = 1 AND role_key = 'Rev_Review'
   AND governance_file = 'REVERSE_ENGINEERING_REVIEW.md';

DELETE FROM schema_migrations WHERE filename = '068_governance_phase5_repoint.sql';
