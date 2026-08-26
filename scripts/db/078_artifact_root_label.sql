-- 078: Label for the artifact_root field on the flow editor.
--
-- Companion to Run 040 / D1 (routers/bridge.py gains artifact_root in
-- bridge_v2_update_flow's updatable list, with empty -> NULL). The frontend
-- editor (handoff 152) will reference this label key at the same shape as
-- the target-project label (lbl_bridge_flow_target_project, seeded by
-- migration 018) and the harness-field labels (LBL-1000505..LBL-1000509,
-- seeded by migration 076). init_db.py seeds the en-US/da-DK/de-DE/sv-SE
-- translations on fresh installs; THIS migration carries the es-ES
-- translation (init_db.py has no es-ES — see TG2).
--
-- The label mirrors lbl_bridge_flow_target_project:
--   LBL-1000510  lbl_bridge_flow_artifact_root
--
-- Idempotent: INSERT OR IGNORE throughout.

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000510', 'lbl_bridge_flow_artifact_root', 'main',
     'Artifact Root',
     'Flow edit form: free-text artifact root (where run artifacts live). Empty = the flow key is the root.', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000510', 'en-US', 'Artifact Root', 1),
    ('LBL-1000510', 'da-DK', 'Artifact-rod', 1),
    ('LBL-1000510', 'de-DE', 'Artefakt-Stammverzeichnis', 1),
    ('LBL-1000510', 'es-ES', 'Raíz de artefactos', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_artifact_root', 'Flow edit form: artifact root field label');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_artifact_root', 'lbl_bridge_flow_artifact_root');
