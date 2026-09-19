-- Rollback for 115: drop the context_budget column and remove its labels.
-- DROP COLUMN needs SQLite 3.35+; the production runtime is Python 3.12 with
-- sqlite3 3.45+, as for the 099 rollback.

ALTER TABLE bridge_roles DROP COLUMN context_budget;

DELETE FROM ui_label_translations WHERE label_id IN ('LBL-1000544', 'LBL-1000545');
DELETE FROM ui_labels WHERE label_key IN ('lbl_bridge_role_context_budget', 'lbl_bridge_role_context_budget_help') OR label_id IN ('LBL-1000544', 'LBL-1000545');
DELETE FROM ui_text_slot_labels WHERE slot_key IN ('lbl_bridge_role_context_budget', 'lbl_bridge_role_context_budget_help');
DELETE FROM ui_text_slots WHERE slot_key IN ('lbl_bridge_role_context_budget', 'lbl_bridge_role_context_budget_help');

DELETE FROM schema_migrations WHERE filename = '115_role_context_budget.sql';
