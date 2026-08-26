-- 076: Labels for the harness fields at role and step level.
--
-- Companion to Run 038 / D1 (routers/bridge.py gains default_harness_source /
-- default_harness_profile on bridge_roles and harness_source / harness_profile
-- on bridge_flow_steps in its updatable list / field_map). The frontend
-- references the harness fields via these label keys at the same shape as
-- the model-field labels (lbl_bridge_default_model_source et al., migration
-- 036). init_db.py seeds the en-US/da-DK/de-DE/sv-SE translations on fresh
-- installs; THIS migration carries the es-ES translations (init_db.py has
-- no es-ES — see TG2).
--
-- The five labels mirror the model-field labels one-for-one:
--   LBL-1000505  lbl_bridge_default_harness_source
--   LBL-1000506  lbl_bridge_default_harness_profile
--   LBL-1000507  lbl_bridge_step_harness_source
--   LBL-1000508  lbl_bridge_step_harness_profile
--   LBL-1000509  lbl_bridge_step_harness_source_inherit
--
-- Idempotent: INSERT OR IGNORE throughout.

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000505', 'lbl_bridge_default_harness_source', 'main',
     'Default Harness Source',
     'Role default harness source input', 1),
    ('LBL-1000506', 'lbl_bridge_default_harness_profile', 'main',
     'Default Harness Profile',
     'Role default harness profile input', 1),
    ('LBL-1000507', 'lbl_bridge_step_harness_source', 'main',
     'Step Harness Source',
     'Step harness source input', 1),
    ('LBL-1000508', 'lbl_bridge_step_harness_profile', 'main',
     'Step Harness Profile',
     'Step harness profile input', 1),
    ('LBL-1000509', 'lbl_bridge_step_harness_source_inherit', 'main',
     'Inherit from role',
     'Step harness source inherit option', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000505', 'en-US', 'Default Harness Source', 1),
    ('LBL-1000505', 'da-DK', 'Standard harness-kilde', 1),
    ('LBL-1000505', 'de-DE', 'Standard-Harness-Quelle', 1),
    ('LBL-1000505', 'es-ES', 'Fuente de harness predeterminada', 1),

    ('LBL-1000506', 'en-US', 'Default Harness Profile', 1),
    ('LBL-1000506', 'da-DK', 'Standard harness-profil', 1),
    ('LBL-1000506', 'de-DE', 'Standard-Harness-Profil', 1),
    ('LBL-1000506', 'es-ES', 'Perfil de harness predeterminado', 1),

    ('LBL-1000507', 'en-US', 'Step Harness Source', 1),
    ('LBL-1000507', 'da-DK', 'Trin harness-kilde', 1),
    ('LBL-1000507', 'de-DE', 'Schritt-Harness-Quelle', 1),
    ('LBL-1000507', 'es-ES', 'Fuente de harness del paso', 1),

    ('LBL-1000508', 'en-US', 'Step Harness Profile', 1),
    ('LBL-1000508', 'da-DK', 'Trin harness-profil', 1),
    ('LBL-1000508', 'de-DE', 'Schritt-Harness-Profil', 1),
    ('LBL-1000508', 'es-ES', 'Perfil de harness del paso', 1),

    ('LBL-1000509', 'en-US', 'Inherit from role', 1),
    ('LBL-1000509', 'da-DK', 'Nedarv fra rolle', 1),
    ('LBL-1000509', 'de-DE', 'Von Rolle erben', 1),
    ('LBL-1000509', 'es-ES', 'Heredar del rol', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_default_harness_source', 'Role default harness source input'),
    ('lbl_bridge_default_harness_profile', 'Role default harness profile input'),
    ('lbl_bridge_step_harness_source', 'Step harness source input'),
    ('lbl_bridge_step_harness_profile', 'Step harness profile input'),
    ('lbl_bridge_step_harness_source_inherit', 'Step harness source inherit option');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_default_harness_source', 'lbl_bridge_default_harness_source'),
    ('lbl_bridge_default_harness_profile', 'lbl_bridge_default_harness_profile'),
    ('lbl_bridge_step_harness_source', 'lbl_bridge_step_harness_source'),
    ('lbl_bridge_step_harness_profile', 'lbl_bridge_step_harness_profile'),
    ('lbl_bridge_step_harness_source_inherit', 'lbl_bridge_step_harness_source_inherit');
