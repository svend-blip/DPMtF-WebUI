-- 060: evidence gate on reveng review steps (Run 006 D3).
--
-- The reveng flow's two review steps (Rev_Imple -> Rev_Review, and
-- Rev_Review -> Rev_Supervisor) had no evidence gate. Every other
-- supervisor-shaped flow (llama_SG, preferred_cloud, preferred_cloud_harness)
-- already runs gate-deliverable-evidence before the supervisor step —
-- see the pre_dispatch_script values on rows 680, 681, 692, 693, 708, 709.
--
-- Without the gate, a reveng deliverable can pass without the evidence
-- check every other supervisor flow already runs. That asymmetry was
-- measured 2026-08-21 (GOAL.md §1 D3) — preferred_cloud runs 001-005
-- were gated; reveng runs 040-044 were not, and one of them produced
-- a verdict that the gate would have rejected.
--
-- This migration sets pre_dispatch_script = 'gate-deliverable-evidence'
-- on rows 701 and 702 only. No other reveng step, no other flow.
--
-- Idempotent: the WHERE clause matches only the unfixed state
-- (pre_dispatch_script = '' or NULL), so re-running is a no-op.

UPDATE bridge_flow_steps
SET pre_dispatch_script = 'gate-deliverable-evidence'
WHERE id IN (701, 702)
  AND flow_key = 'reveng'
  AND (pre_dispatch_script IS NULL OR pre_dispatch_script = '');
