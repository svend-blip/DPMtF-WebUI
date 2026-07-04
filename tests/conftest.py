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
    CREATE TABLE bridge_roles (
        role_key TEXT PRIMARY KEY,
        tmux_session TEXT NOT NULL,
        start_cmd TEXT,
        model_type TEXT DEFAULT 'ollama',
        cloud_model TEXT,
        ollama_model TEXT,
        setup_script TEXT,
        teardown_script TEXT,
        deliver_error_msg TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE bridge_flows (
        flow_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        step_order TEXT,
        is_default INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE bridge_flow_steps (
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
        FOREIGN KEY (flow_key) REFERENCES bridge_flows(flow_key),
        UNIQUE(flow_key, step_key)
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
                (role_key, tmux_session, start_cmd, model_type,
                 ollama_model, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                "test_role",
                "test_tmux_session",
                "echo test",
                "ollama",
                "qwen-test:7b",
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

    app.py reads `DB_PATH = config.get_db_path()` at module import time
    and stores it as a module global. We patch the global so every
    endpoint that touches the database uses the isolated temp DB.

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
    share the same temp DB (session-scoped).
    """
    return TestClient(app_module.app)


@pytest.fixture()
def seed_db(seeded_db_path: str):
    """Expose the temp DB path for tests that want to insert seed data."""
    return seeded_db_path