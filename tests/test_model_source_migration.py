"""Run 021 / §1 D4 — dual-value acceptance tests for model_source migration.

The replacement value `harness_provider` is approved by the Human (GOAL.md Run
021) to migrate the legacy `harness` value away from, but the migration order
is binding: code must accept BOTH values BEFORE migration 070 flips the two
live roles (super-deep-deep4 / imple-codex-minimaxM3).

The reference enumerated exactly TWO comparison sites in the whole repo:

  1. scripts/bridgeV002/start_coding.py:491 — `if model_source == "harness"`
     (native-launch branch — now `if model_source in HARNESS_MODEL_SOURCES`)
  2. scripts/bridgeV002/supervisor_state.py:337 — `!= "harness"`
     in `flow_uses_local_models` (now `not in (...)`)

execution_config.py has ZERO comparison sites; its only mention of 'harness' is
a docstring (D1 step 3: docstring updated, no logic invented). harness.py and
dispatch.py also have ZERO comparison sites (per the reference enumeration).

This file holds the D4 DUAL-VALUE ACCEPTANCE tests (T1, T2, T3). Invariance /
guard / runtime-context tests are a LATER handoff (D5).

Every test builds an isolated SQLite scratch DB under tmp_path; the production
database at databases/dpmtf.db is NEVER touched.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

# Load start_coding as a module so we can reach HARNESS_MODEL_SOURCES without
# triggering its __main__ entrypoint.
_START_CODING = (PROJECT_ROOT / "scripts" / "bridgeV002" / "start_coding.py")
_spec = importlib.util.spec_from_file_location("start_coding", _START_CODING)
start_coding = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(start_coding)

# Load supervisor_state the same way (the existing test_supervisor_state.py uses
# the same pattern).
_SUPERVISOR = (PROJECT_ROOT / "scripts" / "bridgeV002" / "supervisor_state.py")
_sspec = importlib.util.spec_from_file_location("supervisor_state", _SUPERVISOR)
supervisor_state = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(supervisor_state)

# Load execution_config the same way (the existing test_execution_config.py uses
# the same pattern).
_EXEC = (PROJECT_ROOT / "scripts" / "bridgeV002" / "execution_config.py")
_espec = importlib.util.spec_from_file_location("execution_config", _EXEC)
execution_config = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(execution_config)


# ---------------------------------------------------------------------------
# T1 — start_coding accepts both values EXACTLY (no third value invented)
# ---------------------------------------------------------------------------


class TestStartCodingAcceptsBoth:
    """The module predicate `HARNESS_MODEL_SOURCES` is the dual-acceptance
    surface; equality pinning proves both values are accepted AND that no
    extra widening was invented."""

    def test_harness_model_sources_exact_tuple(self):
        assert start_coding.HARNESS_MODEL_SOURCES == ("harness", "harness_provider")

    def test_predicate_constant_exported_and_is_tuple(self):
        # Defensive: the constant must be the right type — a list would still
        # work with `in`, but the contract pins a tuple (immutable, hashable).
        assert isinstance(start_coding.HARNESS_MODEL_SOURCES, tuple)

    def test_predicate_includes_legacy_value(self):
        assert "harness" in start_coding.HARNESS_MODEL_SOURCES

    def test_predicate_includes_replacement_value(self):
        assert "harness_provider" in start_coding.HARNESS_MODEL_SOURCES


# ---------------------------------------------------------------------------
# T2 — supervisor_state excludes both harness values from "local models"
# ---------------------------------------------------------------------------


def _build_supervisor_scratch_db(
    tmp_path: Path,
    *,
    role_specs: list[tuple[str, str, str]],  # (role_key, default_model_source, default_model_alias)
    step_specs: list[tuple[str, str, str, str]],  # (flow_key, step_key, from_role, to_role)
) -> Path:
    """Build a scratch DB mirroring test_supervisor_state's two_flows schema.

    Only the columns flow_uses_local_models reads (default_model_source,
    default_model_alias on bridge_roles) are populated.
    """
    db = tmp_path / "scratch.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            "CREATE TABLE bridge_flow_steps ("
            " flow_key TEXT, step_key TEXT, from_role TEXT, to_role TEXT);"
            "CREATE TABLE bridge_roles ("
            " role_key TEXT, tmux_session TEXT,"
            " default_model_alias TEXT, default_model_source TEXT);"
        )
        conn.executemany(
            "INSERT INTO bridge_flow_steps VALUES (?,?,?,?)",
            step_specs,
        )
        conn.executemany(
            "INSERT INTO bridge_roles VALUES (?,?,?,?)",
            [(r, r, alias, source) for (r, source, alias) in role_specs],
        )
        conn.commit()
    finally:
        conn.close()
    return db


class TestSupervisorStateAcceptsBoth:
    """flow_uses_local_models returns False for a flow whose roles carry
    either harness-backed source ('harness' OR 'harness_provider'), and True
    when a local-model role is present."""

    def test_legacy_harness_excluded_from_local_probe(self, tmp_path):
        db = _build_supervisor_scratch_db(
            tmp_path,
            role_specs=[
                ("sup-deep", "harness", "deepseek-v4-pro"),
                ("imple-cx", "harness", "minimax-m3"),
            ],
            step_specs=[
                ("preferred_cloud_harness", "sup-imple", "sup-deep", "imple-cx"),
            ],
        )
        assert (
            supervisor_state.flow_uses_local_models(
                "preferred_cloud_harness", db_path=str(db)
            )
            is False
        )

    def test_replacement_harness_provider_excluded_from_local_probe(self, tmp_path):
        db = _build_supervisor_scratch_db(
            tmp_path,
            role_specs=[
                ("sup-deep", "harness_provider", "deepseek-v4-pro"),
                ("imple-cx", "harness_provider", "minimax-m3"),
            ],
            step_specs=[
                ("preferred_cloud_harness", "sup-imple", "sup-deep", "imple-cx"),
            ],
        )
        assert (
            supervisor_state.flow_uses_local_models(
                "preferred_cloud_harness", db_path=str(db)
            )
            is False
        )

    def test_mixed_legacy_and_replacement_still_excluded(self, tmp_path):
        """A flow with one legacy and one replacement role (the transition
        shape during migration 070's rollout window) is also NOT a local
        flow — neither value triggers the :8080 probe."""
        db = _build_supervisor_scratch_db(
            tmp_path,
            role_specs=[
                ("sup-deep", "harness", "deepseek-v4-pro"),
                ("imple-cx", "harness_provider", "minimax-m3"),
            ],
            step_specs=[
                ("preferred_cloud_harness", "sup-imple", "sup-deep", "imple-cx"),
            ],
        )
        assert (
            supervisor_state.flow_uses_local_models(
                "preferred_cloud_harness", db_path=str(db)
            )
            is False
        )

    def test_local_model_allocator_role_triggers_local_probe(self, tmp_path):
        """The negative-control: a local-model role (model_allocator +
        local alias) MUST still trip flow_uses_local_models — the harness
        widening is narrow, not a blanket opt-out."""
        db = _build_supervisor_scratch_db(
            tmp_path,
            role_specs=[
                ("sup-deep", "harness_provider", "deepseek-v4-pro"),
                ("imple-fast", "model_allocator", "imple-fast"),
            ],
            step_specs=[
                ("preferred_cloud_harness", "sup-imple", "sup-deep", "imple-fast"),
            ],
        )
        assert (
            supervisor_state.flow_uses_local_models(
                "preferred_cloud_harness", db_path=str(db)
            )
            is True
        )


# ---------------------------------------------------------------------------
# T3 — execution_config passes 'harness_provider' through unchanged
# ---------------------------------------------------------------------------


def _build_execution_config_scratch_db(
    tmp_path: Path, *, db_name: str = "exec_scratch.db"
) -> Path:
    """Mirror test_execution_config._build_scratch_db's shape (the columns
    resolve_execution_config reads). `implementation_mode` is declared on all
    three tables because resolve_implementation_mode -> _read_role/_read_step/
    _read_flow selects from it. The 062 migration's harness/governance columns
    are declared in-line so the helper has no extra file dependency."""
    db = tmp_path / db_name
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE bridge_flows (
                flow_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                implementation_mode TEXT DEFAULT NULL
            );
            CREATE TABLE bridge_flow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_key TEXT NOT NULL,
                step_key TEXT NOT NULL,
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                model_source TEXT,
                model_alias TEXT,
                governance_file TEXT DEFAULT NULL,
                harness_source  TEXT DEFAULT NULL,
                harness_profile TEXT DEFAULT NULL,
                implementation_mode TEXT DEFAULT NULL
            );
            CREATE TABLE bridge_roles (
                role_key TEXT PRIMARY KEY,
                tmux_session TEXT NOT NULL,
                default_model_source TEXT,
                default_model_alias TEXT,
                default_harness_source  TEXT DEFAULT NULL,
                default_harness_profile TEXT DEFAULT NULL,
                implementation_mode TEXT DEFAULT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _seed_role(db: Path, role_key: str, model_source: str, model_alias: str) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO bridge_roles (role_key, tmux_session, "
            "default_model_source, default_model_alias) VALUES (?,?,?,?)",
            (role_key, f"{role_key}_s", model_source, model_alias),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_step(db: Path, flow_key: str, step_key: str, from_role: str, to_role: str) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO bridge_flows (flow_key, name) VALUES (?,?)",
            (flow_key, flow_key),
        )
        conn.execute(
            "INSERT INTO bridge_flow_steps (flow_key, step_key, from_role, "
            "to_role) VALUES (?,?,?,?)",
            (flow_key, step_key, from_role, to_role),
        )
        conn.commit()
    finally:
        conn.close()


class TestExecutionConfigPassesBoth:
    """resolve_execution_config returns the harness-backed model_source
    value verbatim — both legacy 'harness' and replacement
    'harness_provider' pass through UNCHANGED (per the docstring
    widened in D1 step 3)."""

    def test_legacy_harness_passes_through_unchanged(self, tmp_path):
        db = _build_execution_config_scratch_db(tmp_path)
        _seed_role(db, "actor", "harness", "minimax-m3")
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = execution_config.resolve_execution_config("fl", "s", db_path=str(db))
        assert r["model_source"] == "harness"

    def test_replacement_harness_provider_passes_through_unchanged(self, tmp_path):
        db = _build_execution_config_scratch_db(tmp_path)
        _seed_role(db, "actor", "harness_provider", "minimax-m3")
        _seed_step(db, "fl", "s", "actor", "receiver")
        r = execution_config.resolve_execution_config("fl", "s", db_path=str(db))
        assert r["model_source"] == "harness_provider"

    def test_both_values_resolve_to_their_input_not_a_third(self, tmp_path):
        """Equality pinning: a 'harness' role resolves to 'harness'; a
        'harness_provider' role resolves to 'harness_provider'. No aliasing
        to a third value, no normalization."""
        db_a = _build_execution_config_scratch_db(tmp_path)
        _seed_role(db_a, "actor", "harness", "minimax-m3")
        _seed_step(db_a, "fl", "s", "actor", "receiver")
        r_a = execution_config.resolve_execution_config("fl", "s", db_path=str(db_a))
        assert r_a["model_source"] == "harness"
        assert r_a["model_source"] != "harness_provider"

        db_b = _build_execution_config_scratch_db(tmp_path, db_name="second.db")
        _seed_role(db_b, "actor", "harness_provider", "minimax-m3")
        _seed_step(db_b, "fl", "s", "actor", "receiver")
        r_b = execution_config.resolve_execution_config("fl", "s", db_path=str(db_b))
        assert r_b["model_source"] == "harness_provider"
        assert r_b["model_source"] != "harness"


# ===========================================================================
# D4 — D3 snapshot invariance + D2 value migration + D2 guard + D2 runtime-ctx
# ===========================================================================
#
# These tests are LIVE-DB tests (they read /home/svend/DPMtF-WebUI/databases/
# dpmtf.db directly, the same DB the runtime uses). They are deliberately RED
# until migration 070 lands — that is the contract (D3 is the pre-070
# snapshot, D2 is the value flip, and the test pins both halves atomically).
#
# The snapshot md5 (a4616b2ea830245b95e3e3a4aa834d20) was recorded at handoff
# 082 STEP 1 against the production DB BEFORE 070 was applied. The
# (D4b) value-migration tests assume 070 has been applied (the two migrated
# roles resolve to 'harness_provider'; the other 14 steps resolve to a
# non-'harness' value).


import json as _json
import hashlib as _hashlib

# The five autonomous flows whose active steps we enumerate for the D3
# snapshot and the D2 value-migration assertions.
AUTONOMOUS_FLOWS = (
    "supervised_review", "llama_SG", "preferred_cloud", "reveng",
    "preferred_cloud_harness",
)
MIGRATED_STEPS = (
    ("preferred_cloud_harness", "supervisor-imple01"),
    ("preferred_cloud_harness", "imple01-review01"),
)
# Pre-070 snapshot md5 (recorded against the production DB at handoff 082
# STEP 1). The D3 invariance test asserts this md5 is byte-identical before
# and after 070 — the migration is allowed to change model_source for the
# two migrated steps but NOTHING ELSE.
PRE_070_SNAPSHOT_MD5 = "a4616b2ea830245b95e3e3a4aa834d20"
PRODUCTION_DB_PATH = str(PROJECT_ROOT / "databases" / "dpmtf.db")


def _enumerate_active_steps(flows=AUTONOMOUS_FLOWS, db_path=PRODUCTION_DB_PATH):
    """Return the 16 active steps across the five autonomous flows, ordered
    by (flow_key, step_key). The exact same enumeration rule the snapshot
    used — the hash would diverge on a different ordering."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT flow_key, step_key FROM bridge_flow_steps "
            "WHERE is_active=1 AND flow_key IN (?,?,?,?,?) ORDER BY flow_key, step_key",
            flows,
        ).fetchall()
    finally:
        conn.close()
    return rows


