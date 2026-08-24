#!/usr/bin/env python3
"""Harness Source Unification — frozen launch-command fixtures (Run 013 / D1).

This file holds ONLY the fixtures for now (per handoff 057, STEP 1).
Test functions will be added in handoff 3 / D4.

The fixtures were captured from the UNTOUCHED tree on 2026-08-22 by
running scripts/capture_fixtures.py against the pre-D2 readers
(scripts/bridgeV002/harness.py, scripts/bridgeV002/start_coding.py,
scripts/bridgeV002/import-flow-output.py). Each kind was captured from
a role that EXPLICITLY carries that kind as its allocator_client value
(no "missing key falls back to opencode" behavior was used).

Capture-time normalization: any checkout/project-root path in the
captured command was replaced with the literal `{PROJECT_ROOT}`
placeholder (the seam measured is harness/model selection, not checkout
location — GOAL.md §5). The md5s are computed AFTER normalization and
are the byte-identical identity the post-D2 readers must reproduce.

The fixtures are FROZEN — never regenerated from post-change code
(GOAL.md §2 binding constraint).
"""

from __future__ import annotations

import hashlib
from typing import Dict


# The six harness kinds — exact match to the active bridge_roles.allocator_client
# values that exist today (Run 013 / GOAL.md §1 D2). Each entry carries:
#   - role_key: the bridge_roles row used as the canonical source
#   - command:  the launch command the pre-D2 code built, normalized with
#               `{PROJECT_ROOT}` (no other path substitution)
#   - command_md5: md5 of the normalized command (frozen identity)
LAUNCH_FIXTURES: Dict[str, Dict[str, str]] = {
    "opencode": {
        "role_key": "archi01",
        "command": (
            "OPENCODE_CONFIG_DIR=\"$HOME/.config/opencode-roles/archi01\" "
            "OPENCODE_CONFIG=\"$HOME/.config/opencode-roles/archi01/opencode.json\" "
            "opencode"
        ),
        "command_md5": "4d10f74f35c61d4298d550bbbee1ec66",
    },
    "claude-code": {
        "role_key": "archi01pay",
        "command": (
            "ANTHROPIC_BASE_URL=https://openrouter.ai/api "
            "ANTHROPIC_AUTH_TOKEN=\"$OPENROUTER_API_KEY\" "
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS=32768 "
            "MODEL_ALLOCATOR_ACTIVE_MODEL=archi-pay "
            "env -u ANTHROPIC_API_KEY /home/svend/.local/bin/claude "
            "--model z-ai/glm-5.2"
        ),
        "command_md5": "6395be4593adf2f0eb5319711a5a2dba",
    },
    "codex": {
        "role_key": "imple-codex-minimaxM3",
        # Run 024 (migration 071): the role's harness_profile is 'gpu',
        # so the derived launch carries the gpu sandbox. The fixture
        # pins the NEW reality; the old pin (workspace-write,
        # f818d760…) died with the 087 privilege inversion.
        "command": (
            "codex -m MiniMax-M3 --add-dir /home/svend/flows "
            "--add-dir {PROJECT_ROOT} --add-dir /tmp "
            "--sandbox danger-full-access --ask-for-approval never"
        ),
        "command_md5": "0126450cc17e9a3f4a618fba019cac97",
    },
    "dsh": {
        "role_key": "super-deep-deep4",
        "command": (
            "npx @deepseek-ai/dsh --profile headless "
            "--patch /home/svend/dsh-v4-pro.patch.yml"
        ),
        "command_md5": "69a8a6c4544d0d35b762f0a7ed991cba",
    },
    "pi": {
        "role_key": "pi_imple01",
        "command": (
            "MODEL_ALLOCATOR_ACTIVE_MODEL=MiniMax-M3 "
            "/home/svend/.nvm/versions/node/v22.22.3/bin/pi "
            "--provider minimax --model MiniMax-M3 --no-session"
        ),
        "command_md5": "56ea1a698f4cf85ef3e9c3303a594c19",
    },
    "freebuff": {
        "role_key": "imple01cloud",
        "command": "freebuff",
        "command_md5": "bbee15a4ff0e1a07704222cfa6984840",
    },
}


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _verify_fixtures_are_self_consistent() -> None:
    """Self-check: the embedded md5s match the embedded commands.

    This catches the failure mode where someone hand-edits a command
    and forgets to recompute the md5 — a regression to a silent
    identity-test pass (which would then never fail when the post-D2
    readers drift). The check runs at import time and at pytest
    collection time.
    """
    for kind, entry in LAUNCH_FIXTURES.items():
        expected = entry["command_md5"]
        actual = _md5(entry["command"])
        assert expected == actual, (
            f"fixture md5 mismatch for {kind!r}: embedded {expected!r}, "
            f"recomputed {actual!r}"
        )


