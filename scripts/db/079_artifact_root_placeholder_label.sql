-- 079: The missing placeholder label for the artifact_root field.
--
-- Run 040 seeded lbl_bridge_flow_artifact_root (migration 078) and then, in a
-- later handoff, built the frontend control. That control calls lbl() at two
-- sites: once for the field label, and once for the input's placeholder —
--
--     lbl("lbl_bridge_flow_artifact_root_placeholder",
--         "Empty = flow key is the root")
--
-- The second key was never seeded, because the migration was written before
-- the frontend that invented it existed. The lbl() fallback then hid the gap
-- perfectly: the placeholder renders, in English, in every locale. That is
-- CODING_STANDARD auto-fail #2 (hardcoded English reaching the user) and a
-- breach of the four-mandatory-locale rule, and no testgoal could catch it —
-- run 040's TG3 names one label key explicitly, so it measured the label that
-- was seeded and stayed silent about the one that was not.
--
-- The lesson is worth more than the fix: when a run seeds i18n in one handoff
-- and writes the frontend in another, the criterion must measure the UNION of
-- the keys the frontend calls, not a key list written in advance.
--
-- Mirrors migration 078 exactly — all four i18n layers, all four mandatory
-- locales (en-US, da-DK, de-DE, es-ES).
--
--   LBL-1000511  lbl_bridge_flow_artifact_root_placeholder
--
-- Idempotent: INSERT OR IGNORE throughout.

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000511', 'lbl_bridge_flow_artifact_root_placeholder', 'main',
     'Empty = flow key is the root',
     'Flow edit form: placeholder for the artifact root input. Explains that leaving the field empty makes the flow key itself the artifact root.', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000511', 'en-US', 'Empty = flow key is the root', 1),
    ('LBL-1000511', 'da-DK', 'Tom = flow-nøglen er roden', 1),
    ('LBL-1000511', 'de-DE', 'Leer = der Flow-Schlüssel ist die Wurzel', 1),
    ('LBL-1000511', 'es-ES', 'Vacío = la clave del flujo es la raíz', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_artifact_root_placeholder', 'Flow edit form: artifact root input placeholder');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_artifact_root_placeholder', 'lbl_bridge_flow_artifact_root_placeholder');
