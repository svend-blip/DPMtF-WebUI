-- 053: Labels for the flow implementation_mode dropdown (Bridge Flows
-- edit form). Companion to the dpmtf-app.js + routers/bridge.py change
-- that exposes the Deterministic Patcher opt-in (migration 052's
-- bridge_flows.implementation_mode) at flow level in the WebUI.
--
-- Idempotent: INSERT OR IGNORE throughout.

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000500', 'lbl_bridge_flow_implementation_mode', 'main',
     'Implementation Mode',
     'Flow edit form: label for the implementation_mode dropdown', 1),
    ('LBL-1000501', 'lbl_bridge_flow_implementation_mode_inherit', 'main',
     'Inherit (default: direct)',
     'Flow edit form: dropdown option for NULL = inherit', 1),
    ('LBL-1000502', 'lbl_bridge_flow_implementation_mode_direct', 'main',
     'Direct edit',
     'Flow edit form: dropdown option for implementation_mode = direct', 1),
    ('LBL-1000503', 'lbl_bridge_flow_implementation_mode_patch', 'main',
     'Deterministic Patcher',
     'Flow edit form: dropdown option for implementation_mode = deterministic_patch', 1),
    ('LBL-1000504', 'lbl_bridge_flow_implementation_mode_help', 'main',
     'Deterministic Patcher routes this flow''s dispatched roles through the patcher (governance file 102). Step and role level overrides are database-only.',
     'Flow edit form: help text under the implementation_mode dropdown', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000500', 'en-US', 'Implementation Mode', 1),
    ('LBL-1000500', 'da-DK', 'Implementeringstilstand', 1),
    ('LBL-1000500', 'de-DE', 'Implementierungsmodus', 1),
    ('LBL-1000500', 'es-ES', 'Modo de implementación', 1),

    ('LBL-1000501', 'en-US', 'Inherit (default: direct)', 1),
    ('LBL-1000501', 'da-DK', 'Nedarv (standard: direct)', 1),
    ('LBL-1000501', 'de-DE', 'Erben (Standard: direct)', 1),
    ('LBL-1000501', 'es-ES', 'Heredar (predeterminado: direct)', 1),

    ('LBL-1000502', 'en-US', 'Direct edit', 1),
    ('LBL-1000502', 'da-DK', 'Direkte redigering', 1),
    ('LBL-1000502', 'de-DE', 'Direkte Bearbeitung', 1),
    ('LBL-1000502', 'es-ES', 'Edición directa', 1),

    ('LBL-1000503', 'en-US', 'Deterministic Patcher', 1),
    ('LBL-1000503', 'da-DK', 'Deterministisk patcher', 1),
    ('LBL-1000503', 'de-DE', 'Deterministischer Patcher', 1),
    ('LBL-1000503', 'es-ES', 'Parcheador determinista', 1),

    ('LBL-1000504', 'en-US',
     'Deterministic Patcher routes this flow''s dispatched roles through the patcher (governance file 102). Step and role level overrides are database-only.', 1),
    ('LBL-1000504', 'da-DK',
     'Deterministisk patcher sender dette flows dispatchede roller gennem patcheren (governance-fil 102). Step- og rolleniveau-overrides findes kun i databasen.', 1),
    ('LBL-1000504', 'de-DE',
     'Der deterministische Patcher leitet die Rollen dieses Workflows durch den Patcher (Governance-Datei 102). Overrides auf Schritt- und Rollenebene sind nur in der Datenbank verfügbar.', 1),
    ('LBL-1000504', 'es-ES',
     'El parcheador determinista dirige los roles despachados de este flujo a través del parcheador (archivo de gobernanza 102). Los ajustes a nivel de paso y rol solo están disponibles en la base de datos.', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_implementation_mode', 'Flow edit form: implementation_mode dropdown label'),
    ('lbl_bridge_flow_implementation_mode_inherit', 'Flow edit form: implementation_mode inherit option'),
    ('lbl_bridge_flow_implementation_mode_direct', 'Flow edit form: implementation_mode direct option'),
    ('lbl_bridge_flow_implementation_mode_patch', 'Flow edit form: implementation_mode deterministic_patch option'),
    ('lbl_bridge_flow_implementation_mode_help', 'Flow edit form: implementation_mode help text');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_implementation_mode', 'lbl_bridge_flow_implementation_mode'),
    ('lbl_bridge_flow_implementation_mode_inherit', 'lbl_bridge_flow_implementation_mode_inherit'),
    ('lbl_bridge_flow_implementation_mode_direct', 'lbl_bridge_flow_implementation_mode_direct'),
    ('lbl_bridge_flow_implementation_mode_patch', 'lbl_bridge_flow_implementation_mode_patch'),
    ('lbl_bridge_flow_implementation_mode_help', 'lbl_bridge_flow_implementation_mode_help');
