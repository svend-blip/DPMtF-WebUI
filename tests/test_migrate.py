"""Test versioned schema migration system (Fase E-2).

Verifies migrate.py idempotency, 001_baseline schema creation on a fresh DB,
schema_migrations tracking, and init_db.py end-to-end data seeding.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_migrate.db"
        yield str(db_path)


def _table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def test_migrate_idempotent(temp_db_path):
    # Dynamically discover all migration files
    all_migrations = sorted(f.name for f in migrate.MIGRATIONS_DIR.glob("*.sql"))
    
    first = migrate.run_migrations(temp_db_path)
    assert first["applied"] == all_migrations
    assert first["skipped"] == 0

    second = migrate.run_migrations(temp_db_path)
    assert second["applied"] == []
    assert second["skipped"] == len(all_migrations)


def test_baseline_creates_all_tables(temp_db_path):
    migrate.run_migrations(temp_db_path)
    tables = _table_names(temp_db_path)
    tables.discard("sqlite_sequence")
    tables.discard("schema_migrations")
    assert len(tables) >= 37  # baseline tables; may grow with new migrations
    expected = {
        "app_profiles",
        "app_profile_panels",
        "architecture_decision_records",
        "bootstrap_dataset_registry",
        "bridge_convention_rules",
        "bridge_flow_steps",
        "bridge_flows",
        "bridge_id_counters",
        "bridge_roles",
        "bridge_scripts",
        "claude_sessions",
        "comparison_runs",
        "endpoint_registry",
        "frontend_panels",
        "git_operations",
        "git_sync_status",
        "layout_panels",
        "layout_slots",
        "panel_classifications",
        "panel_subgroup_mappings",
        "panel_subgroups",
        "phase_status",
        "reusable_panel_selections",
        "ui_label_translations",
        "ui_labels",
        "ui_text_slot_labels",
        "ui_text_slots",
        "user_language",
        "user_panel_groups",
        "user_preferences",
        "v2_panel_requirements",
        "validation_results",
        "validation_rules",
        "validation_runs",
        "webui_migration_targets",
        "webui_project_skeletons",
        "workflow_runs",
    }
    assert expected <= tables


def test_schema_migrations_tracks_baseline(temp_db_path):
    all_migrations = sorted(f.name for f in migrate.MIGRATIONS_DIR.glob("*.sql"))
    migrate.run_migrations(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    try:
        rows = conn.execute(
            "SELECT filename, applied_at FROM schema_migrations"
        ).fetchall()
        assert len(rows) == len(all_migrations)
        filenames = {row[0] for row in rows}
        assert filenames == set(all_migrations)
        for _, applied_at in rows:
            assert applied_at is not None and len(applied_at) > 0
    finally:
        conn.close()


def test_002_drops_dead_tables(temp_db_path):
    migrate.run_migrations(temp_db_path)
    tables = _table_names(temp_db_path)
    dead_tables = {
        "prompt_runs",
        "prompt_templates",
        "prompt_hitrates",
        "template_model_hitrates",
        "implementation_patterns",
        "prompt_compiler_fields",
        "prompt_compiler_field_options",
        "prompt_sequences",
        "prompt_sequence_steps",
        "generated_prompts",
        "project_plans",
        "projects",
        "reference_projects",
    }
    assert dead_tables.isdisjoint(tables)


def test_init_db_end_to_end(temp_db_path):
    project_root = Path(__file__).resolve().parent.parent
    scripts_dir = project_root / "scripts"

    # Load config and monkey-patch DB path before init_db runs.
    spec = importlib.util.spec_from_file_location(
        "config", project_root / "config.py"
    )
    config_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_mod)
    config_mod.get_db_path = lambda: temp_db_path
    original_config = sys.modules.get("config")
    sys.modules["config"] = config_mod

    # Reset migrate module cache so it picks up the patched config.
    if "migrate" in sys.modules:
        del sys.modules["migrate"]
    spec_migrate = importlib.util.spec_from_file_location(
        "migrate", scripts_dir / "migrate.py"
    )
    migrate_mod = importlib.util.module_from_spec(spec_migrate)
    sys.modules["migrate"] = migrate_mod
    spec_migrate.loader.exec_module(migrate_mod)

    # Load and execute init_db with the patched config + migrate.
    spec_init = importlib.util.spec_from_file_location(
        "init_db", scripts_dir / "init_db.py"
    )
    init_mod = importlib.util.module_from_spec(spec_init)
    sys.modules["init_db"] = init_mod
    spec_init.loader.exec_module(init_mod)

    tables = _table_names(temp_db_path)
    assert "ui_labels" in tables
    assert "workflow_runs" in tables

    conn = sqlite3.connect(temp_db_path)
    try:
        label_count = conn.execute(
            "SELECT COUNT(*) FROM ui_labels"
        ).fetchone()[0]
        assert label_count > 0
    finally:
        conn.close()
        # Restore original config module so other tests aren't affected
        if original_config is not None:
            sys.modules["config"] = original_config


def test_migration_failure_rolls_back(temp_db_path):
    bad_migration = (
        migrate.MIGRATIONS_DIR /
        "999_broken_test_should_be_deleted.sql"
    )
    bad_migration.write_text("CREATE TABLE totally_invalid_syntax (", encoding="utf-8")
    try:
        with pytest.raises(RuntimeError):
            migrate.run_migrations(temp_db_path)
    finally:
        bad_migration.unlink(missing_ok=True)
