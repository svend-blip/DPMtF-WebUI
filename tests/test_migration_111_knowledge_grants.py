"""Migration 111 seeds the operator's own dpmtf-webui grant (GOAL-DRAFT-024).

WORK 1 of GOAL-DRAFT-024 turns knowledge retrieval on for DPMtF's own
repository by recording the D-024-2 triple — ('dpmtf-webui', 'human', NULL)
— in knowledge_scope_grants through the migration system, not by hand.
These tests run the full migration chain against a fresh temporary
database, the way a new installation does, and assert the seed is exactly
one row, is idempotent, and that its rollback removes it cleanly.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import migrate

MIGRATION_111 = PROJECT_ROOT / "scripts" / "db" / "111_knowledge_grants_dpmtf_webui.sql"
ROLLBACK_111 = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "111_knowledge_grants_dpmtf_webui.sql"

GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui' AND agent_role = 'human' AND flow_key IS NULL
"""


@pytest.fixture()
def fresh_db(tmp_path):
    db_path = str(tmp_path / "fresh.db")
    migrate.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn, db_path
    conn.close()


def test_migration_111_seeds_the_dpmtf_webui_grant(fresh_db):
    conn, _ = fresh_db
    assert conn.execute(GRANT_QUERY).fetchone()[0] == 1


def test_migration_111_is_idempotent(fresh_db):
    conn, db_path = fresh_db
    summary = migrate.run_migrations(db_path)
    assert "111_knowledge_grants_dpmtf_webui.sql" not in summary["applied"]
    assert conn.execute(GRANT_QUERY).fetchone()[0] == 1


def test_rollback_111_removes_the_seeded_grant(fresh_db):
    conn, _ = fresh_db
    conn.executescript(ROLLBACK_111.read_text(encoding="utf-8"))
    conn.commit()
    assert conn.execute(GRANT_QUERY).fetchone()[0] == 0
