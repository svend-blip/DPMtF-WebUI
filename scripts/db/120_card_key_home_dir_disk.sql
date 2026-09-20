-- 120 — A card key is not named after a person.
--
-- VPR-1000003 is the disk-usage card for the home directory in the
-- ai_pc_resource_webui_v2 panel requirements. Its title, its source reference
-- and the path it matches on are taken from config.get_home_dir() when
-- init_db.py seeds it, so they are right on any machine. Its card_key was the
-- literal `home_svend_disk`. Nothing reads the key by that name (searched
-- DPMtF-WebUI, mcp-light and both ai-pc-resource-webui checkouts,
-- 2026-09-20); the seed now writes `home_dir_disk`, and this brings an
-- existing database to the same key.
--
-- Measured the same day, for the record: a fresh install built under another
-- home directory contains no other trace of the author's home. The
-- webui_migration_targets, webui_project_skeletons, reusable_panel_selections
-- and v2_panel_requirements paths all follow config, and git_sync_status
-- records where the checkout is.
--
-- Rollback: rollbacks/120_card_key_home_dir_disk_rollback.sql

UPDATE v2_panel_requirements
   SET card_key = 'home_dir_disk', updated_at = datetime('now')
 WHERE card_key = 'home_svend_disk'
   AND NOT EXISTS (SELECT 1 FROM v2_panel_requirements k
                    WHERE k.card_key = 'home_dir_disk'
                      AND k.target_project_key = v2_panel_requirements.target_project_key
                      AND k.panel_key = v2_panel_requirements.panel_key);
