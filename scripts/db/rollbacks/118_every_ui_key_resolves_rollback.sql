-- Rollback for 118. Removes the labels it created and their translations,
-- and returns the template-manager labels to their domain. The slots and
-- bindings of statement 3 are left in place: they are harmless without a
-- reader, and which of them 118 created cannot be told from the data.

DELETE FROM ui_label_translations WHERE label_id BETWEEN 'LBL-1000546' AND 'LBL-1000604';
DELETE FROM ui_labels WHERE label_id BETWEEN 'LBL-1000546' AND 'LBL-1000604';
UPDATE ui_labels SET label_domain = 'template_manager', updated_at = datetime('now')
 WHERE label_key IN (
        'lbl_btn_assign_handoff_id',
        'lbl_btn_copy_command',
        'lbl_btn_deliver_to_bridge',
        'lbl_compiler_create_webui_btn',
        'lbl_compiler_field_required',
        'lbl_compiler_governance_reminder',
        'lbl_compiler_new_webui_name',
        'lbl_compiler_new_webui_port',
        'lbl_compiler_new_webui_title',
        'lbl_compiler_open_webui',
        'lbl_compiler_script_error',
        'lbl_compiler_start_server_btn',
        'lbl_compiler_webui_created',
        'lbl_deliver_in_progress',
        'lbl_deliver_no_handoff',
        'lbl_deliver_success',
        'lbl_dispatch_command',
        'lbl_handoff_file_written',
        'lbl_handoff_ready',
        'lbl_status_assigning_id'
   );
DELETE FROM schema_migrations WHERE filename = '118_every_ui_key_resolves.sql';
