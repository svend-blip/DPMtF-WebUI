"""init_db.py must not undo what a migration did to a convention template.

Found 2026-09-20: section 3.2b of init_db.py rewrote the content_template of
`technical_review`, `verdict` and `human_delivery` UNCONDITIONALLY, with text
from before migration 084 — `{bridge_dir}/{flow_key}/` as the path root where
084 had put `{bridge_dir}/{artifact_root}/`. init_db.py runs the migrations
first and its own statements afterwards, and the validation checklist has
everyone run it routinely, so every run reverted the migration for those three
rules; tests/test_artifact_root_prompt.py TG1/TG2 had been red since the first
run after 2026-08-31. The section exists to repair one thing — rows seeded with
the legacy `implementertoreview/` path — and now touches only those.

Hermetic: every test builds its own database; none reads the live one.
"""
import contextlib
import io
import runpy
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import config  # noqa: E402

RULES = ("technical_review", "verdict", "human_delivery")
FLOW_KEY_ROOT = "{bridge_dir}/{flow_key}/"
ARTIFACT_ROOT = "{bridge_dir}/{artifact_root}/"


def _run_init_db(db_path, monkeypatch):
    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(str(PROJECT_ROOT / "scripts" / "init_db.py"), run_name="__main__")


def _templates(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return dict(conn.execute(
            "SELECT rule_key, COALESCE(content_template, '') FROM bridge_convention_rules"))
    finally:
        conn.close()


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    """One fresh install, built once: migrations, then init_db's seeds."""
    db = tmp_path_factory.mktemp("initdb") / "fresh.db"
    mp = pytest.MonkeyPatch()
    try:
        _run_init_db(db, mp)
    finally:
        mp.undo()
    return db


def _copy(fresh_db, tmp_path):
    target = tmp_path / "copy.db"
    src = sqlite3.connect(fresh_db)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return target


def test_a_fresh_install_seeds_the_artifact_root_not_the_flow_key(fresh_db):
    templates = _templates(fresh_db)
    for rule in RULES:
        assert rule in templates, f"{rule} was not seeded"
        assert FLOW_KEY_ROOT not in templates[rule], f"{rule} is seeded with the flow key as a path root"
        assert ARTIFACT_ROOT in templates[rule], f"{rule} names no artifact-root path"


def test_a_template_a_migration_set_survives_init_db(fresh_db, tmp_path, monkeypatch):
    # The regression itself: whatever a migration (or the UI) put in the
    # template is there after init_db has run again.
    db = _copy(fresh_db, tmp_path)
    conn = sqlite3.connect(db)
    for rule in RULES:
        conn.execute("UPDATE bridge_convention_rules SET content_template = ? WHERE rule_key = ?",
                     (f"set by a later migration for {rule}: {ARTIFACT_ROOT}verdicts/x.md", rule))
    conn.commit()
    conn.close()
    before = _templates(db)

    _run_init_db(db, monkeypatch)

    after = _templates(db)
    for rule in RULES:
        assert after[rule] == before[rule], f"init_db rewrote {rule}"


def test_running_init_db_again_changes_no_template(fresh_db, tmp_path, monkeypatch):
    db = _copy(fresh_db, tmp_path)
    before = _templates(db)
    _run_init_db(db, monkeypatch)
    assert _templates(db) == before


def test_the_legacy_path_is_still_repaired(fresh_db, tmp_path, monkeypatch):
    # What section 3.2b was written for: review02pay wrote verdicts under
    # {bridge_dir}/implementertoreview/ on handoffs 15 and 17.
    db = _copy(fresh_db, tmp_path)
    conn = sqlite3.connect(db)
    for rule in RULES:
        conn.execute("UPDATE bridge_convention_rules SET content_template = ? WHERE rule_key = ?",
                     ("<deliverable_output>\n  {bridge_dir}/implementertoreview/{handoff_id}-verdict.md\n"
                      "</deliverable_output>", rule))
    conn.commit()
    conn.close()

    _run_init_db(db, monkeypatch)

    for rule, template in _templates(db).items():
        if rule in RULES:
            assert "implementertoreview/" not in template, f"{rule} keeps the legacy path"
            assert ARTIFACT_ROOT in template and FLOW_KEY_ROOT not in template, rule
