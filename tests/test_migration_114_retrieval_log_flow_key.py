"""Test migration 114: retrieval log gains the caller's flow key.

GOAL-DRAFT-034. Two properties the contract names are proven here:

1. the forward migration adds a nullable TEXT ``flow_key`` column to
   ``knowledge_retrieval_log``;
2. the rollback removes the column again via the copy-table pattern and
   preserves every existing row.

Everything runs against a temporary database under pytest's ``tmp_path``.
The production database at ``databases/dpmtf.db`` is never opened by this
file — the migration under test is applied to it by ``scripts/migrate.py``,
not here.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# First statements, before any project import: keep this test run from
# writing new __pycache__/ entries inside the repository.
sys.dont_write_bytecode = True

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

import migrate  # noqa: E402

MIGRATION_NAME = "114_retrieval_log_flow_key.sql"
MIGRATION_107 = PROJECT_ROOT / "scripts" / "db" / "107_knowledge_tables.sql"
MIGRATION_114 = PROJECT_ROOT / "scripts" / "db" / MIGRATION_NAME
ROLLBACK_114 = (
    PROJECT_ROOT / "scripts" / "db" / "rollbacks" / MIGRATION_NAME
)


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _column_info(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {
        row["name"]: row
        for row in conn.execute(
            "PRAGMA table_info(knowledge_retrieval_log)"
        )
    }


def _build_pre_114_db(tmp_path: Path) -> str:
    """A database carrying the 107 retrieval-log schema, without flow_key."""
    db_path = str(tmp_path / "pre114.db")
    conn = _connect(db_path)
    try:
        conn.executescript(MIGRATION_107.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return db_path


def _build_post_114_db(tmp_path: Path) -> str:
    """A database carrying the post-114 schema with 114 recorded as applied."""
    db_path = str(tmp_path / "post114.db")
    conn = _connect(db_path)
    try:
        conn.executescript(MIGRATION_107.read_text(encoding="utf-8"))
        conn.executescript(MIGRATION_114.read_text(encoding="utf-8"))
        conn.executescript(migrate.SCHEMA_MIGRATIONS_DDL)
        conn.execute(
            "INSERT INTO schema_migrations (filename, applied_at) "
            "VALUES (?, ?)",
            (MIGRATION_NAME, "2026-09-14T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_migration_114_adds_the_flow_key_column(tmp_path):
    db_path = _build_pre_114_db(tmp_path)
    conn = _connect(db_path)
    try:
        assert "flow_key" not in _column_info(conn), (
            "fixture DB must be at the pre-114 schema"
        )

        conn.executescript(MIGRATION_114.read_text(encoding="utf-8"))
        conn.commit()

        columns = _column_info(conn)
        assert "flow_key" in columns
        column = columns["flow_key"]
        assert column["type"].upper() == "TEXT"
        # ``ALTER TABLE ... ADD COLUMN ... DEFAULT NULL`` stores the default
        # as the SQL expression text ``NULL`` in SQLite's PRAGMA table_info.
        assert column["dflt_value"].upper() == "NULL"
        assert column["notnull"] == 0
    finally:
        conn.close()


def test_rollback_114_removes_the_column_and_keeps_rows(tmp_path):
    db_path = _build_post_114_db(tmp_path)
    conn = _connect(db_path)
    try:
        for index in range(2):
            conn.execute(
                "INSERT INTO knowledge_retrieval_log "
                "(provider, scope, query, result_count, sources, "
                "retrieved_token_count, retrieval_duration_ms, agent_role, "
                "run_id, handoff_id, flow_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"stub-{index}",
                    f"scope-{index}",
                    f"query-{index}",
                    index,
                    json.dumps([f"p{index}"]),
                    index * 10,
                    index * 100,
                    f"role-{index}",
                    f"run-{index}",
                    f"handoff-{index}",
                    f"/tmp/ws-{index}",
                ),
            )
        conn.commit()

        before = [
            dict(row)
            for row in conn.execute(
                "SELECT id, provider, scope, query, result_count, sources, "
                "retrieved_token_count, retrieval_duration_ms, agent_role, "
                "run_id, handoff_id, created_at "
                "FROM knowledge_retrieval_log ORDER BY id"
            )
        ]
        assert len(before) == 2

        conn.executescript(ROLLBACK_114.read_text(encoding="utf-8"))
        conn.commit()

        assert "flow_key" not in _column_info(conn), (
            "rollback must remove the flow_key column"
        )

        after = [
            dict(row)
            for row in conn.execute(
                "SELECT id, provider, scope, query, result_count, sources, "
                "retrieved_token_count, retrieval_duration_ms, agent_role, "
                "run_id, handoff_id, created_at "
                "FROM knowledge_retrieval_log ORDER BY id"
            )
        ]
        assert after == before, "rollback must preserve every existing row"

        index_names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert "idx_knowledge_retrieval_log_scope_time" in index_names
        assert "idx_knowledge_retrieval_log_run" in index_names

        remaining = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE filename = ?",
            (MIGRATION_NAME,),
        ).fetchone()[0]
        assert remaining == 0, "rollback must delete the 114 schema_migrations row"
    finally:
        conn.close()
