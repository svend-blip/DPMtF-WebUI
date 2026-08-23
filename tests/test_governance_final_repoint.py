"""Tests for the Run 012 governance final-repoint (handoff 052 / D2 + D5).

This module codifies the resolver's repoint behavior introduced by
migration 066 (the six LIVE-flow labels binding at STEP level to the
three generic governance files: IMPLEMENTOR.md / SUPERVISOR_AUTONOMOUS.md
/ REVIEW.md) and the 066 rollback's correctness, and pins file existence
for the three generic files plus the three renamed exception files.

  (A) repoint     -- the resolver returns the generic file at STEP level
                     for the six repointed live-flow roles;
                     STEP > ROLE precedence wins even when the role row
                     keeps its 4xx/5xx governance_file pointer.
  (B) rollback    -- the 066 rollback file is REAL (not a no-op): it
                     sets governance_file = NULL scoped to exactly the
                     six from_role labels (NOT a blanket match);
                     applying it to a scratch DB that carries the six
                     repointed rows restores NULL for all six.
  (C) file_exists -- the three generic files (IMPLEMENTOR.md,
                     SUPERVISOR_AUTONOMOUS.md, REVIEW.md) exist under
                     docs/governance-templates-v2/; the three renamed
                     exception files (IMPLEMENTOR_REMOTE_WORKER.md,
                     REVIEW_REMOTE_WORKER.md, REVERSE_ENGINEERING_REVIEW.md)
                     exist under their new names; a made-up name reports
                     missing without raising.

All tests use a scratch SQLite DB built in tmp_path; the production
database at databases/dpmtf.db is NEVER touched.

Test class / function naming is load-bearing: pytest -k selects the
three groups per GOAL.md section 2's keyword list:

    -k repoint     -> group (A). Note: this file is named
                       test_governance_final_repoint.py, so the
                       substring "repoint" appears in every test node
                       ID -- over-selection is KNOWN and HARMLESS
                       (mirrors run 011 / test_governance_impl_sup_repoint.py
                       convention).
    -k rollback    -> group (B).
    -k file_exists -> group (C) only.

TG9 (full module) is the GOAL.md testgoal that gates this handoff.
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
    REPO_ROOT / "scripts" / "db" / "066_governance_live_flow_repoint.sql"
)
_ROLLBACK_PATH = (
    REPO_ROOT / "scripts" / "db" / "rollbacks"
    / "066_governance_live_flow_repoint_rollback.sql"
)

# The six LIVE-flow from_role labels migration 066 repoints at STEP level:
# three for preferred_cloud (Part a, applied in handoff 051) and three
# for preferred_cloud_harness (Part b, applied in handoff 052 = THIS).
_REPOINTED_LIVE_LABELS = (
    # Part a -- preferred_cloud (handoff 051).
    ("Pre-imple-cl", "IMPLEMENTOR.md"),
    ("Pre-super-cl", "SUPERVISOR_AUTONOMOUS.md"),
    ("Pre-review-cl", "REVIEW.md"),
    # Part b -- preferred_cloud_harness (handoff 052).
    ("imple-codex-minimaxM3", "IMPLEMENTOR.md"),
    ("super-deep-deep4", "SUPERVISOR_AUTONOMOUS.md"),
    ("review-claude-sonnet5", "REVIEW.md"),
)

# Three generic governance files bound by migration 066.
_GENERIC_FILES = (
    "IMPLEMENTOR.md",
    "SUPERVISOR_AUTONOMOUS.md",
    "REVIEW.md",
)

# Three renamed exception files (handoff 050 D4).
_RENAMED_EXCEPTION_FILES = (
    "IMPLEMENTOR_REMOTE_WORKER.md",
    "REVIEW_REMOTE_WORKER.md",
    "REVERSE_ENGINEERING_REVIEW.md",
)

# Role-level fallback files still pointed at by bridge_roles.governance_file.
# The 4xx originals cover the four other flows the run touches; the 5xx
# cover the supervisor side. The handoff pins the resolver-level test on
# STEP > ROLE precedence; these are the role-row fallbacks we keep.
_ROLE_LEVEL_FALLBACK_FILES = (
    "472_PREFERRED_CLOUD_IMPLE01.md",
    "471_PREFERRED_CLOUD_SUPERVISOR.md",
    "473_PREFERRED_CLOUD_REVIEW01.md",
    "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
    "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
    "513_PREFERRED_CLOUD_HARNESS_REVIEW01.md",
)


# ---------------------------------------------------------------------------
# (C) file_exists helper (defined in this test module -- the fence forbids
# editing scripts/bridgeV002/execution_config.py, per handoff 052 scope).
# ---------------------------------------------------------------------------


def governance_file_exists(governance_file, repo_root):
    """Return (exists, path) for a referenced governance file.

    Looks under docs/governance-templates-v2/ relative to repo_root.
    Deterministic: uses pathlib.Path.is_file(); no network, no mtime
    games, no caching. A None or empty string is reported as missing.
    """
    if not governance_file or not isinstance(governance_file, str):
        return (False, None)
    candidate = (
        repo_root / "docs" / "governance-templates-v2" / governance_file
    )
    return (candidate.is_file(), candidate)


# ---------------------------------------------------------------------------
# Scratch DB helpers (mirrors tests/test_governance_impl_sup_repoint.py
# and tests/test_governance_review_repoint.py's _build_scratch_db).
# ---------------------------------------------------------------------------


def _build_scratch_db(tmp_path):
    """Build a minimal bridge schema in a tmp sqlite file."""
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


# Map from_role -> the role-level fallback file name. Used by the
# precedence test to seed the role row with a stale pointer.
_ROLE_FALLBACK_BY_LABEL = {
    "Pre-imple-cl": "472_PREFERRED_CLOUD_IMPLE01.md",
    "Pre-super-cl": "471_PREFERRED_CLOUD_SUPERVISOR.md",
    "Pre-review-cl": "473_PREFERRED_CLOUD_REVIEW01.md",
    "imple-codex-minimaxM3": "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
    "super-deep-deep4": "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
    "review-claude-sonnet5": "513_PREFERRED_CLOUD_HARNESS_REVIEW01.md",
}


# ---------------------------------------------------------------------------
# (A) repoint -- the resolver returns the generic file at STEP level for all
#     six repointed live-flow roles; STEP > ROLE precedence wins.
# ---------------------------------------------------------------------------


class Test_repoint:
    """Resolver returns the three generic files at STEP level for the six
    LIVE-flow roles migration 066 repointed (part a + part b).

    Codifies migration 066's Part (a) (handoff 051) and Part (b) (handoff
    052): every active step whose from_role is one of the six labels gets
    a step-level governance_file pointing at the generic file, and the
    resolver reports governance_source_level == 'step'.
    """

    @pytest.mark.parametrize(
        "from_role,expected_file",
        list(_REPOINTED_LIVE_LABELS),
    )
    def test_repoint_label_resolves_generic_at_step(
        self, tmp_path, from_role, expected_file,
    ):
        """A step whose from_role is one of the six LIVE-flow labels
        resolves to the generic file (NOT the role-level 4xx/5xx
        fallback) at source_level == 'step'."""
        db = _build_scratch_db(tmp_path)
        # Seed the role row WITHOUT a role-level governance_file so the
        # result is unambiguous: the only thing that can produce the
        # generic file is the step-level column.
        _seed_role(db, from_role)
        _seed_step(
            db, "fl", "s", from_role, "next_role",
            governance_file=expected_file,
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        assert r["governance_file"] == expected_file, (
            f"expected {expected_file!r} for {from_role!r}, "
            f"got {r['governance_file']!r}"
        )
        assert r["governance_source_level"] == "step", (
            f"expected source_level='step' for {from_role!r}, "
            f"got {r['governance_source_level']!r}"
        )

    @pytest.mark.parametrize(
        "from_role,expected_file",
        list(_REPOINTED_LIVE_LABELS),
    )
    def test_repoint_step_overrides_role_governance(
        self, tmp_path, from_role, expected_file,
    ):
        """STEP > ROLE precedence: even when the role row carries a
        role-level governance_file (the absorbed 4xx/5xx original),
        the step-level value wins."""
        db = _build_scratch_db(tmp_path)
        role_fallback = _ROLE_FALLBACK_BY_LABEL[from_role]
        # Sanity check: the role-level fallback file must NOT equal the
        # step-level generic file (otherwise this test is vacuous).
        assert role_fallback != expected_file, (
            f"role-level fallback {role_fallback!r} matches the "
            f"generic file {expected_file!r} -- precedence test "
            f"would be vacuous for {from_role!r}"
        )
        _seed_role(db, from_role, governance_file=role_fallback)
        _seed_step(
            db, "fl", "s", from_role, "next_role",
            governance_file=expected_file,
        )
        r = resolve_execution_config("fl", "s", db_path=db)
        # STEP wins; the role-level pointer must NOT leak through.
        assert r["governance_file"] == expected_file, (
            f"STEP precedence broken for {from_role!r}: expected "
            f"{expected_file!r} (step), got {r['governance_file']!r} "
            f"(role fallback was {role_fallback!r})"
        )
        assert r["governance_source_level"] == "step"

    def test_repoint_all_six_distinct_from_roles_covered(self):
        """Pin the count: the six LIVE-flow from_role labels that 066
        repoints are exactly these six -- no more, no fewer."""
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")
        # Strip SQL comments.
        out_lines = []
        for line in sql.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("--"):
                continue
            idx = line.find(" --")
            if idx == -1:
                out_lines.append(line)
                continue
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
        cleaned = "\n".join(out_lines)
        # Every repointed label must appear in a `from_role =` predicate.
        for from_role, _ in _REPOINTED_LIVE_LABELS:
            assert f"from_role = '{from_role}'" in cleaned, (
                f"migration 066 missing the from_role = {from_role!r} "
                f"predicate; the six LIVE-flow labels must all be "
                f"repointed"
            )
        # And the repointed set must be exactly these six -- no other
        # from_role is touched by 066's predicates.
        from_role_predicates = re.findall(
            r"from_role\s*=\s*'([^']+)'", cleaned,
        )
        # The migration uses IN (...) for nothing in 066 (single-label
        # predicates), so from_role_predicates is the exact set.
        assert sorted(from_role_predicates) == sorted(
            label for label, _ in _REPOINTED_LIVE_LABELS
        ), (
            f"migration 066 touches from_roles "
            f"{sorted(from_role_predicates)!r}; expected exactly the "
            f"six LIVE-flow labels {sorted(label for label, _ in _REPOINTED_LIVE_LABELS)!r}"
        )


# ---------------------------------------------------------------------------
# (B) rollback -- the 066 rollback file is REAL (not a no-op): scoped to
#     the six from_role labels, restoring NULL for all six repointed rows.
# ---------------------------------------------------------------------------


class Test_rollback:
    """The 066 rollback restores DB state only. The script under test
    pins the rollback's correctness at the SQL-text level (it is scoped
    to the six from_role labels, NOT a blanket match) AND at the
    behavior level (applying it to a scratch DB that carries the six
    repointed rows restores NULL for all six).
    """

    def test_rollback_file_exists(self):
        """The 066 rollback file is on disk."""
        assert _ROLLBACK_PATH.is_file(), (
            f"rollback file missing at {_ROLLBACK_PATH}; handoff 052 "
            "D5 must author it before this handoff can pin it"
        )

    def test_rollback_is_scoped_to_six_from_roles(self):
        """The rollback sets governance_file = NULL scoped to exactly
        the six from_role labels 066 repointed -- NOT a blanket match."""
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        # Strip SQL comments.
        out_lines = []
        for line in sql.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("--"):
                continue
            idx = line.find(" --")
            if idx == -1:
                out_lines.append(line)
                continue
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
        cleaned = "\n".join(out_lines)

        # The rollback must contain an UPDATE that sets governance_file
        # to NULL.
        update_match = re.search(
            r"UPDATE\s+bridge_flow_steps\s+SET\s+governance_file\s*=\s*NULL[^;]*;",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        assert update_match is not None, (
            "066 rollback missing the UPDATE bridge_flow_steps SET "
            "governance_file = NULL ...; statement"
        )
        body = update_match.group(0)

        # And the body MUST scope to a from_role IN (...) predicate
        # naming exactly the six LIVE-flow labels.
        from_role_match = re.search(
            r"from_role\s+IN\s*\(([^)]+)\)",
            body,
            re.IGNORECASE,
        )
        assert from_role_match is not None, (
            "066 rollback must scope governance_file = NULL to a "
            "from_role IN (...) predicate naming exactly the six "
            f"LIVE-flow labels; body was: {body!r}"
        )
        listed_labels = re.findall(r"'([^']+)'", from_role_match.group(1))
        expected_labels = sorted(label for label, _ in _REPOINTED_LIVE_LABELS)
        assert sorted(listed_labels) == expected_labels, (
            f"066 rollback from_role IN (...) labels "
            f"{sorted(listed_labels)!r} do not match the six LIVE-flow "
            f"labels {expected_labels!r}"
        )

    def test_rollback_is_not_blanket_match(self):
        """The rollback does NOT use a blanket WHERE clause such as
        'WHERE governance_file IN (...)' without a from_role predicate.
        A blanket match would clobber any future repoint that also
        binds to the same generic files."""
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        # Look for the danger pattern: WHERE governance_file IN ('...')
        # with no from_role constraint.
        blanket = re.search(
            r"WHERE\s+governance_file\s+IN\s*\(",
            sql,
            re.IGNORECASE,
        )
        assert blanket is None, (
            "066 rollback uses a blanket governance_file IN (...) "
            "match; this would clobber any future repoint to the same "
            "generic files. Scope to from_role IN (...) instead."
        )

    def test_rollback_apply_to_scratch_db_restores_null(self, tmp_path):
        """Applying the rollback's UPDATE to a scratch DB that carries
        the six repointed rows restores NULL for all six."""
        db = _build_scratch_db(tmp_path)
        # Seed six repointed rows, one per LIVE-flow from_role.
        for i, (from_role, expected_file) in enumerate(_REPOINTED_LIVE_LABELS):
            _seed_role(db, from_role, governance_file=_ROLE_FALLBACK_BY_LABEL[from_role])
            _seed_step(
                db, "fl", f"s_{i}", from_role, "next_role",
                governance_file=expected_file,
            )
        # Apply the rollback's UPDATE directly.
        conn = sqlite3.connect(str(db))
        try:
            params = [label for label, _ in _REPOINTED_LIVE_LABELS]
            placeholders = ",".join("?" for _ in params)
            conn.execute(
                f"UPDATE bridge_flow_steps SET governance_file = NULL "
                f"WHERE is_active = 1 AND from_role IN ({placeholders})",
                params,
            )
            conn.commit()
            # All six rows must now have governance_file = NULL.
            for i, (from_role, _) in enumerate(_REPOINTED_LIVE_LABELS):
                row = conn.execute(
                    "SELECT governance_file FROM bridge_flow_steps "
                    "WHERE flow_key = 'fl' AND step_key = ?",
                    (f"s_{i}",),
                ).fetchone()
                assert row is not None, (
                    f"rollback test row s_{i} for {from_role!r} missing "
                    f"from scratch DB"
                )
                assert row[0] is None, (
                    f"rollback failed to restore NULL for {from_role!r} "
                    f"(step s_{i}); governance_file still {row[0]!r}"
                )
        finally:
            conn.close()

    def test_rollback_full_host_recovery_note(self):
        """The rollback header documents FULL HOST RECOVERY coupling
        (SQL rollback PLUS git-revert of the rename commit)."""
        sql = _ROLLBACK_PATH.read_text(encoding="utf-8")
        assert "git-revert" in sql or "revert" in sql.lower(), (
            "066 rollback header does not document the FULL HOST "
            "RECOVERY coupling (SQL rollback PLUS git-revert of the "
            "rename commit). See GOAL.md section 2 'rollback coupling'."
        )
        assert "rename" in sql.lower(), (
            "066 rollback header does not mention the rename commit "
            "that is part of the full host recovery."
        )


# ---------------------------------------------------------------------------
# (C) file_exists -- the three generic files + the three renamed exception
#     files exist under docs/governance-templates-v2/; a made-up name
#     reports missing without raising.
# ---------------------------------------------------------------------------


class Test_file_exists:
    """The governance files the six repointed steps reference exist, and
    the three renamed exception files exist under their new names.

    Spec section 21 "referenced file exists" check, kept self-contained
    in this test module per handoff 052 STEP 3(C). A made-up name
    reports missing; garbage inputs report missing without raising.
    """

    @pytest.mark.parametrize("generic_file", list(_GENERIC_FILES))
    def test_file_exists_generic_file(self, generic_file):
        """Each of the three generic governance files exists on disk."""
        exists, path = governance_file_exists(generic_file, REPO_ROOT)
        assert exists, (
            f"generic governance file {generic_file!r} missing on disk; "
            f"looked under {path}"
        )

    @pytest.mark.parametrize("renamed_file", list(_RENAMED_EXCEPTION_FILES))
    def test_file_exists_renamed_exception(self, renamed_file):
        """Each of the three renamed exception files exists on disk
        under its new name."""
        exists, path = governance_file_exists(renamed_file, REPO_ROOT)
        assert exists, (
            f"renamed exception file {renamed_file!r} missing on disk; "
            f"looked under {path}"
        )

    def test_file_exists_unknown_name_reports_missing(self):
        """A made-up governance file name reports missing without raising."""
        exists, path = governance_file_exists(
            "NOT_A_REAL_FILE_9999.md", REPO_ROOT,
        )
        assert exists is False
        assert path is not None  # the helper returns the candidate path
        assert not path.is_file()

    @pytest.mark.parametrize("garbage", [None, "", 0, 123, [], {}, b"bytes"])
    def test_file_exists_garbage_inputs_no_raise(self, garbage):
        """Garbage inputs (None / empty string / non-string types)
        report missing without raising."""
        exists, path = governance_file_exists(garbage, REPO_ROOT)
        assert exists is False
        assert path is None

    def test_file_exists_role_level_fallbacks_still_present(self):
        """Post Phase-5 (Run 017): the six role-level fallback files
        (4xx/5xx originals) are RETIRED -- Run 017 D3 git rm deleted
        them. The role-level fallback chain now lives at the generic
        equivalents (SUPERVISOR_AUTONOMOUS.md, IMPLEMENTOR.md,
        REVIEW.md, etc.) repointed by migration 068.

        This test asserts the post-D3 invariant: the six originals in
        _ROLE_LEVEL_FALLBACK_FILES must be MISSING on disk, AND the
        seven generic equivalents must be PRESENT."""
        for original in _ROLE_LEVEL_FALLBACK_FILES:
            exists, path = governance_file_exists(original, REPO_ROOT)
            assert not exists, (
                f"retired role-level fallback {original!r} must NOT be "
                f"on disk after Run 017 D3 git rm; looked under {path}"
            )
        # The seven generic equivalents must still exist.
        generic_equivalents = (
            "SUPERVISOR_AUTONOMOUS.md",
            "IMPLEMENTOR.md",
            "REVIEW.md",
            "ARCHITECT.md",
            "HUMAN.md",
            "TECHNICAL_REVIEW.md",
            "GOVERNANCE_REVIEW.md",
        )
        for generic in generic_equivalents:
            exists, path = governance_file_exists(generic, REPO_ROOT)
            assert exists, (
                f"generic equivalent {generic} must exist on disk "
                f"(the role-level fallback chain moved here after "
                f"migration 068); looked under {path}"
            )

    def test_file_exists_helper_is_deterministic(self, tmp_path):
        """The helper is deterministic: same input twice returns the
        same (exists, path) tuple. No caching, no network, no mtime."""
        garbage_name = "DOES_NOT_EXIST.md"
        first = governance_file_exists(garbage_name, REPO_ROOT)
        second = governance_file_exists(garbage_name, REPO_ROOT)
        assert first == second
        # And the helper does not write to the filesystem.
        before = set(p.name for p in tmp_path.iterdir()) if tmp_path.exists() else set()
        governance_file_exists(garbage_name, Path(tmp_path))
        after = set(p.name for p in tmp_path.iterdir()) if tmp_path.exists() else set()
        assert before == after