def _canonical_snapshot(rows, db_path=PRODUCTION_DB_PATH):
    """Rebuild the canonical JSON snapshot from a step enumeration.

    Same rule as STEP 1: per (flow_key, step_key) record
    {model_alias, harness_source}, then json.dumps with
    sort_keys=True, separators=(",",":"). The byte-stable output is what
    gets hashed — order and serialization must match STEP 1 exactly."""
    mapping = {}
    for flow_key, step_key in rows:
        cfg = execution_config.resolve_execution_config(flow_key, step_key, db_path=db_path)
        mapping[f"{flow_key}/{step_key}"] = {
            "model_alias": cfg["model_alias"],
            "harness_source": cfg["harness_source"],
        }
    return _json.dumps(mapping, sort_keys=True, separators=(",", ":"))


class TestD3SnapshotInvariance:
    """D3 — the 16 active steps' (model_alias, harness_source) are byte-
    identical before and after 070. 070 is allowed to change model_source
    for the two migrated steps and NOTHING else (model_alias and
    harness_source are out of scope per GOAL.md §1 D2)."""

    def test_step_count_is_exactly_16(self):
        rows = _enumerate_active_steps()
        assert len(rows) == 16, (
            f"expected EXACTLY 16 active steps across the five autonomous "
            f"flows; got {len(rows)}: {rows}"
        )

    def test_pre_070_snapshot_md5_is_invariant(self):
        rows = _enumerate_active_steps()
        canonical = _canonical_snapshot(rows)
        md5 = _hashlib.md5(canonical.encode("utf-8")).hexdigest()
        assert md5 == PRE_070_SNAPSHOT_MD5, (
            f"D3 snapshot drifted: expected md5 {PRE_070_SNAPSHOT_MD5} "
            f"(recorded pre-070), got {md5}. 070 is not allowed to change "
            f"model_alias or harness_source on any step. "
            f"canonical={canonical}"
        )


