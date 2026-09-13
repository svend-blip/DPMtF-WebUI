import sys

sys.dont_write_bytecode = True

import sqlite3

import config
from knowledge import scopes


def _create_scopes_db(tmp_path) -> str:
    """Create a temporary DB with only the columns get_flow_target_project reads."""
    db = tmp_path / "scopes.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE bridge_flows (
            flow_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_project_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return str(db)


def test_scope_for_target_is_the_lowercased_directory_name():
    assert scopes.scope_for_target("/tmp/x/FlowRunner/") == "flowrunner"
    assert scopes.scope_for_target("/tmp/AI_AdvisoryBoard") == "ai_advisoryboard"
    assert scopes.scope_for_target("") == config.get_knowledge_scope()


def test_scope_for_flow_without_key_is_the_configured_scope():
    assert scopes.scope_for_flow("") == config.get_knowledge_scope()
    assert scopes.scope_for_flow(None) == config.get_knowledge_scope()


def test_scope_for_flow_targeting_father_is_the_configured_scope(
    tmp_path, monkeypatch
):
    db = _create_scopes_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name, target_project_path) "
        "VALUES (?, ?, ?)",
        ("father_flow", "Father Flow", config.get_project_root()),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "get_db_path", lambda: db)
    assert config.get_db_path() == db  # never the live database

    assert scopes.scope_for_flow("father_flow") == config.get_knowledge_scope()


def test_scope_for_flow_with_missing_target_falls_back_to_configured_scope(
    tmp_path, monkeypatch
):
    db = _create_scopes_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name, target_project_path) "
        "VALUES (?, ?, ?)",
        ("missing_target_flow", "Missing Target Flow", str(tmp_path / "does_not_exist_dir")),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "get_db_path", lambda: db)
    assert config.get_db_path() == db  # never the live database

    assert scopes.scope_for_flow("missing_target_flow") == config.get_knowledge_scope()
