-- 032: The bridge_flows row that 031 failed to insert, silently.
--
-- 031 inserted the two roles, both steps and the counter, and reported
-- success. The flow row never landed: `bridge_flows.name` is NOT NULL, 031
-- did not supply it, and `INSERT OR IGNORE` swallowed the constraint
-- violation. The migration runner had nothing to report because nothing
-- raised.
--
-- The lesson is about the idiom, not the column. `INSERT OR IGNORE` is meant
-- to make a re-run harmless; it also makes a wrong INSERT harmless, which is
-- the opposite of what a migration wants. Here the insert is plain, so a
-- second constraint mistake would stop the run instead of being absorbed, and
-- `WHERE NOT EXISTS` supplies the idempotence that OR IGNORE was there for.
--
-- 031 is left as it is. Migrations are append-only: editing one that
-- schema_migrations already records as applied would fix this machine and
-- leave every future install running the broken version.

INSERT INTO bridge_flows (
    flow_key, name, description, target_project_path, is_active
)
SELECT
    'lightworker',
    'LightWorker (remote execution)',
    'Remote execution on svend3060 with review on Father (GOAL.md §41)',
    '/home/svend/DPMtF-LightWorker',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM bridge_flows WHERE flow_key = 'lightworker'
);
