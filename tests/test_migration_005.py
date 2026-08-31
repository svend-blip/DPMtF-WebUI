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

# Roles introduced by the preferred_cloud_harness flow run a coding harness
# (dsh / codex) directly rather than through the model allocator, so their
# model_source is 'harness' — a deliberate, additive exception to 005's
# "everything on model_allocator" invariant. Harness identity stays in
# allocator_client and model identity in default_model_alias.
HARNESS_ROLES = ["super-deep-deep4", "imple-codex-minimaxM3"]

# dsh-harness roles (2026-08-31): the harness owns model identity
# end-to-end — launched via harness_terminal.py, no allocator alias at
# all. An empty default_model_alias is the correct state for these.
HARNESS_OWNS_MODEL_ROLES = [
    "1000-escalation-supervisor",
    "1010-escalation-supervisor",
    "9000-escalation-supervisor",
]


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
        if role_key in HARNESS_OWNS_MODEL_ROLES:
            assert model_source == "harness_provider", (
                f"dsh role '{role_key}' has model_source='{model_source}', "
                f"expected 'harness_provider'")
            continue
        if role_key in HARNESS_ROLES:
            assert model_source in ("harness", "harness_provider"), (
                f"Harness role '{role_key}' has model_source='{model_source}', "
                f"expected 'harness' or 'harness_provider'")
            assert model_alias, f"Harness role '{role_key}' has empty model_alias"
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


def test_migration_005_imple01_still_on_allocator():
    """imple01 was already on allocator before migration — it stays there.

    Asserts the migration's invariant (source + a non-empty alias), NOT a
    specific alias: which model imple01 runs is live configuration the Human
    changes at will (e.g. imple01-local -> cloud_minimax, commit ee4d8d0),
    and pinning it here turned an intentional config change into a red
    suite.
    """
    conn = sqlite3.connect(_db_path())
    row = conn.execute("""
        SELECT default_model_source, default_model_alias FROM bridge_roles
        WHERE role_key = 'imple01' AND is_active = 1
    """).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "model_allocator"
    assert row[1], "imple01 should have a model_alias"
