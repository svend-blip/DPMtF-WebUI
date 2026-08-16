-- Rollback for migration 054: drop the auto_dispatch column (the pi_test
-- row updates disappear with it). Requires SQLite >= 3.35 (DROP COLUMN),
-- same constraint as the 052 rollback.

ALTER TABLE bridge_flow_steps DROP COLUMN auto_dispatch;
