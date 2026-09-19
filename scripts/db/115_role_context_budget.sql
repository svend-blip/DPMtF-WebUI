-- 115 — Per-role context budget.
--
-- Adds bridge_roles.context_budget INTEGER NULL: how many tokens of context
-- the role MAY use, as distinct from how many its model CAN hold.
--
-- simple-harness keeps a run inside a limit by pruning old tool results and
-- compacting older conversation. Since 2026-09-19 the launch hands it the
-- model alias's context window as that limit. On a 1,000,000-token window
-- that bounds nothing a run will ever reach: every turn resends the whole
-- history, and on a cloud alias each of those tokens is paid for. The budget
-- is the cap the window is not.
--
-- start_coding.py threads the SMALLER of the alias's window and this value
-- to the role as SIMPLE_HARNESS_CONTEXT_MODEL_LIMIT; NULL means the window,
-- as before. The FlowApp exporter carries it as the binding's
-- context_budget. The value must hold the role's governance file and tool
-- definitions with room to work: a budget smaller than what is pinned into
-- every request ends the run with a configuration error.
--
-- No value is seeded. A budget is an operating decision per role, made in
-- the role editor.
--
-- Labels for the UI field in the four mandatory locales.
--
-- Rollback: rollbacks/115_role_context_budget_rollback.sql

ALTER TABLE bridge_roles ADD COLUMN context_budget INTEGER;

-- UI labels: 4-layer chain (slot -> slot_label -> label -> translation).
INSERT OR IGNORE INTO ui_text_slots (slot_key, description) VALUES
    ('lbl_bridge_role_context_budget',      'Role edit: context budget field'),
    ('lbl_bridge_role_context_budget_help', 'Role edit: context budget explanation');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) VALUES
    ('lbl_bridge_role_context_budget',      'lbl_bridge_role_context_budget'),
    ('lbl_bridge_role_context_budget_help', 'lbl_bridge_role_context_budget_help');

INSERT OR IGNORE INTO ui_labels (label_id, label_key, label_domain, default_text, description, is_active) VALUES
    ('LBL-1000544', 'lbl_bridge_role_context_budget',      'main', 'Context Budget (tokens)', 'Role edit: context budget field', 1),
    ('LBL-1000545', 'lbl_bridge_role_context_budget_help', 'main', 'Most context tokens this role may use. The smaller of this and the model''s window bounds the run. Empty = the model''s window. Must hold the governance file and tool definitions with room to work.', 'Role edit: context budget explanation', 1);

INSERT OR IGNORE INTO ui_label_translations (label_id, locale, translated_text, is_active) VALUES
    ('LBL-1000544', 'en-US', 'Context Budget (tokens)', 1),
    ('LBL-1000544', 'da-DK', 'Kontekstbudget (tokens)', 1),
    ('LBL-1000544', 'de-DE', 'Kontextbudget (Tokens)', 1),
    ('LBL-1000544', 'es-ES', 'Presupuesto de contexto (tokens)', 1),
    ('LBL-1000545', 'en-US', 'Most context tokens this role may use. The smaller of this and the model''s window bounds the run. Empty = the model''s window. Must hold the governance file and tool definitions with room to work.', 1),
    ('LBL-1000545', 'da-DK', 'Det højeste antal kontekst-tokens rollen må bruge. Den mindste af denne værdi og modellens vindue begrænser kørslen. Tom = modellens vindue. Skal kunne rumme governance-filen og tool-definitionerne med plads til at arbejde.', 1),
    ('LBL-1000545', 'de-DE', 'Höchstzahl an Kontext-Tokens, die diese Rolle verwenden darf. Der kleinere Wert aus diesem und dem Fenster des Modells begrenzt den Lauf. Leer = Fenster des Modells. Muss die Governance-Datei und die Tool-Definitionen mit Arbeitsraum fassen.', 1),
    ('LBL-1000545', 'es-ES', 'Máximo de tokens de contexto que puede usar este rol. El menor entre este valor y la ventana del modelo limita la ejecución. Vacío = la ventana del modelo. Debe caber el archivo de gobernanza y las definiciones de herramientas con margen para trabajar.', 1);
