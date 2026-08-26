-- 077: target_project_path for the two 1000 flows.
--
-- Human decision 2026-08-26: both PLOOP and ELOOP operate on DPMtF itself.
-- The value was set in the live database when the decision was made (the
-- standing write exception); this migration carries it to fresh databases
-- so a rebuilt install does not silently fall back to the NULL default.
--
-- NULL already resolved to Father, so this changes no behaviour — it makes
-- an implicit default explicit, and lets get_flow_target_project fail loudly
-- if the path ever goes missing rather than quietly targeting a fallback.
--
-- CONSEQUENCE worth knowing: ELOOP roles carry workdir_mode=target_project,
-- so from here they work in the real DPMtF repository rather than a scratch
-- target. "Do not touch the working tree while a run is active" therefore
-- binds everyone, including the supervising session, with respect to 1000
-- runs.
--
-- Idempotent: a plain UPDATE; re-running rewrites identical values.
UPDATE bridge_flows
SET target_project_path = '/home/svend/DPMtF-WebUI'
WHERE flow_key IN ('1000-01-PLOOP', '1000-02-ELOOP');
