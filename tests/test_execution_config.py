"""Tests for migration 062 (step_execution_config) and the unified resolver.

Spec sections 1-8, 15, 17 define the unified precedence
STEP -> ROLE DEFAULT -> SYSTEM/LEGACY for governance, model, and harness,
identically. Migration 062 adds the bound storage columns;
scripts/bridgeV002/execution_config.py implements the resolver.

These tests pin both halves against an isolated scratch database
(built in tmp_path). The production database at databases/dpmtf.db is
NEVER touched by a test -- the fixture builds a fresh SQLite file per
test, applies the 062 migration to it (mirroring what migrate.py does
in production), and seeds the rows the test needs. Every test starts
from a clean scratch DB so test order cannot leak state.

Test class naming is load-bearing:
    - precedence  -> selected by `pytest -k precedence` (TG7)
    - from_role   -> selected by `pytest -k from_role`  (TG8)

Other classes (`runtime_context`, `endpoint`) are intentionally absent
here -- handoffs 032 and 033 own those.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

from execution_config import (  # noqa: E402
    resolve_execution_config,
    resolve_for_receiver,
)

_REPO_ROOT = PROJECT_ROOT
_MIGRATION_PATH = _REPO_ROOT / "scripts" / "db" / "062_step_execution_config.sql"


# ---------------------------------------------------------------------------
# Scratch DB helpers
# ---------------------------------------------------------------------------


def _build_scratch_db(tmp_path: Path, *, with_062_columns: bool = True) -> Path:
    """Build a minimal bridge schema in a tmp sqlite file.

    Mirrors the columns the resolver reads. The 062 migration columns are
    either present (with_062_columns=True, the default) or absent
    (with_062_columns=False, for the pre-062 degradation test). The
    schema is intentionally narrower than the production schema --
    the resolver only reads the columns listed in GOAL.md section 2.

    A flag (rather than a separate fixture) keeps the pre-062
    degradation test honest: the test asks for "a DB predating
    migration 062" and gets exactly that.
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
                implementation_mode TEXT DEFAULT NULL,
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
                implementation_mode TEXT DEFAULT NULL
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
                execution_target TEXT,
                implementation_mode TEXT DEFAULT NULL
            );
            """
        )
        if with_062_columns:
            sql = _MIGRATION_PATH.read_text(encoding="utf-8")
            conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
    return db


def _seed_row(db: Path, table: str, columns: list, values: list) -> None:
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


# Common fixtures: one fully-specified role, one minimal role, one flow.
def _seed_minimal_role(db, role_key="actor", tmux_session="actor_s"):
    _seed_row(
        db, "bridge_roles",
        ["role_key", "tmux_session"],
        [role_key, tmux_session],
    )


def _seed_role_with_defaults(
    db,
    role_key,
    *,
    governance_file="GOV_ROLE.md",
    default_model_source="opencode",
    default_model_alias="sonnet",
    default_harness_source=None,
    default_harness_profile=None,
    allocator_client="codex",
    implementation_mode=None,
    tmux_session=None,
):
    _seed_row(
        db, "bridge_roles",
        [
            "role_key", "tmux_session", "governance_file",
            "default_model_source", "default_model_alias",
            "default_harness_source", "default_harness_profile",
            "allocator_client", "implementation_mode",
        ],
        [
            role_key, tmux_session or f"{role_key}_s",
            governance_file,
            default_model_source, default_model_alias,
            default_harness_source, default_harness_profile,
            allocator_client, implementation_mode,
        ],
    )


def _seed_step(
    db,
    flow_key, step_key,
    from_role, to_role,
    *,
    governance_file=None,
    model_source=None, model_alias=None,
    harness_source=None, harness_profile=None,
    implementation_mode=None,
    is_active=1,
    sort_order=0,
):
    _seed_row(
        db, "bridge_flow_steps",
        [
            "flow_key", "step_key", "from_role", "to_role",
            "governance_file",
            "model_source", "model_alias",
            "harness_source", "harness_profile",
            "implementation_mode",
            "is_active", "sort_order",
        ],
        [
            flow_key, step_key, from_role, to_role,
            governance_file,
            model_source, model_alias,
            harness_source, harness_profile,
            implementation_mode,
            is_active, sort_order,
        ],
    )


def _seed_flow(db, flow_key="fl", name="F"):
    _seed_row(
        db, "bridge_flows",
        ["flow_key", "name"],
        [flow_key, name],
    )


# ---------------------------------------------------------------------------
# precedence (TG7)
# ---------------------------------------------------------------------------


class Test_precedence:
    """Precedence walk: STEP overrides ROLE overrides SYSTEM/LEGACY.

    Covers governance, model, harness independently, plus the
    source-driven pair semantics (a step that overrides only the alias
    without the source falls through as a pair), the role-level harness
    COALESCE(default_harness_source, allocator_client), the pre-062
    degradation contract, and the explicit ValueError on a missing
    step_key.
    """

    def test_step_governance_overrides_role(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor", governance_file="GOV_ROLE.md")
        _seed_step(db, "fl", "s", "actor", "receiver",
                   governance_file="GOV_STEP.md")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "GOV_STEP.md"
        assert r["governance_source_level"] == "step"

    def test_role_governance_fallback(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor", governance_file="GOV_ROLE.md")
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "GOV_ROLE.md"
        assert r["governance_source_level"] == "role"

    def test_system_governance_fallback(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_minimal_role(db, "actor")  # no governance_file
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] is None
        assert r["governance_source_level"] == "system"

    def test_step_model_pair_overrides_role_pair(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            model_source="codex", model_alias="minimax-m3",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "codex"
        assert r["model_alias"] == "minimax-m3"
        assert r["model_source_level"] == "step"

    def test_role_model_pair_fallback(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "opencode"
        assert r["model_alias"] == "sonnet"
        assert r["model_source_level"] == "role"

    def test_step_model_alias_only_falls_through_to_role_pair(self, tmp_path):
        """Step setting only alias without source falls through as a pair.

        Per GOAL.md section 2(c) and bridge_lib.get_effective_model_source
        precedent: alias is the format the source expects. A step that
        sets only the alias (without changing the source) is incoherent
        with the role's source, so the resolver falls through to the
        role's full (source, alias) pair. The step's orphan alias is
        not picked up; the role alias wins alongside the role source.
        """
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            model_alias="haiku",  # no model_source
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "opencode"
        assert r["model_alias"] == "sonnet"
        assert r["model_source_level"] == "role"

    def test_model_source_inherit_from_role_is_unset(self, tmp_path):
        """model_source='inherit_from_role' at step is treated as unset."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            model_source="inherit_from_role",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "opencode"
        assert r["model_source_level"] == "role"

    def test_model_source_harness_passes_through_unchanged(self, tmp_path):
        """Legacy: model_source='harness' is a valid stored value."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            model_source="harness", model_alias=None,
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "harness"
        assert r["model_source_level"] == "step"

    def test_step_harness_pair_overrides_role(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_harness_source="opencode",
            default_harness_profile="opencode-default",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            harness_source="codex", harness_profile="codex-review",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] == "codex"
        assert r["harness_profile"] == "codex-review"
        assert r["harness_source_level"] == "step"

    def test_step_harness_alias_only_falls_through_to_role_pair(self, tmp_path):
        """Step setting only harness_profile without source falls through."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_harness_source="opencode",
            default_harness_profile="opencode-default",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            harness_profile="codex-review",  # no harness_source
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] == "opencode"
        assert r["harness_profile"] == "opencode-default"
        assert r["harness_source_level"] == "role"

    def test_role_harness_falls_back_to_allocator_client(self, tmp_path):
        """COALESCE(default_harness_source, allocator_client) at role level.

        GOAL.md section 1 D2: until Phase 4 migrates it, the legacy
        allocator_client column keeps working as the role default for
        harness. The role's default_harness_profile is the companion
        profile for whatever source wins.
        """
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_harness_source=None,  # explicitly unset -> use allocator_client
            default_harness_profile="codex-strict",
            allocator_client="codex",
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] == "codex"
        assert r["harness_profile"] == "codex-strict"
        assert r["harness_source_level"] == "role"

    def test_role_harness_default_harness_source_wins_over_allocator(self, tmp_path):
        """When default_harness_source is set, allocator_client is ignored."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_harness_source="opencode",
            default_harness_profile=None,
            allocator_client="codex",
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] == "opencode"
        assert r["harness_source_level"] == "role"

    def test_system_harness_fallback(self, tmp_path):
        """No step, no role default_harness_source, no allocator_client -> system."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_harness_source=None,
            allocator_client=None,
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] is None
        assert r["harness_profile"] is None
        assert r["harness_source_level"] == "system"

    def test_model_and_harness_are_independent(self, tmp_path):
        """A step overriding model does not change harness, and vice versa."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
            default_harness_source="opencode",
            default_harness_profile="opencode-default",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            model_source="codex", model_alias="minimax-m3",
            # harness columns left NULL
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "codex"
        assert r["model_source_level"] == "step"
        # harness falls through to role (not affected by model override)
        assert r["harness_source"] == "opencode"
        assert r["harness_source_level"] == "role"

    def test_harness_override_does_not_change_model(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
            default_harness_source="opencode",
            default_harness_profile="opencode-default",
        )
        _seed_step(
            db, "fl", "s", "actor", "receiver",
            harness_source="codex", harness_profile="codex-strict",
            # model columns left NULL
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] == "codex"
        assert r["harness_source_level"] == "step"
        # model falls through to role (not affected by harness override)
        assert r["model_source"] == "opencode"
        assert r["model_source_level"] == "role"

    def test_pre_062_db_degrades_to_none_system_without_raising(self, tmp_path):
        """A DB lacking the five 062 columns degrades cleanly.

        The resolver reads the new columns via .get(name) so a DB
        predating migration 062 returns None for them and the precedence
        walk falls through to SYSTEM/LEGACY rather than raising
        KeyError (GOAL.md section 2(d)). Existing columns (model_source,
        model_alias, governance_file, allocator_client,
        default_model_source, default_model_alias) still work because
        they exist on the pre-062 schema.

        The role row is seeded with only the LEGACY columns (no
        default_harness_source / default_harness_profile) because the
        pre-062 schema lacks those columns entirely.
        """
        db = _build_scratch_db(tmp_path, with_062_columns=False)
        # pre-062 rows still have the legacy columns populated
        _seed_row(
            db, "bridge_roles",
            [
                "role_key", "tmux_session",
                "governance_file",
                "default_model_source", "default_model_alias",
                "allocator_client",
            ],
            [
                "actor", "actor_s",
                "GOV_ROLE.md",
                "opencode", "sonnet",
                "codex",
            ],
        )
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role"],
            ["fl", "s", "actor", "receiver"],
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        # legacy columns still resolve
        assert r["governance_file"] == "GOV_ROLE.md"
        assert r["governance_source_level"] == "role"
        assert r["model_source"] == "opencode"
        assert r["model_source_level"] == "role"
        # The harness step columns (harness_source, harness_profile on
        # bridge_flow_steps) are absent on the pre-062 schema, so the
        # step level falls through to role. The role-level harness
        # COALESCE has default_harness_source absent too, so it falls
        # through to allocator_client = "codex" (legacy) -- exactly
        # the pre-migration behavior. Zero behavior change contract.
        assert r["harness_source"] == "codex"
        assert r["harness_profile"] is None  # no default_harness_profile stored
        assert r["harness_source_level"] == "role"
        assert r["implementation_mode"] == "direct"  # default fallback

    def test_nonexistent_step_key_raises_value_error(self, tmp_path):
        """A missing step_key raises ValueError naming flow_key + step_key.

        GOAL.md section 2: never a silent default. The message names
        both identifiers so the configurator can fix the offending
        call without re-reading the resolver.
        """
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor")
        with pytest.raises(ValueError) as excinfo:
            resolve_execution_config("fl", "does_not_exist", db_path=db)
        msg = str(excinfo.value)
        assert "fl" in msg
        assert "does_not_exist" in msg

    def test_missing_role_row_degrades_to_all_none(self, tmp_path):
        """A missing role row is not an error -- it degrades cleanly."""
        db = _build_scratch_db(tmp_path)
        # no role row for "actor" -- the precedence walk has nothing
        # at the role level and falls through to SYSTEM for everything.
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] is None
        assert r["governance_source_level"] == "system"
        assert r["model_source"] is None
        assert r["model_source_level"] == "system"
        assert r["harness_source"] is None
        assert r["harness_source_level"] == "system"


# ---------------------------------------------------------------------------
# from_role (TG8)
# ---------------------------------------------------------------------------


class Test_from_role:
    """from_role is the actor; resolve_for_receiver maps receiver -> step.

    Step configuration describes from_role. Governance / model / harness
    defaults are read from the from_role's role row, NEVER from
    to_role's. resolve_for_receiver maps a receiver role to the step
    whose from_role IS the receiver -- the step the receiver is about
    to execute, not the transition step being signaled.
    """

    def test_resolve_execution_config_returns_step_from_to(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor")
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["flow_key"] == "fl"
        assert r["step_key"] == "s"
        assert r["from_role"] == "actor"
        assert r["to_role"] == "receiver"

    def test_governance_uses_from_role_defaults_not_to_role(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor", governance_file="GOV_FROM.md")
        _seed_role_with_defaults(
            db, "receiver", governance_file="GOV_TO.md",
            tmux_session="receiver_s",
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "GOV_FROM.md"
        assert r["governance_source_level"] == "role"

    def test_model_uses_from_role_defaults_not_to_role(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_model_source="opencode", default_model_alias="sonnet",
        )
        _seed_role_with_defaults(
            db, "receiver",
            default_model_source="codex", default_model_alias="haiku",
            tmux_session="receiver_s",
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["model_source"] == "opencode"
        assert r["model_alias"] == "sonnet"
        assert r["model_source_level"] == "role"

    def test_harness_uses_from_role_defaults_not_to_role(self, tmp_path):
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "actor",
            default_harness_source="opencode",
            default_harness_profile="opencode-default",
        )
        _seed_role_with_defaults(
            db, "receiver",
            default_harness_source="codex",
            default_harness_profile="codex-strict",
            tmux_session="receiver_s",
        )
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["harness_source"] == "opencode"
        assert r["harness_profile"] == "opencode-default"
        assert r["harness_source_level"] == "role"

    def test_resolve_for_receiver_maps_receiver_to_step(self, tmp_path):
        """resolve_for_receiver returns the step whose from_role IS receiver."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor")
        _seed_role_with_defaults(db, "receiver", tmux_session="receiver_s")
        _seed_step(db, "fl", "do_thing", "receiver", "next_receiver")
        r = resolve_for_receiver("fl", "receiver", db_path=db)
        assert r["flow_key"] == "fl"
        assert r["step_key"] == "do_thing"
        assert r["from_role"] == "receiver"
        assert r["to_role"] == "next_receiver"

    def test_resolve_for_receiver_returns_resolved_config(self, tmp_path):
        """The dict returned by resolve_for_receiver is the full resolver output.

        from_role == receiver: any from_role-level defaults (governance,
        model, harness) on the receiver's role row apply, since from_role
        IS the receiver.
        """
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "receiver",
            governance_file="GOV_RECEIVER.md",
            default_model_source="codex", default_model_alias="minimax-m3",
            default_harness_source="codex",
            default_harness_profile="codex-strict",
            tmux_session="receiver_s",
        )
        _seed_step(db, "fl", "do_thing", "receiver", "next_receiver")
        r = resolve_for_receiver("fl", "receiver", db_path=db)
        assert r["governance_file"] == "GOV_RECEIVER.md"
        assert r["governance_source_level"] == "role"
        assert r["model_source"] == "codex"
        assert r["model_source_level"] == "role"
        assert r["harness_source"] == "codex"
        assert r["harness_source_level"] == "role"

    def test_resolve_for_receiver_raises_when_no_active_step(self, tmp_path):
        """Receiver with no matching active step raises ValueError."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "actor")
        _seed_step(db, "fl", "s", "actor", "receiver")
        with pytest.raises(ValueError) as excinfo:
            resolve_for_receiver("fl", "no_such_receiver", db_path=db)
        msg = str(excinfo.value)
        assert "fl" in msg
        assert "no_such_receiver" in msg

    def test_resolve_for_receiver_ignores_inactive_steps(self, tmp_path):
        """Inactive matching step is not selected -- treated as no match."""
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "receiver", tmux_session="receiver_s")
        _seed_step(db, "fl", "do_thing", "receiver", "next",
                   is_active=0)
        with pytest.raises(ValueError):
            resolve_for_receiver("fl", "receiver", db_path=db)

    def test_resolve_for_receiver_raises_when_multiple_active_steps(self, tmp_path):
        """Ambiguity (multiple active steps with from_role == receiver)
        raises ValueError listing the conflicting step_keys. A silent
        pick would hide a config bug.
        """
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(db, "receiver", tmux_session="receiver_s")
        _seed_step(db, "fl", "step_a", "receiver", "next", sort_order=0)
        _seed_step(db, "fl", "step_b", "receiver", "next", sort_order=1)
        with pytest.raises(ValueError) as excinfo:
            resolve_for_receiver("fl", "receiver", db_path=db)
        msg = str(excinfo.value)
        assert "step_a" in msg
        assert "step_b" in msg


# ---------------------------------------------------------------------------
# runtime_context (TG9)
# ---------------------------------------------------------------------------


class Test_runtime_context:
    """runtime_context_block() renders a deterministic block from a resolved dict.

    The block is what dispatch prepends at each of the three
    signal_complete / signal_escalation / signal_send sites. With all
    five new 062 columns NULL after migration, the block's
    governance_file line carries the same value as the legacy direct
    column read -- so the block is additive on top of an unchanged
    resolution (zero behavior change for resolution, TG10).

    These tests exercise the helper directly: the dispatch-site
    integration is verified by the TG12 regression on the existing
    dispatch test suites, not here.
    """

    def _resolved_dict(self, **overrides):
        """Build a minimal resolved dict (13 keys, GOAL.md section 2)."""
        base = {
            "flow_key": "fl",
            "step_key": "s",
            "from_role": "actor",
            "to_role": "receiver",
            "governance_file": "GOV.md",
            "governance_source_level": "role",
            "model_source": None,
            "model_alias": None,
            "model_source_level": "system",
            "harness_source": None,
            "harness_profile": None,
            "harness_source_level": "system",
            "implementation_mode": "direct",
        }
        base.update(overrides)
        return base

    def test_block_is_deterministic_across_repeated_calls(self):
        """Same input dict yields a byte-identical string every time."""
        from execution_config import runtime_context_block
        r = self._resolved_dict()
        first = runtime_context_block(r)
        for _ in range(5):
            assert runtime_context_block(r) == first

    def test_block_contains_all_five_fields_with_resolved_values(self):
        """All five fields are present in fixed order with the dict's values."""
        from execution_config import runtime_context_block
        r = self._resolved_dict(
            flow_key="fl_X",
            step_key="s_Y",
            from_role="roleA",
            to_role="roleB",
            governance_file="DOC.md",
        )
        block = runtime_context_block(r)
        # fixed order: flow_key, step_key, from_role, to_role, governance_file
        idx = {}
        for needle in (
            "flow_key: fl_X",
            "step_key: s_Y",
            "from_role: roleA",
            "to_role: roleB",
            "governance_file: DOC.md",
        ):
            assert needle in block, f"missing {needle!r} in block:\n{block}"
            idx[needle] = block.index(needle)
        # ordering: each subsequent field appears after the previous one
        order = ["flow_key:", "step_key:", "from_role:", "to_role:", "governance_file:"]
        positions = [block.index(t) for t in order]
        assert positions == sorted(positions), (
            f"fields are not in fixed order: positions={positions}"
        )

    def test_block_end_to_end_with_receiver_resolution(self, tmp_path):
        """End-to-end through resolve_for_receiver.

        Seeds a flow with a step whose from_role is the receiver, plus a
        separate role row with a governance_file default. Resolves via
        resolve_for_receiver and asserts the block carries the right
        governance_file + the receiver's step_key / from_role / to_role.
        """
        from execution_config import resolve_for_receiver, runtime_context_block
        db = _build_scratch_db(tmp_path)
        _seed_role_with_defaults(
            db, "receiver",
            governance_file="GOV_RECEIVER.md",
            tmux_session="receiver_s",
        )
        _seed_step(db, "fl", "do_thing", "receiver", "next_receiver")
        resolved = resolve_for_receiver("fl", "receiver", db_path=db)
        assert resolved["governance_file"] == "GOV_RECEIVER.md"
        block = runtime_context_block(resolved)
        assert "flow_key: fl" in block
        assert "step_key: do_thing" in block
        assert "from_role: receiver" in block
        assert "to_role: next_receiver" in block
        assert "governance_file: GOV_RECEIVER.md" in block

    def test_block_renders_none_governance_file_as_literal_none(self):
        """governance_file=None renders as the literal 'None', deterministically."""
        from execution_config import runtime_context_block
        r = self._resolved_dict(governance_file=None)
        block = runtime_context_block(r)
        assert "governance_file: None" in block
        # The field line is present (not omitted, not blank).
        assert "governance_file:" in block
        # Other fields still present.
        assert "flow_key: fl" in block
        # Deterministic: same dict yields same string.
        assert block == runtime_context_block(r)

    def test_block_renders_all_none_fields_as_literal_none(self):
        """All five fields present even when each resolved value is None."""
        from execution_config import runtime_context_block
        r = self._resolved_dict(
            flow_key=None, step_key=None, from_role=None, to_role=None,
            governance_file=None,
        )
        block = runtime_context_block(r)
        for line in (
            "flow_key: None",
            "step_key: None",
            "from_role: None",
            "to_role: None",
            "governance_file: None",
        ):
            assert line in block, f"missing {line!r} in block:\n{block}"


