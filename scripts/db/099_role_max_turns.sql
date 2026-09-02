-- 099 — Per-role turn ceiling (Run 023 WORK 1 + WORK 3).
--
-- Adds bridge_roles.max_turns INTEGER NULL so each role can carry its own
-- session ceiling. The harness reads SIMPLE_HARNESS_MAX_TURNS from the
-- child env (start_coding.py threads it when the value is non-NULL);
-- absent means the ini default applies, as today.
--
-- Seeds the three 9000 roles with the Human's initial values:
--   9000-execution-decomposer = 40
--   9000-reviewer             = 80
--   9000-implementer          = 160
-- These are UI-editable afterwards via the role editor.
--
-- Labels for the UI field in the four mandatory locales.
--
-- Rollback: rollbacks/099_role_max_turns_rollback.sql

-- Schema: add the column (idempotent via SQLite's lack of IF NOT EXISTS for
-- ALTER TABLE; the rollback drops it, so re-running after a rollback is safe).
ALTER TABLE bridge_roles ADD COLUMN max_turns INTEGER;

-- Seed data for the 9000 planning chain.
UPDATE bridge_roles SET max_turns = 40  WHERE role_key = '9000-execution-decomposer';
UPDATE bridge_roles SET max_turns = 80  WHERE role_key = '9000-reviewer';
UPDATE bridge_roles SET max_turns = 160 WHERE role_key = '9000-implementer';

-- UI labels: 4-layer chain (slot -> slot_label -> label -> translation).
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_role_max_turns',      'Role edit: max turns field'),
    ('lbl_bridge_role_max_turns_help', 'Role edit: max turns explanation');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_role_max_turns',      'lbl_bridge_role_max_turns'),
    ('lbl_bridge_role_max_turns_help', 'lbl_bridge_role_max_turns_help');

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000542', 'lbl_bridge_role_max_turns',      'main', 'Max Turns',      'Role edit: max turns field',      1),
    ('LBL-1000543', 'lbl_bridge_role_max_turns_help', 'main', 'Session turn ceiling for this role. Empty = harness default.', 'Role edit: max turns explanation', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000542', 'en-US', 'Max Turns', 1),
    ('LBL-1000542', 'da-DK', 'Maks. turns', 1),
    ('LBL-1000542', 'de-DE', 'Max. Turns', 1),
    ('LBL-1000542', 'es-ES', 'Turnos máximos', 1),
    ('LBL-1000543', 'en-US', 'Session turn ceiling for this role. Empty = harness default.', 1),
    ('LBL-1000543', 'da-DK', 'Sessions-turn-loft for denne rolle. Tom = harness-standard.', 1),
    ('LBL-1000543', 'de-DE', 'Sitzungs-Turn-Obergrenze für diese Rolle. Leer = Harness-Standard.', 1),
    ('LBL-1000543', 'es-ES', 'Límite de turnos de sesión para este rol. Vacío = valor por defecto del harness.', 1);