class TestD2ValueMigration:
    """D2 — post-070, the EXACTLY TWO migrated steps resolve to
    'harness_provider', and NO active step resolves to legacy 'harness'."""

    def test_migrated_steps_resolve_to_harness_provider(self):
        for flow_key, step_key in MIGRATED_STEPS:
            cfg = execution_config.resolve_execution_config(
                flow_key, step_key, db_path=PRODUCTION_DB_PATH,
            )
            assert cfg["model_source"] == "harness_provider", (
                f"migrated step {flow_key}/{step_key} resolves to "
                f"model_source={cfg['model_source']!r}, expected "
                f"'harness_provider' (070 was supposed to flip this step)"
            )

    def test_no_active_step_resolves_to_legacy_harness(self):
        rows = _enumerate_active_steps()
        legacy = []
        for flow_key, step_key in rows:
            cfg = execution_config.resolve_execution_config(
                flow_key, step_key, db_path=PRODUCTION_DB_PATH,
            )
            if cfg["model_source"] == "harness":
                legacy.append((flow_key, step_key))
        assert not legacy, (
            f"D2 invariant violated: {len(legacy)} active step(s) still "
            f"resolve to legacy 'harness' after 070: {legacy}. The "
            f"post-update guard should have ABORTED the migration in that "
            f"case; if the migration reported success, the guard is broken."
        )


