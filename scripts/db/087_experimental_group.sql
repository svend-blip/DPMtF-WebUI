-- 087: The Experimental panel group (Human decision 2026-08-30).
--
-- A sixth top-level group, rendered as the LAST section of the page, holds
-- panels whose everyday value is unproven:
--   - Prompt Templates moves Daily -> Experimental.
--   - A new "Experimental Flows" panel (fed by 088's bridge_flows.ui_category)
--     will hold the trade flows, which are atypical and should not mix with
--     the daily flows.
-- Flows moves Periodic -> Daily: it is the everyday overview. Periodic is
-- then EMPTY (its three original subgroups have been deactivated since
-- Spor G) and is hidden at group level — the exact inverse of migration
-- 049's rationale for showing it. Reports is hidden for the same reason
-- Journals has been since Fase 3A: an empty shell is not a section.
--
-- Also seeds the pg_job_queue heading label: the Job Queue group has been
-- live since the jobs system landed but its <h2 data-slot="pg_job_queue">
-- never had a label row, so it silently fell back to hardcoded English —
-- an i18n auto-fail (12_CODING_STANDARD).
--
-- The matching seed rows in scripts/init_db.py are updated in the same
-- commit; the seeds use INSERT OR REPLACE, so a migration alone would be
-- reverted by the next idempotent init_db run.
--
-- Governance: 30_FRONTEND_GOVERNANCE.md's fixed group list is amended in
-- the same commit; the decision is recorded in 25_DECISIONS.md.
--
-- Idempotent: INSERT OR IGNORE / UPDATE converging on the same values.

-- ── Panel groups: membership + visibility ───────────────────────────
UPDATE panel_subgroups
   SET group_name = 'daily',
       sort_order = 1,
       is_visible = 1
 WHERE subgroup_key = 'sg_setup_flows';

INSERT OR IGNORE INTO panel_subgroups
    (subgroup_key, group_name, title_da, title_en, sort_order, is_visible)
VALUES
    ('sg_experimental_templates', 'experimental', 'Prompt-skabeloner', 'Prompt Templates', 1, 1),
    ('sg_experimental_flows',     'experimental', 'Eksperimentelle flows', 'Experimental Flows', 2, 1);

INSERT OR IGNORE INTO panel_subgroup_mappings (slot_key, subgroup_key) VALUES
    ('lbl_panel_templates',      'sg_experimental_templates'),
    ('lbl_bridge_expflows_title', 'sg_experimental_flows');

INSERT OR IGNORE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
VALUES ('default', 'experimental', 'expanded', 1, datetime('now'));

UPDATE user_panel_groups SET is_visible = 1
 WHERE user_id = 'default' AND group_name = 'daily';

INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
VALUES
    ('default', 'reports',  'collapsed', 0, datetime('now')),
    ('default', 'periodic', 'collapsed', 0, datetime('now'));

-- ── Layer 1+2: slots ────────────────────────────────────────────────
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('pg_experimental',          'Experimental panel group heading'),
    ('pg_job_queue',             'Job Queue panel group heading'),
    ('lbl_bridge_expflows_title', 'Experimental Flows section heading'),
    ('lbl_bridge_no_expflows',   'Experimental Flows empty state'),
    ('lbl_bridge_role_flow_target',      'Role edit: target project note label'),
    ('lbl_bridge_role_flow_target_help', 'Role edit: target project explanation');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('pg_experimental',          'pg_experimental'),
    ('pg_job_queue',             'pg_job_queue'),
    ('lbl_bridge_expflows_title', 'lbl_bridge_expflows_title'),
    ('lbl_bridge_no_expflows',   'lbl_bridge_no_expflows'),
    ('lbl_bridge_role_flow_target',      'lbl_bridge_role_flow_target'),
    ('lbl_bridge_role_flow_target_help', 'lbl_bridge_role_flow_target_help');

-- ── Layer 3: labels (LBL-1000512 .. LBL-1000517) ────────────────────
INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000512', 'pg_experimental',           'main', '🧪 Experimental',      'Experimental panel group heading', 1),
    ('LBL-1000513', 'pg_job_queue',              'main', '📋 Job Queue',         'Job Queue panel group heading', 1),
    ('LBL-1000514', 'lbl_bridge_expflows_title', 'main', 'Experimental Flows',   'Experimental Flows section heading', 1),
    ('LBL-1000515', 'lbl_bridge_no_expflows',    'main', 'No experimental flows', 'Experimental Flows empty state', 1),
    ('LBL-1000516', 'lbl_bridge_role_flow_target', 'main', 'Target Project (set on the flow)', 'Role edit: target project note label', 1),
    ('LBL-1000517', 'lbl_bridge_role_flow_target_help', 'main',
     'Each flow decides the repository its roles work in — edit Target Project Path on the flow. This role''s workdir_mode decides whether it works there or in this project.',
     'Role edit: target project explanation', 1);

-- ── Layer 4: translations (4 mandatory locales per label) ───────────
INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000512', 'en-US', '🧪 Experimental', 1),
    ('LBL-1000512', 'da-DK', '🧪 Eksperimentelt', 1),
    ('LBL-1000512', 'de-DE', '🧪 Experimentell', 1),
    ('LBL-1000512', 'es-ES', '🧪 Experimental', 1),
    ('LBL-1000513', 'en-US', '📋 Job Queue', 1),
    ('LBL-1000513', 'da-DK', '📋 Jobkø', 1),
    ('LBL-1000513', 'de-DE', '📋 Job-Warteschlange', 1),
    ('LBL-1000513', 'es-ES', '📋 Cola de trabajos', 1),
    ('LBL-1000514', 'en-US', 'Experimental Flows', 1),
    ('LBL-1000514', 'da-DK', 'Eksperimentelle flows', 1),
    ('LBL-1000514', 'de-DE', 'Experimentelle Flows', 1),
    ('LBL-1000514', 'es-ES', 'Flujos experimentales', 1),
    ('LBL-1000515', 'en-US', 'No experimental flows', 1),
    ('LBL-1000515', 'da-DK', 'Ingen eksperimentelle flows', 1),
    ('LBL-1000515', 'de-DE', 'Keine experimentellen Flows', 1),
    ('LBL-1000515', 'es-ES', 'No hay flujos experimentales', 1),
    ('LBL-1000516', 'en-US', 'Target Project (set on the flow)', 1),
    ('LBL-1000516', 'da-DK', 'Target Project (sættes på flowet)', 1),
    ('LBL-1000516', 'de-DE', 'Target Project (am Flow gesetzt)', 1),
    ('LBL-1000516', 'es-ES', 'Target Project (se define en el flujo)', 1),
    ('LBL-1000517', 'en-US', 'Each flow decides the repository its roles work in — edit Target Project Path on the flow. This role''s workdir_mode decides whether it works there or in this project.', 1),
    ('LBL-1000517', 'da-DK', 'Hvert flow bestemmer hvilket repository dets roller arbejder i — redigér Target Project Path på flowet. Rollens workdir_mode afgør om den arbejder dér eller i dette projekt.', 1),
    ('LBL-1000517', 'de-DE', 'Jeder Flow bestimmt das Repository, in dem seine Rollen arbeiten — Target Project Path am Flow bearbeiten. Der workdir_mode dieser Rolle entscheidet, ob sie dort oder in diesem Projekt arbeitet.', 1),
    ('LBL-1000517', 'es-ES', 'Cada flujo decide el repositorio en el que trabajan sus roles — edite Target Project Path en el flujo. El workdir_mode de este rol decide si trabaja allí o en este proyecto.', 1);
