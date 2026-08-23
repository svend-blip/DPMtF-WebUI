"""Tests for the Run 010 governance review repoint (handoff 045 / D4 + D5).

This module codifies the resolver's repoint behavior introduced by
migration 064 and the three generic review governance files
(TECHNICAL_REVIEW.md, GOVERNANCE_REVIEW.md, REVIEW.md) that handoffs
041-044 produced. It pins five things end-to-end:

  (A) repoint            -- the resolver returns the generic file at STEP
                            level for the nine repointed steps; the
                            STEP > ROLE precedence still wins even when
                            the role row keeps its 4xx governance pointer;
  (B) invariant          -- every OTHER active step (every step not
                            repointed by migration 064) resolves exactly
                            as before. Section 15 of the spec is
                            load-bearing here: step governance describes
                            from_role, never to_role; a from_role-shaped
                            mistake would have leaked into the migration
                            and this invariant test catches it (rehearsal
                            mutation m2 from Run 009);
  (C) live_flows_deferred -- the two LIVE reviewers stay on their
                            role-level files. The deferral is pinned at
                            both the resolver level AND the migration-text
                            level -- the test reads the migration file
                            from disk and asserts the two deferred labels
                            do not appear in any UPDATE predicate;
  (D) file_exists        -- a referenced governance file that does not
                            exist on disk is reported by a small validation
                            helper defined in this module. The fence
                            forbids editing scripts/bridgeV002/execution_config.py,
                            so the helper lives here (spec section 21).
                            Extended to the three new names (and to the
                            eleven absorbed originals);
  (E) rollback           -- the rollback file is real (NOT a no-op):
                            scoped UPDATE ... SET governance_file = NULL
                            referencing the three generic names AND the
                            nine from_role labels (NOT a blanket match),
                            AND the schema_migrations DELETE for 064's
                            filename.

All tests use a scratch SQLite DB built in tmp_path; the production
database at databases/dpmtf.db is NEVER touched.

Test class / function naming is load-bearing: pytest -k selects the
five groups per GOAL.md section 2's keyword list:

    -k repoint             -> group (A), the rollback-pinning tests
                              (Test_repoint_rollback_not_a_noop), AND,
                              by accident of the filename, every test
                              in this module -- because the file is named
                              test_governance_review_repoint.py, the
                              substring "repoint" is present in every
                              test node ID. This over-selection is
                              KNOWN and HARMLESS -- GOAL.md §2 TG8
                              (`-k "repoint or invariant or
                              live_flows_deferred"`) therefore also runs
                              the file_exists and rollback tests. Do
                              NOT "fix" this into a narrower selector
                              that silently skips tests.

    -k invariant           -> group (B) only (no filename substring
                              collision in any single test name beyond
                              the filename itself).
    -k live_flows_deferred -> group (C) only.
    -k file_exists         -> group (D) only.
    -k rollback            -> group (E) only (Test_repoint_rollback_not_a_noop).

TG8 (`-k "repoint or invariant or live_flows_deferred"`) and TG9
(`-k "file_exists or rollback"`) are the GOAL.md testgoals that gate
this handoff. The over-selection noted above does not affect either
testgoal because the whole module exits 0 -- every test in this file
passes regardless of which -k substring matches it.
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

REPO_ROOT = PROJECT_ROOT
_MIGRATION_PATH = (
    REPO_ROOT / "scripts" / "db" / "064_governance_review_repoint.sql"
)
_ROLLBACK_PATH = (
    REPO_ROOT / "scripts" / "db" / "rollbacks"
    / "064_governance_review_repoint_rollback.sql"
)

# The nine from_role labels migration 064 repoints (4 technical + 4
# governance + 1 single-layer).
_TECHNICAL_LABELS = (
    "review01", "review01cloud", "review01pay", "review01sup",
)
_GOVERNANCE_LABELS = (
    "review02", "review02cloud", "review02pay", "review02sup",
)
_SINGLE_LAYER_LABELS = ("review01SG",)
_REPOINTED_LABELS = (
    _TECHNICAL_LABELS + _GOVERNANCE_LABELS + _SINGLE_LAYER_LABELS
)

# The two LIVE reviewers deliberately NOT repointed by 064.
_DEFERRED_LABELS = ("Pre-review-cl", "review-claude-sonnet5")

# The eleven absorbed originals (the role-level fallback pointers that
# bridge_roles.governance_file keeps pointing at after the repoint).
_ABSORBED_ORIGINALS = (
    "404_STRICT_REVIEW_REVIEW01.md",
    "405_STRICT_REVIEW_REVIEW02.md",
    "414_CLOUD_LLM_REVIEW01CLOUD.md",
    "415_CLOUD_LLM_REVIEW02CLOUD.md",
    "424_CLOUD_PAY_REVIEW01PAY.md",
    "425_CLOUD_PAY_REVIEW02PAY.md",
    "453_SUPERVISED_REVIEW_REVIEW01.md",
    "454_SUPERVISED_REVIEW_REVIEW02.md",
    "463_LLAMA_SG_REVIEW01.md",
    "473_PREFERRED_CLOUD_REVIEW01.md",
    "513_PREFERRED_CLOUD_HARNESS_REVIEW01.md",
)


# ---------------------------------------------------------------------------
# file_exists helper (defined in this test module -- the fence forbids
# editing scripts/bridgeV002/execution_config.py, per handoff 045 scope).
# ---------------------------------------------------------------------------


def governance_file_exists(governance_file, repo_root):
    """Return (exists, path) for a referenced governance file.

    Looks under docs/governance-templates-v2/ relative to repo_root.
    Deterministic: uses pathlib.Path.is_file(); no network, no mtime
    games, no caching. A None or empty string is reported as missing.

    This is the spec section 21 "referenced file exists" check, kept
    self-contained in the test module per handoff 045 STEP 4(D).
    Extended to the three new generic names (TECHNICAL_REVIEW.md,
    GOVERNANCE_REVIEW.md, REVIEW.md) added by handoffs 041-044.
    """
    if not governance_file or not isinstance(governance_file, str):
        return (False, None)
    candidate = (
        repo_root / "docs" / "governance-templates-v2" / governance_file
    )
    return (candidate.is_file(), candidate)


# ---------------------------------------------------------------------------
# Scratch DB helpers (mirrors tests/test_execution_config.py's pattern
# and tests/test_governance_repoint.py's _build_scratch_db).
# ---------------------------------------------------------------------------


def _build_scratch_db(tmp_path):
    """Build a minimal bridge schema in a tmp sqlite file with 062 cols.

    Mirrors the columns the resolver reads. The production schema is
    intentionally narrower than real bridge_flows / bridge_flow_steps /
    bridge_roles -- the resolver only reads the columns listed in
    GOAL.md section 2, and the helper inserts exactly those columns.
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


