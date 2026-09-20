-- Rollback for 120. The key is deliberately NOT renamed back: init_db.py
-- seeds `home_dir_disk`, and the old key was the defect. Only the bookkeeping
-- is undone; the statement is a no-op on a database already corrected.

DELETE FROM schema_migrations WHERE filename = '120_card_key_home_dir_disk.sql';
