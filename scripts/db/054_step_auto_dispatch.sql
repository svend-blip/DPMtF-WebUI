-- 054: bridge_flow_steps.auto_dispatch — manual-dispatch-only steps.
--
-- pi_test's fan-out defect (2026-08-16): every oc_imple01 completion was
-- followed seconds later by a second, improvised signal-complete carrying
-- --from-role human. On this cyclic flow that resolves the FIRST step with
-- from_role = 'human' (human-pi_imple01) and re-injects the same handoff
-- id into the parallel implementer — a duplicate execution of a possibly
-- repository-mutating task, with both roles writing the same
-- {ID}-result.md. Measured on handoffs 008, 009 and 010 (010's attempt
-- failed only because the pi_imple01 session had been removed).
--
-- The flag makes the refusal mechanical instead of hoping a model never
-- improvises: auto_dispatch = 0 marks a step as Human-initiated only —
-- signal_complete refuses to deliver it; --signal-send remains the only
-- way in. NULL/1 = today's behavior (chain delivery allowed).
--
-- pi_test's two handoff steps are Human-dispatched by definition
-- (from_role = 'human'), so both are opted out here.

ALTER TABLE bridge_flow_steps ADD COLUMN auto_dispatch INTEGER DEFAULT NULL;

UPDATE bridge_flow_steps SET auto_dispatch = 0
WHERE flow_key = 'pi_test' AND step_key IN ('human-oc_imple01', 'human-pi_imple01');
