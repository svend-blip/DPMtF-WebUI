"""Test migration 005: Unified Model Allocator migration.

These tests run against the live database (after migration 005 is applied)
because the test fixture DB may not include migrations 003/004 columns.
"""
import sqlite3
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config


def _db_path():
    p = config.get_db_path()
    if not os.path.isabs(p):
        p = os.path.join(str(PROJECT_ROOT), p)
    return p


MIGRATED_ROLES = [
    "archi01", "review01", "review02", "imple01pay",
    "archi01cloud", "review01cloud", "review01pay", "review02cloud", "review02pay", "archi01pay",
    "analyst01_trade", "sim01_trade", "trend01_trade",
    "market01_trade", "portfolio01_trade",
    "risk01_trade", "score01_trade", "learn01_trade",
    "review01_trade", "imple01cloud",
]

EXCLUDED_ROLES = ["human", "humancloud", "humanpay", "humantrade"]


def test_migration_005_all_nonhuman_roles_use_allocator():
    """Every non-human, non-excluded role must use model_allocator."""
    conn = sqlite3.connect(_db_path())
    rows = conn.execute("""
        SELECT role_key, default_model_source, default_model_alias, role_type
        FROM bridge_roles WHERE is_active = 1
    """).fetchall()
    conn.close()

    for row in rows:
        role_key, model_source, model_alias, role_type = row
        if role_type == "human":
            assert not model_source, f"Human role '{role_key}' has model_source set"
            continue
        if role_key in EXCLUDED_ROLES:
            continue
        assert model_source == "model_allocator", (
            f"Role '{role_key}' has model_source='{model_source}', expected 'model_allocator'")
        assert model_alias, f"Role '{role_key}' has empty model_alias"


def test_migration_005_no_human_role_migrated():
    """No human role should have model_source set."""
    conn = sqlite3.connect(_db_path())
    rows = conn.execute("""
        SELECT role_key FROM bridge_roles
        WHERE is_active = 1 AND role_type = 'human'
          AND (default_model_source IS NOT NULL AND default_model_source != '')
    """).fetchall()
    conn.close()
    assert len(rows) == 0, f"Human roles with model_source: {[r[0] for r in rows]}"


def test_migration_005_imple01cloud_migrated():
    """imple01cloud should now use model_allocator (Freebuff is just a program, not a separate runtime)."""
    conn = sqlite3.connect(_db_path())
    row = conn.execute("""
        SELECT default_model_source, default_model_alias FROM bridge_roles
        WHERE role_key = 'imple01cloud' AND is_active = 1
    """).fetchone()
    conn.close()
    assert row is not None, "imple01cloud not found"
    assert row[0] == "model_allocator", f"imple01cloud should be migrated, got source={row[0]}"
    assert row[1], "imple01cloud should have a model_alias"


def test_migration_005_imple01_unchanged():
    """imple01 was already on allocator before migration — stays unchanged."""
    conn = sqlite3.connect(_db_path())
    row = conn.execute("""
        SELECT default_model_source, default_model_alias FROM bridge_roles
        WHERE role_key = 'imple01' AND is_active = 1
    """).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "model_allocator"
    assert row[1] == "imple01-local"
