-- 050: Labels for the flow-card sub-panels (Manage Roles button + the
-- missing-role-definition marker in the flow-scoped roles list).
-- Companion to the dpmtf-app.js change that replaced Manage Steps'
-- jump-to-Setup with inline sub-panels on the flow card.
--
-- Idempotent: INSERT OR IGNORE throughout.

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000498', 'lbl_bridge_manage_roles', 'main', 'Manage Roles', 'Flow card: open the flow-scoped roles sub-panel', 1),
    ('LBL-1000499', 'lbl_bridge_role_missing', 'main', 'No role definition', 'Flow roles sub-panel: a step names a role with no bridge_roles row', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000498', 'en-US', 'Manage Roles', 1),
    ('LBL-1000498', 'da-DK', 'Administrér roller', 1),
    ('LBL-1000498', 'de-DE', 'Rollen verwalten', 1),
    ('LBL-1000498', 'es-ES', 'Gestionar roles', 1),
    ('LBL-1000499', 'en-US', 'No role definition', 1),
    ('LBL-1000499', 'da-DK', 'Ingen rolledefinition', 1),
    ('LBL-1000499', 'de-DE', 'Keine Rollendefinition', 1),
    ('LBL-1000499', 'es-ES', 'Sin definición de rol', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_manage_roles', 'Flow card: open the flow-scoped roles sub-panel'),
    ('lbl_bridge_role_missing', 'Flow roles sub-panel: step names a role with no definition');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_manage_roles', 'lbl_bridge_manage_roles'),
    ('lbl_bridge_role_missing', 'lbl_bridge_role_missing');
