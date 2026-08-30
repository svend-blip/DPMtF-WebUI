-- 089: i18n for the role editor's allocator fields (2026-08-30 alignment).
--
-- Four bridge_roles columns that could only be set by direct SQL become
-- frontend-editable (allocator_client, execution_target,
-- fresh_session_command, codex_fresh_context_policy), and config_dir gets
-- a rendered read-only-style display with an explanation. Every field the
-- UI does NOT edit now says WHY in its help text — the Human rule is that
-- an absent field must be well-founded, not accidental.
--
-- 4-layer chain, 4 mandatory locales. Idempotent: INSERT OR IGNORE.

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_allocator_client',        'Role edit: allocator client field'),
    ('lbl_bridge_allocator_client_help',   'Role edit: allocator client explanation'),
    ('lbl_bridge_execution_target',        'Role edit: execution target field'),
    ('lbl_bridge_execution_target_help',   'Role edit: execution target explanation'),
    ('lbl_bridge_fresh_session_command',   'Role edit: fresh session command field'),
    ('lbl_bridge_fresh_session_command_help', 'Role edit: fresh session command explanation'),
    ('lbl_bridge_codex_fresh_policy',      'Role edit: codex fresh-context policy field'),
    ('lbl_bridge_codex_fresh_policy_help', 'Role edit: codex fresh-context policy explanation'),
    ('lbl_bridge_config_dir',              'Role edit: config dir field'),
    ('lbl_bridge_config_dir_help',         'Role edit: config dir explanation'),
    ('lbl_bridge_harness_source_help',     'Role/step edit: harness source picker hint');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_allocator_client',        'lbl_bridge_allocator_client'),
    ('lbl_bridge_allocator_client_help',   'lbl_bridge_allocator_client_help'),
    ('lbl_bridge_execution_target',        'lbl_bridge_execution_target'),
    ('lbl_bridge_execution_target_help',   'lbl_bridge_execution_target_help'),
    ('lbl_bridge_fresh_session_command',   'lbl_bridge_fresh_session_command'),
    ('lbl_bridge_fresh_session_command_help', 'lbl_bridge_fresh_session_command_help'),
    ('lbl_bridge_codex_fresh_policy',      'lbl_bridge_codex_fresh_policy'),
    ('lbl_bridge_codex_fresh_policy_help', 'lbl_bridge_codex_fresh_policy_help'),
    ('lbl_bridge_config_dir',              'lbl_bridge_config_dir'),
    ('lbl_bridge_config_dir_help',         'lbl_bridge_config_dir_help'),
    ('lbl_bridge_harness_source_help',     'lbl_bridge_harness_source_help');

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000521', 'lbl_bridge_allocator_client', 'main', 'Allocator Client', 'Role edit: allocator client field', 1),
    ('LBL-1000522', 'lbl_bridge_allocator_client_help', 'main', 'Which client adapter model-allocator renders config for (e.g. opencode, claude-code). Must be allowed on the alias''s Harness list in model-allocator.', 'Role edit: allocator client explanation', 1),
    ('LBL-1000523', 'lbl_bridge_execution_target', 'main', 'Execution Target', 'Role edit: execution target field', 1),
    ('LBL-1000524', 'lbl_bridge_execution_target_help', 'main', 'Machine that runs this role. Empty = this machine (Father); a worker key routes execution to that LightWorker.', 'Role edit: execution target explanation', 1),
    ('LBL-1000525', 'lbl_bridge_fresh_session_command', 'main', 'Fresh Session Command', 'Role edit: fresh session command field', 1),
    ('LBL-1000526', 'lbl_bridge_fresh_session_command_help', 'main', 'Command dispatch sends to reset the session before injecting a prompt (e.g. /new for OpenCode). Empty = the harness''s default behavior.', 'Role edit: fresh session command explanation', 1),
    ('LBL-1000527', 'lbl_bridge_codex_fresh_policy', 'main', 'Codex Fresh-Context Policy', 'Role edit: codex fresh-context policy field', 1),
    ('LBL-1000528', 'lbl_bridge_codex_fresh_policy_help', 'main', 'codex only: work_unit restarts the harness between work units to release context (codex has no in-session reset); off keeps the session. Empty = inherit the global setting.', 'Role edit: codex fresh-context policy explanation', 1),
    ('LBL-1000529', 'lbl_bridge_config_dir', 'main', 'Config Dir', 'Role edit: config dir field', 1),
    ('LBL-1000530', 'lbl_bridge_config_dir_help', 'main', 'OpenCode config directory override (~/.config/opencode-roles/<dir>). Contract-bound: must match the role''s entry in model-allocator roles.yaml, so it is edited together with that file — not casually.', 'Role edit: config dir explanation', 1),
    ('LBL-1000531', 'lbl_bridge_harness_source_help', 'main', 'Pick from the harness-allocator roster, or type another key.', 'Role/step edit: harness source picker hint', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000521', 'en-US', 'Allocator Client', 1),
    ('LBL-1000521', 'da-DK', 'Allocator-klient', 1),
    ('LBL-1000521', 'de-DE', 'Allocator-Client', 1),
    ('LBL-1000521', 'es-ES', 'Cliente del asignador', 1),
    ('LBL-1000522', 'en-US', 'Which client adapter model-allocator renders config for (e.g. opencode, claude-code). Must be allowed on the alias''s Harness list in model-allocator.', 1),
    ('LBL-1000522', 'da-DK', 'Hvilken klient-adapter model-allocator renderer config for (fx opencode, claude-code). Skal være tilladt på aliasets Harness-liste i model-allocator.', 1),
    ('LBL-1000522', 'de-DE', 'Für welchen Client-Adapter model-allocator die Konfiguration rendert (z. B. opencode, claude-code). Muss auf der Harness-Liste des Alias in model-allocator erlaubt sein.', 1),
    ('LBL-1000522', 'es-ES', 'Para qué adaptador de cliente renderiza model-allocator la configuración (p. ej. opencode, claude-code). Debe estar permitido en la lista Harness del alias en model-allocator.', 1),
    ('LBL-1000523', 'en-US', 'Execution Target', 1),
    ('LBL-1000523', 'da-DK', 'Eksekverings-mål', 1),
    ('LBL-1000523', 'de-DE', 'Ausführungsziel', 1),
    ('LBL-1000523', 'es-ES', 'Destino de ejecución', 1),
    ('LBL-1000524', 'en-US', 'Machine that runs this role. Empty = this machine (Father); a worker key routes execution to that LightWorker.', 1),
    ('LBL-1000524', 'da-DK', 'Maskinen der kører rollen. Tom = denne maskine (Father); en worker-nøgle sender eksekveringen til den LightWorker.', 1),
    ('LBL-1000524', 'de-DE', 'Maschine, auf der diese Rolle läuft. Leer = diese Maschine (Father); ein Worker-Schlüssel leitet die Ausführung an diesen LightWorker.', 1),
    ('LBL-1000524', 'es-ES', 'Máquina que ejecuta este rol. Vacío = esta máquina (Father); una clave de worker dirige la ejecución a ese LightWorker.', 1),
    ('LBL-1000525', 'en-US', 'Fresh Session Command', 1),
    ('LBL-1000525', 'da-DK', 'Frisk-sessions-kommando', 1),
    ('LBL-1000525', 'de-DE', 'Befehl für frische Sitzung', 1),
    ('LBL-1000525', 'es-ES', 'Comando de sesión nueva', 1),
    ('LBL-1000526', 'en-US', 'Command dispatch sends to reset the session before injecting a prompt (e.g. /new for OpenCode). Empty = the harness''s default behavior.', 1),
    ('LBL-1000526', 'da-DK', 'Kommando dispatch sender for at nulstille sessionen før prompt-injektion (fx /new til OpenCode). Tom = harnessens standardadfærd.', 1),
    ('LBL-1000526', 'de-DE', 'Befehl, den dispatch vor der Prompt-Injektion zum Zurücksetzen der Sitzung sendet (z. B. /new für OpenCode). Leer = Standardverhalten des Harness.', 1),
    ('LBL-1000526', 'es-ES', 'Comando que dispatch envía para reiniciar la sesión antes de inyectar un prompt (p. ej. /new para OpenCode). Vacío = comportamiento por defecto del harness.', 1),
    ('LBL-1000527', 'en-US', 'Codex Fresh-Context Policy', 1),
    ('LBL-1000527', 'da-DK', 'Codex frisk-kontekst-politik', 1),
    ('LBL-1000527', 'de-DE', 'Codex-Frischkontext-Richtlinie', 1),
    ('LBL-1000527', 'es-ES', 'Política de contexto nuevo de Codex', 1),
    ('LBL-1000528', 'en-US', 'codex only: work_unit restarts the harness between work units to release context (codex has no in-session reset); off keeps the session. Empty = inherit the global setting.', 1),
    ('LBL-1000528', 'da-DK', 'Kun codex: work_unit genstarter harnessen mellem arbejdsenheder for at frigive kontekst (codex har ingen nulstilling i sessionen); off beholder sessionen. Tom = arv den globale indstilling.', 1),
    ('LBL-1000528', 'de-DE', 'Nur codex: work_unit startet den Harness zwischen Arbeitseinheiten neu, um Kontext freizugeben (codex hat kein Zurücksetzen innerhalb der Sitzung); off behält die Sitzung. Leer = globale Einstellung erben.', 1),
    ('LBL-1000528', 'es-ES', 'Solo codex: work_unit reinicia el harness entre unidades de trabajo para liberar contexto (codex no tiene reinicio dentro de la sesión); off mantiene la sesión. Vacío = heredar el ajuste global.', 1),
    ('LBL-1000529', 'en-US', 'Config Dir', 1),
    ('LBL-1000529', 'da-DK', 'Config-mappe', 1),
    ('LBL-1000529', 'de-DE', 'Config-Verzeichnis', 1),
    ('LBL-1000529', 'es-ES', 'Directorio de configuración', 1),
    ('LBL-1000530', 'en-US', 'OpenCode config directory override (~/.config/opencode-roles/<dir>). Contract-bound: must match the role''s entry in model-allocator roles.yaml, so it is edited together with that file — not casually.', 1),
    ('LBL-1000530', 'da-DK', 'OpenCode config-mappe-override (~/.config/opencode-roles/<dir>). Kontraktbundet: skal matche rollens post i model-allocator roles.yaml og redigeres derfor sammen med den fil — ikke i forbifarten.', 1),
    ('LBL-1000530', 'de-DE', 'OpenCode-Config-Verzeichnis-Override (~/.config/opencode-roles/<dir>). Vertragsgebunden: muss dem Eintrag der Rolle in model-allocator roles.yaml entsprechen und wird daher zusammen mit dieser Datei bearbeitet — nicht beiläufig.', 1),
    ('LBL-1000530', 'es-ES', 'Directorio de configuración de OpenCode (~/.config/opencode-roles/<dir>). Vinculado por contrato: debe coincidir con la entrada del rol en roles.yaml de model-allocator, por lo que se edita junto con ese archivo — no a la ligera.', 1),
    ('LBL-1000531', 'en-US', 'Pick from the harness-allocator roster, or type another key.', 1),
    ('LBL-1000531', 'da-DK', 'Vælg fra harness-allocatorens roster, eller skriv en anden nøgle.', 1),
    ('LBL-1000531', 'de-DE', 'Aus dem Roster des harness-allocator wählen oder einen anderen Schlüssel eingeben.', 1),
    ('LBL-1000531', 'es-ES', 'Elija del roster del harness-allocator o escriba otra clave.', 1);
