-- 117 — A fresh install and the live database hold the same system data.
--
-- Measured 2026-09-20, after init_db.py had been put in the order the live
-- database grew in (baseline, seeds, then every other migration): the schema
-- of a fresh install was identical to the live one, and the system data still
-- differed in six places. Each is corrected here in the direction of the
-- side that was right, and every statement is a no-op where the data is
-- already in that form, so the migration does nothing twice.
--
-- 1. Convention rules `callback` and `json_output` existed only in the live
--    database (created by hand on 2026-06-19 and 2026-07-05; migrations 057,
--    059 and 100 update them and found nothing to update on a fresh install).
--    Copied verbatim from the live rows. Neither names a machine path.
--
-- 2. `technical_review` in the live database still told the reviewer to
--    escalate with `--db-flow FLOW ... --to-role archi01`; a fresh install has
--    the `{flow_key}` / `{escalation_role}` placeholders that migration 034
--    introduced and dispatch.py renders. The live row is brought to the
--    placeholder form. `verdict.error_template` is brought to the seeded text.
--
-- 3. Migration 038 retired three duplicate labels (lbl_bridge_step_add,
--    lbl_alloc_delete, lbl_alloc_save) and rebound their slots to the labels
--    it kept. init_db.py seeded labels with INSERT OR REPLACE and no
--    is_active, so its next run re-activated all three and bound each slot a
--    second time: the live database has two labels on each of those slots and
--    the i18n API returns whichever row comes last. 038 is applied again; the
--    seed is corrected in init_db.py in the same commit.
--
-- 4. LBL-1000540 (lbl_bridge_flow_supervisor_role, migration 096) is missing
--    from the live database although 096 is recorded as applied and its slot
--    and mapping are there; the flow editor has shown the fallback text since.
--    Restored.
--
-- 5. Six step-form slots whose labels (LBL-1000277..282) are seeded existed
--    only in the live database; on a fresh install the labels could not be
--    reached.
--
-- 6. LBL-1000319..329 (System Setup) carried the texts of the role editor's
--    model fields in en-US, de-DE, es-ES and sv-SE in the live database —
--    "Default Model Source" under system_setup_machine_profile. A fresh
--    install had no en-US, de-DE or sv-SE text for them at all, and the es-ES
--    text migration 036 had translated from the wrong English. All four are
--    set to what the key and the Danish text say.
--
-- Deliberately NOT copied from the live database:
--   - flows, roles, steps, id counters and knowledge grants: installation
--     data (and the core flows name machine paths);
--   - 216 el-GR translations added through the UI (an optional locale);
--   - six labels no code refers to (lbl_bridge_restart_*, lbl_btn_create_
--     project_plan, lbl_panel_prompt_sequences);
--   - fifteen slots bound to labels that exist in neither database;
--   - endpoint_registry / bootstrap_dataset_registry / phase_status rows that
--     describe tables migration 002 dropped.
--
-- Rollback: rollbacks/117_fresh_install_matches_live_rollback.sql

-- 1. Convention rules.
INSERT OR IGNORE INTO bridge_convention_rules
    (rule_key, step_type, dir_template, pattern_template, error_template, prompt_template, content_template, validation_schema, rule_type)
VALUES (
    'callback',
    'Callback',
    'results',
    '{ID}-result.md',
    'Failed to deliver callback to {to_role}.',
    '',
    '<handoff_id>{handoff_id}</handoff_id>

<source_role>{source_role}</source_role>

<deliverable_input>
  {bridge_dir}/{artifact_root}/results/{handoff_id}-result.md
  {bridge_dir}/{artifact_root}/results/{handoff_id}-notification.md
</deliverable_input>

<deliverable_output>
  verdict: {bridge_dir}/{artifact_root}/verdicts/{handoff_id}-verdict.md
  commit_msg (if APPROVED): {bridge_dir}/{artifact_root}/verdicts/{handoff_id}-commit-message.md
</deliverable_output>

<verdict_summary>
status: {verdict_status}
{verdict_lines}
work_item: {work_item}
</verdict_summary>

<next_action>
{next_action}
</next_action>

<stop>
you have every fact you need; do not read the repository; at most 6 tool calls
</stop>

<dispatch_command>
  escalation: python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role {next_role} --to-role {escalation_role} --id {handoff_id} --action signal-escalation
</dispatch_command>
',
    '["<handoff_id>", "<source_role>", "<deliverable_input>", "<deliverable_output>"]',
    'callback_content'
);

