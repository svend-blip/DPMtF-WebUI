-- 096 — Per-flow supervisor mandate, database-driven and UI-managed.
--
-- A resident planning supervisor (the PLOOP side of a two-flow pair) is the
-- one session that may open a Run on the ELOOP chain. It must do so only
-- under a mandate the Human has given, and today that mandate lives in a
-- prose GOAL.md or in the supervisor's own memory — invisible to the UI,
-- unmeasurable by the bridge, and lost on every cold start.
--
-- Three properties of the flow are pinned here:
--
--   supervisor_mandate  the Human's standing instruction to the resident
--                       supervisor. Free text. Fail-closed: NULL means
--                       PLANNING ONLY — the supervisor may plan, draft and
--                       report, and never opens a Run.
--   commit_cadence      when the chain may commit on the Human's behalf:
--                       'none' (the Human commits — the historical rule),
--                       'per_run' or 'per_handoff'. NOT NULL DEFAULT 'none'
--                       so a database predating the setting keeps the
--                       Human-commits rule. SQLite's ALTER cannot add a
--                       CHECK; the allowed set is enforced in the router.
--   supervisor_role     already exists (migration 061, the stall wake-up
--                       target). 096 makes it editable from the UI by
--                       seeding its label; the column itself is unchanged.
--
-- All three belong to the FLOW, exactly like cold_start_skill (094): roles
-- are shared across flows, and one mandate covers one workspace.
--
-- They belong in the database AND in the UI: a field that exists only in the
-- database is invisible and unmanageable, and flows must stay administrable
-- from the frontend.
--
-- Labels seeded in all four mandatory locales (en-US, da-DK, de-DE, es-ES):
--
--   LBL-1000534  lbl_bridge_flow_supervisor_mandate
--   LBL-1000535  lbl_bridge_flow_supervisor_mandate_placeholder
--   LBL-1000536  lbl_bridge_flow_commit_cadence
--   LBL-1000537  lbl_bridge_flow_commit_cadence_none
--   LBL-1000538  lbl_bridge_flow_commit_cadence_per_run
--   LBL-1000539  lbl_bridge_flow_commit_cadence_per_handoff
--   LBL-1000540  lbl_bridge_flow_supervisor_role
--
-- Idempotent for the seed rows: INSERT OR IGNORE throughout. The ALTERs run
-- once, guarded by the migration runner's applied-migrations ledger.

