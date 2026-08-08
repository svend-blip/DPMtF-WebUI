-- Rollback 038: restore the three duplicate labels and their slot mappings.

UPDATE ui_text_slot_labels SET label_key = 'lbl_bridge_step_add'
 WHERE slot_key = 'lbl_bridge_step_add';
UPDATE ui_labels SET is_active = 1, updated_at = datetime('now')
 WHERE label_key = 'lbl_bridge_step_add';

UPDATE ui_text_slot_labels SET label_key = 'lbl_alloc_delete'
 WHERE slot_key = 'lbl_alloc_delete';
UPDATE ui_labels SET is_active = 1, updated_at = datetime('now')
 WHERE label_key = 'lbl_alloc_delete';

UPDATE ui_text_slot_labels SET label_key = 'lbl_alloc_save'
 WHERE slot_key = 'lbl_alloc_save';
UPDATE ui_labels SET is_active = 1, updated_at = datetime('now')
 WHERE label_key = 'lbl_alloc_save';
