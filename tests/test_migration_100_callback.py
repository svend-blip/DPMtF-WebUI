"""Tests for migration 100: callback verdict_summary block."""
import os
import sqlite3
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "databases", "dpmtf.db")
MIGRATION = os.path.join(ROOT, "scripts", "db", "100_callback_verdict_summary.sql")
ROLLBACK = os.path.join(
    ROOT, "scripts", "db", "rollbacks", "100_callback_verdict_summary_rollback.sql"
)


def _read_template():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT content_template FROM bridge_convention_rules WHERE rule_key='callback'"
        )
        row = cur.fetchone()
    finally:
        conn.close()
    assert row is not None, "callback rule missing"
    return row[0]


def test_migration_files_exist_at_convention_paths():
    assert os.path.isfile(MIGRATION), f"missing {MIGRATION}"
    assert os.path.isfile(ROLLBACK), f"missing {ROLLBACK}"


def test_migration_sql_targets_callback_only():
    sql = open(MIGRATION).read()
    # Must reference callback
    assert "rule_key = 'callback'" in sql or "rule_key='callback'" in sql
    # Must NOT reference handoff
    assert "rule_key = 'handoff'" not in sql
    assert "rule_key='handoff'" not in sql


def test_rollback_restores_previous_template():
    # Apply rollback
    subprocess.run(["sqlite3", DB_PATH], input=open(ROLLBACK).read(), text=True, check=True)
    tpl = _read_template()
    assert "<verdict_summary>" not in tpl, "verdict_summary still present after rollback"

    # Re-apply forward migration
    subprocess.run(["sqlite3", DB_PATH], input=open(MIGRATION).read(), text=True, check=True)
    tpl = _read_template()
    assert "<verdict_summary>" in tpl, "verdict_summary missing after re-apply"
    assert "<next_action>" in tpl, "next_action missing after re-apply"
    assert "<stop>" in tpl, "stop missing after re-apply"