ALTER TABLE bridge_flows ADD COLUMN supervisor_mandate TEXT DEFAULT NULL;
ALTER TABLE bridge_flows ADD COLUMN commit_cadence TEXT NOT NULL DEFAULT 'none';

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000534', 'lbl_bridge_flow_supervisor_mandate', 'main',
     'Supervisor mandate',
     'Flow edit form: the Human''s standing mandate to the resident planning supervisor. Empty = planning only.', 1),
    ('LBL-1000535', 'lbl_bridge_flow_supervisor_mandate_placeholder', 'main',
     'Empty = planning only; the supervisor never opens a Run',
     'Flow edit form: placeholder for the supervisor mandate input. Explains the fail-closed default.', 1),
    ('LBL-1000536', 'lbl_bridge_flow_commit_cadence', 'main',
     'Commit cadence',
     'Flow edit form: when the chain may commit on the Human''s behalf (none, per Run, per handoff).', 1),
    ('LBL-1000537', 'lbl_bridge_flow_commit_cadence_none', 'main',
     'None (the Human commits)',
     'Flow edit form: commit cadence option — no autonomous commits; the Human commits.', 1),
    ('LBL-1000538', 'lbl_bridge_flow_commit_cadence_per_run', 'main',
     'Per Run',
     'Flow edit form: commit cadence option — one commit when a Run closes.', 1),
    ('LBL-1000539', 'lbl_bridge_flow_commit_cadence_per_handoff', 'main',
     'Per handoff',
     'Flow edit form: commit cadence option — one commit per accepted handoff.', 1),
    ('LBL-1000540', 'lbl_bridge_flow_supervisor_role', 'main',
     'Supervisor role (wake-up target)',
     'Flow edit form: the role key the stall watchdog wakes for this flow (bridge_flows.supervisor_role, migration 061).', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000534', 'en-US', 'Supervisor mandate', 1),
    ('LBL-1000534', 'da-DK', 'Supervisor-mandat', 1),
    ('LBL-1000534', 'de-DE', 'Supervisor-Mandat', 1),
    ('LBL-1000534', 'es-ES', 'Mandato del supervisor', 1),
    ('LBL-1000535', 'en-US', 'Empty = planning only; the supervisor never opens a Run', 1),
    ('LBL-1000535', 'da-DK', 'Tom = kun planlægning; supervisoren åbner aldrig et Run', 1),
    ('LBL-1000535', 'de-DE', 'Leer = nur Planung; der Supervisor öffnet nie einen Run', 1),
    ('LBL-1000535', 'es-ES', 'Vacío = solo planificación; el supervisor nunca abre un Run', 1),
    ('LBL-1000536', 'en-US', 'Commit cadence', 1),
    ('LBL-1000536', 'da-DK', 'Commit-kadence', 1),
    ('LBL-1000536', 'de-DE', 'Commit-Kadenz', 1),
    ('LBL-1000536', 'es-ES', 'Cadencia de commits', 1),
    ('LBL-1000537', 'en-US', 'None (the Human commits)', 1),
    ('LBL-1000537', 'da-DK', 'Ingen (Human committer)', 1),
    ('LBL-1000537', 'de-DE', 'Keine (der Human committet)', 1),
    ('LBL-1000537', 'es-ES', 'Ninguna (el Human hace los commits)', 1),
    ('LBL-1000538', 'en-US', 'Per Run', 1),
    ('LBL-1000538', 'da-DK', 'Pr. Run', 1),
    ('LBL-1000538', 'de-DE', 'Pro Run', 1),
    ('LBL-1000538', 'es-ES', 'Por Run', 1),
    ('LBL-1000539', 'en-US', 'Per handoff', 1),
    ('LBL-1000539', 'da-DK', 'Pr. handoff', 1),
    ('LBL-1000539', 'de-DE', 'Pro Handoff', 1),
    ('LBL-1000539', 'es-ES', 'Por handoff', 1),
    ('LBL-1000540', 'en-US', 'Supervisor role (wake-up target)', 1),
    ('LBL-1000540', 'da-DK', 'Supervisor-rolle (wake-up-mål)', 1),
    ('LBL-1000540', 'de-DE', 'Supervisor-Rolle (Wake-up-Ziel)', 1),
    ('LBL-1000540', 'es-ES', 'Rol de supervisor (destino del wake-up)', 1);

INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_flow_supervisor_mandate', 'Flow edit form: supervisor mandate field label'),
    ('lbl_bridge_flow_supervisor_mandate_placeholder', 'Flow edit form: supervisor mandate input placeholder'),
    ('lbl_bridge_flow_commit_cadence', 'Flow edit form: commit cadence field label'),
    ('lbl_bridge_flow_commit_cadence_none', 'Flow edit form: commit cadence option none'),
    ('lbl_bridge_flow_commit_cadence_per_run', 'Flow edit form: commit cadence option per Run'),
    ('lbl_bridge_flow_commit_cadence_per_handoff', 'Flow edit form: commit cadence option per handoff'),
    ('lbl_bridge_flow_supervisor_role', 'Flow edit form: supervisor role field label');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_flow_supervisor_mandate', 'lbl_bridge_flow_supervisor_mandate'),
    ('lbl_bridge_flow_supervisor_mandate_placeholder', 'lbl_bridge_flow_supervisor_mandate_placeholder'),
    ('lbl_bridge_flow_commit_cadence', 'lbl_bridge_flow_commit_cadence'),
    ('lbl_bridge_flow_commit_cadence_none', 'lbl_bridge_flow_commit_cadence_none'),
    ('lbl_bridge_flow_commit_cadence_per_run', 'lbl_bridge_flow_commit_cadence_per_run'),
    ('lbl_bridge_flow_commit_cadence_per_handoff', 'lbl_bridge_flow_commit_cadence_per_handoff'),
    ('lbl_bridge_flow_supervisor_role', 'lbl_bridge_flow_supervisor_role');
