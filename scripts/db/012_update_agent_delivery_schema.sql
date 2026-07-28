-- Update agent_delivery validation_schema to match human_delivery format
-- Migration 012: Update agent_delivery validation_schema

UPDATE bridge_convention_rules 
SET validation_schema = '["<handoff_id>", "<source_role>", "<deliverable_input>"]'
WHERE rule_key = 'agent_delivery';