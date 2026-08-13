-- 039: i18n seed + panel subgroup for the Flow Control dispatch UI (O3).
--
-- The dispatch and trace endpoints (handed in by 023 and 024) are now
-- surfaced in the WebUI under the Setup panel as the "Flow Control"
-- subgroup. Every user-facing string in the new section resolves
-- through the standard 4-layer chain:
--   ui_text_slots -> ui_text_slot_labels -> ui_labels -> ui_label_translations.
--
-- Slot namespace: lbl_flowdisp_ (collision-free today — measured zero
-- occurrences anywhere in static/, templates/, or earlier migrations).
-- Reuse rule (12_CODING_STANDARD): the slots for "Status" and "Error"
-- map to the existing active labels lbl_col_status and
-- lbl_bridge_validation_error in ui_text_slot_labels, so the four
-- mandatory locale rows are not duplicated (migration 038 just merged
-- three duplicate groups; we do not reintroduce them).
--
-- Locales follow the current 4-locale norm: en-US, da-DK, de-DE, es-ES.
-- sv-SE was retired in 037.
-- Idempotent: INSERT OR IGNORE throughout.

-- ── Panel subgroup: Flow Control under Setup ────────────────
INSERT OR IGNORE INTO panel_subgroups
    (subgroup_key, group_name, title_da, title_en, sort_order, is_visible)
VALUES
    ('sg_setup_bridgev002_flow_disp', 'setup', 'Flow-styring', 'Flow Control', 8, 1);

-- Map the section's title data-slot to the new subgroup so
-- buildSubgroups() in dpmtf-app.js moves the <section data-slot="lbl_flowdisp_title">
-- element into the new Flow Control subgroup body at render time.
INSERT OR IGNORE INTO panel_subgroup_mappings (slot_key, subgroup_key) VALUES
    ('lbl_flowdisp_title', 'sg_setup_bridgev002_flow_disp');

-- ── Layer 3: the labels (LBL-1000439 .. LBL-1000456) ────────────
-- 18 new labels. "Status" and "Error" reuse existing active labels —
-- no LBL row created for them; the slot_labels mapping points at the
-- existing keys.
INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000439', 'lbl_flowdisp_title',           'main', 'Flow Control',          'Flow Control subgroup title', 1),
    ('LBL-1000440', 'lbl_flowdisp_flow_label',      'main', 'Flow',                  'Flow select label', 1),
    ('LBL-1000441', 'lbl_flowdisp_step_label',      'main', 'Step',                  'Step select label', 1),
    ('LBL-1000442', 'lbl_flowdisp_flow_placeholder','main', 'Select a flow…',        'Empty flow option', 1),
    ('LBL-1000443', 'lbl_flowdisp_step_placeholder','main', 'Select a flow first',   'Empty step option when no flow is chosen', 1),
    ('LBL-1000444', 'lbl_flowdisp_send',            'main', 'Send dispatch',         'Send button label', 1),
    ('LBL-1000445', 'lbl_flowdisp_sending',         'main', 'Sending…',              'Send button label while in flight', 1),
    ('LBL-1000446', 'lbl_flowdisp_result_heading',  'main', 'Result',                'Result panel heading', 1),
    ('LBL-1000447', 'lbl_flowdisp_result_exit_code','main', 'Exit code',             'Result panel exit-code label', 1),
    ('LBL-1000448', 'lbl_flowdisp_result_stdout',   'main', 'stdout',                'Result panel stdout label', 1),
    ('LBL-1000449', 'lbl_flowdisp_result_stderr',   'main', 'stderr',                'Result panel stderr label', 1),
    ('LBL-1000450', 'lbl_flowdisp_result_idle',     'main', 'No dispatch yet.',      'Initial result panel text', 1),
    ('LBL-1000451', 'lbl_flowdisp_feed_heading',    'main', 'Signal feed',           'Feed panel heading', 1),
    ('LBL-1000452', 'lbl_flowdisp_col_time',        'main', 'Time',                  'Feed table: time column header', 1),
    ('LBL-1000453', 'lbl_flowdisp_col_direction',   'main', 'Direction',             'Feed table: direction column header', 1),
    ('LBL-1000454', 'lbl_flowdisp_col_id',          'main', 'Handoff ID',            'Feed table: handoff id column header', 1),
    ('LBL-1000455', 'lbl_flowdisp_col_event',       'main', 'Event',                 'Feed table: event column header', 1),
    ('LBL-1000456', 'lbl_flowdisp_col_message',     'main', 'Message',               'Feed table: message column header', 1),
    ('LBL-1000457', 'lbl_flowdisp_feed_empty',      'main', 'No signals yet.',       'Feed empty state text', 1);

