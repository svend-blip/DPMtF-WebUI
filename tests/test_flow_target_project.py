"""Tests for the per-flow target project (migration 016).

A flow does not necessarily operate on Father. Roles are shared across
flows — ``imple01`` serves both ``strict_review`` and
``supervised_review`` — so the target belongs to the flow, not the role.

Before migration 016 the governance files carried ``cd {project_path}``,
a placeholder dispatch.py never replaced. Roles read it as literal text,
never changed directory, and ran Father's checks against whatever the
real target was. Measured in run goal-009 (2026-07-30): handoff 32 was
rejected for "the files do not exist" and "235 tests not 315" — both
true of Father, neither true of the target — while the same blind
checklist APPROVED two earlier handoffs.

These tests pin both halves: the resolver, and the authoritative Target
Project preamble that dispatch injects (the governance file is read from
disk by the role, so the preamble is the only text that can carry the
target).
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

from bridge_lib import get_flow_target_project  # noqa: E402


def _make_db(tmp_path, rows):
    """Build a minimal bridge_flows table. rows: [(flow_key, target)]."""
    db = str(tmp_path / "flows.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE bridge_flows ("
        "  flow_key TEXT PRIMARY KEY,"
        "  target_project_path TEXT DEFAULT NULL"
        ")"
    )
    conn.executemany(
        "INSERT INTO bridge_flows (flow_key, target_project_path) VALUES (?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def test_flow_with_target_returns_that_path(tmp_path):
    target = tmp_path / "some-project"
    target.mkdir()
    db = _make_db(tmp_path, [("supervised_review", str(target))])

    assert get_flow_target_project("supervised_review", db_path=db) == str(target)


def test_flow_without_target_falls_back_to_father(tmp_path):
    """NULL means "targets Father" — the behaviour that predates the column."""
    import config

    db = _make_db(tmp_path, [("strict_review", None)])

    assert get_flow_target_project("strict_review", db_path=db) == config.get_project_root()


def test_empty_string_target_is_treated_as_unset(tmp_path):
    """A blank field from the UI must not resolve to the filesystem root."""
    import config

    db = _make_db(tmp_path, [("strict_review", "   ")])

    assert get_flow_target_project("strict_review", db_path=db) == config.get_project_root()


def test_unknown_flow_falls_back_to_father(tmp_path):
    import config

    db = _make_db(tmp_path, [("strict_review", None)])

    assert get_flow_target_project("no_such_flow", db_path=db) == config.get_project_root()


def test_missing_target_directory_raises_rather_than_falling_back(tmp_path):
    """The silent failure this column exists to remove must not be reintroduced.

    Falling back to Father when the configured target is missing would
    recreate exactly the goal-009 failure: a role reviewing the wrong
    repository while believing it reviewed the right one.
    """
    db = _make_db(tmp_path, [("supervised_review", str(tmp_path / "gone"))])

    with pytest.raises(ValueError) as exc:
        get_flow_target_project("supervised_review", db_path=db)

    assert "gone" in str(exc.value)


def test_resolver_survives_a_database_without_the_column(tmp_path):
    """Pre-016 databases must keep working — the column is additive."""
    import config

    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE bridge_flows (flow_key TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO bridge_flows (flow_key) VALUES ('strict_review')")
    conn.commit()
    conn.close()

    assert get_flow_target_project("strict_review", db_path=db) == config.get_project_root()


def test_target_block_is_empty_when_the_flow_targets_father(tmp_path, monkeypatch):
    """Father-targeting flows must see a byte-identical injection to before."""
    import dispatch

    db = _make_db(tmp_path, [("strict_review", None)])
    monkeypatch.setattr(dispatch, "_db_path", lambda: db)

    assert dispatch.build_target_project_block("strict_review") == ""


def test_target_block_states_the_default_and_defers_to_the_handoff(tmp_path, monkeypatch):
    """The preamble states a fact and yields to the handoff's fence.

    It used to assert its own authority ("This line is authoritative … NOT
    on Father") unconditionally -- so when a run's scope differed from the
    flow's default, it ordered every role to cd AWAY from the work,
    contradicting the handoff, the result file and the run contract at
    once (preferred_cloud run 009). A reviewer that had obeyed it would
    have reviewed an untouched repository.

    The contract now: name the flow's default target, state that the
    handoff wins when it names a location, and keep the {project_path}
    warning -- a placeholder in a governance file read from disk is never
    interpolated by anything.
    """
    import dispatch

    target = tmp_path / "music-video-orchestrator"
    target.mkdir()
    db = _make_db(tmp_path, [("supervised_review", str(target))])
    monkeypatch.setattr(dispatch, "_db_path", lambda: db)

    block = dispatch.build_target_project_block("supervised_review")
    assert str(target) in block
    assert "THE HANDOFF WINS" in block
    assert "{project_path}" in block
    # Det gamle autoritetskrav må ikke genopstå: en prompt der hævder sin
    # egen autoritet er uskelnelig fra et injektionsforsøg.
    assert "authoritative" not in block.lower()


def test_target_block_propagates_the_missing_directory_error(tmp_path, monkeypatch):
    """Dispatch must not inject a prompt naming a directory that is not there."""
    import dispatch

    db = _make_db(tmp_path, [("supervised_review", str(tmp_path / "gone"))])
    monkeypatch.setattr(dispatch, "_db_path", lambda: db)

    with pytest.raises(ValueError):
        dispatch.build_target_project_block("supervised_review")
