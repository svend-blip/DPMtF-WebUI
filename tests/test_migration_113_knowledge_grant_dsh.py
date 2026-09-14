"""Migration 113 seeds the DeepSeek Harness dpmtf-webui grant (GOAL-DRAFT-033).

WORK 1 of GOAL-DRAFT-033 turns knowledge access for the DeepSeek Harness
role 'dsh' into data: ('dpmtf-webui', 'dsh', NULL) is recorded in
knowledge_scope_grants through the migration system, not by hand. A DSH
session has no flow key -- it sends its workspace as flow_key -- so the grant
is wildcard on flow (flow_key NULL).

These tests run the full migration chain against a fresh temporary database
the way a new installation does, and assert the seed is exactly one row, is
idempotent, and that its rollback removes only the dsh grant (leaving the
run-024 human grant and the migration-112 chain-role grants untouched).
"""

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import migrate

ROLLBACK_113 = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "113_knowledge_grant_dsh.sql"

DSH_GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = ? AND agent_role = ? AND flow_key IS NULL
"""

HUMAN_GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = ? AND agent_role = ? AND flow_key IS NULL
"""

CHAIN_GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = ? AND agent_role = ? AND flow_key = ?
"""


@pytest.fixture()
def fresh_db(tmp_path):
    db_path = str(tmp_path / "fresh.db")
    migrate.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn, db_path
    conn.close()


def test_migration_113_grants_dsh_on_dpmtf_webui(fresh_db):
    conn, _ = fresh_db
    assert conn.execute(DSH_GRANT_QUERY, ("dpmtf-webui", "dsh")).fetchone()[0] == 1


def test_migration_113_is_idempotent(fresh_db):
    conn, db_path = fresh_db
    summary = migrate.run_migrations(db_path)
    assert "113_knowledge_grant_dsh.sql" not in summary["applied"]
    assert conn.execute(DSH_GRANT_QUERY, ("dpmtf-webui", "dsh")).fetchone()[0] == 1


def test_rollback_113_removes_only_the_dsh_grant(fresh_db):
    conn, _ = fresh_db
    conn.executescript(ROLLBACK_113.read_text(encoding="utf-8"))
    conn.commit()
    assert conn.execute(DSH_GRANT_QUERY, ("dpmtf-webui", "dsh")).fetchone()[0] == 0
    assert conn.execute(HUMAN_GRANT_QUERY, ("dpmtf-webui", "human")).fetchone()[0] == 1
    assert (
        conn.execute(CHAIN_GRANT_QUERY, ("dpmtf-webui", "imple01SG", "llama_SG")).fetchone()[0]
        == 1
    )
