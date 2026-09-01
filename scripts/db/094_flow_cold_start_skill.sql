-- 094 — Per-flow cold-start skill, database-driven and UI-managed.
--
-- A chain role is stateless: every dispatch is a fresh invocation with no
-- memory of the last. Without a cold-start procedure it rediscovers which Run
-- it is in, where its channels are and how to signal — by reading source.
-- Measured 2026-09-01 on 9000-02-ELOOP: the decomposer's post-verdict wake-up
-- spent its whole turn budget exploring and wrote no END-REPORT.
--
-- The harness mechanism already exists (simple-harness --skill, resolved from
-- its own skills roots). What was missing is WHERE the name lives. It is a
-- property of the flow — one skill describes one workspace's conventions — so
-- a machine-wide setting would hand one flow's skill to another flow's role.
--
-- It belongs in the database AND in the UI: a field that exists only in the
-- database is invisible and unmanageable, and flows must stay administrable
-- from the frontend.
--
-- Labels seeded in all four mandatory locales (en-US, da-DK, de-DE, es-ES):
--
--   LBL-1000532  lbl_bridge_flow_cold_start_skill
--   LBL-1000533  lbl_bridge_flow_cold_start_skill_placeholder
--
-- Idempotent for the seed rows: INSERT OR IGNORE throughout. The ALTER runs
-- once, guarded by the migration runner's applied-migrations ledger.

ALTER TABLE bridge_flows ADD COLUMN cold_start_skill TEXT DEFAULT NULL;

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000532', 'lbl_bridge_flow_cold_start_skill', 'main',
     'Cold-Start Skill',
     'Flow edit form: name of the cold-start skill a chain role loads at dispatch. Resolved by the harness from its own skills roots.', 1),
    ('LBL-1000533', 'lbl_bridge_flow_cold_start_skill_placeholder', 'main',
     'Empty = no cold-start skill is loaded',
     'Flow edit form: placeholder for the cold-start skill input. Explains that an empty value emits no skill flag at launch.', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000532', 'en-US', 'Cold-Start Skill', 1),
    ('LBL-1000532', 'da-DK', 'Koldstart-skill', 1),
    ('LBL-1000532', 'de-DE', 'Kaltstart-Skill', 1),
    ('LBL-1000532', 'es-ES', 'Habilidad de arranque en frío', 1),
    ('LBL-1000533', 'en-US', 'Empty = no cold-start skill is loaded', 1),
    ('LBL-1000533', 'da-DK', 'Tom = ingen koldstart-skill indlæses', 1),
    ('LBL-1000533', 'de-DE', 'Leer = es wird kein Kaltstart-Skill geladen', 1),
    ('LBL-1000533', 'es-ES', 'Vacío = no se carga ninguna habilidad de arranque en frío', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_cold_start_skill', 'Flow edit form: cold-start skill field label'),
    ('lbl_bridge_flow_cold_start_skill_placeholder', 'Flow edit form: cold-start skill input placeholder');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_cold_start_skill', 'lbl_bridge_flow_cold_start_skill'),
    ('lbl_bridge_flow_cold_start_skill_placeholder', 'lbl_bridge_flow_cold_start_skill_placeholder');
