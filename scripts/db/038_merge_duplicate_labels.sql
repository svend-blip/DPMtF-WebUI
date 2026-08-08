-- 038: merge the three duplicate label groups find_duplicate_labels found.
--
-- Slots are unique; labels are shared (12_CODING_STANDARD.md find-or-create
-- rule). These six labels are three labels twice — identical default_text
-- and description, created per-slot instead of reused:
--
--   'Add Step' : lbl_btn_add_step (kept, oldest) <- lbl_bridge_step_add
--   'Delete'   : lbl_bridge_delete (kept, oldest) <- lbl_alloc_delete
--   'Save'     : lbl_bridge_save (kept, oldest)   <- lbl_alloc_save
--
-- Merge procedure per the standard: repoint the duplicate's slots to the
-- kept label, then deactivate the duplicate (is_active = 0 — never DELETE).
-- The i18n API resolves slots through ui_text_slot_labels, so the slot keys
-- the frontend uses (data-slot / lbl()) are untouched and keep resolving —
-- now to the kept label's translations.

UPDATE ui_text_slot_labels SET label_key = 'lbl_btn_add_step'
 WHERE label_key = 'lbl_bridge_step_add';
UPDATE ui_labels SET is_active = 0, updated_at = datetime('now')
 WHERE label_key = 'lbl_bridge_step_add';

UPDATE ui_text_slot_labels SET label_key = 'lbl_bridge_delete'
 WHERE label_key = 'lbl_alloc_delete';
UPDATE ui_labels SET is_active = 0, updated_at = datetime('now')
 WHERE label_key = 'lbl_alloc_delete';

UPDATE ui_text_slot_labels SET label_key = 'lbl_bridge_save'
 WHERE label_key = 'lbl_alloc_save';
UPDATE ui_labels SET is_active = 0, updated_at = datetime('now')
 WHERE label_key = 'lbl_alloc_save';