INSERT OR IGNORE INTO bridge_convention_rules
    (rule_key, step_type, dir_template, pattern_template, error_template, prompt_template, content_template, validation_schema, rule_type)
VALUES (
    'json_output',
    'JsonOutput',
    'inbox/pending',
    '{ID}_{role_key}.json',
    'JSON output for {to_role} missing or invalid',
    '',
    '<json_output>
<role>{next_role}</role>
<flow_run_id>{flow_run_id}</flow_run_id>
<flow_key>{flow_key}</flow_key>
<output_type>{output_type}</output_type>

<task>
You are {next_role} in the {flow_key} flow (run {flow_run_id}).

The previous role {source_role} has written its output to:
  {previous_deliverable_path}

Read that file, then execute your role exactly as defined in your governance
file (provided separately by the dispatch system).

Write YOUR output to this exact path:
  {deliverable_dir}/{output_file}

Required JSON wrapper fields (trade_output_v001, or your flow''s schema):
  flow_run_id: "{flow_run_id}"
  flow_key: "{flow_key}"
  role_key: "{next_role}"
  model_name: "{model_name}"
  created_at: (ISO-8601 datetime with timezone, e.g. 2026-06-28T08:57:00+02:00)
  output_type: "{output_type}"
  status: "completed"   (or "needs_more_data" if a required prior output is missing)
  payload: MUST be a JSON object (never an array — the import gate
    rejects non-object payloads); role-specific fields per your
    governance file
  quality.data_quality: MUST be exactly one of: high, medium, low, insufficient
    (no other values — the import gate rejects the whole file otherwise;
    if the data situation is catastrophic, use "insufficient" and explain
    in quality.warnings)
</task>

<constraint>
- Honor your flow''s safety invariants (for trade flows: SIMULATION_ONLY = TRUE — no real orders, no broker execution)
- Follow your role-specific gates from your governance file
- If a required prior output is missing, emit status "needs_more_data"
- Write valid JSON only — the import pipeline rejects malformed files
- Allowed decisions only — see your governance file for your role''s allowed decisions
</constraint>

<notification>
Your JSON output will be imported and used by the next role in the chain.
</notification>

<output_writing_discipline>
Write your output JSON file in ONE single Write tool operation — you run
with --bare and right-sized context, so one complete write fits the budget.
NEVER write the file via shell heredocs (cat << EOF) or echo redirection;
truncated shell writes have produced broken half-written outputs. Keep
prose minimal and pipe any web-search output through `head -60`.
</output_writing_discipline>
<output_validation_gate>
MANDATORY before signaling completion — validate the file you just wrote:

    python3 -c "import json; d=json.load(open(''{deliverable_dir}/{output_file}'')); print(''VALID'', d[''status''], len(str(d)))"

Then verify the content is COMPLETE: every item your governance file
requires from the input (e.g. one entry per symbol/candidate you received)
must be present in the file ON DISK. If validation fails or items are
missing, REWRITE the entire file with one Write operation and validate
again. NEVER run signal-complete until validation prints VALID. Reporting
completion while the file on disk is invalid or incomplete breaks the
entire chain.
</output_validation_gate>
<chain_advancement>
After writing your output JSON to the path above, you MUST signal completion
so the bridge dispatches the next role in the chain. Run this exact command:

    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py enqueue \
      --flow {flow_key} --from-role {next_role} --to-role {next_role} \
      --id {flow_run_id} --action signal-complete \
      > /tmp/bridge-signal-{flow_run_id}.log 2>&1 &

{flow_key}, {next_role}, and {flow_run_id} are already resolved for you —
substitute nothing. The command runs in the background (nohup + &) so your turn ends
immediately — dispatch.py''s post-dispatch step can hang and must never
block you. Progress is written to /tmp/bridge-signal-{flow_run_id}.log.
Do NOT skip this step — without signal-complete, the next role is never
dispatched and the chain stalls. (If you are the final role in the flow,
signal-complete marks the run complete.)
</chain_advancement>
</json_output>',
    '',
    'json_output_content'
);

-- 2. technical_review: placeholders, not a flow and a role by name.
UPDATE bridge_convention_rules
SET content_template = replace(
        content_template,
        '--db-flow FLOW --signal-escalation --from-role {next_role} --to-role archi01',
        '--db-flow {flow_key} --signal-escalation --from-role {next_role} --to-role {escalation_role}'
    ),
    updated_at = datetime('now')
