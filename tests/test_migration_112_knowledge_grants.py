"""Migration 112 grants the internal dpmtf-webui scope to chain roles.

WORK 1 of GOAL-DRAFT-028 turns the knowledge scope grant into data: every
active bridge_flow_steps row whose flow targets Father (bridge_flows
.target_project_path is NULL, empty, or names the DPMtF checkout) and whose
flow_key does not start with 'example' gets ('dpmtf-webui', to_role,
flow_key). The compiler passes to_role as agent_role, so the grant is keyed
by exactly the string the guard compares.

These tests run the full migration chain against a fresh temporary database
the way a new install does, then re-run the migration file against a seeded
catalog to exercise its predicate deterministically. The fresh catalog is
not empty — migrations 025, 091, 104 and 106 seed flows before 112 first
runs — so the fixture resets the chain-role grants the initial apply
produced (keeping only the run-024 operator grant) before re-applying 112
against the exact Father/foreign/example states the contract requires.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import migrate

MIGRATION_112 = PROJECT_ROOT / "scripts" / "db" / "112_knowledge_grants_dpmtf_chain_roles.sql"
ROLLBACK_112 = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "112_knowledge_grants_dpmtf_chain_roles.sql"

CHAIN_GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui' AND agent_role = 'imple01SG' AND flow_key = 'llama_SG'
"""

FOREIGN_GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui' AND flow_key = '1020-02-ELOOP'
"""

EXAMPLE_GRANT_QUERY = """
SELECT COUNT(*) FROM knowledge_scope_grants
WHERE scope = 'dpmtf-webui' AND flow_key LIKE 'example%'
"""

HUMAN_GRANT_QUERY = """
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


def _seed_catalog(conn):
    """Seed the three flows the predicate must distinguish.

    INSERT OR IGNORE keeps this safe on the fresh catalog where llama_SG
    (migration 025) and 1020-02-ELOOP (migration 104) already exist; the
    UPDATEs then force the exact target states the contract names.
    """
    conn.execute(
        "INSERT OR IGNORE INTO bridge_flows (flow_key, name, target_project_path) "
        "VALUES (?, ?, ?)",
        ("llama_SG", "Llama SG", "/home/svend/DPMtF-WebUI"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO bridge_flows (flow_key, name, target_project_path) "
        "VALUES (?, ?, ?)",
        ("1020-02-ELOOP", "1020 ELOOP", "/home/svend/AI_AdvisoryBoard"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO bridge_flows (flow_key, name, target_project_path) "
        "VALUES (?, ?, ?)",
        ("example-demo", "Example demo", None),
    )
    conn.execute(
        "INSERT OR IGNORE INTO bridge_flow_steps "
        "(flow_key, step_key, from_role, to_role, is_active) VALUES (?, ?, ?, ?, 1)",
        ("llama_SG", "supervisor-imple01", "supervisor01_llama", "imple01SG"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO bridge_flow_steps "
        "(flow_key, step_key, from_role, to_role, is_active) VALUES (?, ?, ?, ?, 1)",
        ("1020-02-ELOOP", "decomposer-implementer", "1020-execution-decomposer", "1020-implementer"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO bridge_flow_steps "
        "(flow_key, step_key, from_role, to_role, is_active) VALUES (?, ?, ?, ?, 1)",
        ("example-demo", "demo-step", "demo-from", "demo"),
    )
    conn.execute(
        "UPDATE bridge_flows SET target_project_path = ? WHERE flow_key = ?",
        ("/home/svend/DPMtF-WebUI", "llama_SG"),
    )
    conn.execute(
        "UPDATE bridge_flows SET target_project_path = ? WHERE flow_key = ?",
        ("/home/svend/AI_AdvisoryBoard", "1020-02-ELOOP"),
    )
    conn.commit()


def _reset_grants_to_operator_only(conn):
    """Drop the chain-role grants the initial full-chain apply produced.

    run_migrations already applied migration 112 against the pre-seeded
    catalog (where both llama_SG and 1020-02-ELOOP still carry a NULL
    target), so its auto-inserted grants must be removed before the seeded
    re-run below. The run-024 operator grant ('dpmtf-webui', 'human', NULL)
    is deliberately kept.
    """
    conn.execute(
        "DELETE FROM knowledge_scope_grants "
        "WHERE NOT (scope = 'dpmtf-webui' AND agent_role = 'human' AND flow_key IS NULL)"
    )
    conn.commit()


def _apply_migration_112(conn):
    conn.executescript(MIGRATION_112.read_text(encoding="utf-8"))
    conn.commit()


def test_migration_112_grants_every_father_targeted_chain_role(fresh_db):
    conn, _ = fresh_db
    _seed_catalog(conn)
    _reset_grants_to_operator_only(conn)
    _apply_migration_112(conn)
    assert conn.execute(CHAIN_GRANT_QUERY).fetchone()[0] == 1


def test_migration_112_grants_nothing_to_foreign_flows(fresh_db):
    conn, _ = fresh_db
    _seed_catalog(conn)
    _reset_grants_to_operator_only(conn)
    _apply_migration_112(conn)
    assert conn.execute(FOREIGN_GRANT_QUERY).fetchone()[0] == 0
    assert conn.execute(EXAMPLE_GRANT_QUERY).fetchone()[0] == 0


def test_rollback_112_keeps_the_human_grant(fresh_db):
    conn, _ = fresh_db
    _seed_catalog(conn)
    _reset_grants_to_operator_only(conn)
    _apply_migration_112(conn)
    conn.executescript(ROLLBACK_112.read_text(encoding="utf-8"))
    conn.commit()
    assert conn.execute(HUMAN_GRANT_QUERY).fetchone()[0] == 1
    assert conn.execute(CHAIN_GRANT_QUERY).fetchone()[0] == 0
