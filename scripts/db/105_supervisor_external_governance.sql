-- Migration: supervisor_external_governance
-- Rebind the conversational `supervisor` role's governance from
-- 500_SUPERVISOR.md to EXTERNAL_SUPERVISOR.md. The role has become the
-- External Supervisor: the single human-facing session that watches and
-- drives other chains on the Human's behalf, gating and promoting under
-- mandate, quality-assuring and close-verifying, relaying the Human's
-- rulings — the operating mode EXTERNAL_SUPERVISOR.md describes.
--
-- The supervisor flow's `supervisor-human` step carries no governance_file
-- of its own, so it resolves through this role — its effective governance
-- becomes EXTERNAL_SUPERVISOR.md. 500_SUPERVISOR.md stays with the other
-- conversational role (ex-super-cl) that still references it.
--
-- RAW SQL, idempotent (the WHERE bounds it), no BEGIN/COMMIT (migrate.py
-- wraps each file), no absolute machine paths.

UPDATE bridge_roles
SET governance_file = 'EXTERNAL_SUPERVISOR.md'
WHERE role_key = 'supervisor'
  AND governance_file = '500_SUPERVISOR.md';