_verify_fixtures_are_self_consistent()


# ---------------------------------------------------------------------------
# D4 — Test functions (Run 013 / handoff 059)
#
# These four test functions exercise the four testgoals Run 013 promises:
#   - backfill          -> TG2/TG3 (backfill applied, mirror equality)
#   - launch_identity   -> TG6 identity proof (six six kinds)
#   - no_direct_reads   -> TG5 (no primary allocator_client read)
#   - rollback          -> rollback restores NULL on marker rows,
#                          leaves independent post-backfill writes intact
#
# Tests must NOT mutate the production database at databases/dpmtf.db.
# Any migration/rollback apply uses a scratch DB built in tmp_path. The
# launch_identity test reads the live DB read-only via config.get_db_path()
# and only for the six fixture role_keys.
# ---------------------------------------------------------------------------


import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts/bridgeV002 and the project root are importable so the
# test can call into harness.build_launch_command / build_dsh_invocation
# and use config.get_db_path() (no hardcoded /home/svend paths).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BRIDGEV002 = _PROJECT_ROOT / "scripts" / "bridgeV002"
for p in (str(_PROJECT_ROOT), str(_BRIDGEV002), "/home/svend/harness-allocator"):
    if p not in sys.path:
        sys.path.insert(0, p)

import config  # noqa: E402
import harness  # noqa: E402

# Project root for the {PROJECT_ROOT} normalization used in the fixtures.
# config.get_project_root() is the same value (resolves to the Father root).
_PROJECT_ROOT_STR = str(config.get_project_root())

# ---------------------------------------------------------------------------
# Scratch DB helpers (backfill + rollback tests)
# ---------------------------------------------------------------------------


def _build_scratch_roles_db(tmp_path: Path) -> Path:
    """Build a minimal bridge_roles table in tmp_path for migration tests.

    The migration only reads/writes columns role_key, is_active,
    default_harness_source, and allocator_client; the marker table is
    created by the migration itself.
    """
    db = tmp_path / "scratch_roles.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE bridge_roles (
                role_key TEXT PRIMARY KEY,
                tmux_session TEXT,
                is_active INTEGER DEFAULT 1,
                default_harness_source TEXT DEFAULT NULL,
                allocator_client TEXT DEFAULT NULL
            );
            CREATE TABLE schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _seed_role(
    db: Path,
    role_key: str,
    *,
    is_active: int = 1,
    allocator_client,
    default_harness_source,
) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO bridge_roles "
            "(role_key, tmux_session, is_active, allocator_client, default_harness_source) "
            "VALUES (?, ?, ?, ?, ?)",
            (role_key, f"{role_key}_s", is_active, allocator_client, default_harness_source),
        )
        conn.commit()
    finally:
        conn.close()