WHERE rule_key = 'technical_review'
  AND content_template LIKE '%--db-flow FLOW --signal-escalation --from-role {next_role} --to-role archi01%';

UPDATE bridge_convention_rules
SET error_template = 'Failed to deliver verdict to {to_role}.', updated_at = datetime('now')
WHERE rule_key = 'verdict'
  AND error_template = 'Failed to deliver verdict. Present to Human manually.';

-- 3. Migration 038 again. The kept binding already exists wherever 038 ran,
--    so the duplicate binding is removed rather than renamed into a UNIQUE
--    conflict; where only the duplicate exists it is rebound as 038 did.
DELETE FROM ui_text_slot_labels
 WHERE (slot_key, label_key) IN (('lbl_bridge_step_add', 'lbl_bridge_step_add'),
                                 ('lbl_alloc_delete',    'lbl_alloc_delete'),
                                 ('lbl_alloc_save',      'lbl_alloc_save'))
   AND EXISTS (SELECT 1 FROM ui_text_slot_labels k
                WHERE k.slot_key = ui_text_slot_labels.slot_key
                  AND k.label_key != ui_text_slot_labels.label_key);
UPDATE ui_text_slot_labels SET label_key = 'lbl_btn_add_step'  WHERE label_key = 'lbl_bridge_step_add';
UPDATE ui_text_slot_labels SET label_key = 'lbl_bridge_delete' WHERE label_key = 'lbl_alloc_delete';
UPDATE ui_text_slot_labels SET label_key = 'lbl_bridge_save'   WHERE label_key = 'lbl_alloc_save';
UPDATE ui_labels SET is_active = 0, updated_at = datetime('now')
 WHERE label_key IN ('lbl_bridge_step_add', 'lbl_alloc_delete', 'lbl_alloc_save') AND is_active != 0;

-- 4. LBL-1000540, as migration 096 wrote it.
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_supervisor_role', 'Flow form: supervisor role field label (SUPERVISOR_PLANNING wake-up target)');
INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_supervisor_role', 'lbl_bridge_flow_supervisor_role');
INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000540', 'lbl_bridge_flow_supervisor_role', 'main',
     'Supervisor role (wake-up target)',
     'Flow edit form: the role key the stall watchdog wakes for this flow (bridge_flows.supervisor_role, migration 061).', 1);
INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000540', 'en-US', 'Supervisor role (wake-up target)', 1),
    ('LBL-1000540', 'da-DK', 'Supervisor-rolle (wake-up-mål)', 1),
    ('LBL-1000540', 'de-DE', 'Supervisor-Rolle (Wake-up-Ziel)', 1),
    ('LBL-1000540', 'es-ES', 'Rol de supervisor (destino del wake-up)', 1);

-- 5. Step-form slots for labels LBL-1000277..282.
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_select_flow', 'Flow selector placeholder'),
    ('lbl_bridge_step_form_title', 'Step form title'),
    ('lbl_bridge_rule_key', 'Step form: convention rule'),
    ('lbl_bridge_script_pre', 'Step form: pre-script'),
    ('lbl_bridge_script_post', 'Step form: post-script'),
    ('lbl_bridge_auto_filled', 'Step form: auto-filled marker');
INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_select_flow', 'lbl_bridge_select_flow'),
    ('lbl_bridge_step_form_title', 'lbl_bridge_step_form_title'),
    ('lbl_bridge_rule_key', 'lbl_bridge_rule_key'),
    ('lbl_bridge_script_pre', 'lbl_bridge_script_pre'),
    ('lbl_bridge_script_post', 'lbl_bridge_script_post'),
    ('lbl_bridge_auto_filled', 'lbl_bridge_auto_filled');

