-- 018: i18n seed for the flow Target Project field (4-layer, 4 locales).
--
-- Migration 016 added bridge_flows.target_project_path; the Bridge Flows
-- edit form exposes it. Every user-facing string must resolve through
-- ui_text_slots -> ui_text_slot_labels -> ui_labels -> ui_label_translations,
-- so lbl() has something to return besides its fallback.
--
-- Locales follow the current bridge-label norm: da-DK, de-DE, en-US, sv-SE.
--
-- Idempotent: INSERT OR IGNORE throughout.

-- ── Layer 3: the labels ────────────────────────────────────
INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active)
VALUES
    ('LBL-1000427', 'lbl_bridge_flow_target_project', 'main',
     'Target Project Path',
     'Flow edit form: absolute path to the repository the flow operates on', 1),
    ('LBL-1000428', 'lbl_bridge_flow_target_project_placeholder', 'main',
     'Empty = this project',
     'Flow edit form: placeholder for an unset target project path', 1),
    ('LBL-1000429', 'lbl_bridge_flow_target_project_help', 'main',
     'Absolute path to the repository this flow''s roles work in. Must exist. Leave empty for flows that operate on this project.',
     'Flow edit form: help text under the target project path field', 1);

-- ── Layer 4: translations ──────────────────────────────────
INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000427', 'en-US', 'Target Project Path', 1),
    ('LBL-1000427', 'da-DK', 'Sti til målprojekt', 1),
    ('LBL-1000427', 'de-DE', 'Pfad zum Zielprojekt', 1),
    ('LBL-1000427', 'sv-SE', 'Sökväg till målprojekt', 1),

    ('LBL-1000428', 'en-US', 'Empty = this project', 1),
    ('LBL-1000428', 'da-DK', 'Tom = dette projekt', 1),
    ('LBL-1000428', 'de-DE', 'Leer = dieses Projekt', 1),
    ('LBL-1000428', 'sv-SE', 'Tom = detta projekt', 1),

    ('LBL-1000429', 'en-US',
     'Absolute path to the repository this flow''s roles work in. Must exist. Leave empty for flows that operate on this project.', 1),
    ('LBL-1000429', 'da-DK',
     'Absolut sti til det repository, som dette flows roller arbejder i. Stien skal findes. Lad feltet være tomt for flows, der arbejder på dette projekt.', 1),
    ('LBL-1000429', 'de-DE',
     'Absoluter Pfad zum Repository, in dem die Rollen dieses Workflows arbeiten. Muss vorhanden sein. Für Workflows, die in diesem Projekt arbeiten, leer lassen.', 1),
    ('LBL-1000429', 'sv-SE',
     'Absolut sökväg till det repository som detta flödes roller arbetar i. Sökvägen måste finnas. Lämna tomt för flöden som arbetar i detta projekt.', 1);

-- ── Layers 1-2: slots and their mapping ────────────────────
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_target_project', 'Flow edit form: target project path label'),
    ('lbl_bridge_flow_target_project_placeholder', 'Flow edit form: target project path placeholder'),
    ('lbl_bridge_flow_target_project_help', 'Flow edit form: target project path help text');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_target_project', 'lbl_bridge_flow_target_project'),
    ('lbl_bridge_flow_target_project_placeholder', 'lbl_bridge_flow_target_project_placeholder'),
    ('lbl_bridge_flow_target_project_help', 'lbl_bridge_flow_target_project_help');
