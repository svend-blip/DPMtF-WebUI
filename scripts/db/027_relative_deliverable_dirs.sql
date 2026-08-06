-- 027_relative_deliverable_dirs.sql
-- Store deliverable_dir relative to the bridge directory.
--
-- Migrations 008 and 010 wrote the author's own paths — '/home/svend/flows/
-- supervisor/handoffs' and four more for supervised_review — so every fresh
-- install ended up with a database pointing at another person's directories.
-- Those files are fixed, which covers new installs; this repairs the rows that
-- existing databases already carry, including the ones seeded before the
-- migration system existed (cloud_llm and strict_review).
--
-- dispatch.py resolves a non-absolute deliverable_dir with
-- os.path.join(bridge_dir, …), which is the convention llama_SG has used from
-- the start: 'llama_SG/handoffs', not the full path.
--
-- Only rows under the bridge directory are rewritten. The trade flows point at
-- '/home/svend/trade-ui/inbox/pending', which is outside it — making that
-- relative would silently redirect trade output into the bridge tree. It has
-- its own resolver, config.get_trade_inbox_dir(), and is left alone here.
--
-- bridge_flows.target_project_path is also left alone. It names a project
-- checkout and is chosen per project in the database, so an absolute path is
-- what it is for.

-- Matched by shape rather than by this machine's path: strip everything up to
-- and including the '/flows/' segment. Naming '/home/svend/flows/' here would
-- have reintroduced the very literal being removed, and would only repair
-- databases that came from this machine.

UPDATE bridge_flow_steps
SET deliverable_dir = SUBSTR(deliverable_dir,
                             INSTR(deliverable_dir, '/flows/') + LENGTH('/flows/'))
WHERE deliverable_dir LIKE '/%/flows/%';
