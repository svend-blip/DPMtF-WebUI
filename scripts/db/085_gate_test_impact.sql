-- 085: Gate-test-impact pre-dispatch wire on 1000-02-ELOOP implementer-reviewer.
--
-- Registers the 'gate-test-impact' script key in bridge_scripts and wires it
-- as the pre_dispatch_script on the implementer-reviewer step of the ELOOP
-- flow. Runs in WARN mode; the step configuration does not switch to block.
--
-- TWO statements, both required:
--
-- (1) Register the script key in bridge_scripts (idempotent: INSERT OR IGNORE).
--
-- (2) Append the key to pre_dispatch_script on the ELOOP implementer-reviewer
--     step using an append-safe CASE expression so existing keys are preserved.

INSERT OR IGNORE INTO bridge_scripts
    (script_key, name, description, path, stage, params_required, is_active)
VALUES
    ('gate-test-impact',
     'Test Impact Pre-Dispatch Gate',
     'Deterministic test impact gate: policy -> changes -> plan -> run -> evidence',
     'scripts/bridgeV002/gate-test-impact.py',
     'pre',
     '--flow-key,--step-key,--from-role,--to-role,--deliverable-dir,--deliverable-pattern,--deliverable-file,--handoff-id,--bridge-dir,--prompt-template,--mode',
     1);

UPDATE bridge_flow_steps
SET pre_dispatch_script = CASE
    WHEN pre_dispatch_script IS NULL OR pre_dispatch_script = ''
        THEN 'gate-test-impact'
    WHEN pre_dispatch_script NOT LIKE '%gate-test-impact%'
        THEN pre_dispatch_script || ',gate-test-impact'
    ELSE pre_dispatch_script
END
WHERE flow_key = '1000-02-ELOOP'
  AND step_key = 'implementer-reviewer';