-- 6. System Setup labels say what their keys say.
INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000319', 'en-US', 'Machine Profile', 1),
    ('LBL-1000319', 'de-DE', 'Maschinenprofil', 1),
    ('LBL-1000319', 'es-ES', 'Perfil de máquina', 1),
    ('LBL-1000320', 'en-US', 'Model Providers', 1),
    ('LBL-1000320', 'de-DE', 'Modellanbieter', 1),
    ('LBL-1000320', 'es-ES', 'Proveedores de modelos', 1),
    ('LBL-1000321', 'en-US', 'Role Runtime Config', 1),
    ('LBL-1000321', 'de-DE', 'Laufzeitkonfiguration der Rollen', 1),
    ('LBL-1000321', 'es-ES', 'Configuración de ejecución de roles', 1),
    ('LBL-1000322', 'en-US', 'Path Checks', 1),
    ('LBL-1000322', 'de-DE', 'Pfadprüfungen', 1),
    ('LBL-1000322', 'es-ES', 'Comprobaciones de rutas', 1),
    ('LBL-1000323', 'en-US', 'Port Checks', 1),
    ('LBL-1000323', 'de-DE', 'Port-Prüfungen', 1),
    ('LBL-1000323', 'es-ES', 'Comprobaciones de puertos', 1),
    ('LBL-1000324', 'en-US', 'Secrets Check', 1),
    ('LBL-1000324', 'de-DE', 'Secrets-Prüfung', 1),
    ('LBL-1000324', 'es-ES', 'Comprobación de secretos', 1),
    ('LBL-1000325', 'en-US', 'Tmux Session Check', 1),
    ('LBL-1000325', 'de-DE', 'Tmux-Sitzungsprüfung', 1),
    ('LBL-1000325', 'es-ES', 'Comprobación de sesiones tmux', 1),
    ('LBL-1000326', 'en-US', 'Ollama Model Check', 1),
    ('LBL-1000326', 'de-DE', 'Ollama-Modellprüfung', 1),
    ('LBL-1000326', 'es-ES', 'Comprobación de modelos de Ollama', 1),
    ('LBL-1000327', 'en-US', 'Migration', 1),
    ('LBL-1000327', 'de-DE', 'Migration', 1),
    ('LBL-1000327', 'es-ES', 'Migración', 1),
    ('LBL-1000328', 'en-US', 'No Machine Profile configured. Create profiles/machine.local.json or set DPMTF_MACHINE_PROFILE in .env. Existing DPMtF functionality is unchanged.', 1),
    ('LBL-1000328', 'de-DE', 'Kein Maschinenprofil konfiguriert. Erstellen Sie profiles/machine.local.json oder setzen Sie DPMTF_MACHINE_PROFILE in .env. Die bestehende DPMtF-Funktionalität bleibt unverändert.', 1),
    ('LBL-1000328', 'es-ES', 'No hay ningún perfil de máquina configurado. Cree profiles/machine.local.json o defina DPMTF_MACHINE_PROFILE en .env. La funcionalidad existente de DPMtF no cambia.', 1),
    ('LBL-1000329', 'en-US', 'Existing DPMtF functionality is unchanged.', 1),
    ('LBL-1000329', 'de-DE', 'Die bestehende DPMtF-Funktionalität bleibt unverändert.', 1),
    ('LBL-1000329', 'es-ES', 'La funcionalidad existente de DPMtF no cambia.', 1),
    ('LBL-1000319', 'sv-SE', 'Maskinprofil', 1),
    ('LBL-1000320', 'sv-SE', 'Modelleverantörer', 1),
    ('LBL-1000321', 'sv-SE', 'Körtidskonfiguration för roller', 1),
    ('LBL-1000322', 'sv-SE', 'Sökvägskontroller', 1),
    ('LBL-1000323', 'sv-SE', 'Portkontroller', 1),
    ('LBL-1000324', 'sv-SE', 'Kontroll av hemligheter', 1),
    ('LBL-1000325', 'sv-SE', 'Kontroll av tmux-sessioner', 1),
    ('LBL-1000326', 'sv-SE', 'Kontroll av Ollama-modeller', 1),
    ('LBL-1000327', 'sv-SE', 'Migrering', 1),
    ('LBL-1000328', 'sv-SE', 'Ingen maskinprofil konfigurerad. Skapa profiles/machine.local.json eller ange DPMTF_MACHINE_PROFILE i .env. Befintlig DPMtF-funktionalitet är oförändrad.', 1),
    ('LBL-1000329', 'sv-SE', 'Befintlig DPMtF-funktionalitet är oförändrad.', 1)
ON CONFLICT(label_id, locale) DO UPDATE
   SET translated_text = excluded.translated_text, is_active = 1, updated_at = datetime('now')
 WHERE ui_label_translations.translated_text != excluded.translated_text
    OR ui_label_translations.is_active != 1;
