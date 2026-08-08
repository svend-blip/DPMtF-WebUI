-- 037: close the remaining en-US and de-DE gaps.
--
-- After 036 the completeness tool still reported 51 incomplete labels:
-- 51 missing de-DE (the lbl_alloc_* family and system_setup checks
-- predate the de-DE seed), 25 of them also missing en-US. en-US rows
-- are promoted from default_text, which is English project-wide; de-DE
-- is authored. Same NOT EXISTS idempotency as 036.

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Aliase', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_aliases' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', '''{name}'' löschen?', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_confirm_delete' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Löschen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_delete' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Detail', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_detail' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Fehler', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Client-Aliase', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_client_aliases' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Clients', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_clients' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Konfigurationsverzeichnis', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_config_dir' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Kontext', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_context' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Standard-Alias', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_default_alias' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Lebenszyklus-Richtlinie', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_lifecycle' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Reales Modell', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Modellpfad', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_model_path' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Name', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Laufzeitprofil', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Allocator-Konfiguration konnte nicht geladen werden', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_load_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Name erforderlich', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_name_required' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', '+ Neuer Alias', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_new_alias' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', '+ Neue Rolle', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_new_role' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Laufzeitprofile (schreibgeschützt)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_profiles' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Rollen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_roles' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Speichern', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_save' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Gespeichert', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_saved' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Wählen Sie einen Alias oder eine Rolle zum Bearbeiten', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_select_hint' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'default_model', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'default_model', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'default_provider', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_provider' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'default_provider', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_provider' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'default_runtime', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_runtime' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'default_runtime', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_runtime' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Edit Flow', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_edit_flow' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Flow bearbeiten', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_edit_flow' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Alle Daten exportieren', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_export_all_data' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Use Machine Profile for start commands', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_use_machine_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Maschinenprofil für Startbefehle verwenden', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_use_machine_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Checking Machine Profile...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_checking' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Maschinenprofil wird geprüft...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_checking' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Machine Profile missing — create profile in System Setup before activating.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_missing' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Maschinenprofil fehlt — Profil in der Systemeinrichtung erstellen, bevor aktiviert wird.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_missing' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Machine Profile has JSON error — fix profile before activating.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_parse_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Maschinenprofil hat einen JSON-Fehler — Profil vor der Aktivierung korrigieren.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_parse_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Machine Profile schema_version mismatch — update profile before activating.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_schema_mismatch' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'schema_version des Maschinenprofils stimmt nicht überein — Profil vor der Aktivierung aktualisieren.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_schema_mismatch' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', '🧩 Model Allocator', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_allocator' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Machine', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_machine' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Maschine', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_machine' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'No checks returned', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_no_checks' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Keine Prüfungen zurückgegeben', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_no_checks' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'JSON parse error in profile', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_parse_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'JSON-Fehler im Profil', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_parse_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Profile', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Profil', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Ready. Click a check button to run.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_ready' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Bereit. Klicken Sie auf eine Prüftaste, um zu starten.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_ready' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run binaries', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_binaries' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Binärdateien prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_binaries' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run ollama', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_ollama' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Ollama prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_ollama' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run paths', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_paths' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Pfade prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_paths' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run ports', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_ports' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Ports prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_ports' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run profile', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Profil prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run providers', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_providers' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Anbieter prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_providers' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run secrets', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_secrets' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Secrets prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_secrets' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Run tmux', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_tmux' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'tmux prüfen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_tmux' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Running checks...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_running' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Prüfungen laufen...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_running' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Schema', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_schema' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Schema', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_schema' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'en-US', 'Status', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'en-US');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'de-DE', 'Status', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'de-DE');
