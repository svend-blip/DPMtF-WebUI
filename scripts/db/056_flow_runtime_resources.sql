-- 056_flow_runtime_resources.sql
-- Ownership registry for flow-owned runtime resources.
--
-- The ownership rule behind the Stop-servers lifecycle (CLAUDE.md and the
-- flow governance): DPMtF started it -> DPMtF may stop it; externally/
-- manually started -> DPMtF must not stop it. The model allocator already
-- tracks its own runtimes (llama.cpp/SGLang pid files, model leases); this
-- table is the small, general registry for the *harness* side of the new
-- preferred_cloud_harness flow, where a role's runtime is a tmux-resident
-- coding harness rather than an allocator-managed server.
--
-- resource_type: 'tmux_session' (a session start_tmuxflow.py created for a
--   flow) or 'harness_process' (a persistent harness DPMtF launched and can
--   therefore tear down).
-- resource_id: the session name for tmux_session; a stable marker for
--   harness_process (the session it was launched in).
-- pid: the owned process id for harness_process. NULL means "recorded but
--   no pid captured" -- a stop then degrades to a no-op rather than a guess.
--   Stops are ALWAYS by recorded pid/session, never by executable name.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS; migrate.py records the filename
-- in schema_migrations after the first successful apply.

CREATE TABLE IF NOT EXISTS flow_runtime_resources (
    flow_key TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    pid INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (flow_key, resource_type, resource_id)
);
