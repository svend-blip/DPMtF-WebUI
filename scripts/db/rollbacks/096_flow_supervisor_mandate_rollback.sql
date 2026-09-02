-- Rollback for 096: remove the supervisor-mandate columns and the seven
-- labels 096 seeds.
--
-- Exact inverse of the forward migration. WHERE clauses match ONLY the
-- label ids and slot keys 096 seeds, so every other label is untouched.
-- bridge_flows.supervisor_role is NOT dropped — it predates 096 (migration
-- 061); 096 only seeded its UI label, which is what is removed here.
--
-- ALTER TABLE ... DROP COLUMN requires SQLite >= 3.35.0 (the host runs
-- 3.45.1). On an older SQLite, use the recreate-table route instead:
-- CREATE TABLE bridge_flows_new (... every column except the two below ...),
-- INSERT INTO bridge_flows_new SELECT <those columns> FROM bridge_flows,
-- DROP TABLE bridge_flows, ALTER TABLE bridge_flows_new RENAME TO bridge_flows,
-- then recreate any indexes on bridge_flows.

DELETE FROM ui_label_translations
WHERE label_id IN ('LBL-1000534', 'LBL-1000535', 'LBL-1000536', 'LBL-1000537',
                   'LBL-1000538', 'LBL-1000539', 'LBL-1000540');

DELETE FROM ui_text_slot_labels
WHERE slot_key IN ('lbl_bridge_flow_supervisor_mandate',
                   'lbl_bridge_flow_supervisor_mandate_placeholder',
                   'lbl_bridge_flow_commit_cadence',
                   'lbl_bridge_flow_commit_cadence_none',
                   'lbl_bridge_flow_commit_cadence_per_run',
                   'lbl_bridge_flow_commit_cadence_per_handoff',
                   'lbl_bridge_flow_supervisor_role');

DELETE FROM ui_text_slots
WHERE slot_key IN ('lbl_bridge_flow_supervisor_mandate',
                   'lbl_bridge_flow_supervisor_mandate_placeholder',
                   'lbl_bridge_flow_commit_cadence',
                   'lbl_bridge_flow_commit_cadence_none',
                   'lbl_bridge_flow_commit_cadence_per_run',
                   'lbl_bridge_flow_commit_cadence_per_handoff',
                   'lbl_bridge_flow_supervisor_role');

DELETE FROM ui_labels
WHERE label_id IN ('LBL-1000534', 'LBL-1000535', 'LBL-1000536', 'LBL-1000537',
                   'LBL-1000538', 'LBL-1000539', 'LBL-1000540');

ALTER TABLE bridge_flows DROP COLUMN supervisor_mandate;
ALTER TABLE bridge_flows DROP COLUMN commit_cadence;

DELETE FROM schema_migrations WHERE filename = '096_flow_supervisor_mandate.sql';