-- ── Layer 4: translations (4 mandatory locales per label) ──────
-- 19 labels × 4 locales = 76 rows.
INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    -- LBL-1000439 title
    ('LBL-1000439', 'en-US', 'Flow Control', 1),
    ('LBL-1000439', 'da-DK', 'Flow-styring', 1),
    ('LBL-1000439', 'de-DE', 'Flow-Steuerung', 1),
    ('LBL-1000439', 'es-ES', 'Control de flujo', 1),

    -- LBL-1000440 flow_label
    ('LBL-1000440', 'en-US', 'Flow', 1),
    ('LBL-1000440', 'da-DK', 'Flow', 1),
    ('LBL-1000440', 'de-DE', 'Flow', 1),
    ('LBL-1000440', 'es-ES', 'Flujo', 1),

    -- LBL-1000441 step_label
    ('LBL-1000441', 'en-US', 'Step', 1),
    ('LBL-1000441', 'da-DK', 'Trin', 1),
    ('LBL-1000441', 'de-DE', 'Schritt', 1),
    ('LBL-1000441', 'es-ES', 'Paso', 1),

    -- LBL-1000442 flow_placeholder
    ('LBL-1000442', 'en-US', 'Select a flow…', 1),
    ('LBL-1000442', 'da-DK', 'Vælg en flow…', 1),
    ('LBL-1000442', 'de-DE', 'Flow auswählen…', 1),
    ('LBL-1000442', 'es-ES', 'Seleccione un flujo…', 1),

    -- LBL-1000443 step_placeholder
    ('LBL-1000443', 'en-US', 'Select a flow first', 1),
    ('LBL-1000443', 'da-DK', 'Vælg først en flow', 1),
    ('LBL-1000443', 'de-DE', 'Zuerst Flow auswählen', 1),
    ('LBL-1000443', 'es-ES', 'Primero seleccione un flujo', 1),

    -- LBL-1000444 send
    ('LBL-1000444', 'en-US', 'Send dispatch', 1),
    ('LBL-1000444', 'da-DK', 'Send afsendelse', 1),
    ('LBL-1000444', 'de-DE', 'Versand senden', 1),
    ('LBL-1000444', 'es-ES', 'Enviar dispatch', 1),

    -- LBL-1000445 sending
    ('LBL-1000445', 'en-US', 'Sending…', 1),
    ('LBL-1000445', 'da-DK', 'Sender…', 1),
    ('LBL-1000445', 'de-DE', 'Wird gesendet…', 1),
    ('LBL-1000445', 'es-ES', 'Enviando…', 1),

    -- LBL-1000446 result_heading
    ('LBL-1000446', 'en-US', 'Result', 1),
    ('LBL-1000446', 'da-DK', 'Resultat', 1),
    ('LBL-1000446', 'de-DE', 'Ergebnis', 1),
    ('LBL-1000446', 'es-ES', 'Resultado', 1),

    -- LBL-1000447 result_exit_code
    ('LBL-1000447', 'en-US', 'Exit code', 1),
    ('LBL-1000447', 'da-DK', 'Afslutningskode', 1),
    ('LBL-1000447', 'de-DE', 'Exit-Code', 1),
    ('LBL-1000447', 'es-ES', 'Código de salida', 1),

    -- LBL-1000448 result_stdout
    ('LBL-1000448', 'en-US', 'stdout', 1),
    ('LBL-1000448', 'da-DK', 'stdout', 1),
    ('LBL-1000448', 'de-DE', 'stdout', 1),
    ('LBL-1000448', 'es-ES', 'stdout', 1),

    -- LBL-1000449 result_stderr
    ('LBL-1000449', 'en-US', 'stderr', 1),
    ('LBL-1000449', 'da-DK', 'stderr', 1),
    ('LBL-1000449', 'de-DE', 'stderr', 1),
    ('LBL-1000449', 'es-ES', 'stderr', 1),

    -- LBL-1000450 result_idle
    ('LBL-1000450', 'en-US', 'No dispatch yet.', 1),
    ('LBL-1000450', 'da-DK', 'Ingen afsendelse endnu.', 1),
    ('LBL-1000450', 'de-DE', 'Noch kein Versand.', 1),
    ('LBL-1000450', 'es-ES', 'Aún no se ha enviado.', 1),

    -- LBL-1000451 feed_heading
    ('LBL-1000451', 'en-US', 'Signal feed', 1),
    ('LBL-1000451', 'da-DK', 'Signal-feed', 1),
    ('LBL-1000451', 'de-DE', 'Signal-Feed', 1),
    ('LBL-1000451', 'es-ES', 'Feed de señales', 1),

    -- LBL-1000452 col_time
    ('LBL-1000452', 'en-US', 'Time', 1),
    ('LBL-1000452', 'da-DK', 'Tid', 1),
    ('LBL-1000452', 'de-DE', 'Zeit', 1),
    ('LBL-1000452', 'es-ES', 'Hora', 1),

    -- LBL-1000453 col_direction
    ('LBL-1000453', 'en-US', 'Direction', 1),
    ('LBL-1000453', 'da-DK', 'Retning', 1),
    ('LBL-1000453', 'de-DE', 'Richtung', 1),
    ('LBL-1000453', 'es-ES', 'Dirección', 1),

    -- LBL-1000454 col_id
    ('LBL-1000454', 'en-US', 'Handoff ID', 1),
    ('LBL-1000454', 'da-DK', 'Handoff-id', 1),
    ('LBL-1000454', 'de-DE', 'Handoff-ID', 1),
    ('LBL-1000454', 'es-ES', 'ID de handoff', 1),

    -- LBL-1000455 col_event
    ('LBL-1000455', 'en-US', 'Event', 1),
    ('LBL-1000455', 'da-DK', 'Hændelse', 1),
    ('LBL-1000455', 'de-DE', 'Ereignis', 1),
    ('LBL-1000455', 'es-ES', 'Evento', 1),

    -- LBL-1000456 col_message
    ('LBL-1000456', 'en-US', 'Message', 1),
    ('LBL-1000456', 'da-DK', 'Besked', 1),
    ('LBL-1000456', 'de-DE', 'Nachricht', 1),
    ('LBL-1000456', 'es-ES', 'Mensaje', 1),

    -- LBL-1000457 feed_empty
    ('LBL-1000457', 'en-US', 'No signals yet.', 1),
    ('LBL-1000457', 'da-DK', 'Ingen signaler endnu.', 1),
    ('LBL-1000457', 'de-DE', 'Noch keine Signale.', 1),
    ('LBL-1000457', 'es-ES', 'Aún no hay señales.', 1);

