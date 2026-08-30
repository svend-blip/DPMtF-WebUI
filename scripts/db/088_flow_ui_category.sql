-- 088: bridge_flows.ui_category — which flows panel a flow renders in.
--
-- 'standard' flows render in the Flows panel (Daily, after 087);
-- 'experimental' flows render in the Experimental Flows panel. The trade
-- cockpit flows are atypical (cron-driven, MCP-push) and move there
-- (Human decision 2026-08-30). The category is data, editable in the
-- flow edit form, so future reclassification is a frontend action —
-- not a code change.
--
-- migrate.py records applied filenames, so the ALTER runs once per
-- database; the seed statements are INSERT OR IGNORE / converging UPDATE.

ALTER TABLE bridge_flows ADD COLUMN ui_category TEXT NOT NULL DEFAULT 'standard';

UPDATE bridge_flows
   SET ui_category = 'experimental'
 WHERE flow_key LIKE 'trade_cockpit_%';

-- ── i18n for the flow edit field (LBL-1000518 .. LBL-1000520) ───────
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_ui_category', 'Flow edit: UI category field label');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_ui_category', 'lbl_bridge_flow_ui_category');

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000518', 'lbl_bridge_flow_ui_category', 'main', 'UI category', 'Flow edit: UI category field label', 1),
    ('LBL-1000519', 'lbl_bridge_ui_category_standard', 'main', 'Standard', 'Flow UI category option: standard', 1),
    ('LBL-1000520', 'lbl_bridge_ui_category_experimental', 'main', 'Experimental', 'Flow UI category option: experimental', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000518', 'en-US', 'UI category', 1),
    ('LBL-1000518', 'da-DK', 'UI-kategori', 1),
    ('LBL-1000518', 'de-DE', 'UI-Kategorie', 1),
    ('LBL-1000518', 'es-ES', 'Categoría de UI', 1),
    ('LBL-1000519', 'en-US', 'Standard', 1),
    ('LBL-1000519', 'da-DK', 'Standard', 1),
    ('LBL-1000519', 'de-DE', 'Standard', 1),
    ('LBL-1000519', 'es-ES', 'Estándar', 1),
    ('LBL-1000520', 'en-US', 'Experimental', 1),
    ('LBL-1000520', 'da-DK', 'Eksperimentel', 1),
    ('LBL-1000520', 'de-DE', 'Experimentell', 1),
    ('LBL-1000520', 'es-ES', 'Experimental', 1);