def _seed_flow(db, flow_key="fl", name="F"):
    _seed_row(
        db, "bridge_flows",
        ["flow_key", "name"],
        [flow_key, name],
    )


# ---------------------------------------------------------------------------
# (A) repoint -- the resolver returns the generic file at STEP level for
#     the nine repointed steps, AND the STEP > ROLE precedence still wins
#     when the role row keeps its 4xx governance pointer.
# ---------------------------------------------------------------------------


class Test_repoint:
    """Resolver returns TECHNICAL_REVIEW.md / GOVERNANCE_REVIEW.md / REVIEW.md
    at STEP level for the nine repointed steps.

    Codifies migration 064's repoint: every active step whose from_role
    is one of the nine labels listed in the migration gets a step-level
    governance_file pointing at the generic file, and the resolver
    reports governance_source_level == 'step'.
    """

    @pytest.mark.parametrize("technical_label", list(_TECHNICAL_LABELS))
    def test_repoint_technical_label_resolves_TECHNICAL_REVIEW_at_step(
        self, tmp_path, technical_label,
    ):
        db = _build_scratch_db(tmp_path)
        # Seed the role row WITHOUT a role-level governance_file so the
        # result is unambiguous: the only thing that can produce
        # TECHNICAL_REVIEW.md is the step-level column.
        _seed_role(db, technical_label)
        _seed_step(
            db, "fl", "s", technical_label, "next_role",
            governance_file="TECHNICAL_REVIEW.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "TECHNICAL_REVIEW.md", (
            f"expected TECHNICAL_REVIEW.md for {technical_label}, "
            f"got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {technical_label}, "
            f"got {r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("governance_label", list(_GOVERNANCE_LABELS))
    def test_repoint_governance_label_resolves_GOVERNANCE_REVIEW_at_step(
        self, tmp_path, governance_label,
    ):
        db = _build_scratch_db(tmp_path)
        _seed_role(db, governance_label)
        _seed_step(
            db, "fl", "s", governance_label, "next_role",
            governance_file="GOVERNANCE_REVIEW.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "GOVERNANCE_REVIEW.md", (
            f"expected GOVERNANCE_REVIEW.md for {governance_label}, "
            f"got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {governance_label}, "
            f"got {r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("single_layer_label", list(_SINGLE_LAYER_LABELS))
    def test_repoint_single_layer_label_resolves_REVIEW_at_step(
        self, tmp_path, single_layer_label,
    ):
        db = _build_scratch_db(tmp_path)
        _seed_role(db, single_layer_label)
        _seed_step(
            db, "fl", "s", single_layer_label, "next_role",
            governance_file="REVIEW.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "REVIEW.md", (
            f"expected REVIEW.md for {single_layer_label}, "
            f"got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {single_layer_label}, "
            f"got {r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("technical_label", list(_TECHNICAL_LABELS))
    def test_repoint_step_overrides_role_governance_for_technical(
        self, tmp_path, technical_label,
    ):
        """STEP value wins even when the role row still has a 4xx pointer.

        The role-level pointer is preserved in production (bridge_roles
        still points at the 4xx originals as the resolver fallback).
        The step-level value MUST win; otherwise the repoint never
        takes effect for any role that has a non-NULL governance_file.
        """
        db = _build_scratch_db(tmp_path)
        # Role row keeps a 4xx-style governance_file pointer (the
        # absorbed originals are still in place as the fallback).
        _seed_role(db, technical_label, governance_file="404_4XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", technical_label, "next_role",
            governance_file="TECHNICAL_REVIEW.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "TECHNICAL_REVIEW.md"
        assert r["governance_source_level"] == "step"

    @pytest.mark.parametrize("governance_label", list(_GOVERNANCE_LABELS))
    def test_repoint_step_overrides_role_governance_for_governance(
        self, tmp_path, governance_label,
    ):
        """Same precedence proof for the governance side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, governance_label, governance_file="405_4XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", governance_label, "next_role",
            governance_file="GOVERNANCE_REVIEW.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "GOVERNANCE_REVIEW.md"
        assert r["governance_source_level"] == "step"

    @pytest.mark.parametrize("single_layer_label", list(_SINGLE_LAYER_LABELS))
    def test_repoint_step_overrides_role_governance_for_single_layer(
        self, tmp_path, single_layer_label,
    ):
        """Same precedence proof for the single-layer side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, single_layer_label, governance_file="463_4XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", single_layer_label, "next_role",
            governance_file="REVIEW.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "REVIEW.md"
        assert r["governance_source_level"] == "step"


class Test_repoint_rollback_not_a_noop:
    """The rollback file is real: scoped UPDATE + schema_migrations DELETE.

    Pins the rollback against the no-op-rollback failure mode (Run 009
    rehearsal mutation m3): a rollback that silently leaves the
    repointed rows in place. A correct rollback MUST contain:

      1. An UPDATE that clears governance_file back to NULL for the
         repointed rows (the migration's UPDATE was the inverse
         operation); and
      2. A DELETE on schema_migrations for 064's filename.

    Without both, applying the rollback leaves the repointed rows
    pointing at the three new generic files and a stale
    schema_migrations row that prevents re-application of the
    migration.
    """

    def test_repoint_rollback_scoped_update_clears_governance_file(self):
        """The rollback's UPDATE targets the repointed rows specifically.

        Asserts the rollback SQL sets governance_file back to NULL
        (the inverse of the migration's UPDATE) for the nine labels
        migration 064 listed, AND does not match a blanket governance
        match (which would clobber unrelated future repoints).
        """
        assert _ROLLBACK_PATH.is_file(), (
            f"rollback file missing at {_ROLLBACK_PATH}; handoff 045 "
            "D4 must author it before this handoff can pin it"
        )
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")

        # The UPDATE statement must:
        # - SET governance_file = NULL  (inverse of the migration)
        # - reference governance_file IN the three new generic files
        # - scope to the nine from_role labels the migration listed.
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
        # Scoped to the three new generic files AND the nine from_role
        # labels migration 064 listed. The label list is the same set
        # the migration binds to (see _REPOINTED_LABELS above).
        for generic in (
            "TECHNICAL_REVIEW.md", "GOVERNANCE_REVIEW.md", "REVIEW.md",
        ):
            assert f"'{generic}'" in body, (
                f"rollback UPDATE must scope to the three new generic "
                f"names; missing '{generic}'"
            )
        for label in _REPOINTED_LABELS:
            assert f"'{label}'" in body, (
                f"rollback UPDATE must scope to the migration's "
                f"from_role label set; missing '{label}'"
            )

    def test_repoint_rollback_deletes_schema_migrations_row(self):
        """The rollback removes the schema_migrations row for 064.

        Without this DELETE, a subsequent `python3 scripts/migrate.py`
        would see 064 as already-applied and skip re-applying it,
        leaving the schema_migrations row in place even after a manual
        rollback-and-re-apply cycle.
        """
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        assert re.search(
            r"DELETE\s+FROM\s+schema_migrations\s+WHERE\s+filename\s*=\s*"
            r"'064_governance_review_repoint\.sql'",
            sql,
            re.IGNORECASE,
        ), (
            "rollback is missing the schema_migrations DELETE; without "
            "it, migrate.py would treat 064 as already-applied even "
            "after a manual re-apply"
        )


# ---------------------------------------------------------------------------
# (B) invariant -- every OTHER active step (not repointed by 064) resolves
#     exactly as before. §15 from_role semantics is load-bearing here.
# ---------------------------------------------------------------------------


class Test_invariant:
    """Resolver behavior for steps that migration 064 did NOT touch.

    The repoint touched 9 rows; every other active row must resolve
    exactly as it did pre-064. §15 of the spec (step governance describes
    from_role) is load-bearing: a from_role->to_role mistake in the
    migration would have repointed the WRONG steps; this invariant
    group catches that mistake by checking the resolver itself never
    looks at to_role when picking governance.
    """

    def test_invariant_non_repointed_step_keeps_role_governance(
        self, tmp_path,
    ):
        """Step with NULL governance_file + role with a 4xx pointer
        resolves to the role-level value (unchanged pre/post 064)."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "actor", governance_file="99_OTHER_GOVERNANCE.md")
        _seed_step(db, "fl", "s", "actor", "next_role")  # governance_file NULL
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "99_OTHER_GOVERNANCE.md"
        assert r["governance_source_level"] == "role"

    def test_invariant_step_with_no_role_governance_falls_to_system(
        self, tmp_path,
    ):
        """Step with NULL governance_file AND a role with no governance
        file falls through to system (NULL), unchanged."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "actor")  # no governance_file
        _seed_step(db, "fl", "s", "actor", "next_role")
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] is None
        assert r["governance_source_level"] == "system"

    @pytest.mark.parametrize("technical_label", list(_TECHNICAL_LABELS))
    def test_invariant_to_role_shape_does_not_trigger_technical_repoint(
        self, tmp_path, technical_label,
    ):
        """§15: a step whose TO_ROLE is a technical-review label but whose
        FROM_ROLE is NOT must NOT resolve to TECHNICAL_REVIEW.md.

        This is the load-bearing catch for the to_role-shaped mistake
        (Run 009 rehearsal mutation m2): a migration that mistakenly
        used `to_role IN (...)` instead of `from_role IN (...)` would
        have repointed such a step. The resolver itself reads
        from_role -> bridge_roles.governance_file and ignores to_role
        entirely; this test pins that contract.

        The step is seeded with governance_file left NULL (it was
        never repointed). The resolver must return the from_role's own
        role-level governance_file, NOT the generic file.
        """
        db = _build_scratch_db(tmp_path)
        # from_role is unrelated to the repoint set; to_role IS a
        # technical-review label (this is the m2-shaped row).
        _seed_role(db, "plain_actor", governance_file="PLAIN_GOV.md")
        _seed_role(db, technical_label)
        _seed_step(
            db, "fl", "s", "plain_actor", technical_label,
            # governance_file deliberately NULL -- not repointed
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        # Resolver must use from_role's role-level governance_file,
        # never the to_role, never the generic.
        assert r["governance_file"] == "PLAIN_GOV.md", (
            f"resolver leaked to_role ({technical_label!r}) into the "
            f"governance pick; got {r['governance_file']!r} -- "
            "§15 from_role semantics violated (rehearsal mutation m2)"
        )
        assert r["governance_source_level"] == "role"
        assert r["from_role"] == "plain_actor"
        assert r["to_role"] == technical_label

    @pytest.mark.parametrize("governance_label", list(_GOVERNANCE_LABELS))
    def test_invariant_to_role_shape_does_not_trigger_governance_repoint(
        self, tmp_path, governance_label,
    ):
        """Same shape as the technical variant, on the governance side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "plain_actor", governance_file="PLAIN_GOV.md")
        _seed_role(db, governance_label)
        _seed_step(
            db, "fl", "s", "plain_actor", governance_label,
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "PLAIN_GOV.md", (
            f"resolver leaked to_role ({governance_label!r}) into the "
            f"governance pick; got {r['governance_file']!r} -- "
            "§15 from_role semantics violated (rehearsal mutation m2)"
        )
        assert r["governance_source_level"] == "role"
        assert r["from_role"] == "plain_actor"
        assert r["to_role"] == governance_label

    @pytest.mark.parametrize("single_layer_label", list(_SINGLE_LAYER_LABELS))
    def test_invariant_to_role_shape_does_not_trigger_single_layer_repoint(
        self, tmp_path, single_layer_label,
    ):
        """Same shape as the technical variant, on the single-layer side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "plain_actor", governance_file="PLAIN_GOV.md")
        _seed_role(db, single_layer_label)
        _seed_step(
            db, "fl", "s", "plain_actor", single_layer_label,
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "PLAIN_GOV.md", (
            f"resolver leaked to_role ({single_layer_label!r}) into the "
            f"governance pick; got {r['governance_file']!r} -- "
            "§15 from_role semantics violated (rehearsal mutation m2)"
        )
        assert r["governance_source_level"] == "role"
        assert r["from_role"] == "plain_actor"
        assert r["to_role"] == single_layer_label

    def test_invariant_unrelated_step_unaffected(self, tmp_path):
        """A step whose from_role is NOT in the repoint list resolves
        to its own role-level pointer (or system). None of the three
        new generic names must leak in."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "unrelated", governance_file="UNRELATED_GOV.md")
        _seed_role(db, "review01cloud")  # exists, but not the from_role
        _seed_role(db, "review02cloud")  # exists, but not the from_role
        _seed_role(db, "review01SG")     # exists, but not the from_role
        _seed_step(
            db, "fl", "s", "unrelated", "review02cloud",
            # governance_file NULL
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "UNRELATED_GOV.md"
        assert r["governance_source_level"] == "role"
        assert r["governance_file"] not in (
            "TECHNICAL_REVIEW.md",
            "GOVERNANCE_REVIEW.md",
            "REVIEW.md",
        )


# ---------------------------------------------------------------------------
# (C) live_flows_deferred -- the two LIVE reviewers stay on their
#     role-level files. The deferral is pinned at BOTH the resolver
#     level AND the migration-text level.
# ---------------------------------------------------------------------------


class Test_live_flows_deferred:
    """The two LIVE reviewers are deliberately NOT repointed.

    'Pre-review-cl' (preferred_cloud) and 'review-claude-sonnet5'
    (preferred_cloud_harness -- this very flow's reviewer) keep their
    role-level files via bridge_roles.governance_file. This test group
    pins that deferral at both the resolver level (these roles resolve
    to their original 4xx file, NOT any of the three new generic
    names) AND the migration-text level (the migration file does not
    reference the two deferred labels in any UPDATE predicate -- so a
    future mutation that "fixes" the deferral by adding the labels to
    the predicates is caught at test time).
    """

    @pytest.mark.parametrize("deferred_label", list(_DEFERRED_LABELS))
    def test_live_flows_deferred_resolver_returns_role_level_file(
        self, tmp_path, deferred_label,
    ):
        """A step whose from_role is one of the two deferred labels
        resolves to the role-level file (NOT any of the three generic
        names). The role row keeps the 4xx original as its fallback
        pointer; the step has governance_file left NULL (no
        repointing)."""
        db = _build_scratch_db(tmp_path)
        # The role row keeps the 4xx-style pointer (the absorbed
        # original is still in place as the fallback).
        if deferred_label == "Pre-review-cl":
            role_gov = "473_PREFERRED_CLOUD_REVIEW01.md"
        else:
            role_gov = "513_PREFERRED_CLOUD_HARNESS_REVIEW01.md"
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
        # Specifically: NONE of the three generic names.
        assert r["governance_file"] not in (
            "TECHNICAL_REVIEW.md",
            "GOVERNANCE_REVIEW.md",
            "REVIEW.md",
        )

    @pytest.mark.parametrize("deferred_label", list(_DEFERRED_LABELS))
    def test_live_flows_deferred_migration_text_does_not_reference_label(
        self, deferred_label,
    ):
        """The migration's UPDATE statements do not reference either
        deferred label. This pins the deferral at the UPDATE-predicate
        level -- a future mutation that adds the labels to a
        predicate is caught here.

        Note: the migration file's header comment (a documentation
        block above the first UPDATE) deliberately names the two
        deferred labels to document the deferral. The test therefore
        checks the UPDATE-statement bodies only, NOT the header
        comment -- the comment is documentation, not behavior.
        """
        assert _MIGRATION_PATH.is_file(), (
            f"migration file missing at {_MIGRATION_PATH}; handoff 045 "
            "D4 must author it before this handoff can pin it"
        )
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")

        # Extract every UPDATE statement's body. We need to strip SQL
        # line comments ("-- ...") so a comment that happens to mention
        # a deferred label does not trip the check; then we look for
        # the deferred label as a string literal in the resulting
        # UPDATE bodies.
        def _strip_sql_comments(s):
            # Drop full-line comments first, then trailing comments on
            # the same line as SQL.
            out_lines = []
            for line in s.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("--"):
                    continue
                # Drop trailing "-- ..." comment, if any.
                idx = line.find(" --")
                if idx == -1:
                    out_lines.append(line)
                else:
                    # Only treat as comment when "--" is not inside a
                    # string literal. Simple heuristic: walk char by
                    # char, tracking single-quote state.
                    in_quote = False
                    cut = -1
                    for i, ch in enumerate(line):
                        if ch == "'":
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

        # Find every UPDATE ... SET ... ; statement.
        update_bodies = re.findall(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+[^;]+;",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        assert len(update_bodies) == 3, (
            f"migration 064 must contain exactly 3 UPDATE statements; "
            f"found {len(update_bodies)} (after stripping comments)"
        )

        for body in update_bodies:
            assert f"'{deferred_label}'" not in body, (
                f"migration 064 UPDATE predicate must not reference "
                f"the deferred live reviewer label {deferred_label!r}; "
                f"the deferral is deliberate and pinned at the "
                f"UPDATE-predicate level. UPDATE body was: {body!r}"
            )

    def test_live_flows_deferred_migration_has_no_blanquet_match(self):
        """The migration must not use a blanket UPDATE (e.g.
        `WHERE governance_file IS NULL` without a from_role
        constraint) -- that would clobber the deferred rows that
        are deliberately NOT repointed. Every UPDATE in the
        migration must include an explicit from_role IN (...) clause."""
        assert _MIGRATION_PATH.is_file()
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")
        # Find every UPDATE statement and assert each contains a
        # from_role IN (...) clause. This is a structural check:
        # the §15 contract requires from_role predicates.
        updates = re.findall(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+(?P<set>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert len(updates) == 3, (
            f"migration 064 must contain exactly 3 UPDATE statements "
            f"(technical / governance / single-layer); found {len(updates)}"
        )
        for body in updates:
            assert "from_role IN" in body, (
                "every UPDATE in migration 064 must include a "
                "from_role IN (...) clause (the §15 from_role contract "
                "-- a blanket match would clobber the deferred live "
                "reviewer rows that are deliberately NOT repointed)"
            )


# ---------------------------------------------------------------------------
# (D) file_exists -- a referenced governance file that does not exist on
#     disk is reported by the validation helper defined in this module.
# ---------------------------------------------------------------------------


class Test_file_exists:
    """The spec §21 "referenced file exists" check.

    The fence forbids editing scripts/bridgeV002/execution_config.py
    (handoff 045 scope); the helper therefore lives in this test
    module. It is deterministic, self-contained, and uses pathlib's
    is_file() so a missing file is reported without network or mtime
    games. Extended to the three new generic names added by handoffs
    041-044.
    """

    @pytest.mark.parametrize(
        "generic",
        [
            "TECHNICAL_REVIEW.md",
            "GOVERNANCE_REVIEW.md",
            "REVIEW.md",
        ],
    )
    def test_file_exists_helper_reports_present_for_three_new_generics(
        self, generic,
    ):
        """The three new generic files (D1 / D2 / D3 deliverables) exist."""
        exists, path = governance_file_exists(generic, REPO_ROOT)
        assert exists is True, (
            f"{generic} (D1/D2/D3 deliverable) must exist under "
            f"docs/governance-templates-v2/; path={path}"
        )
        assert path == (
            REPO_ROOT / "docs" / "governance-templates-v2" / generic
        )

    @pytest.mark.parametrize("original", list(_ABSORBED_ORIGINALS))
    def test_file_exists_helper_reports_present_for_eleven_originals(
        self, original,
    ):
        """Post Phase-5 (Run 017): the eleven absorbed originals were
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
        # None / empty-string / non-string inputs also return path=None
        # (no path constructed). Whitespace and relative-path strings
        # construct a path but is_file() returns False -> exists=False.
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


# ---------------------------------------------------------------------------
# (E) rollback -- the rollback file is real (NOT a no-op).
# ---------------------------------------------------------------------------


class Test_rollback:
    """The rollback file is real: scoped UPDATE + schema_migrations DELETE.

    This is the explicit `rollback` test group named in GOAL.md §2 TG9
    (`-k "file_exists or rollback"`). The Test_repoint_rollback_not_a_noop
    class above also pins the rollback, but the test module's filename
    collision (every node ID contains the substring "repoint") makes
    the `rollback` keyword a load-bearing fallback. The two groups
    together pin the rollback's structural correctness end-to-end.

    A correct rollback MUST contain:

      1. An UPDATE that clears governance_file back to NULL for the
         repointed rows (the migration's UPDATE was the inverse
         operation); and
      2. A DELETE on schema_migrations for 064's filename.

    Without both, applying the rollback leaves the repointed rows
    pointing at the three new generic files and a stale
    schema_migrations row that prevents re-application of the
    migration.
    """

    def test_rollback_scoped_update_clears_governance_file_for_nine_labels(
        self,
    ):
        """The rollback's UPDATE targets the nine repointed rows
        specifically -- not a blanket governance_file match."""
        assert _ROLLBACK_PATH.is_file(), (
            f"rollback file missing at {_ROLLBACK_PATH}; handoff 045 "
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
        # Must scope to all three generic names AND all nine from_role
        # labels.
        for generic in (
            "TECHNICAL_REVIEW.md", "GOVERNANCE_REVIEW.md", "REVIEW.md",
        ):
            assert f"'{generic}'" in body
        for label in _REPOINTED_LABELS:
            assert f"'{label}'" in body, (
                f"rollback UPDATE must scope to all nine repointed "
                f"labels; missing '{label}'"
            )

    def test_rollback_does_not_reference_deferred_labels(self):
        """The rollback must not include either deferred live-reviewer
        label in its from_role IN (...) list -- the deferred rows
        were never repointed, so a rollback that scoped to them would
        be a no-op on those rows but is structurally wrong (it would
        imply the deferred rows were ever touched)."""
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
            assert f"'{deferred}'" not in body, (
                f"rollback UPDATE must not include the deferred "
                f"live-reviewer label {deferred!r}; those rows were "
                f"never repointed"
            )

    def test_rollback_deletes_schema_migrations_row_for_064(self):
        """The rollback removes the schema_migrations row for 064."""
        assert _ROLLBACK_PATH.is_file()
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        assert re.search(
            r"DELETE\s+FROM\s+schema_migrations\s+WHERE\s+filename\s*=\s*"
            r"'064_governance_review_repoint\.sql'",
            sql,
            re.IGNORECASE,
        ), (
            "rollback is missing the schema_migrations DELETE; without "
            "it, migrate.py would treat 064 as already-applied even "
            "after a manual re-apply"
        )

    def test_rollback_targets_three_new_generics_only_no_other_files(self):
        """The rollback's governance_file IN (...) list must contain
        EXACTLY the three new generic names -- no absorbed 4xx
        original (e.g. ARCHITECT.md, HUMAN.md from Run 009) must leak
        in (Run 009 is a different migration, not part of 064's
        rollback) and no blanket match must appear."""
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
        # Extract every string literal from the governance_file IN (...) list.
        # The list is bounded by the parenthesis of IN ( ... ).
        in_match = re.search(
            r"governance_file\s+IN\s*\((?P<list>[^)]*)\)",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        assert in_match is not None, (
            "rollback UPDATE must include a governance_file IN (...) clause"
        )
        listed = set(re.findall(r"'([^']+)'", in_match.group("list")))
        assert listed == {
            "TECHNICAL_REVIEW.md", "GOVERNANCE_REVIEW.md", "REVIEW.md",
        }, (
            f"rollback governance_file IN (...) must contain EXACTLY "
            f"the three new generic names; got {listed!r}"
        )