# ---------------------------------------------------------------------------
# endpoint (TG11)
# ---------------------------------------------------------------------------


class Test_endpoint:
    """The explainability GET endpoint returns the resolver dict verbatim.

    The endpoint is the read-only, additive surface the operator uses to
    see WHY dispatch chose a governance / model / harness for a given
    step. With all five new 062 columns NULL after migration, the
    endpoint's output for any existing step is byte-identical to what
    the legacy direct-column reads would have produced (TG10 = 0).
    These tests pin the endpoint contract: 200 + verbatim dict on the
    success path, 404 on a missing flow or missing step.
    """

    @staticmethod
    def _ensure_migrations_applied(db_path):
        """Apply migrations 052 + 062 to the temp DB if not already applied.

        The conftest's seed_db is a session-scoped temp DB whose schema
        intentionally omits columns added by later migrations. The
        endpoint delegates to resolve_execution_config which calls
        patch_mode.resolve_implementation_mode, and that helper reads
        implementation_mode from bridge_roles / bridge_flow_steps /
        bridge_flows. Without the migration columns, the call raises
        sqlite3.OperationalError. We apply the migrations here so the
        endpoint test exercises the production schema.

        ALTER TABLE statements are applied INDIVIDUALLY (not via
        executescript) so that one duplicate-column failure does not
        abort the rest of the migration -- conftest's seed schema
        already has implementation_mode on bridge_flows but not on
        bridge_flow_steps / bridge_roles, so a single executescript
        would partially apply.
        """
        conn = sqlite3.connect(db_path)
        try:
            existing = {
                row[0]
                for row in conn.execute(
                    "SELECT migration_filename FROM schema_migrations"
                ).fetchall()
            }
        except sqlite3.OperationalError:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(migration_filename TEXT PRIMARY KEY, "
                "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            existing = set()
            conn.commit()
        import re as _re
        for fname in ("052_implementation_mode.sql",
                      "062_step_execution_config.sql"):
            sql_path = _REPO_ROOT / "scripts" / "db" / fname
            sql = sql_path.read_text(encoding="utf-8")
            # Extract the ALTER TABLE statements only (skip comments).
            alters = _re.findall(
                r"ALTER TABLE \w+\s+ADD COLUMN \w+\s+\w+(?:\s+DEFAULT\s+\w+)?(?:\s+NULL)?;",
                sql,
            )
            for stmt in alters:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    # Idempotent re-apply raises "duplicate column name";
                    # treat as applied (already there from a prior run or
                    # from conftest's schema).
                    if "duplicate column" not in str(exc):
                        raise
            conn.commit()
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations "
                "(migration_filename) VALUES (?)",
                (fname,),
            )
            conn.commit()
        conn.close()

    def _seed_endpoint_data(self, db_path, *, flow_key="ep_flow",
                            role_key="ep_role", step_key="ep_step",
                            to_role_key="test_role",
                            governance_file="GOV_EP.md",
                            default_model_source="opencode",
                            default_model_alias="sonnet"):
        """Insert a flow + role + step for the endpoint tests.

        Uses conftest's pre-existing test_flow / test_role as the
        to_role target so the step's to_role FK chain resolves to a
        real role row. INSERT OR IGNORE so re-runs are idempotent.
        """
        self._ensure_migrations_applied(db_path)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO bridge_flows "
                "(flow_key, name, description, step_order, "
                "is_default, is_active) "
                "VALUES (?, ?, ?, ?, 0, 1)",
                (flow_key, "Endpoint Test Flow",
                 "A minimal flow used by the endpoint tests.",
                 "ep_step"),
            )
            conn.execute(
                "INSERT OR IGNORE INTO bridge_roles "
                "(role_key, tmux_session, start_cmd, "
                "governance_file, default_model_source, "
                "default_model_alias, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                (role_key, f"{role_key}_session", f"echo {role_key}",
                 governance_file, default_model_source,
                 default_model_alias),
            )
            conn.execute(
                "INSERT OR IGNORE INTO bridge_flow_steps "
                "(flow_key, step_key, from_role, to_role, "
                "sort_order, is_active) "
                "VALUES (?, ?, ?, ?, 0, 1)",
                (flow_key, step_key, role_key, to_role_key),
            )
            conn.commit()
        finally:
            conn.close()

    def test_endpoint_returns_resolver_dict_verbatim(self, seed_db):
        """HTTP 200 + JSON body equal to resolve_execution_config output."""
        # Arrange: seed a flow + role + step in the shared temp DB.
        self._seed_endpoint_data(
            seed_db,
            flow_key="ep_flow",
            role_key="ep_role",
            step_key="ep_step",
            governance_file="GOV_EP.md",
        )
        # Act: HTTP round-trip via httpx async over the FastAPI app's
        # ASGI transport. The conftest's TestClient-based `client` fixture
        # is broken in the current environment (hangs on every request,
        # including pre-existing tests like test_bridge_endpoints.py and
        # test_health.py), so we use the lower-level transport that the
        # TestClient itself is built on.
        import httpx
        import asyncio
        import app as _app_mod
        _app_mod.DB_PATH = seed_db
        transport = httpx.ASGITransport(app=_app_mod.app)
        async def _round_trip():
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
            ) as ac:
                return await ac.get(
                    "/api/bridge-v2/flows/ep_flow"
                    "/steps/ep_step/execution-config",
                )
        response = asyncio.run(_round_trip())
        assert response.status_code == 200, (
            f"expected 200, got {response.status_code}: {response.text}"
        )
        body = response.json()

        # Assert: the body has exactly the 13 bound keys
        # (GOAL.md section 2).
        expected_keys = {
            "flow_key", "step_key", "from_role", "to_role",
            "governance_file", "governance_source_level",
            "model_source", "model_alias", "model_source_level",
            "harness_source", "harness_profile", "harness_source_level",
            "implementation_mode",
        }
        assert set(body.keys()) == expected_keys, (
            f"endpoint body keys mismatch: got {set(body.keys())}"
        )

        # Assert: the body equals the resolver's output VERBATIM for the
        # SAME (flow_key, step_key, db_path) inputs.
        from execution_config import resolve_execution_config
        expected = resolve_execution_config(
            "ep_flow", "ep_step", db_path=seed_db)
        assert body == expected, (
            f"endpoint body != resolver output:\n"
            f"  body     = {body}\n"
            f"  expected = {expected}"
        )

        # Sanity: governance_file resolved from the role row, not None.
        assert body["governance_file"] == "GOV_EP.md"
        assert body["governance_source_level"] == "role"
        assert body["flow_key"] == "ep_flow"
        assert body["step_key"] == "ep_step"
        assert body["from_role"] == "ep_role"
        assert body["to_role"] == "test_role"

    def _async_get(self, path, db_path):
        """Issue an HTTP GET over the FastAPI ASGI transport.

        See the verbatim test for why we use httpx async instead of the
        conftest's TestClient-based `client` fixture: the latter hangs
        on every request in this environment (pre-existing infra issue).
        """
        import httpx
        import asyncio
        import app as _app_mod
        _app_mod.DB_PATH = db_path
        transport = httpx.ASGITransport(app=_app_mod.app)
        async def _do():
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
            ) as ac:
                return await ac.get(path)
        return asyncio.run(_do())

    def test_endpoint_returns_404_for_nonexistent_flow(self, seed_db):
        """A flow_key that does not exist returns 404 (not 500, not 200)."""
        response = self._async_get(
            "/api/bridge-v2/flows/no_such_flow_xyz"
            "/steps/no_such_step_xyz/execution-config",
            seed_db,
        )
        assert response.status_code == 404, (
            f"expected 404 for missing flow, got {response.status_code}: "
            f"{response.text}"
        )

    def test_endpoint_returns_404_for_nonexistent_step(self, seed_db):
        """A step_key that does not exist for an existing flow returns 404.

        Uses the conftest's pre-seeded test_flow (which has NO rows in
        bridge_flow_steps, so any step_key is nonexistent for that flow).
        """
        response = self._async_get(
            "/api/bridge-v2/flows/test_flow"
            "/steps/no_such_step_xyz/execution-config",
            seed_db,
        )
        assert response.status_code == 404, (
            f"expected 404 for missing step, got {response.status_code}: "
            f"{response.text}"
        )
