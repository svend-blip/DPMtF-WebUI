"""Test fixtures for DPMtF-WebUI pytest suite.

Provides an isolated FastAPI TestClient backed by a TEMPORARY SQLite
database (created in pytest's `tmp_path` per test session). The production
database at databases/dpmtf.db is NEVER touched by the test suite.

The fixture strategy:
1. Create a fresh temp DB file in tmp_path/test_dpmtf.db.
2. Create the bridge_roles, bridge_flows, bridge_flow_steps tables
   (the schema required by the /api/bridge-v2/* endpoints). Tests can
   INSERT seed rows into these tables via the `seed_db` fixture.
3. Monkey-patch `app.DB_PATH` to point to the temp file so the running
   app connects to the isolated DB.
4. Yield a `TestClient(app.app)` for HTTP calls.
5. Restore `app.DB_PATH` and remove the temp DB on teardown.
"""

import os
import sys
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── Temp DB schema (minimal subset required by tested endpoints) ─────

_BRIDGE_SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS bridge_roles (
        role_key TEXT PRIMARY KEY,
        tmux_session TEXT NOT NULL,
        start_cmd TEXT,
        setup_script TEXT,
        teardown_script TEXT,
        deliver_error_msg TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        restart_policy TEXT,
        governance_file TEXT,
        role_type TEXT DEFAULT 'agent',
        enter_command TEXT DEFAULT 'default',
        config_dir TEXT,
        primary_output_type TEXT,
        default_model_source TEXT,
        default_model_alias TEXT,
        trade_mcp_push_mode TEXT,
        max_output_tokens INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bridge_flows (
        flow_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        step_order TEXT,
        is_default INTEGER DEFAULT 0,
        use_machine_profile INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        auto_complete_enabled INTEGER DEFAULT 0,
        target_project_path TEXT DEFAULT NULL,
        implementation_mode TEXT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bridge_flow_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flow_key TEXT NOT NULL,
        step_key TEXT NOT NULL,
        from_role TEXT NOT NULL,
        to_role TEXT NOT NULL,
        deliverable_dir TEXT,
        deliverable_pattern TEXT,
        pre_dispatch_script TEXT,
        post_dispatch_script TEXT,
        error_msg TEXT,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        rule_key TEXT,
        auto_chain_to_next INTEGER DEFAULT 0,
        validation_required INTEGER DEFAULT 0,
        model_source TEXT,
        model_alias TEXT,
        FOREIGN KEY (flow_key) REFERENCES bridge_flows(flow_key),
        UNIQUE(flow_key, step_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        workflow_run_id TEXT,
        flow_key TEXT NOT NULL,
        step_key TEXT,
        role_key TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        allocator_alias TEXT,
        handoff_id TEXT,
        idempotency_key TEXT UNIQUE,
        retry_count INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        lease_owner TEXT,
        lease_expires_at TEXT,
        heartbeat_at TEXT,
        priority INTEGER DEFAULT 0,
        goal TEXT NOT NULL,
        target_project TEXT NOT NULL,
        scope_version TEXT,
        checkpoint_path TEXT,
        context_fit_state TEXT,
        parent_job_id TEXT,
        continuation_index INTEGER,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        from_state TEXT,
        to_state TEXT,
        actor TEXT,
        detail TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bridge_scripts (
        script_key TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bridge_conventions (
        rule_key TEXT PRIMARY KEY,
        name TEXT,
        dir_template TEXT,
        pattern_template TEXT,
        error_template TEXT,
        prompt_template TEXT,
        content_template TEXT,
        is_active INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bridge_content_templates (
        rule_key TEXT PRIMARY KEY,
        template TEXT,
        is_active INTEGER DEFAULT 1
    )
    """,
]


def _create_temp_db(db_path: str) -> None:
    """Create a fresh SQLite file at db_path with the bridge schema."""
    conn = sqlite3.connect(db_path)
    try:
        for stmt in _BRIDGE_SCHEMA_SQL:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session")
def temp_db_path(tmp_path_factory) -> str:
    """Session-scoped path to a fresh temporary test database.

    Created once per pytest session; reused across all tests to amortize
    fixture setup. The file lives under pytest's tmp_path and is removed
    automatically when the session ends.
    """
    db_path = str(tmp_path_factory.mktemp("dpmtf_test") / "test_dpmtf.db")
    _create_temp_db(db_path)
    return db_path


@pytest.fixture(scope="session")
def seeded_db_path(temp_db_path: str) -> str:
    """Temp DB pre-populated with one minimal role + flow for endpoint tests."""
    conn = sqlite3.connect(temp_db_path)
    try:
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, start_cmd,
                 default_model_source, default_model_alias, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                "test_role",
                "test_tmux_session",
                "echo test",
                "model_allocator",
                "test-alias",
            ),
        )
        conn.execute(
            """
            INSERT INTO bridge_flows
                (flow_key, name, description, step_order,
                 is_default, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (
                "test_flow",
                "Test Flow",
                "A minimal flow used by the test suite.",
                "step1,step2",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return temp_db_path


@pytest.fixture(scope="session")
def app_module(seeded_db_path: str):
    """Import app.py once and patch DB_PATH to the temp DB.

    Patches `app.DB_PATH` at session scope so the FastAPI app uses the
    isolated temp DB. The `config.get_db_path` patch is applied per-test
    in the `client` fixture to avoid affecting tests that read the live
    database directly (e.g. migration tests).

    Returns the imported app module.
    """
    # Ensure the project root is on sys.path so `import app` resolves.
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import app  # type: ignore[import-not-found]

    original_db_path = app.DB_PATH
    app.DB_PATH = seeded_db_path
    try:
        yield app
    finally:
        app.DB_PATH = original_db_path


@pytest.fixture()
def client(app_module) -> TestClient:
    """Yield a FastAPI TestClient bound to the patched app.

    Each test gets a fresh TestClient (function-scoped) but they all
    share the same temp DB (session-scoped). Patches `config.get_db_path`
    per-test so JobRepository() (which calls config.get_db_path()) also
    uses the temp DB. Migration tests that read the live DB directly are
    not affected because they don't use this fixture.
    """
    import config as dpmtf_config
    original_config_fn = dpmtf_config.get_db_path
    dpmtf_config.get_db_path = lambda: app_module.DB_PATH
    try:
        yield TestClient(app_module.app)
    finally:
        dpmtf_config.get_db_path = original_config_fn


@pytest.fixture()
def seed_db(seeded_db_path: str):
    """Expose the temp DB path for tests that want to insert seed data."""
    return seeded_db_path