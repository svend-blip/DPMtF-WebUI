"""Tests for the single knowledge-retrieval-log writer.

GOAL-DRAFT-034. The writer gains an optional ``flow_key`` keyword, but a
database whose ``knowledge_retrieval_log`` predates migration 114 (no
``flow_key`` column) must still accept a row without raising; the column
absence is detected once per connection and the pre-114 INSERT shape is
used.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# First statements, before any project import: keep this test run from
# writing new __pycache__/ entries inside the repository.
sys.dont_write_bytecode = True

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from knowledge import retrieval_log  # noqa: E402

MIGRATION_107 = PROJECT_ROOT / "scripts" / "db" / "107_knowledge_tables.sql"


def _pre_114_db(tmp_path: Path) -> str:
    """A temp database whose log table is exactly the 107 schema."""
    db_path = str(tmp_path / "pre114.db")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(MIGRATION_107.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_record_retrieval_tolerates_a_schema_without_flow_key(
    tmp_path, monkeypatch
):
    db_path = _pre_114_db(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: db_path)

    # Must not raise on a pre-114 schema, even though a flow_key is offered.
    retrieval_log.record_retrieval(
        provider="stub",
        scope="s",
        query="q",
        results=[],
        duration_ms=1,
        agent_role="a",
        run_id="r",
        handoff_id="h",
        flow_key="/tmp/ws",
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM knowledge_retrieval_log"
        ).fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row["provider"] == "stub"
        assert row["scope"] == "s"
        assert row["query"] == "q"
        assert row["result_count"] == 0
        assert row["sources"] == "[]"
        assert row["retrieved_token_count"] == 0
        assert row["retrieval_duration_ms"] == 1
        assert row["agent_role"] == "a"
        assert row["run_id"] == "r"
        assert row["handoff_id"] == "h"
        assert row["created_at"], "created_at must default to a timestamp"

        column_names = {
            column["name"]
            for column in conn.execute(
                "PRAGMA table_info(knowledge_retrieval_log)"
            )
        }
        assert "flow_key" not in column_names, (
            "pre-114 schema must remain without the flow_key column"
        )
    finally:
        conn.close()
