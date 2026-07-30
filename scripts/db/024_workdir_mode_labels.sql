-- 024: i18n seed for the role Working Directory field (4-layer, 4 locales).
--
-- Migration 023 added bridge_roles.workdir_mode; the Bridge Roles edit
-- form exposes it as a select. Every user-facing string resolves through
-- ui_text_slots -> ui_text_slot_labels -> ui_labels -> ui_label_translations.
--
-- Locales follow the bridge-label norm: da-DK, de-DE, en-US, sv-SE.
-- Idempotent: INSERT OR IGNORE throughout.

-- ── Layer 3: the labels ────────────────────────────────────
INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active)
VALUES
    ('LBL-1000435', 'lbl_bridge_workdir_mode', 'main',
     'Working Directory',
     'Role edit form: label for the coding-session working directory select', 1),
    ('LBL-1000436', 'lbl_bridge_workdir_target', 'main',
     'Flow''s target project',
     'Role edit form: workdir_mode option target_project', 1),
    ('LBL-1000437', 'lbl_bridge_workdir_father', 'main',
     'This project (Father)',
     'Role edit form: workdir_mode option father', 1),
    ('LBL-1000438', 'lbl_bridge_workdir_help', 'main',
     'Where this role''s coding session starts. Chain workers follow the flow''s Target Project Path; supervisors and architects stay in this project.',
     'Role edit form: help text under the workdir_mode select', 1);

-- ── Layer 4: translations ──────────────────────────────────
INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000435', 'en-US', 'Working Directory', 1),
    ('LBL-1000435', 'da-DK', 'Arbejdsmappe', 1),
    ('LBL-1000435', 'de-DE', 'Arbeitsverzeichnis', 1),
    ('LBL-1000435', 'sv-SE', 'Arbetskatalog', 1),

    ('LBL-1000436', 'en-US', 'Flow''s target project', 1),
    ('LBL-1000436', 'da-DK', 'Flowets målprojekt', 1),
    ('LBL-1000436', 'de-DE', 'Zielprojekt des Workflows', 1),
    ('LBL-1000436', 'sv-SE', 'Flödets målprojekt', 1),

    ('LBL-1000437', 'en-US', 'This project (Father)', 1),
    ('LBL-1000437', 'da-DK', 'Dette projekt (Father)', 1),
    ('LBL-1000437', 'de-DE', 'Dieses Projekt (Father)', 1),
    ('LBL-1000437', 'sv-SE', 'Detta projekt (Father)', 1),

    ('LBL-1000438', 'en-US',
     'Where this role''s coding session starts. Chain workers follow the flow''s Target Project Path; supervisors and architects stay in this project.', 1),
    ('LBL-1000438', 'da-DK',
     'Hvor denne rolles kodesession starter. Kædearbejdere følger flowets sti til målprojekt; supervisorer og arkitekter bliver i dette projekt.', 1),
    ('LBL-1000438', 'de-DE',
     'Wo die Coding-Session dieser Rolle startet. Kettenrollen folgen dem Zielprojekt-Pfad des Workflows; Supervisoren und Architekten bleiben in diesem Projekt.', 1),
    ('LBL-1000438', 'sv-SE',
     'Var denna rolls kodsession startar. Kedjeroller följer flödets sökväg till målprojekt; supervisorer och arkitekter stannar i detta projekt.', 1);

-- ── Layers 1-2: slots and their mapping ────────────────────
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_workdir_mode', 'Role edit form: working directory label'),
    ('lbl_bridge_workdir_target', 'Role edit form: workdir option target_project'),
    ('lbl_bridge_workdir_father', 'Role edit form: workdir option father'),
    ('lbl_bridge_workdir_help', 'Role edit form: working directory help text');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_workdir_mode', 'lbl_bridge_workdir_mode'),
    ('lbl_bridge_workdir_target', 'lbl_bridge_workdir_target'),
    ('lbl_bridge_workdir_father', 'lbl_bridge_workdir_father'),
    ('lbl_bridge_workdir_help', 'lbl_bridge_workdir_help');
