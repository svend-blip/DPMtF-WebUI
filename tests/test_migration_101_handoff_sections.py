"""Migration 101: the handoff prompt names the result sections and the README Impact block.

Mirrors the live-database correction of 2026-09-03 (README_IMPACT_BLOCK_MISSING
refusals; verdicts without the four result sections).
"""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MIG = PROJECT_ROOT / "scripts" / "db" / "101_handoff_template_result_sections.sql"
ROLLBACK = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "101_handoff_template_result_sections_rollback.sql"


def _apply(conn, path):
    conn.executescript(path.read_text(encoding="utf-8"))


def _fresh_row():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE bridge_convention_rules (rule_key TEXT PRIMARY KEY, content_template TEXT, updated_at TEXT);"
        "INSERT INTO bridge_convention_rules (rule_key, content_template) VALUES ('handoff', 'placeholder'), ('callback', 'untouched');"
    )
    return conn


def test_migration_and_rollback_files_exist():
    assert MIG.is_file() and ROLLBACK.is_file()


def test_migration_touches_only_the_handoff_row_and_names_the_result_contract():
    conn = _fresh_row()
    _apply(conn, MIG)
    handoff = conn.execute("SELECT content_template FROM bridge_convention_rules WHERE rule_key='handoff'").fetchone()[0]
    for needle in ("<handoff_id>", "<source_role>", "<deliverable_input>", "<deliverable_output>",
                   "## README Impact", "README impact: yes", "Reason:", "## Signal Completion"):
        assert needle in handoff, needle
    assert "Your callback file must include these XML sections" not in handoff
    assert conn.execute("SELECT content_template FROM bridge_convention_rules WHERE rule_key='callback'").fetchone()[0] == "untouched"


def test_rollback_restores_the_095_shape():
    conn = _fresh_row()
    _apply(conn, MIG)
    _apply(conn, ROLLBACK)
    handoff = conn.execute("SELECT content_template FROM bridge_convention_rules WHERE rule_key='handoff'").fetchone()[0]
    assert "- <role>: The target role for this handoff" in handoff
    assert "## README Impact" not in handoff
    assert "<chain_advancement>" in handoff


def test_migration_matches_the_live_database_row():
    live = PROJECT_ROOT / "databases" / "dpmtf.db"
    if not live.is_file():
        return
    conn = sqlite3.connect(str(live))
    live_text = conn.execute("SELECT content_template FROM bridge_convention_rules WHERE rule_key='handoff'").fetchone()[0]
    fresh = _fresh_row()
    _apply(fresh, MIG)
    assert fresh.execute("SELECT content_template FROM bridge_convention_rules WHERE rule_key='handoff'").fetchone()[0] == live_text