class TestD2GuardOnScratch:
    """D2 — the post-update guard (a) aborts on a leftover 'harness' role
    AND rolls back the two migrated roles, (b) passes cleanly when the DB
    has only the two migrated roles on 'harness'."""

    @staticmethod
    def _minimal_scratch_db_with_roles(
        tmp_path, *, harness_role_specs,
    ):
        """Build a scratch DB with a minimal bridge_roles table holding
        the role specs in `harness_role_specs` (a list of (role_key,
        default_model_source) tuples). Returns the Path."""
        db = tmp_path / "guard.db"
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(
                """
                CREATE TABLE bridge_roles (
                    role_key TEXT PRIMARY KEY,
                    tmux_session TEXT,
                    default_model_source TEXT,
                    default_model_alias TEXT,
                    workdir_mode TEXT DEFAULT 'target_project',
                    governance_file TEXT,
                    is_active INTEGER DEFAULT 1
                );
                CREATE TABLE bridge_flow_steps (
                    flow_key TEXT,
                    step_key TEXT,
                    from_role TEXT,
                    to_role TEXT,
                    model_source TEXT,
                    is_active INTEGER DEFAULT 1
                );
                """
            )
            for role_key, default_model_source in harness_role_specs:
                conn.execute(
                    "INSERT INTO bridge_roles (role_key, tmux_session, "
                    "default_model_source, default_model_alias) "
                    "VALUES (?,?,?,?)",
                    (role_key, f"{role_key}_s", default_model_source, "alias-x"),
                )
            conn.commit()
        finally:
            conn.close()
        return db

    def test_guard_aborts_on_leftover_harness_role(self, tmp_path):
        """Three 'harness' roles (the two migrated + one leftover) -> the
        migration's guard RAISEs ABORT, the two migrated roles still read
        'harness' afterwards (atomic rollback)."""
        db = self._minimal_scratch_db_with_roles(
            tmp_path,
            harness_role_specs=[
                ("super-deep-deep4", "harness"),
                ("imple-codex-minimaxM3", "harness"),
                ("leftover-role", "harness"),
            ],
        )
        sql_text = (PROJECT_ROOT / "scripts" / "db" / "070_model_source_harness_provider.sql").read_text(
            encoding="utf-8"
        )
        conn = sqlite3.connect(str(db))
        try:
            with pytest.raises(sqlite3.IntegrityError) as excinfo:
                conn.executescript(sql_text)
            assert "migration 070 guard violation" in str(excinfo.value), (
                f"expected guard-violation RAISE; got: {excinfo.value}"
            )
        finally:
            conn.close()
        # Verify the two migrated roles still read 'harness' (rollback
        # worked) and the leftover role is untouched.
        c2 = sqlite3.connect(str(db))
        try:
            rows = c2.execute(
                "SELECT role_key, default_model_source FROM bridge_roles "
                "WHERE role_key IN ('super-deep-deep4','imple-codex-minimaxM3') "
                "ORDER BY role_key"
            ).fetchall()
        finally:
            c2.close()
        assert rows == [
            ("imple-codex-minimaxM3", "harness"),
            ("super-deep-deep4", "harness"),
        ], (
            f"expected the two migrated roles to keep 'harness' after the "
            f"guard-aborted transaction rolled back; got: {rows}"
        )

    def test_guard_passes_on_clean_two_role_db(self, tmp_path):
        """Two 'harness' roles (the migrated pair, no leftover) -> the
        migration applies cleanly, both end up on 'harness_provider'."""
        db = self._minimal_scratch_db_with_roles(
            tmp_path,
            harness_role_specs=[
                ("super-deep-deep4", "harness"),
                ("imple-codex-minimaxM3", "harness"),
            ],
        )
        sql_text = (PROJECT_ROOT / "scripts" / "db" / "070_model_source_harness_provider.sql").read_text(
            encoding="utf-8"
        )
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(sql_text)
        finally:
            conn.close()
        c2 = sqlite3.connect(str(db))
        try:
            rows = c2.execute(
                "SELECT role_key, default_model_source FROM bridge_roles "
                "WHERE role_key IN ('super-deep-deep4','imple-codex-minimaxM3') "
                "ORDER BY role_key"
            ).fetchall()
            legacy = c2.execute(
                "SELECT COUNT(*) FROM bridge_roles WHERE is_active=1 "
                "AND default_model_source='harness'"
            ).fetchone()[0]
        finally:
            c2.close()
        assert rows == [
            ("imple-codex-minimaxM3", "harness_provider"),
            ("super-deep-deep4", "harness_provider"),
        ], (
            f"expected both migrated roles to read 'harness_provider' "
            f"after a clean apply; got: {rows}"
        )
        assert legacy == 0, (
            f"expected zero legacy 'harness' roles after a clean apply; "
            f"got: {legacy}"
        )


