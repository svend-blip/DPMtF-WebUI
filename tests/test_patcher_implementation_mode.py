"""Tests for migration 052 (implementation_mode) and the resolver.

Spec sections 41-42 define the opt-in principle for the Deterministic
Patcher: global default 'direct', precedence role > step > flow, NULL
at any level inherits from the next. Migration 052 adds the storage
columns; scripts/bridgeV002/patch_mode.py implements the resolver.

These tests pin both halves against an isolated scratch database
(built in tmp_path). The production database at databases/dpmtf.db is
opened READ-ONLY to assert that the migration did not opt anything in
— that guard runs only after the handoff's Step 5 has applied the
migration, and skips cleanly with a message if the column is not yet
present so test order never breaks.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

from patch_mode import (  # noqa: E402
    ALLOWED_MODES,
    DEFAULT_MODE,
    resolve_implementation_mode,
)


_REPO_ROOT = PROJECT_ROOT
_MIGRATION_PATH = _REPO_ROOT / "scripts" / "db" / "052_implementation_mode.sql"
_PRODUCTION_DB = _REPO_ROOT / "databases" / "dpmtf.db"


def _build_scratch_db(tmp_path: Path) -> Path:
    """Build a minimal bridge schema in a tmp sqlite file.

    Mirrors the columns required by the resolver's SELECT statements.
    The schema is intentionally narrower than the production schema
    (no flow_steps.id, no governance_file, etc.) — the resolver only
    reads (flow_key, step_key, implementation_mode) and (role_key,
    implementation_mode), so anything else is noise.
    """
    db = tmp_path / "scratch.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE bridge_flows (
                flow_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                step_order TEXT,
                is_default INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                auto_complete_enabled INTEGER DEFAULT 0,
                use_machine_profile INTEGER DEFAULT 0,
                target_project_path TEXT DEFAULT NULL
            );
            CREATE TABLE bridge_flow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_key TEXT NOT NULL,
                step_key TEXT NOT NULL,
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                deliverable_dir TEXT,
                deliverable_pattern TEXT,
                pre_dispatch_script TEXT,
                post_dispatch_script TEXT,
                error_msg TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                rule_key TEXT,
                auto_chain_to_next INTEGER DEFAULT 0,
                validation_required INTEGER DEFAULT 0,
                model_source TEXT,
                model_alias TEXT,
                UNIQUE(flow_key, step_key)
            );
            CREATE TABLE bridge_roles (
                role_key TEXT PRIMARY KEY,
                tmux_session TEXT NOT NULL,
                setup_script TEXT,
                teardown_script TEXT,
                deliver_error_msg TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                restart_policy TEXT DEFAULT 'none',
                governance_file TEXT,
                role_type TEXT DEFAULT 'agent',
                enter_command TEXT DEFAULT 'default',
                config_dir TEXT,
                primary_output_type TEXT,
                default_model_source TEXT,
                default_model_alias TEXT,
                trade_mcp_push_mode TEXT,
                max_output_tokens INTEGER,
                allocator_client TEXT DEFAULT 'opencode',
                fresh_session_command TEXT,
                workdir_mode TEXT NOT NULL DEFAULT 'target_project',
                execution_target TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _apply_migration(db: Path) -> None:
    """Run migration 052 against the given DB. Mirrors what migrate.py does."""
    sql = _MIGRATION_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def _seed_row(db: Path, table: str, columns: list[str], values: list) -> None:
    """Single-row INSERT with parameterized placeholders."""
    placeholders = ", ".join(["?"] * len(values))
    column_list = ", ".join(columns)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    finally:
        conn.close()


class TestMigrationApplies:
    def test_052_applies_cleanly_on_a_scratch_db(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _apply_migration(db)

        conn = sqlite3.connect(str(db))
        try:
            for table in ("bridge_flows", "bridge_flow_steps", "bridge_roles"):
                cols = {
                    row[1]
                    for row in conn.execute(f"PRAGMA table_info({table});").fetchall()
                }
                assert "implementation_mode" in cols, (
                    f"{table} missing implementation_mode after 052"
                )
        finally:
            conn.close()

    def test_052_keeps_every_existing_row_at_null(self, tmp_path):
        """Opt-in is a deliberate separate decision — this migration must
        not flip any existing row to a non-NULL value."""
        db = _build_scratch_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name"],
            ["preferred_cloud", "Preferred Cloud"],
        )
        _seed_row(
            db,
            "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role"],
            ["preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl"],
        )
        _seed_row(
            db,
            "bridge_roles",
            ["role_key", "tmux_session"],
            ["pre_imple_cl", "pre_imple_cl_session"],
        )

        _apply_migration(db)

        conn = sqlite3.connect(str(db))
        try:
            for table in ("bridge_flows", "bridge_flow_steps", "bridge_roles"):
                n_nonnull = conn.execute(
                    f"SELECT COUNT(*) FROM {table} "
                    "WHERE implementation_mode IS NOT NULL"
                ).fetchone()[0]
                assert n_nonnull == 0, (
                    f"{table} has {n_nonnull} non-NULL implementation_mode "
                    "after a fresh apply — the migration opted rows in"
                )
        finally:
            conn.close()


class TestPrecedence:
    def _build_db(self, tmp_path) -> Path:
        db = _build_scratch_db(tmp_path)
        _apply_migration(db)
        return db

    def test_all_unset_resolves_to_default(self, tmp_path):
        db = self._build_db(tmp_path)
        assert (
            resolve_implementation_mode(db, "preferred_cloud")
            == DEFAULT_MODE
        )
        assert (
            resolve_implementation_mode(
                db, "preferred_cloud", "step_a", "pre_imple_cl"
            )
            == DEFAULT_MODE
        )

    def test_flow_level_overrides_default(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        assert (
            resolve_implementation_mode(db, "preferred_cloud")
            == "deterministic_patch"
        )

    def test_step_level_overrides_flow(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        _seed_row(
            db,
            "bridge_flow_steps",
            [
                "flow_key",
                "step_key",
                "from_role",
                "to_role",
                "implementation_mode",
            ],
            [
                "preferred_cloud",
                "step_a",
                "Pre-super-cl",
                "Pre-imple-cl",
                "direct",
            ],
        )
        assert (
            resolve_implementation_mode(db, "preferred_cloud", "step_a")
            == "direct"
        )

    def test_role_level_overrides_step_and_flow(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "direct"],
        )
        _seed_row(
            db,
            "bridge_flow_steps",
            [
                "flow_key",
                "step_key",
                "from_role",
                "to_role",
                "implementation_mode",
            ],
            [
                "preferred_cloud",
                "step_a",
                "Pre-super-cl",
                "Pre-imple-cl",
                "direct",
            ],
        )
        _seed_row(
            db,
            "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            [
                "pre_imple_cl",
                "pre_imple_cl_session",
                "deterministic_patch",
            ],
        )
        assert (
            resolve_implementation_mode(
                db, "preferred_cloud", "step_a", "pre_imple_cl"
            )
            == "deterministic_patch"
        )

    def test_null_at_one_level_inherits_from_the_next(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        _seed_row(
            db,
            "bridge_flow_steps",
            [
                "flow_key",
                "step_key",
                "from_role",
                "to_role",
                "implementation_mode",
            ],
            [
                "preferred_cloud",
                "step_a",
                "Pre-super-cl",
                "Pre-imple-cl",
                None,
            ],
        )
        assert (
            resolve_implementation_mode(db, "preferred_cloud", "step_a")
            == "deterministic_patch"
        )

    def test_role_key_with_no_matching_row_inherits(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        assert (
            resolve_implementation_mode(
                db, "preferred_cloud", "step_a", "no_such_role"
            )
            == "deterministic_patch"
        )

    def test_empty_string_is_treated_as_unset(self, tmp_path):
        """The UI persists blank values for "unset" — the resolver must
        not promote an empty string to a real mode."""
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        _seed_row(
            db,
            "bridge_flow_steps",
            [
                "flow_key",
                "step_key",
                "from_role",
                "to_role",
                "implementation_mode",
            ],
            [
                "preferred_cloud",
                "step_a",
                "Pre-super-cl",
                "Pre-imple-cl",
                "   ",
            ],
        )
        assert (
            resolve_implementation_mode(db, "preferred_cloud", "step_a")
            == "deterministic_patch"
        )

    def test_role_key_none_skips_role_level(self, tmp_path):
        """When the caller has no role, the resolver must walk step
        directly, not pretend a missing role is a NULL role."""
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        _seed_row(
            db,
            "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            [
                "pre_imple_cl",
                "pre_imple_cl_session",
                "direct",
            ],
        )
        assert (
            resolve_implementation_mode(db, "preferred_cloud", "step_a", None)
            == "deterministic_patch"
        )


class TestInvalidValue:
    def _build_db(self, tmp_path) -> Path:
        db = _build_scratch_db(tmp_path)
        _apply_migration(db)
        return db

    def test_invalid_value_in_bridge_flows_raises(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "patcher_v2"],
        )
        with pytest.raises(ValueError) as exc:
            resolve_implementation_mode(db, "preferred_cloud")
        msg = str(exc.value)
        assert "bridge_flows" in msg
        assert "preferred_cloud" in msg
        assert "patcher_v2" in msg

    def test_invalid_value_in_bridge_flow_steps_raises(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        _seed_row(
            db,
            "bridge_flow_steps",
            [
                "flow_key",
                "step_key",
                "from_role",
                "to_role",
                "implementation_mode",
            ],
            [
                "preferred_cloud",
                "step_a",
                "Pre-super-cl",
                "Pre-imple-cl",
                "patcher_v2",
            ],
        )
        with pytest.raises(ValueError) as exc:
            resolve_implementation_mode(db, "preferred_cloud", "step_a")
        msg = str(exc.value)
        assert "bridge_flow_steps" in msg
        assert "preferred_cloud/step_a" in msg
        assert "patcher_v2" in msg

    def test_invalid_value_in_bridge_roles_raises(self, tmp_path):
        db = self._build_db(tmp_path)
        _seed_row(
            db,
            "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            ["pre_imple_cl", "pre_imple_cl_session", "patcher_v2"],
        )
        with pytest.raises(ValueError) as exc:
            resolve_implementation_mode(
                db, "preferred_cloud", "step_a", "pre_imple_cl"
            )
        msg = str(exc.value)
        assert "bridge_roles" in msg
        assert "pre_imple_cl" in msg
        assert "patcher_v2" in msg

    def test_allowed_modes_constant_is_stable(self):
        """The set of allowed modes is part of the public contract
        (this test pins it so a refactor that quietly drops the
        'deterministic_patch' option is caught)."""
        assert ALLOWED_MODES == frozenset({"direct", "deterministic_patch"})


class TestProductionDbGuard:
    def test_every_configured_row_in_production_db_is_valid(self):
        """Production DB must be opened READ-ONLY; every stored
        implementation_mode must be a value the resolver accepts.

        This guard originally asserted ZERO opted-in rows — the run-018
        close state, where the migration itself must not opt anything
        in. That migration property is still proven by the scratch-DB
        tests above. The production count stopped being an invariant on
        2026-08-16, when the Human deliberately opted pi_test in; what
        remains durable is that no row may hold a value outside
        ALLOWED_MODES, because dispatch raises ValueError on such a row
        and the chain stops."""
        if not _PRODUCTION_DB.exists():
            pytest.skip(
                f"production DB not present at {_PRODUCTION_DB} "
                "(Step 5 may not have run yet) — skipping guard"
            )

        uri = f"file:{_PRODUCTION_DB}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.OperationalError as exc:
            pytest.skip(
                f"production DB at {_PRODUCTION_DB} could not be opened "
                f"READ-ONLY ({exc}); skipping guard"
            )

        try:
            for table in ("bridge_flows", "bridge_flow_steps", "bridge_roles"):
                cols = {
                    row[1]
                    for row in conn.execute(
                        f"PRAGMA table_info({table});"
                    ).fetchall()
                }
                if "implementation_mode" not in cols:
                    pytest.skip(
                        f"{table} has no implementation_mode column yet "
                        "(Step 5 has not been applied) — skipping guard"
                    )
                invalid = conn.execute(
                    f"SELECT implementation_mode, COUNT(*) FROM {table} "
                    "WHERE implementation_mode IS NOT NULL "
                    "AND TRIM(implementation_mode) != '' "
                    "AND implementation_mode NOT IN "
                    "('direct', 'deterministic_patch') "
                    "GROUP BY implementation_mode"
                ).fetchall()
                assert not invalid, (
                    f"{table} holds implementation_mode values the "
                    f"resolver rejects: {invalid} — dispatch would raise "
                    "ValueError on these rows and stop the chain"
                )
        finally:
            conn.close()
