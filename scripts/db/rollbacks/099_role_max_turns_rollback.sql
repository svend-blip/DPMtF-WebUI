-- Rollback for 099: drop the max_turns column and remove its labels.
-- SQLite does not support DROP COLUMN before 3.35.0; the project's
-- baseline migration (001) creates bridge_roles with a fixed schema,
-- so we rebuild without the column. For modern SQLite this is a single
-- DROP COLUMN; for older engines the reviewer can use the table-rebuild
-- pattern. We use DROP COLUMN here because the production runtime is
-- Python 3.12 + sqlite3 3.45+.

ALTER TABLE bridge_roles DROP COLUMN max_turns;

DELETE FROM ui_label_translations WHERE label_id IN ('LBL-1000542', 'LBL-1000543');
DELETE FROM ui_labels WHERE label_key IN ('lbl_bridge_role_max_turns', 'lbl_bridge_role_max_turns_help') OR label_id IN ('LBL-1000542', 'LBL-1000543');
DELETE FROM ui_text_slot_labels WHERE slot_key IN ('lbl_bridge_role_max_turns', 'lbl_bridge_role_max_turns_help');
DELETE FROM ui_text_slots WHERE slot_key IN ('lbl_bridge_role_max_turns', 'lbl_bridge_role_max_turns_help');

DELETE FROM schema_migrations WHERE filename = '099_role_max_turns.sql';