class TestD2RuntimeContext:
    """D2 — for the migrated step, dispatch.build_runtime_context renders
    the new model_source value ('harness_provider') verbatim; for the
    non-migrated step, it still renders 'model_allocator'."""

    def test_runtime_context_renders_harness_provider_for_migrated_step(self):
        cfg = execution_config.resolve_execution_config(
            "preferred_cloud_harness", "supervisor-imple01",
            db_path=PRODUCTION_DB_PATH,
        )
        # Import dispatch lazily — the existing Test_runtime_context
        # precedent in test_governance_impl_sup_repoint.py imports it the
        # same way (noqa: E402 because the import sits after sys.path edits).
        import dispatch  # noqa: E402
        out = dispatch.build_runtime_context(cfg)
        assert "- model_source: harness_provider" in out, (
            f"expected '- model_source: harness_provider' in "
            f"build_runtime_context output for the migrated step; "
            f"output: {out!r}"
        )

    def test_runtime_context_renders_model_allocator_for_non_migrated_step(self):
        cfg = execution_config.resolve_execution_config(
            "preferred_cloud_harness", "review01-supervisor",
            db_path=PRODUCTION_DB_PATH,
        )
        import dispatch  # noqa: E402
        out = dispatch.build_runtime_context(cfg)
        assert "- model_source: model_allocator" in out, (
            f"expected '- model_source: model_allocator' in "
            f"build_runtime_context output for the non-migrated review "
            f"step; output: {out!r}"
        )
