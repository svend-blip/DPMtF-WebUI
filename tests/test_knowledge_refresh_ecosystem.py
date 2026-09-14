"""Tests for ``scripts/knowledge_refresh_ecosystem.py``.

The script is loaded through ``importlib.util`` so pytest's own ``sys.argv``
never reaches its ``argparse`` parser and no ``__pycache__`` is written. Each
test builds a throwaway ``bridge_flows`` table in a temp SQLite database and
points ``config.get_db_path`` at it; the production database is never opened.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config  # noqa: E402
from knowledge import scopes as knowledge_scopes  # noqa: E402

_SCRIPT_PATH = _PROJECT_ROOT / "scripts" / "knowledge_refresh_ecosystem.py"


@pytest.fixture(scope="module")
def ecosystem_script():
    spec = importlib.util.spec_from_file_location(
        "knowledge_refresh_ecosystem", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_flows_db(tmp_path, targets):
    """Create a temp ``bridge_flows`` table with the columns the script reads."""
    db_path = tmp_path / "flows.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE bridge_flows ("
            "flow_key TEXT, name TEXT, target_project_path TEXT)"
        )
        for flow_key, target_path in targets:
            conn.execute(
                "INSERT INTO bridge_flows "
                "(flow_key, name, target_project_path) VALUES (?, ?, ?)",
                (flow_key, "flow " + flow_key, str(target_path)),
            )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_ecosystem_targets_are_derived_from_bridge_flows_and_father(
    ecosystem_script, tmp_path, monkeypatch
):
    foo = tmp_path / "FooProj"
    foo.mkdir()
    db_path = _create_flows_db(tmp_path, [("f1", foo)])

    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))

    targets = ecosystem_script.collect_targets(str(db_path))

    father_scope = config.get_knowledge_scope()
    father_path = str(Path(config.get_project_root()).resolve())
    assert (father_scope, father_path) in targets
    assert ("fooproj", str(foo.resolve())) in targets
    # The non-Father scope is derived through scope_for_target, not invented.
    assert knowledge_scopes.scope_for_target(str(foo)) == "fooproj"


def test_ecosystem_dry_run_touches_nothing(
    ecosystem_script, tmp_path, monkeypatch, capsys
):
    foo = tmp_path / "FooProj"
    foo.mkdir()
    db_path = _create_flows_db(tmp_path, [("f1", foo)])

    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))
    fresh_index_dir = tmp_path / "fresh-index"
    monkeypatch.setattr(
        config, "get_knowledge_index_dir", lambda: str(fresh_index_dir)
    )

    def tripwire(scope, target_path):
        raise AssertionError("refresh_scope must not be called during --dry-run")

    monkeypatch.setattr(ecosystem_script, "refresh_scope", tripwire)

    exit_code = ecosystem_script.main(["--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert ("fooproj\t" + str(foo.resolve())) in captured.out
    assert not fresh_index_dir.exists()

    conn = sqlite3.connect(db_path)
    try:
        table_count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'knowledge_indexes'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert table_count == 0


def test_ecosystem_reports_a_failed_target_and_exits_one(
    ecosystem_script, tmp_path, monkeypatch, capsys
):
    ok_dir = tmp_path / "OkProj"
    ok_dir.mkdir()
    bad_dir = tmp_path / "BadProj"
    bad_dir.mkdir()
    db_path = _create_flows_db(
        tmp_path, [("ok", ok_dir), ("bad", bad_dir)]
    )

    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))

    def fake_refresh_scope(scope, target_path):
        if target_path == str(bad_dir.resolve()):
            raise RuntimeError("boom")
        return {"status": "noop", "manifest": "/tmp/manifest.jsonl"}

    monkeypatch.setattr(ecosystem_script, "refresh_scope", fake_refresh_scope)

    exit_code = ecosystem_script.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "knowledge_refresh_ecosystem: error: badproj: boom" in captured.err
    assert "okproj\tnoop\t-" in captured.out