-- ── Layer 1: slots ─────────────────────────────────────────────
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_flowdisp_title',             'Flow Control subgroup title'),
    ('lbl_flowdisp_flow_label',        'Flow select label'),
    ('lbl_flowdisp_step_label',        'Step select label'),
    ('lbl_flowdisp_flow_placeholder',  'Empty flow option text'),
    ('lbl_flowdisp_step_placeholder',  'Empty step option text'),
    ('lbl_flowdisp_send',              'Send button label'),
    ('lbl_flowdisp_sending',           'Send button label while in flight'),
    ('lbl_flowdisp_result_heading',    'Result panel heading'),
    ('lbl_flowdisp_result_status',     'Result panel status label (reuses lbl_col_status)'),
    ('lbl_flowdisp_result_exit_code',  'Result panel exit-code label'),
    ('lbl_flowdisp_result_stdout',     'Result panel stdout label'),
    ('lbl_flowdisp_result_stderr',     'Result panel stderr label'),
    ('lbl_flowdisp_result_idle',       'Initial result panel text'),
    ('lbl_flowdisp_feed_heading',      'Feed panel heading'),
    ('lbl_flowdisp_col_time',          'Feed table time column header'),
    ('lbl_flowdisp_col_direction',     'Feed table direction column header'),
    ('lbl_flowdisp_col_id',            'Feed table handoff id column header'),
    ('lbl_flowdisp_col_event',         'Feed table event column header'),
    ('lbl_flowdisp_col_message',       'Feed table message column header'),
    ('lbl_flowdisp_feed_empty',        'Feed empty state text'),
    ('lbl_flowdisp_error',             'Error label (reuses lbl_bridge_validation_error)');

-- ── Layer 2: slot → label mapping ─────────────────────────────
-- 19 new mappings + 2 reuse mappings for status and error.
INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_flowdisp_title',             'lbl_flowdisp_title'),
    ('lbl_flowdisp_flow_label',        'lbl_flowdisp_flow_label'),
    ('lbl_flowdisp_step_label',        'lbl_flowdisp_step_label'),
    ('lbl_flowdisp_flow_placeholder',  'lbl_flowdisp_flow_placeholder'),
    ('lbl_flowdisp_step_placeholder',  'lbl_flowdisp_step_placeholder'),
    ('lbl_flowdisp_send',              'lbl_flowdisp_send'),
    ('lbl_flowdisp_sending',           'lbl_flowdisp_sending'),
    ('lbl_flowdisp_result_heading',    'lbl_flowdisp_result_heading'),
    -- Reuse: lbl_col_status already covers the result panel's "Status" line.
    ('lbl_flowdisp_result_status',     'lbl_col_status'),
    ('lbl_flowdisp_result_exit_code',  'lbl_flowdisp_result_exit_code'),
    ('lbl_flowdisp_result_stdout',     'lbl_flowdisp_result_stdout'),
    ('lbl_flowdisp_result_stderr',     'lbl_flowdisp_result_stderr'),
    ('lbl_flowdisp_result_idle',       'lbl_flowdisp_result_idle'),
    ('lbl_flowdisp_feed_heading',      'lbl_flowdisp_feed_heading'),
    ('lbl_flowdisp_col_time',          'lbl_flowdisp_col_time'),
    ('lbl_flowdisp_col_direction',     'lbl_flowdisp_col_direction'),
    ('lbl_flowdisp_col_id',            'lbl_flowdisp_col_id'),
    ('lbl_flowdisp_col_event',         'lbl_flowdisp_col_event'),
    ('lbl_flowdisp_col_message',       'lbl_flowdisp_col_message'),
    ('lbl_flowdisp_feed_empty',        'lbl_flowdisp_feed_empty'),
    -- Reuse: lbl_bridge_validation_error already covers the result error line.
    ('lbl_flowdisp_error',             'lbl_bridge_validation_error');
