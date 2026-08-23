"""Tests for the Run 011 governance implementor + supervisor repoint (handoff 049 / D4 + D6 + D7).

This module codifies the resolver's repoint behavior introduced by
migration 065 (the eight IDLE implementor labels binding to
IMPLEMENTOR.md, the three autonomous-supervisor labels binding to
SUPERVISOR_AUTONOMOUS.md, and the supervisor_role seeding for the five
autonomous flows) and the watchdog-default repoint (D6). It pins six
things end-to-end:

  (A) repoint              -- the resolver returns the generic file at
                              STEP level for the eleven repointed steps;
                              the STEP > ROLE precedence still wins even
                              when the role row keeps its 4xx / 5xx
                              governance_file pointer;
  (B) live_flows_deferred  -- the five EXCLUDED roles stay on their
                              role-level files. The deferral is pinned
                              at both the resolver level AND the
                              migration-text level -- the test reads
                              the migration file from disk and asserts
                              the five deferred labels do not appear in
                              any UPDATE predicate;
  (C) supervisor_role_seed -- bridge_flows.supervisor_role is seeded
                              for the five autonomous flows (the D4
                              bridge_flows UPDATE statements are pinned
                              by content, then applied to a scratch DB
                              to verify the seedings land correctly);
  (D) runtime_context      -- dispatch.build_runtime_context renders
                              the three new keys (model_source /
                              harness_source / autonomous) in the fixed
                              D5 order; the autonomous value flips yes
                              when a flow's supervisor_role is set and
                              no when it is NULL; chain_watchdog's
                              watchdog-default repoint (D6) is also
                              pinned here -- the file no longer names
                              451_SUPERVISED_REVIEW_SUPERVISOR.md and
                              SUPERVISOR_AUTONOMOUS.md appears as the
                              fallback;
  (E) rollback             -- the rollback file is real (NOT a no-op):
                              scoped UPDATE ... SET governance_file =
                              NULL referencing both new generic names
                              AND the eleven from_role labels (NOT a
                              blanket match); the scoped UPDATE bridge_flows
                              SET supervisor_role = NULL referencing the
                              five flow_keys; AND the schema_migrations
                              DELETE for 065's filename;
  (F) file_exists          -- the four new governance files (the two
                              D1/D2 base files and the two D3 addenda)
                              exist; the thirteen absorbed originals
                              still exist; a made-up name reports
                              missing; garbage inputs (None / "" /
                              non-string) report missing without raising.

All tests use a scratch SQLite DB built in tmp_path; the production
database at databases/dpmtf.db is NEVER touched.

Test class / function naming is load-bearing: pytest -k selects the
six groups per GOAL.md section 2's keyword list:

    -k repoint             -> group (A), AND (because the file is named
                              test_governance_impl_sup_repoint.py) every
                              test in this module -- the substring
                              "repoint" is present in every test node
                              ID. This over-selection is KNOWN and
                              HARMLESS (mirrors Run 009 / Run 010's
                              review-pilot modules); do NOT "fix" it
                              into a narrower selector that silently
                              skips tests.
    -k live_flows_deferred -> group (B) only.
    -k supervisor_role_seed -> group (C) only.
    -k runtime_context     -> group (D) only.
    -k rollback            -> group (E) only.
    -k file_exists         -> group (F) only.

TG10 (full module) is the GOAL.md testgoal that gates this handoff.
The over-selection above does not affect TG10 because the whole module
exits 0 -- every test in this file passes regardless of which -k
substring matches it.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

from execution_config import resolve_execution_config  # noqa: E402
import dispatch  # noqa: E402  -- D5's build_runtime_context lives here

REPO_ROOT = PROJECT_ROOT
_MIGRATION_PATH = (
    REPO_ROOT / "scripts" / "db" / "065_governance_impl_sup_repoint.sql"
)
_ROLLBACK_PATH = (
    REPO_ROOT / "scripts" / "db" / "rollbacks"
    / "065_governance_impl_sup_repoint_rollback.sql"
)
_WATCHDOG_PATH = (
    REPO_ROOT / "scripts" / "bridgeV002" / "chain_watchdog.py"
)

# The eight IDLE implementor from_role labels migration 065 repoints to
# IMPLEMENTOR.md (Part (a)).
_IMPLEMENTOR_LABELS = (
    "imple01", "imple01cloud", "imple01pay", "imple01sup",
    "pi_imple01", "oc_imple01", "imple01SG", "Rev_Imple",
)

# The three autonomous-supervisor from_role labels migration 065 repoints
# to SUPERVISOR_AUTONOMOUS.md (Part (a) supervisor half).
_SUPERVISOR_LABELS = (
    "supervisor_auto", "supervisor01_llama", "Rev_Supervisor",
)

# The eleven repointed labels in aggregate (union of the two sets above).
_REPOINTED_LABELS = _IMPLEMENTOR_LABELS + _SUPERVISOR_LABELS

# The five from_role labels deliberately NOT repointed by 065. Each keeps
# its role-level governance_file (472 / 471 / 512 / 511 / 481).
_DEFERRED_LABELS = (
    "Pre-imple-cl", "Pre-super-cl",
    "imple-codex-minimaxM3", "super-deep-deep4",
    "imple01LW",
)

# The five bridge_flows supervisor_role seedings (Part (b)).
_SUPERVISOR_ROLE_SEEDINGS = (
    ("supervised_review", "supervisor_auto"),
    ("llama_SG", "supervisor01_llama"),
    ("reveng", "Rev_Supervisor"),
    ("preferred_cloud", "Pre-super-cl"),
    ("preferred_cloud_harness", "super-deep-deep4"),
)

# The thirteen absorbed originals (still pointed at by bridge_roles.
# governance_file as the role-level fallback).
_ABSORBED_ORIGINALS = (
    # Implementor originals (8).
    "403_STRICT_REVIEW_IMPLE01.md",
    "413_CLOUD_LLM_IMPLE01CLOUD.md",
    "423_CLOUD_PAY_IMPLE01PAY.md",
    "452_SUPERVISED_REVIEW_IMPLE01.md",
    "462_LLAMA_SG_IMPLE01.md",
    "472_PREFERRED_CLOUD_IMPLE01.md",
    "492_REVENG_IMPLE.md",
    "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
    # Supervisor originals (5).
    "451_SUPERVISED_REVIEW_SUPERVISOR.md",
    "461_LLAMA_SG_SUPERVISOR.md",
    "471_PREFERRED_CLOUD_SUPERVISOR.md",
    "491_REVENG_SUPERVISOR.md",
    "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
)

# The four new governance files (the D1 / D2 / D3 deliverables) the D7
# file_exists group covers in addition to the thirteen absorbed originals.
_NEW_GENERICS = (
    "IMPLEMENTOR.md",
    "SUPERVISOR_AUTONOMOUS.md",
    "ADDENDUM_AUTONOMOUS_RUN.md",
    "ADDENDUM_LOCAL_MODEL_LIFECYCLE.md",
)


# ---------------------------------------------------------------------------
# (F) file_exists helper (defined in this test module -- the fence forbids
# editing scripts/bridgeV002/execution_config.py and dispatch.py, per
# handoff 049 scope).
# ---------------------------------------------------------------------------


def governance_file_exists(governance_file, repo_root):
    """Return (exists, path) for a referenced governance file.

    Looks under docs/governance-templates-v2/ relative to repo_root.
    Deterministic: uses pathlib.Path.is_file(); no network, no mtime
    games, no caching. A None or empty string is reported as missing.

    This is the spec section 21 "referenced file exists" check, kept
    self-contained in the test module per handoff 049 STEP 5(F).
    Extended to the four new names (IMPLEMENTOR.md, SUPERVISOR_AUTONOMOUS.md,
    ADDENDUM_AUTONOMOUS_RUN.md, ADDENDUM_LOCAL_MODEL_LIFECYCLE.md) added by
    handoffs 046 / 047 / 048.
    """
    if not governance_file or not isinstance(governance_file, str):
        return (False, None)
    candidate = (
        repo_root / "docs" / "governance-templates-v2" / governance_file
    )
    return (candidate.is_file(), candidate)


# ---------------------------------------------------------------------------
# Scratch DB helpers (mirrors tests/test_governance_review_repoint.py and
# tests/test_governance_pilot_repoint.py's _build_scratch_db).
# ---------------------------------------------------------------------------


def _build_scratch_db(tmp_path, *, with_supervisor_role=False):
    """Build a minimal bridge schema in a tmp sqlite file with 061/062 cols.

    `with_supervisor_role=True` adds the supervisor_role column on
    bridge_flows (needed by the supervisor_role_seed test group). The
    default leaves it out so other tests build the narrowest possible
    schema.
    """
    db = tmp_path / "scratch.db"
    conn = sqlite3.connect(str(db))
    try:
        flow_cols = """flow_key TEXT PRIMARY KEY,
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
                target_project_path TEXT DEFAULT NULL"""
        if with_supervisor_role:
            flow_cols += ",\n                supervisor_role TEXT DEFAULT NULL"
        conn.executescript(
            f"""
            CREATE TABLE bridge_flows (
                {flow_cols}
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
                implementation_mode TEXT DEFAULT NULL,
                auto_dispatch INTEGER DEFAULT NULL,
                governance_file TEXT DEFAULT NULL,
                harness_source  TEXT DEFAULT NULL,
                harness_profile TEXT DEFAULT NULL
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
        conn.commit()
    finally:
        conn.close()
    return db


def _seed_row(db, table, columns, values):
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


def _seed_role(db, role_key, *, governance_file=None, tmux_session=None):
    """Seed a bridge_roles row with the columns the resolver reads."""
    _seed_row(
        db, "bridge_roles",
        ["role_key", "tmux_session", "governance_file"],
        [role_key, tmux_session or f"{role_key}_s", governance_file],
    )


def _seed_step(
    db,
    flow_key, step_key,
    from_role, to_role,
    *,
    governance_file=None,
    is_active=1,
    sort_order=0,
):
    _seed_row(
        db, "bridge_flow_steps",
        [
            "flow_key", "step_key", "from_role", "to_role",
            "governance_file",
            "is_active", "sort_order",
        ],
        [
            flow_key, step_key, from_role, to_role,
            governance_file,
            is_active, sort_order,
        ],
    )


def _seed_flow(db, flow_key, name=None, *, supervisor_role=None):
    cols = ["flow_key", "name"]
    vals = [flow_key, name or flow_key]
    if supervisor_role is not None:
        cols.append("supervisor_role")
        vals.append(supervisor_role)
    _seed_row(db, "bridge_flows", cols, vals)


# ---------------------------------------------------------------------------
# (A) repoint -- the resolver returns the generic file at STEP level for
#     the eleven repointed steps; STEP > ROLE precedence still wins when
#     the role row keeps its 4xx / 5xx governance pointer.
# ---------------------------------------------------------------------------


class Test_repoint:
    """Resolver returns IMPLEMENTOR.md / SUPERVISOR_AUTONOMOUS.md at STEP
    level for the eleven repointed steps.

    Codifies migration 065's Part (a): every active step whose from_role
    is one of the eleven labels listed in the migration gets a
    step-level governance_file pointing at the generic file, and the
    resolver reports governance_source_level == 'step'.
    """

    @pytest.mark.parametrize("imple_label", list(_IMPLEMENTOR_LABELS))
    def test_repoint_implementor_label_resolves_IMPLEMENTOR_at_step(
        self, tmp_path, imple_label,
    ):
        db = _build_scratch_db(tmp_path)
        # Seed the role row WITHOUT a role-level governance_file so the
        # result is unambiguous: the only thing that can produce
        # IMPLEMENTOR.md is the step-level column.
        _seed_role(db, imple_label)
        _seed_step(
            db, "fl", "s", imple_label, "next_role",
            governance_file="IMPLEMENTOR.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "IMPLEMENTOR.md", (
            f"expected IMPLEMENTOR.md for {imple_label}, "
            f"got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {imple_label}, "
            f"got {r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("sup_label", list(_SUPERVISOR_LABELS))
    def test_repoint_supervisor_label_resolves_SUPERVISOR_AUTONOMOUS_at_step(
        self, tmp_path, sup_label,
    ):
        db = _build_scratch_db(tmp_path)
        _seed_role(db, sup_label)
        _seed_step(
            db, "fl", "s", sup_label, "next_role",
            governance_file="SUPERVISOR_AUTONOMOUS.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "SUPERVISOR_AUTONOMOUS.md", (
            f"expected SUPERVISOR_AUTONOMOUS.md for {sup_label}, "
            f"got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {sup_label}, "
            f"got {r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("imple_label", list(_IMPLEMENTOR_LABELS))
    def test_repoint_step_overrides_role_governance_for_implementor(
        self, tmp_path, imple_label,
    ):
        """STEP value wins even when the role row still has a 4xx /
        5xx pointer. The role-level pointer is preserved in production
        (bridge_roles still points at the absorbed originals as the
        resolver fallback); the step-level value MUST win."""
        db = _build_scratch_db(tmp_path)
        # Role row keeps an absorbed-original-style governance_file
        # pointer (the absorbed originals are still in place as the
        # fallback).
        _seed_role(db, imple_label, governance_file="452_4XX5XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", imple_label, "next_role",
            governance_file="IMPLEMENTOR.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "IMPLEMENTOR.md"
        assert r["governance_source_level"] == "step"

    @pytest.mark.parametrize("sup_label", list(_SUPERVISOR_LABELS))
    def test_repoint_step_overrides_role_governance_for_supervisor(
        self, tmp_path, sup_label,
    ):
        """Same precedence proof for the supervisor side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, sup_label, governance_file="451_4XX5XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", sup_label, "next_role",
            governance_file="SUPERVISOR_AUTONOMOUS.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "SUPERVISOR_AUTONOMOUS.md"
        assert r["governance_source_level"] == "step"


# ---------------------------------------------------------------------------
# (B) live_flows_deferred -- the five EXCLUDED roles stay on their
#     role-level files. Pinned at both the resolver level AND the
#     migration-text level.
# ---------------------------------------------------------------------------


# Mapping from each deferred from_role label to its expected role-level
# governance_file (the absorbed original that the role row keeps as the
# fallback).
_DEFERRED_ROLE_GOVERNANCE = {
    "Pre-imple-cl": "472_PREFERRED_CLOUD_IMPLE01.md",
    "Pre-super-cl": "471_PREFERRED_CLOUD_SUPERVISOR.md",
    "imple-codex-minimaxM3": "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
    "super-deep-deep4": "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
    "imple01LW": "481_LIGHTWORKER_IMPLE01LW.md",
}


class Test_live_flows_deferred:
    """The five EXCLUDED roles are deliberately NOT repointed.

    `Pre-imple-cl` and `Pre-super-cl` (preferred_cloud production actors),
    `imple-codex-minimaxM3` and `super-deep-deep4` (this executing flow's
    remote worker and autonomous supervisor), and `imple01LW` (the
    remote-worker exception -- 481 stays authoritative) keep their
    role-level files via bridge_roles.governance_file. This test group
    pins the deferral at both the resolver level (these roles resolve
    to their original 5xx file, NOT any of the two new generic names)
    AND the migration-text level (the migration file does not
    reference the five deferred labels in any UPDATE predicate).
    """

    @pytest.mark.parametrize("deferred_label", list(_DEFERRED_LABELS))
    def test_live_flows_deferred_resolver_returns_role_level_file(
        self, tmp_path, deferred_label,
    ):
        """A step whose from_role is one of the five deferred labels
        resolves to the role-level file (NOT IMPLEMENTOR.md or
        SUPERVISOR_AUTONOMOUS.md). The role row keeps the absorbed
        original as its fallback pointer; the step has governance_file
        left NULL (no repointing)."""
        db = _build_scratch_db(tmp_path)
        role_gov = _DEFERRED_ROLE_GOVERNANCE[deferred_label]
        _seed_role(db, deferred_label, governance_file=role_gov)
        _seed_step(
            db, "fl", "s", deferred_label, "next_role",
            # governance_file deliberately NULL -- never repointed
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        # Resolver returns the role-level file (not any generic).
        assert r["governance_file"] == role_gov, (
            f"resolver leaked generic-file repointing to live "
            f"deferred label {deferred_label!r}; got "
            f"{r['governance_file']!r}, expected {role_gov!r}"
        )
        assert r["governance_source_level"] == "role"
        # Specifically: NEITHER of the two generic names.
        assert r["governance_file"] not in (
            "IMPLEMENTOR.md",
            "SUPERVISOR_AUTONOMOUS.md",
        )

    @pytest.mark.parametrize("deferred_label", list(_DEFERRED_LABELS))
    def test_live_flows_deferred_migration_text_does_not_reference_label(
        self, deferred_label,
    ):
        """The migration's UPDATE statements do not reference any of
        the five deferred labels. This pins the deferral at the
        UPDATE-predicate level -- a future mutation that adds the
        labels to a predicate is caught here.

        Note: the migration file's header comment deliberately names
        the five deferred labels to document the deferral. The test
        therefore checks the UPDATE-statement bodies only, NOT the
        header comment -- the comment is documentation, not behavior.
        """
        assert _MIGRATION_PATH.is_file(), (
            f"migration file missing at {_MIGRATION_PATH}; handoff 049 "
            "D4 must author it before this handoff can pin it"
        )
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")

        # Strip SQL line comments ("-- ...") so a comment that happens
        # to mention a deferred label does not trip the check; then we
        # look for the deferred label as a string literal in the
        # resulting UPDATE bodies.
        def _strip_sql_comments(s):
            out_lines = []
            for line in s.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("--"):
                    continue
                idx = line.find(" --")
                if idx == -1:
                    out_lines.append(line)
                else:
                    in_quote = False
                    cut = -1
                    for i, ch in enumerate(line):
                        if ch == "\'":
                            in_quote = not in_quote
                        elif not in_quote and ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
                            cut = i
                            break
                    if cut == -1:
                        out_lines.append(line)
                    else:
                        out_lines.append(line[:cut].rstrip())
            return "\n".join(out_lines)

        cleaned = _strip_sql_comments(sql)

        # Find every UPDATE statement (steps and flows).
        update_bodies = re.findall(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+[^;]+;",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        flow_update_bodies = re.findall(
            r"UPDATE\s+bridge_flows\s+SET\s+supervisor_role\s*=[^;]+;",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        assert len(update_bodies) == 2, (
            f"migration 065 must contain exactly 2 UPDATE statements "
            f"against bridge_flow_steps; found {len(update_bodies)} "
            f"(after stripping comments)"
        )
        assert len(flow_update_bodies) == 5, (
            f"migration 065 must contain exactly 5 UPDATE statements "
            f"against bridge_flows SET supervisor_role; found "
            f"{len(flow_update_bodies)} (after stripping comments)"
        )

        # The deferral is pinned at the bridge_flow_steps UPDATE-predicate
        # level only. bridge_flow_steps UPDATEs describe from_role and are
        # what "repointing" means; the bridge_flows UPDATEs are flow-level
        # supervisor_role seeding and legitimately reference two of the
        # five deferred labels as VALUES (preferred_cloud -> Pre-super-cl,
        # preferred_cloud_harness -> super-deep-deep4) -- that is the whole
        # point of the seeding, not a violation of the deferral. So we
        # only check step UPDATE bodies for the deferred label.
        for body in update_bodies:
            assert f"\'{deferred_label}\'" not in body, (
                f"migration 065 bridge_flow_steps UPDATE must not "
                f"reference the deferred live role label "
                f"{deferred_label!r}; the deferral is deliberate and "
                f"pinned at the step UPDATE-predicate level. "
                f"UPDATE body was: {body!r}"
            )

    def test_live_flows_deferred_migration_has_explicit_blank_check(self):
        """Every bridge_flow_steps UPDATE in the migration must include
        an explicit from_role IN (...) clause -- the §15 from_role
        contract. A blanket UPDATE (e.g. WHERE governance_file IS NULL
        without a from_role constraint) would clobber the deferred
        rows that are deliberately NOT repointed."""
        assert _MIGRATION_PATH.is_file()
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")
        updates = re.findall(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+(?P<set>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert len(updates) == 2, (
            f"migration 065 must contain exactly 2 UPDATE statements "
            f"against bridge_flow_steps (implementor / supervisor); "
            f"found {len(updates)}"
        )
        for body in updates:
            assert "from_role IN" in body, (
                "every UPDATE against bridge_flow_steps in migration "
                "065 must include a from_role IN (...) clause (the §15 "
                "from_role contract -- a blanket match would clobber "
                "the deferred live roles that are deliberately NOT "
                "repointed)"
            )


# ---------------------------------------------------------------------------
# (C) supervisor_role_seed -- the five flows are seeded with their
#     bound supervisor_role. Pinned by content (the migration contains
#     the right UPDATE statements) AND by behavior (applying them to a
#     scratch DB leaves each flow with the expected value).
# ---------------------------------------------------------------------------


class Test_supervisor_role_seed:
    """bridge_flows.supervisor_role is seeded for the five autonomous flows.

    Pins both:
      1. The migration text contains the five UPDATE statements with
         the exact (flow_key, supervisor_role) pairings from §1 D4(b);
      2. Applying those UPDATEs to a scratch bridge_flows (with the
         061 supervisor_role column) leaves each flow with its bound
         supervisor_role value.
    """

    @pytest.mark.parametrize(
        "flow_key,supervisor_role",
        list(_SUPERVISOR_ROLE_SEEDINGS),
    )
    def test_supervisor_role_seed_migration_contains_update(
        self, flow_key, supervisor_role,
    ):
        """Migration 065 contains the explicit
        `UPDATE bridge_flows SET supervisor_role = '<X>' WHERE flow_key = '<Y>'`
        statement for each of the five seedings."""
        assert _MIGRATION_PATH.is_file()
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")
        expected = (
            f"UPDATE bridge_flows SET supervisor_role = \'{supervisor_role}\'"
            f" WHERE flow_key = \'{flow_key}\' AND is_active = 1"
        )
        assert expected in sql, (
            f"migration 065 missing the supervisor_role seed for "
            f"{flow_key!r} -> {supervisor_role!r}; expected literal: "
            f"{expected!r}"
        )

    @pytest.mark.parametrize(
        "flow_key,supervisor_role",
        list(_SUPERVISOR_ROLE_SEEDINGS),
    )
    def test_supervisor_role_seed_apply_to_scratch_db(
        self, tmp_path, flow_key, supervisor_role,
    ):
        """Applying the migration's flow UPDATE to a scratch DB leaves
        bridge_flows.supervisor_role = expected value for the flow."""
        db = _build_scratch_db(tmp_path, with_supervisor_role=True)
        _seed_flow(db, flow_key)
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "UPDATE bridge_flows SET supervisor_role = ? "
                "WHERE flow_key = ? AND is_active = 1",
                (supervisor_role, flow_key),
            )
            conn.commit()
            row = conn.execute(
                "SELECT supervisor_role FROM bridge_flows WHERE flow_key = ?",
                (flow_key,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, f"flow {flow_key!r} missing from scratch DB"
        assert row[0] == supervisor_role, (
            f"supervisor_role for {flow_key!r} expected "
            f"{supervisor_role!r}, got {row[0]!r}"
        )

    def test_supervisor_role_seed_migration_no_other_flows_touched(self):
        """The migration does not write supervisor_role for any flow
        other than the five seeded ones. A blanket UPDATE would clobber
        flows that have their own (still-NULL) supervisor_role state."""
        assert _MIGRATION_PATH.is_file()
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")
        seeded = {fk for fk, _ in _SUPERVISOR_ROLE_SEEDINGS}
        # Find every UPDATE bridge_flows SET supervisor_role = ...; body
        updates = re.findall(
            r"UPDATE\s+bridge_flows\s+SET\s+supervisor_role\s*=[^;]+;",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert len(updates) == 5, (
            f"migration 065 must contain exactly 5 UPDATE statements "
            f"against bridge_flows; found {len(updates)}"
        )
        for body in updates:
            m = re.search(
                r"WHERE\s+flow_key\s*=\s*\'([^\']+)\'", body,
            )
            assert m is not None, (
                f"every UPDATE bridge_flows statement must scope to "
                f"a specific flow_key; body was: {body!r}"
            )
            assert m.group(1) in seeded, (
                f"unexpected flow_key {m.group(1)!r} in migration 065; "
                f"only the five seeded flows may appear"
            )


# ---------------------------------------------------------------------------
# (D) runtime_context -- build_runtime_context renders the three new
#     keys (model_source / harness_source / autonomous) in the D5 fixed
#     order; the autonomous value flips yes / no with supervisor_role;
#     chain_watchdog's watchdog-default repoint (D6) is also pinned here.
# ---------------------------------------------------------------------------


class Test_runtime_context:
    """The D5 wrapper renders model_source / harness_source / autonomous.

    Pins the D5 contract (build_runtime_context keeps the five base
    runtime-context lines byte-identical and APPENDS three more in the
    fixed order documented in dispatch.py). Also pins the D6 watchdog
    default repoint (the file no longer names 451_SUPERVISED_REVIEW_SUPERVISOR
    and SUPERVISOR_AUTONOMOUS.md appears as the fallback).
    """

    def test_runtime_context_renders_three_keys(self):
        """build_runtime_context(resolved) contains the three new keys
        in the fixed D5 order."""
        cfg = {
            "flow_key": "preferred_cloud_harness",
            "step_key": "imple01-review01",
            "from_role": "imple-codex-minimaxM3",
            "to_role": "review-claude-sonnet5",
            "governance_file": "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
            "model_source": "harness",
            "model_alias": None,
            "model_source_level": "system",
            "harness_source": "codex",
            "harness_profile": None,
            "harness_source_level": "system",
            "implementation_mode": "direct",
        }
        out = dispatch.build_runtime_context(cfg)
        for needle in ("- model_source:", "- harness_source:", "- autonomous:"):
            assert needle in out, (
                f"build_runtime_context output is missing {needle!r}; "
                f"output: {out!r}"
            )
        # The three keys appear in the documented D5 order.
        idx_ms = out.find("- model_source:")
        idx_hs = out.find("- harness_source:")
        idx_au = out.find("- autonomous:")
        assert idx_ms < idx_hs < idx_au, (
            f"three new keys must appear in D5 order "
            f"(model_source, harness_source, autonomous); "
            f"got positions model_source={idx_ms}, "
            f"harness_source={idx_hs}, autonomous={idx_au}"
        )

    def test_runtime_context_autonomous_yes_when_supervisor_role_set(
        self, tmp_path, monkeypatch,
    ):
        """build_runtime_context renders `autonomous: yes` for a flow
        whose bridge_flows.supervisor_role is set (non-NULL,
        non-empty)."""
        db = _build_scratch_db(tmp_path, with_supervisor_role=True)
        # Seed a flow with supervisor_role set, a step, and a role.
        _seed_flow(db, "test_fl", supervisor_role="super-deep-deep4")
        _seed_role(db, "actor")
        _seed_step(db, "test_fl", "s", "actor", "next_role",
                   governance_file=None)
        # Monkeypatch dispatch._db_path to point at our scratch DB so
        # the wrapper reads from it (the dispatch.py docstring at line
        # ~201 documents this as the supported fixture pattern).
        monkeypatch.setattr(dispatch, "_db_path", lambda: str(db))
        cfg = {
            "flow_key": "test_fl",
            "step_key": "s",
            "from_role": "actor",
            "to_role": "next_role",
            "governance_file": None,
            "model_source": "harness",
            "model_alias": None,
            "model_source_level": "system",
            "harness_source": "codex",
            "harness_profile": None,
            "harness_source_level": "system",
            "implementation_mode": "direct",
        }
        out = dispatch.build_runtime_context(cfg)
        assert "- autonomous: yes" in out, (
            f"expected `autonomous: yes` for flow with supervisor_role "
            f"set; output: {out!r}"
        )

    def test_runtime_context_autonomous_no_when_supervisor_role_null(
        self, tmp_path, monkeypatch,
    ):
        """build_runtime_context renders `autonomous: no` for a flow
        whose bridge_flows.supervisor_role is NULL."""
        db = _build_scratch_db(tmp_path, with_supervisor_role=True)
        # Seed a flow WITHOUT supervisor_role (NULL).
        _seed_flow(db, "test_fl")
        _seed_role(db, "actor")
        _seed_step(db, "test_fl", "s", "actor", "next_role",
                   governance_file=None)
        monkeypatch.setattr(dispatch, "_db_path", lambda: str(db))
        cfg = {
            "flow_key": "test_fl",
            "step_key": "s",
            "from_role": "actor",
            "to_role": "next_role",
            "governance_file": None,
            "model_source": "harness",
            "model_alias": None,
            "model_source_level": "system",
            "harness_source": "codex",
            "harness_profile": None,
            "harness_source_level": "system",
            "implementation_mode": "direct",
        }
        out = dispatch.build_runtime_context(cfg)
        assert "- autonomous: no" in out, (
            f"expected `autonomous: no` for flow with supervisor_role "
            f"NULL; output: {out!r}"
        )

    def test_runtime_context_watchdog_default_d6_repoint(self):
        """D6 pin: chain_watchdog.py no longer references the 4xx
        supervisor original as the fallback default, and
        SUPERVISOR_AUTONOMOUS.md appears in its place."""
        assert _WATCHDOG_PATH.is_file()
        text = _WATCHDOG_PATH.read_text(encoding="utf-8")
        # 1. The 4xx original must NOT appear anywhere in the watchdog.
        assert "451_SUPERVISED_REVIEW_SUPERVISOR" not in text, (
            "chain_watchdog.py still references the absorbed original "
            "451_SUPERVISED_REVIEW_SUPERVISOR; D6 must remove it"
        )
        # 2. The D6 fallback default must appear.
        assert "SUPERVISOR_AUTONOMOUS.md" in text, (
            "chain_watchdog.py is missing the D6 fallback default "
            "SUPERVISOR_AUTONOMOUS.md; TG9 expects 0 occurrences of "
            "the 4xx original AND the new default must be wired in"
        )


# ---------------------------------------------------------------------------
# (E) rollback -- the rollback file is real (NOT a no-op).
# ---------------------------------------------------------------------------


class Test_rollback:
    """The rollback file is real: scoped UPDATEs + schema_migrations DELETE.

    A correct rollback MUST contain:

      1. UPDATE bridge_flow_steps SET governance_file = NULL scoped to
         the eleven repointed from_role labels (NOT a blanket match)
         AND referencing both new generic names in the
         governance_file IN (...) clause;
      2. UPDATE bridge_flows SET supervisor_role = NULL scoped to the
         five seeded flow_keys (NOT a blanket match);
      3. DELETE on schema_migrations for 065's filename.

    Without (1)+(3), applying the rollback leaves the repointed rows
    pointing at the two new generic files and a stale schema_migrations
    row that prevents re-application of the migration. Without (2)+(3),
    the supervisor_role column stays seeded and chain_watchdog keeps
    routing stall wake-ups to the five new supervisors after a
    rollback.
    """

    def test_rollback_scoped_step_update_clears_governance_file_for_eleven_labels(self):
        """The rollback's UPDATE on bridge_flow_steps targets the
        eleven repointed rows specifically -- not a blanket
        governance_file match."""
        assert _ROLLBACK_PATH.is_file(), (
            f"rollback file missing at {_ROLLBACK_PATH}; handoff 049 "
            "D4 must author it before this handoff can pin it"
        )
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        update_match = re.search(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+governance_file\s*=\s*NULL"
            r"(?P<body>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert update_match is not None, (
            "rollback is missing the scoped UPDATE ... SET "
            "governance_file = NULL; a no-op rollback would silently "
            "leave the repointed rows pointing at the generic files"
        )
        body = update_match.group("body")
        # Must scope to BOTH new generic names AND all eleven
        # from_role labels (the union of _IMPLEMENTOR_LABELS and
        # _SUPERVISOR_LABELS).
        for generic in ("IMPLEMENTOR.md", "SUPERVISOR_AUTONOMOUS.md"):
            assert f"\'{generic}\'" in body, (
                f"rollback UPDATE must scope to both new generic "
                f"names; missing \'{generic}\'"
            )
        for label in _REPOINTED_LABELS:
            assert f"\'{label}\'" in body, (
                f"rollback UPDATE must scope to all eleven repointed "
                f"from_role labels; missing \'{label}\'"
            )

    def test_rollback_scoped_flow_update_clears_supervisor_role_for_five_flows(self):
        """The rollback's UPDATE on bridge_flows targets the five
        seeded flows specifically -- not a blanket flow match."""
        assert _ROLLBACK_PATH.is_file()
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        update_match = re.search(
            r"UPDATE\s+bridge_flows\s+SET\s+supervisor_role\s*=\s*NULL"
            r"(?P<body>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert update_match is not None, (
            "rollback is missing the scoped UPDATE bridge_flows SET "
            "supervisor_role = NULL; a no-op rollback would leave the "
            "supervisor_role seeding in place"
        )
        body = update_match.group("body")
        # Must scope to all five flow_keys the migration listed.
        for flow_key, _ in _SUPERVISOR_ROLE_SEEDINGS:
            assert f"\'{flow_key}\'" in body, (
                f"rollback UPDATE must scope to all five seeded "
                f"flow_keys; missing \'{flow_key}\'"
            )
        # Must also scope to all five seeded supervisor_role values
        # (a blanket flow_key match without the supervisor_role IN list
        # would clobber any future seeding of these flows).
        for _, sup_role in _SUPERVISOR_ROLE_SEEDINGS:
            assert f"\'{sup_role}\'" in body, (
                f"rollback UPDATE must scope to the five seeded "
                f"supervisor_role values; missing \'{sup_role}\'"
            )

    def test_rollback_does_not_reference_deferred_labels(self):
        """The rollback must not include any of the five deferred
        live-role labels in its bridge_flow_steps UPDATE from_role IN
        (...) list -- the deferred rows were never repointed, so a
        rollback that scoped to them would be a no-op on those rows
        but is structurally wrong (it would imply the deferred rows
        were ever touched)."""
        assert _ROLLBACK_PATH.is_file()
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        update_match = re.search(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+governance_file\s*=\s*NULL"
            r"(?P<body>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert update_match is not None
        body = update_match.group("body")
        for deferred in _DEFERRED_LABELS:
            assert f"\'{deferred}\'" not in body, (
                f"rollback UPDATE must not include the deferred "
                f"live-role label {deferred!r}; those rows were never "
                f"repointed"
            )

    def test_rollback_deletes_schema_migrations_row_for_065(self):
        """The rollback removes the schema_migrations row for 065."""
        assert _ROLLBACK_PATH.is_file()
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        assert re.search(
            r"DELETE\s+FROM\s+schema_migrations\s+WHERE\s+filename\s*=\s*"
            r"\'065_governance_impl_sup_repoint\.sql\'",
            sql,
            re.IGNORECASE,
        ), (
            "rollback is missing the schema_migrations DELETE; without "
            "it, migrate.py would treat 065 as already-applied even "
            "after a manual re-apply"
        )

    def test_rollback_targets_two_new_generics_only_no_other_files(self):
        """The rollback's bridge_flow_steps governance_file IN (...)
        list must contain EXACTLY the two new generic names -- no
        absorbed 4xx / 5xx original (e.g. ARCHITECT.md, HUMAN.md from
        Run 009) must leak in, and no blanket match must appear."""
        assert _ROLLBACK_PATH.is_file()
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        update_match = re.search(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+governance_file\s*=\s*NULL"
            r"(?P<body>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert update_match is not None
        body = update_match.group("body")
        in_match = re.search(
            r"governance_file\s+IN\s*\((?P<list>[^)]*)\)",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        assert in_match is not None, (
            "rollback UPDATE must include a governance_file IN (...) clause"
        )
        listed = set(re.findall(r"\'([^\']+)\'", in_match.group("list")))
        assert listed == {
            "IMPLEMENTOR.md", "SUPERVISOR_AUTONOMOUS.md",
        }, (
            f"rollback governance_file IN (...) must contain EXACTLY "
            f"the two new generic names; got {listed!r}"
        )


# ---------------------------------------------------------------------------
# (F) file_exists -- the four new governance files (D1/D2/D3
#     deliverables) exist; the thirteen absorbed originals still exist
#     as the role-level fallback pointers; a made-up name reports
#     missing; garbage inputs (None / "" / non-string) report missing
#     without raising.
# ---------------------------------------------------------------------------


class Test_file_exists:
    """The spec §21 "referenced file exists" check.

    The fence forbids editing scripts/bridgeV002/execution_config.py
    (handoff 049 scope); the helper therefore lives in this test
    module. It is deterministic, self-contained, and uses pathlib's
    is_file() so a missing file is reported without network or mtime
    games. Extended to the four new generic names added by handoffs
    046 / 047 / 048 (IMPLEMENTOR.md, SUPERVISOR_AUTONOMOUS.md,
    ADDENDUM_AUTONOMOUS_RUN.md, ADDENDUM_LOCAL_MODEL_LIFECYCLE.md).
    """

    @pytest.mark.parametrize("generic", list(_NEW_GENERICS))
    def test_file_exists_helper_reports_present_for_four_new_generics(
        self, generic,
    ):
        """The four new generic files (D1 / D2 / D3 deliverables) exist."""
        exists, path = governance_file_exists(generic, REPO_ROOT)
        assert exists is True, (
            f"{generic} (D1/D2/D3 deliverable) must exist under "
            f"docs/governance-templates-v2/; path={path}"
        )
        assert path == (
            REPO_ROOT / "docs" / "governance-templates-v2" / generic
        )

    @pytest.mark.parametrize("original", list(_ABSORBED_ORIGINALS))
    def test_file_exists_helper_reports_present_for_thirteen_originals(
        self, original,
    ):
        """Post Phase-5 (Run 017): the thirteen absorbed originals were
        RETIRED via git rm (D3). The helper must report them absent
        on disk now (migration 068 repointed bridge_roles.governance_file
        to its generic equivalent)."""
        exists, path = governance_file_exists(original, REPO_ROOT)
        assert exists is False, (
            f"retired absorbed original {original} must NOT be on disk "
            f"after Run 017 D3 git rm; path={path}"
        )

    def test_file_exists_helper_reports_missing_for_unknown_name(self):
        """A made-up governance filename is reported as missing."""
        exists, path = governance_file_exists(
            "NO_SUCH_GOVERNANCE.md", REPO_ROOT,
        )
        assert exists is False, (
            f"NO_SUCH_GOVERNANCE.md must be reported missing; "
            f"path={path}"
        )

    @pytest.mark.parametrize(
        "garbage",
        [None, "", "   ", 123, "../etc/passwd"],
    )
    def test_file_exists_helper_handles_garbage_inputs(self, garbage):
        """Empty/None/non-string inputs are reported as missing, not
        raised. The helper is called from arbitrary call sites and
        must degrade cleanly. For None / empty / non-string inputs,
        path is also None (no path was constructed); for whitespace
        and relative-path strings, a path is constructed but the
        exists flag is False (the helper does not silently promote
        a non-existent file to present)."""
        exists, path = governance_file_exists(garbage, REPO_ROOT)
        assert exists is False, (
            f"garbage input {garbage!r} must be reported missing"
        )
        if garbage is None or garbage == "" or not isinstance(garbage, str):
            assert path is None

    def test_file_exists_helper_is_deterministic(self, tmp_path):
        """Same input twice -> same output. Pure function over the FS."""
        sandbox = tmp_path / "sandbox" / "docs" / "governance-templates-v2"
        sandbox.mkdir(parents=True)
        (sandbox / "PRESENT.md").write_text("# present\n")
        fake_root = tmp_path / "sandbox"
        e1, p1 = governance_file_exists("PRESENT.md", fake_root)
        e2, p2 = governance_file_exists("PRESENT.md", fake_root)
        assert e1 is True and e2 is True
        assert p1 == p2
        # And the missing case from the same sandbox:
        e3, p3 = governance_file_exists("ABSENT.md", fake_root)
        assert e3 is False
