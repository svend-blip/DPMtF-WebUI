-- Rollback for migration 053: remove the flow implementation_mode
-- dropdown labels (all four i18n layers, in dependency order).

DELETE FROM ui_text_slot_labels WHERE slot_key IN (
    'lbl_bridge_flow_implementation_mode',
    'lbl_bridge_flow_implementation_mode_inherit',
    'lbl_bridge_flow_implementation_mode_direct',
    'lbl_bridge_flow_implementation_mode_patch',
    'lbl_bridge_flow_implementation_mode_help'
);

DELETE FROM ui_text_slots WHERE slot_key IN (
    'lbl_bridge_flow_implementation_mode',
    'lbl_bridge_flow_implementation_mode_inherit',
    'lbl_bridge_flow_implementation_mode_direct',
    'lbl_bridge_flow_implementation_mode_patch',
    'lbl_bridge_flow_implementation_mode_help'
);

DELETE FROM ui_label_translations WHERE label_id IN (
    'LBL-1000500', 'LBL-1000501', 'LBL-1000502', 'LBL-1000503', 'LBL-1000504'
);

DELETE FROM ui_labels WHERE label_id IN (
    'LBL-1000500', 'LBL-1000501', 'LBL-1000502', 'LBL-1000503', 'LBL-1000504'
);
