-- 049: Move the Flows subgroup from Setup to Periodic (Human decision
-- 2026-08-14). Steps, Roles, Conventions, Export, Database Status,
-- System Setup and Flow Control stay under Setup.
--
-- The subgroup KEEPS its key (sg_setup_flows): user_panel_groups holds a
-- per-user collapse-state row under that key and panel_subgroup_mappings
-- references it; renaming would orphan both. The matching seed rows in
-- scripts/init_db.py are updated in the same commit — the seed uses
-- INSERT OR REPLACE plus two Spor-G UPDATEs, so a migration alone would
-- be reverted by the next idempotent init_db run.
--
-- Periodic was hidden by Spor G because it was EMPTY (its three original
-- subgroups were all deactivated). With Flows inside it that rationale
-- inverts: the group must be visible or the Flows UI becomes unreachable.
-- The group's collapse STATE is left as the user had it.
--
-- Idempotent: every statement converges on the same row values.

UPDATE panel_subgroups
   SET group_name = 'periodic',
       sort_order = 4,
       is_visible = 1
 WHERE subgroup_key = 'sg_setup_flows';

UPDATE user_panel_groups
   SET is_visible = 1
 WHERE user_id = 'default'
   AND group_name = 'periodic';