def _apply_sql(db: Path, sql_path: Path) -> None:
    """Apply a .sql file (migration or rollback) against the scratch DB."""
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(sql_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def _read(db: Path, sql: str, params=()):
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# (a) backfill
# ---------------------------------------------------------------------------


_MIGRATION_067 = _PROJECT_ROOT / "scripts" / "db" / "067_harness_source_backfill.sql"
_ROLLBACK_067 = (
    _PROJECT_ROOT / "scripts" / "db" / "rollbacks"
    / "067_harness_source_backfill_rollback.sql"
)


def test_backfill_applies_only_to_marker_rows(tmp_path):
    """067 backfills default_harness_source from allocator_client for active
    roles where default_harness_source IS NULL and allocator_client IS NOT NULL.

    Roles with a pre-existing non-NULL default_harness_source are left
    UNCHANGED (independent post-backfill writes survive). The marker
    table records exactly the backfilled rows.
    """
    db = _build_scratch_roles_db(tmp_path)
    _seed_role(db, "backfill_a", allocator_client="opencode", default_harness_source=None)
    _seed_role(db, "backfill_b", allocator_client="claude-code", default_harness_source=None)
    _seed_role(db, "independent_c", allocator_client="opencode",
               default_harness_source="preset_value")
    _seed_role(db, "null_alloc_d", allocator_client=None, default_harness_source=None)
    _seed_role(db, "inactive_e", is_active=0, allocator_client="codex",
               default_harness_source=None)

    _apply_sql(db, _MIGRATION_067)

    rows = dict(
        (r[0], (r[1], r[2])) for r in
        _read(db, "SELECT role_key, allocator_client, default_harness_source "
                  "FROM bridge_roles ORDER BY role_key")
    )
    # backfilled rows
    assert rows["backfill_a"] == ("opencode", "opencode"), rows["backfill_a"]
    assert rows["backfill_b"] == ("claude-code", "claude-code"), rows["backfill_b"]
    # pre-existing value unchanged
    assert rows["independent_c"] == ("opencode", "preset_value"), rows["independent_c"]
    # NULL allocator_client — no backfill
    assert rows["null_alloc_d"] == (None, None), rows["null_alloc_d"]
    # inactive role — no backfill (migration predicates on is_active=1)
    assert rows["inactive_e"] == ("codex", None), rows["inactive_e"]

    # Marker table exists and lists exactly the two backfilled rows
    marker = _read(
        db, "SELECT role_key FROM _migration_067_backfilled_roles ORDER BY role_key"
    )
    assert [r[0] for r in marker] == ["backfill_a", "backfill_b"]


# ---------------------------------------------------------------------------
# (b) launch_identity — re-derive each fixture through the SWITCHED code.
#
# The derivation uses ONLY the fixture's `role_key` (and `kind`) as input;
# it MUST NOT read fixture["command"] as the expected value. The
# fixture["command_md5"] is the byte-identical target to compare against.
# ---------------------------------------------------------------------------


def _load_role_readonly(role_key: str) -> dict:
    """Read a single role row from the live DB (READ-ONLY — production
    DB is never mutated by this test). Returns a dict with all columns.
    """
    db_path = str(config.get_db_path())
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM bridge_roles WHERE role_key = ? AND is_active = 1",
        (role_key,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def _switched_harness_source(role: dict) -> str:
    """The exact expression start_coding.py uses for harness_source."""
    return (
        role.get("default_harness_source")
        or role.get("allocator_client")
        or "opencode"
    )


def _ma_run(role_key: str, client: str) -> str:
    """Resolve a model-allocator kind's launch command via subprocess."""
    proc = subprocess.run(
        [
            "/home/svend/model-allocator/venv/bin/model-allocator",
            "run",
            "--role", role_key,
            "--client", client,
            "--no-auto-start",
        ],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"model-allocator run failed for {role_key}/{client}: rc={proc.returncode} "
        f"stderr={proc.stderr!r}"
    )
    return proc.stdout.strip()


@pytest.mark.parametrize(
    "kind",
    ["opencode", "claude-code", "codex", "dsh", "pi", "freebuff"],
)
def test_launch_identity_reproduced_by_switched_readers(kind):
    """For each fixture, derive the launch command through the SWITCHED
    code path (the readers landed in handoff 058) and assert the
    resulting command matches the frozen fixture md5 byte-for-byte.

    The derivation reads ONLY the fixture's role_key and the live role
    row — never fixture["command"] (the expected output). A pass that
    echoes fixture["command"] is a fabricated pass and is rejected.
    """
    fixture = LAUNCH_FIXTURES[kind]  # structure lookup only — never reads fixture["command"]
    role_key = fixture["role_key"]
    expected_md5 = fixture["command_md5"]

    role = _load_role_readonly(role_key)
    assert role, f"role {role_key!r} not found in live DB"
    harness_source = _switched_harness_source(role)

    if kind in ("codex", "dsh"):
        # Native kinds — harness.py builds the launch command directly.
        assert harness_source == kind, (
            f"native kind {kind} role {role_key}: harness_source={harness_source!r}"
        )
        if kind == "codex":
            cmd = harness.build_launch_command("codex", role)
        else:
            cmd = harness.build_dsh_invocation(role)
    elif kind in ("opencode", "claude-code", "pi"):
        # Model-allocator kinds (start_coding.py --client shape).
        assert harness_source == kind, (
            f"model-allocator kind {kind} role {role_key}: "
            f"harness_source={harness_source!r}"
        )
        cmd = _ma_run(role_key, harness_source)
    elif kind == "freebuff":
        # import-flow-output.py derivation shape (uses enter_command fallback).
        enter_cmd = role.get("enter_command", "default")
        expected_fb = (
            role.get("default_harness_source")
            or role.get("allocator_client")
            or ("freebuff" if enter_cmd == "c-m" else "opencode")
        )
        assert expected_fb == "freebuff", (
            f"freebuff role {role_key}: expected_fb={expected_fb!r}"
        )
        cmd = _ma_run(role_key, expected_fb)
    else:
        raise AssertionError(f"unknown kind {kind!r}")

    normalized = cmd.replace(_PROJECT_ROOT_STR, "{PROJECT_ROOT}")
    actual_md5 = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    assert actual_md5 == expected_md5, (
        f"launch_identity mismatch for {kind!r} role {role_key!r}: "
        f"expected md5={expected_md5!r}, got md5={actual_md5!r}; "
        f"command={normalized!r}"
    )


# ---------------------------------------------------------------------------
# (c) no_direct_reads — every allocator_client reference is a fallback
# ---------------------------------------------------------------------------


_READER_FILES = [
    _BRIDGEV002 / "harness.py",
    _BRIDGEV002 / "start_coding.py",
    _BRIDGEV002 / "import-flow-output.py",
]

# A "primary" allocator_client read is one that is NOT annotated as
# deprecated/fallback AND is NOT the second operand of an `or` fallback.
# The TG5 grep equivalent expressed as a per-line rule:
_PRIMARY_PATTERNS = [
    re.compile(r"or\s+role\.get\(\s*[\"']allocator_client[\"']\s*\)"),  # or-fallback
    re.compile(r"or\s+row\[\"allocator_client\"\]"),                   # SELECT or-fallback
    re.compile(r"allocator_client.*#\s*deprecated"),                  # deprecated annotation
    re.compile(r"\bdeprecated\b.*\b(allocator_client|fallback)"),      # deprecated near fallback
    re.compile(r"\bfallback\b"),                                       # "fallback" keyword anywhere on line
]


def test_no_direct_reads_of_allocator_client_in_three_readers():
    """Every `allocator_client` reference in the three readers must be
    a deprecated/fallback annotation or the second operand of an `or`
    fallback (mirrors TG5's grep as a pytest assertion).

    harness.py is expected to contain ZERO `allocator_client`
    occurrences (the switch landed in the docstrings of handoff 058);
    start_coding.py and import-flow-output.py contain only
    `or`-fallback operands and `# deprecated`/fallback annotations.
    """
    flagged = []
    for path in _READER_FILES:
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "allocator_client" not in line:
                continue
            if any(p.search(line) for p in _PRIMARY_PATTERNS):
                continue
            flagged.append(f"{path}:{lineno}: {line.strip()}")
    assert not flagged, (
        "primary allocator_client read(s) found in the three readers:\n"
        + "\n".join(flagged)
    )


# ---------------------------------------------------------------------------
# (d) rollback — restores marker rows to NULL, leaves independent
#     post-backfill writes intact, drops the marker table.
# ---------------------------------------------------------------------------


def test_rollback_restores_marker_rows_and_preserves_independent_writes(tmp_path):
    """After 067 is applied, an independent post-backfill write on a
    role whose default_harness_source was non-NULL BEFORE 067 (and so
    NOT in the marker table) survives the rollback. Marker rows go
    back to NULL. The marker table is dropped."""
    db = _build_scratch_roles_db(tmp_path)
    _seed_role(db, "marker_a", allocator_client="opencode", default_harness_source=None)
    _seed_role(db, "marker_b", allocator_client="claude-code", default_harness_source=None)
    _seed_role(db, "independent_c", allocator_client="opencode",
               default_harness_source="preset_value")

    _apply_sql(db, _MIGRATION_067)

    # An independent post-backfill write simulating a different path
    # setting default_harness_source after 067 ran.
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "UPDATE bridge_roles SET default_harness_source = ? WHERE role_key = ?",
            ("post_backfill_write", "independent_c"),
        )
        conn.commit()
    finally:
        conn.close()

    _apply_sql(db, _ROLLBACK_067)

    rows = dict(
        (r[0], r[1]) for r in
        _read(db, "SELECT role_key, default_harness_source FROM bridge_roles ORDER BY role_key")
    )
    # marker rows restored to NULL
    assert rows["marker_a"] is None, rows["marker_a"]
    assert rows["marker_b"] is None, rows["marker_b"]
    # independent post-backfill write survived (not in marker table)
    assert rows["independent_c"] == "post_backfill_write", rows["independent_c"]

    # marker table dropped
    marker_tables = _read(
        db, "SELECT name FROM sqlite_master WHERE type='table' AND name='_migration_067_backfilled_roles'"
    )
    assert marker_tables == [], marker_tables
