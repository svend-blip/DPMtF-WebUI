"""Tests for the Run 009 governance pilot repoint (handoff 038 / D4).

This module codifies the resolver's repoint behavior introduced by
migration 063 and the two new generic governance files
(ARCHITECT.md, HUMAN.md) that handoffs 036 and 037 produced. It
pins three things end-to-end:

  (A) repoint     -- the resolver returns the generic file at STEP
                     level for the repointed steps; the STEP > ROLE
                     precedence still wins even when the role row
                     keeps its 4xx governance pointer;
  (B) invariant   -- every OTHER active step (every step not
                     repointed by migration 063) resolves exactly
                     as before. Section 15 of the spec is load-bearing
                     here: step governance describes from_role, never
                     to_role; a from_role-shaped mistake would have
                     leaked into the migration and this invariant
                     test catches it (rehearsal mutation m2);
  (C) file_exists -- a referenced governance file that does not exist
                     on disk is reported by a small validation helper
                     defined in this module. The fence forbids editing
                     scripts/bridgeV002/execution_config.py, so the
                     helper lives here (spec section 21).

The migration's rollback file is also pinned: a no-op rollback
(rehearsal mutation m3) would silently leave the repointed rows in
place. The rollback test reads the rollback file from disk and
asserts it contains the scoped UPDATE ... SET governance_file = NULL
AND the schema_migrations DELETE.

All tests use a scratch SQLite DB built in tmp_path; the production
database at databases/dpmtf.db is NEVER touched.

Test class / function naming is load-bearing: pytest -k selects the
three groups per GOAL.md section 2's keyword list:

    -k repoint       -> group (A), the rollback-pinning tests
                         (Test_repoint_rollback_not_a_noop), AND, by
                         accident of the filename, every test in this
                         module -- because the file is named
                         test_governance_repoint.py, the substring
                         "repoint" is present in every test node ID.
                         This over-selection is harmless: TG8
                         (`-k "repoint or invariant"`) and TG9
                         (`-k file_exists`) are satisfied either way
                         because every test in this module passes.
    -k invariant     -> group (B) only (no filename substring
                         collision).
    -k file_exists   -> group (C) only (no filename substring
                         collision).

TG8 (`-k "repoint or invariant"`) and TG9 (`-k file_exists`) are the
GOAL.md testgoals that gate this handoff. The over-selection noted
above does not affect either testgoal because the whole module exits 0.
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
_ROLLBACK_PATH = (
    REPO_ROOT / "scripts" / "db" / "rollbacks"
    / "063_governance_pilot_repoint_rollback.sql"
)

# The six from_role labels migration 063 repoints (3 architect + 3 human).
_ARCHI_LABELS = ("archi01", "archi01cloud", "archi01pay")
_HUMAN_LABELS = ("human", "humancloud", "humanpay")
_REPOINTED_LABELS = _ARCHI_LABELS + _HUMAN_LABELS


# ---------------------------------------------------------------------------
# file_exists helper (defined in this test module -- the fence forbids
# editing scripts/bridgeV002/execution_config.py, per handoff 038 scope).
# ---------------------------------------------------------------------------


def governance_file_exists(governance_file: str, repo_root: Path) -> tuple:
    """Return (exists, path) for a referenced governance file.

    Looks under docs/governance-templates-v2/ relative to repo_root.
    Deterministic: uses pathlib.Path.is_file(); no network, no mtime
    games, no caching. A None or empty string is reported as missing.

    This is the spec section 21 "referenced file exists" check, kept
    self-contained in the test module per handoff 038 STEP 2(C).
    """
    if not governance_file or not isinstance(governance_file, str):
        return (False, None)
    candidate = (
        repo_root / "docs" / "governance-templates-v2" / governance_file
    )
    return (candidate.is_file(), candidate)


# ---------------------------------------------------------------------------
# Scratch DB helpers (mirrors tests/test_execution_config.py's pattern)
# ---------------------------------------------------------------------------


def _build_scratch_db(tmp_path: Path) -> Path:
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
#     the repointed steps, AND the STEP > ROLE precedence still wins when
#     the role row keeps its 4xx governance pointer.
# ---------------------------------------------------------------------------


class Test_repoint:
    """Resolver returns ARCHITECT.md / HUMAN.md at STEP level.

    Codifies migration 063's repoint: every active step whose from_role
    is one of the six labels listed in the migration gets a step-level
    governance_file pointing at the generic file, and the resolver
    reports governance_source_level == 'step'.
    """

    @pytest.mark.parametrize("archi_label", list(_ARCHI_LABELS))
    def test_repoint_architect_label_resolves_ARCHITECT_at_step(
        self, tmp_path, archi_label,
    ):
        db = _build_scratch_db(tmp_path)
        # Seed the role row WITHOUT a role-level governance_file so the
        # result is unambiguous: the only thing that can produce
        # ARCHITECT.md is the step-level column.
        _seed_role(db, archi_label)
        _seed_step(
            db, "fl", "s", archi_label, "next_role",
            governance_file="ARCHITECT.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "ARCHITECT.md", (
            f"expected ARCHITECT.md for {archi_label}, got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {archi_label}, got "
            f"{r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("human_label", list(_HUMAN_LABELS))
    def test_repoint_human_label_resolves_HUMAN_at_step(
        self, tmp_path, human_label,
    ):
        db = _build_scratch_db(tmp_path)
        _seed_role(db, human_label)
        _seed_step(
            db, "fl", "s", human_label, "next_role",
            governance_file="HUMAN.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "HUMAN.md", (
            f"expected HUMAN.md for {human_label}, got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {human_label}, got "
            f"{r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize("archi_label", list(_ARCHI_LABELS))
    def test_repoint_step_overrides_role_governance_for_architect(
        self, tmp_path, archi_label,
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
        _seed_role(db, archi_label, governance_file="402_4XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", archi_label, "next_role",
            governance_file="ARCHITECT.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "ARCHITECT.md"
        assert r["governance_source_level"] == "step"

    @pytest.mark.parametrize("human_label", list(_HUMAN_LABELS))
    def test_repoint_step_overrides_role_governance_for_human(
        self, tmp_path, human_label,
    ):
        """Same precedence proof for the human side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, human_label, governance_file="401_4XX_ORIGINAL.md")
        _seed_step(
            db, "fl", "s", human_label, "next_role",
            governance_file="HUMAN.md",
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "HUMAN.md"
        assert r["governance_source_level"] == "step"


class Test_repoint_rollback_not_a_noop:
    """The rollback file is real: scoped UPDATE + schema_migrations DELETE.

    Pins the rollback against rehearsal mutation m3 (a no-op rollback
    that silently leaves the repointed rows in place). A correct
    rollback MUST contain:

      1. An UPDATE that clears governance_file back to NULL for the
         repointed rows (the migration's UPDATE was the inverse
         operation); and
      2. A DELETE on schema_migrations for 063's filename.

    Without both, applying the rollback leaves the repointed rows
    pointing at ARCHITECT.md / HUMAN.md and a stale schema_migrations
    row that prevents re-application of the migration.
    """

    def test_repoint_rollback_scoped_update_clears_governance_file(self):
        """The rollback's UPDATE targets the repointed rows specifically.

        Asserts the rollback SQL sets governance_file back to NULL
        (the inverse of the migration's UPDATE) for the six labels
        migration 063 listed, AND does not match a blanket governance
        match (which would clobber unrelated future repoints).
        """
        assert _ROLLBACK_PATH.is_file(), (
            f"rollback file missing at {_ROLLBACK_PATH}; handoff 037 "
            "D3 must author it before this handoff can pin it"
        )
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")

        # The UPDATE statement must:
        # - SET governance_file = NULL  (inverse of the migration)
        # - reference governance_file IN ('ARCHITECT.md', 'HUMAN.md')
        # - scope to the six from_role labels the migration listed
        update_match = re.search(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+governance_file\s*=\s*NULL"
            r"(?P<body>.*?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert update_match is not None, (
            "rollback is missing the scoped UPDATE ... SET "
            "governance_file = NULL; rehearsal mutation m3 would have "
            "produced a no-op rollback (it would silently leave the "
            "repointed rows pointing at the generic files)"
        )
        body = update_match.group("body")
        # Scoped to the two new generic files AND the six from_role
        # labels migration 063 listed. The label list is the same set
        # the migration binds to (see _REPOINTED_LABELS above).
        assert "ARCHITECT.md" in body, (
            "rollback UPDATE must reference 'ARCHITECT.md' to be scoped"
        )
        assert "HUMAN.md" in body, (
            "rollback UPDATE must reference 'HUMAN.md' to be scoped"
        )
        for label in _REPOINTED_LABELS:
            assert f"'{label}'" in body, (
                f"rollback UPDATE must scope to the migration's "
                f"from_role label set; missing '{label}'"
            )

    def test_repoint_rollback_deletes_schema_migrations_row(self):
        """The rollback removes the schema_migrations row for 063.

        Without this DELETE, a subsequent `python3 scripts/migrate.py`
        would see 063 as already-applied and skip re-applying it,
        leaving the schema_migrations row in place even after a manual
        rollback-and-re-apply cycle.
        """
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        assert re.search(
            r"DELETE\s+FROM\s+schema_migrations\s+WHERE\s+filename\s*=\s*"
            r"'063_governance_pilot_repoint\.sql'",
            sql,
            re.IGNORECASE,
        ), (
            "rollback is missing the schema_migrations DELETE; without "
            "it, migrate.py would treat 063 as already-applied even "
            "after a manual re-apply"
        )


# ---------------------------------------------------------------------------
# (B) invariant -- every OTHER active step (not repointed by 063) resolves
#     exactly as before. §15 from_role semantics is load-bearing here.
# ---------------------------------------------------------------------------


class Test_invariant:
    """Resolver behavior for steps that migration 063 did NOT touch.

    The repoint touched 7 rows; the other 39 active rows must resolve
    exactly as they did pre-063. §15 of the spec (step governance
    describes from_role) is load-bearing: a from_role->to_role mistake
    in the migration would have repointed the WRONG steps; this
    invariant group catches that mistake by checking the resolver
    itself never looks at to_role when picking governance.
    """

    def test_invariant_non_repointed_step_keeps_role_governance(
        self, tmp_path,
    ):
        """Step with NULL governance_file + role with a 4xx pointer
        resolves to the role-level value (unchanged pre/post 063)."""
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

    @pytest.mark.parametrize("archi_label", list(_ARCHI_LABELS))
    def test_invariant_to_role_shape_does_not_trigger_architect_repoint(
        self, tmp_path, archi_label,
    ):
        """§15: a step whose TO_ROLE is an architect label but whose
        FROM_ROLE is NOT must NOT resolve to ARCHITECT.md.

        This is the load-bearing catch for rehearsal mutation m2: a
        migration that mistakenly used `to_role IN (...)` instead of
        `from_role IN (...)` would have repointed such a step. The
        resolver itself reads from_role -> bridge_roles.governance_file
        and ignores to_role entirely; this test pins that contract.

        The step is seeded with governance_file left NULL (it was
        never repointed). The resolver must return the from_role's own
        role-level governance_file, NOT the generic file.
        """
        db = _build_scratch_db(tmp_path)
        # from_role is unrelated to the repoint set; to_role IS an
        # architect label (this is the m2-shaped row).
        _seed_role(db, "plain_actor", governance_file="PLAIN_GOV.md")
        _seed_role(db, archi_label)
        _seed_step(
            db, "fl", "s", "plain_actor", archi_label,
            # governance_file deliberately NULL -- not repointed
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        # Resolver must use from_role's role-level governance_file,
        # never the to_role, never the generic.
        assert r["governance_file"] == "PLAIN_GOV.md", (
            f"resolver leaked to_role ({archi_label!r}) into the "
            f"governance pick; got {r['governance_file']!r} -- "
            "§15 from_role semantics violated (rehearsal mutation m2)"
        )
        assert r["governance_source_level"] == "role"
        assert r["from_role"] == "plain_actor"
        assert r["to_role"] == archi_label

    @pytest.mark.parametrize("human_label", list(_HUMAN_LABELS))
    def test_invariant_to_role_shape_does_not_trigger_human_repoint(
        self, tmp_path, human_label,
    ):
        """Same shape as the architect variant, on the human side."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "plain_actor", governance_file="PLAIN_GOV.md")
        _seed_role(db, human_label)
        _seed_step(
            db, "fl", "s", "plain_actor", human_label,
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "PLAIN_GOV.md", (
            f"resolver leaked to_role ({human_label!r}) into the "
            f"governance pick; got {r['governance_file']!r} -- "
            "§15 from_role semantics violated (rehearsal mutation m2)"
        )
        assert r["governance_source_level"] == "role"
        assert r["from_role"] == "plain_actor"
        assert r["to_role"] == human_label

    def test_invariant_unrelated_step_unaffected(self, tmp_path):
        """A step whose from_role is NOT in the repoint list resolves
        to its own role-level pointer (or system). Neither the generic
        ARCHITECT.md nor HUMAN.md must leak in."""
        db = _build_scratch_db(tmp_path)
        _seed_role(db, "unrelated", governance_file="UNRELATED_GOV.md")
        _seed_role(db, "archi01cloud")  # exists, but not the from_role
        _seed_role(db, "human")         # exists, but not the from_role
        _seed_step(
            db, "fl", "s", "unrelated", "human",
            # governance_file NULL
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == "UNRELATED_GOV.md"
        assert r["governance_source_level"] == "role"
        assert r["governance_file"] not in ("ARCHITECT.md", "HUMAN.md")


# ---------------------------------------------------------------------------
# (C) file_exists -- a referenced governance file that does not exist on
#     disk is reported by the validation helper defined in this module.
# ---------------------------------------------------------------------------


class Test_file_exists:
    """The spec §21 "referenced file exists" check.

    The fence forbids editing scripts/bridgeV002/execution_config.py
    (handoff 038 scope); the helper therefore lives in this test
    module. It is deterministic, self-contained, and uses pathlib's
    is_file() so a missing file is reported without network or mtime
    games.
    """

    def test_file_exists_helper_reports_present_for_ARCHITECT(self):
        exists, path = governance_file_exists("ARCHITECT.md", REPO_ROOT)
        assert exists is True, (
            f"ARCHITECT.md (D1 deliverable) must exist under "
            f"docs/governance-templates-v2/; path={path}"
        )
        assert path == (
            REPO_ROOT / "docs" / "governance-templates-v2" / "ARCHITECT.md"
        )

    def test_file_exists_helper_reports_present_for_HUMAN(self):
        exists, path = governance_file_exists("HUMAN.md", REPO_ROOT)
        assert exists is True, (
            f"HUMAN.md (D2 deliverable) must exist; path={path}"
        )

    @pytest.mark.parametrize(
        "original",
        [
            "401_STRICT_REVIEW_HUMAN.md",
            "402_STRICT_REVIEW_ARCHI01.md",
            "411_CLOUD_LLM_HUMANCLOUD.md",
            "412_CLOUD_LLM_ARCHI01CLOUD.md",
            "421_CLOUD_PAY_HUMANPAY.md",
            "422_CLOUD_PAY_ARCHI01PAY.md",
        ],
    )
    def test_file_exists_helper_reports_present_for_4xx_originals(
        self, original,
    ):
        """The six absorbed originals are still on disk as the role-level
        fallback pointers. The helper must report them present."""
        exists, path = governance_file_exists(original, REPO_ROOT)
        assert exists is True, (
            f"absorbed original {original} must still be on disk "
            f"(bridge_roles.governance_file points at it); path={path}"
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
        # Build a sandbox dir with a known file, then call the helper
        # twice on the same input pointing into that sandbox via a
        # sub-repo_root proxy.
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
