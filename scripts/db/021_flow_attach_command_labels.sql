-- 021: i18n seed for the flow card's attach command field (4-layer, 4 locales).
--
-- Each flow card now shows `tmux attach -t flow-<flow_key>` in a readonly
-- field with a copy button, so reconnecting to the viewer session that
-- groups the flow's role windows is one paste rather than a remembered
-- convention.
--
-- Two of these keys were already referenced by existing frontend code and
-- had no seed at all, so lbl() fell through to its hardcoded fallback:
-- lbl_btn_copied (used by the Prompt Compiler's copy button) and
-- lbl_bridge_attach_tmux (the Attach tmux button on this same card). They
-- are seeded here rather than left as silent English-only strings.
--
-- Locales follow the current bridge-label norm: da-DK, de-DE, en-US, sv-SE.
--
-- Idempotent: INSERT OR IGNORE throughout.

-- ── Layer 3: the labels ────────────────────────────────────
INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active)
VALUES
    ('LBL-1000430', 'lbl_bridge_flow_attach_command', 'main',
     'Attach command',
     'Flow card: label above the tmux attach command field', 1),
    ('LBL-1000431', 'lbl_bridge_flow_attach_hint', 'main',
     'Run "Attach tmux" first to build this session, then paste the command in a terminal.',
     'Flow card: hint under the tmux attach command field', 1),
    ('LBL-1000432', 'lbl_btn_copied', 'main',
     'Copied!',
     'Transient confirmation shown on a copy button after a successful copy', 1),
    ('LBL-1000433', 'lbl_btn_copy_failed', 'main',
     'Copy failed — select and copy manually',
     'Shown on a copy button when the clipboard is unavailable', 1),
    ('LBL-1000434', 'lbl_bridge_attach_tmux', 'main',
     'Attach tmux',
     'Flow card: button that builds the tmux viewer session for the flow', 1);

-- ── Layer 4: translations ──────────────────────────────────
INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000430', 'en-US', 'Attach command', 1),
    ('LBL-1000430', 'da-DK', 'Attach-kommando', 1),
    ('LBL-1000430', 'de-DE', 'Verbindungsbefehl', 1),
    ('LBL-1000430', 'sv-SE', 'Anslutningskommando', 1),

    ('LBL-1000431', 'en-US',
     'Run "Attach tmux" first to build this session, then paste the command in a terminal.', 1),
    ('LBL-1000431', 'da-DK',
     'Kør "Attach tmux" først for at bygge sessionen, og indsæt derefter kommandoen i en terminal.', 1),
    ('LBL-1000431', 'de-DE',
     'Führen Sie zuerst "Attach tmux" aus, um die Sitzung zu erstellen, und fügen Sie den Befehl dann in einem Terminal ein.', 1),
    ('LBL-1000431', 'sv-SE',
     'Kör "Attach tmux" först för att bygga sessionen, klistra sedan in kommandot i en terminal.', 1),

    ('LBL-1000432', 'en-US', 'Copied!', 1),
    ('LBL-1000432', 'da-DK', 'Kopieret!', 1),
    ('LBL-1000432', 'de-DE', 'Kopiert!', 1),
    ('LBL-1000432', 'sv-SE', 'Kopierat!', 1),

    ('LBL-1000433', 'en-US', 'Copy failed — select and copy manually', 1),
    ('LBL-1000433', 'da-DK', 'Kopiering mislykkedes — markér og kopiér manuelt', 1),
    ('LBL-1000433', 'de-DE', 'Kopieren fehlgeschlagen — bitte manuell markieren und kopieren', 1),
    ('LBL-1000433', 'sv-SE', 'Kopieringen misslyckades — markera och kopiera manuellt', 1),

    ('LBL-1000434', 'en-US', 'Attach tmux', 1),
    ('LBL-1000434', 'da-DK', 'Tilknyt tmux', 1),
    ('LBL-1000434', 'de-DE', 'tmux verbinden', 1),
    ('LBL-1000434', 'sv-SE', 'Anslut tmux', 1);

-- ── Layers 1-2: slots and their mapping ────────────────────
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_attach_command', 'Flow card: tmux attach command label'),
    ('lbl_bridge_flow_attach_hint', 'Flow card: tmux attach command hint'),
    ('lbl_btn_copied', 'Copy button: success confirmation'),
    ('lbl_btn_copy_failed', 'Copy button: clipboard unavailable'),
    ('lbl_bridge_attach_tmux', 'Flow card: Attach tmux button');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_attach_command', 'lbl_bridge_flow_attach_command'),
    ('lbl_bridge_flow_attach_hint', 'lbl_bridge_flow_attach_hint'),
    ('lbl_btn_copied', 'lbl_btn_copied'),
    ('lbl_btn_copy_failed', 'lbl_btn_copy_failed'),
    ('lbl_bridge_attach_tmux', 'lbl_bridge_attach_tmux');
