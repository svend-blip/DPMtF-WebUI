"""Migration 117 brings a database in the live shape to the fresh-install shape.

Measured 2026-09-20: with init_db.py in the right order a fresh install and
the live database had the same schema and differed in six places of system
data (see the migration header). The live shape is rebuilt here from a fresh
install by undoing each correction, because the live database is never read
by a test.
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

NAME = "117_fresh_install_matches_live.sql"
MIG = PROJECT_ROOT / "scripts" / "db" / NAME
ROLLBACK = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "117_fresh_install_matches_live_rollback.sql"
VOLATILE = {"id", "created_at", "updated_at", "applied_at", "granted_at"}
DUPLICATES = {"lbl_bridge_step_add": "lbl_btn_add_step",
              "lbl_alloc_delete": "lbl_bridge_delete",
              "lbl_alloc_save": "lbl_bridge_save"}
LIVE_ESCALATION = "--db-flow FLOW --signal-escalation --from-role {next_role} --to-role archi01"
FRESH_ESCALATION = "--db-flow {flow_key} --signal-escalation --from-role {next_role} --to-role {escalation_role}"


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("fresh117") / "fresh.db"
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(config, "get_db_path", lambda: str(db))
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(PROJECT_ROOT / "scripts" / "init_db.py"), run_name="__main__")
    finally:
        mp.undo()
    return db


def _copy(src_path, dst_path):
    src, dst = sqlite3.connect(src_path), sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return dst_path


def _content(conn):
    out = {}
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")') if r[1] not in VOLATILE]
        if cols:
            select = ", ".join(f'"{c}"' for c in cols)
            out[t] = sorted(map(repr, conn.execute(f'SELECT {select} FROM "{t}"')))
    return out


@pytest.fixture()
def live_shaped(fresh_db, tmp_path):
    conn = sqlite3.connect(_copy(fresh_db, tmp_path / "live-shaped.db"))
    # 1. the two rules are there (the live database has them) — nothing to undo
    # 2. the escalation line names a flow and a role
    assert FRESH_ESCALATION in conn.execute(
        "SELECT content_template FROM bridge_convention_rules WHERE rule_key='technical_review'").fetchone()[0]
    conn.execute("UPDATE bridge_convention_rules SET content_template = replace(content_template, ?, ?) "
                 "WHERE rule_key='technical_review'", (FRESH_ESCALATION, LIVE_ESCALATION))
    conn.execute("UPDATE bridge_convention_rules SET error_template = "
                 "'Failed to deliver verdict. Present to Human manually.' WHERE rule_key='verdict'")
    # 3. the retired duplicates are active and bound beside the kept labels
    for dup in DUPLICATES:
        conn.execute("UPDATE ui_labels SET is_active = 1 WHERE label_key = ?", (dup,))
        conn.execute("INSERT INTO ui_text_slot_labels (slot_key, label_key) VALUES (?, ?)", (dup, dup))
    # 4. the label of migration 096 is gone, its slot and mapping are not
    conn.execute("DELETE FROM ui_label_translations WHERE label_id = 'LBL-1000540'")
    conn.execute("DELETE FROM ui_labels WHERE label_id = 'LBL-1000540'")
    # 6. System Setup says what the role editor says
    for locale, wrong in (("en-US", "Default Model Source"), ("de-DE", "Standardmodell-Quelle"),
                          ("es-ES", "Fuente de modelo predeterminada")):
        conn.execute("UPDATE ui_label_translations SET translated_text = ? "
                     "WHERE label_id = 'LBL-1000319' AND locale = ?", (wrong, locale))
    conn.execute("UPDATE ui_label_translations SET translated_text = 'Standard modellkälla' "
                 "WHERE label_id = 'LBL-1000319' AND locale = 'sv-SE'")
    conn.commit()
    yield conn
    conn.close()


def test_a_live_shaped_database_ends_as_a_fresh_install(fresh_db, live_shaped):
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    live_shaped.commit()
    fresh = sqlite3.connect(fresh_db)
    try:
        want = _content(fresh)
    finally:
        fresh.close()
    got = _content(live_shaped)
    differing = {t: (sorted(set(want[t]) - set(got.get(t, [])))[:3], sorted(set(got.get(t, [])) - set(want[t]))[:3])
                 for t in want if want[t] != got.get(t)}
    assert differing == {}, f"(only fresh, only migrated): {differing}"
    assert live_shaped.execute("SELECT translated_text FROM ui_label_translations "
                               "WHERE label_id='LBL-1000319' AND locale='sv-SE'").fetchone()[0] == "Maskinprofil"


def test_each_retired_slot_is_bound_to_the_kept_label_only(live_shaped):
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    for dup, kept in DUPLICATES.items():
        bound = [r[0] for r in live_shaped.execute(
            "SELECT label_key FROM ui_text_slot_labels WHERE slot_key = ?", (dup,))]
        assert bound == [kept], (dup, bound)
        assert live_shaped.execute("SELECT is_active FROM ui_labels WHERE label_key = ?", (dup,)).fetchone()[0] == 0
        # retired, never deleted (migration 038's rule)
        assert live_shaped.execute("SELECT COUNT(*) FROM ui_labels WHERE label_key = ?", (dup,)).fetchone()[0] == 1


def test_a_database_without_the_two_rules_gets_them(live_shaped):
    live_shaped.execute("DELETE FROM bridge_convention_rules WHERE rule_key IN ('callback', 'json_output')")
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    rows = dict(live_shaped.execute(
        "SELECT rule_key, content_template FROM bridge_convention_rules WHERE rule_key IN ('callback', 'json_output')"))
    assert set(rows) == {"callback", "json_output"}
    # the artifact root of migrations 084/116, not the flow key, and no machine path
    assert "{bridge_dir}/{flow_key}/" not in rows["callback"] + rows["json_output"]
    assert "/home/" not in rows["callback"] + rows["json_output"]


def test_an_existing_rule_is_not_overwritten(live_shaped):
    live_shaped.execute("UPDATE bridge_convention_rules SET content_template = 'edited by hand' WHERE rule_key = 'callback'")
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    assert live_shaped.execute(
        "SELECT content_template FROM bridge_convention_rules WHERE rule_key = 'callback'").fetchone()[0] == "edited by hand"


def test_it_does_nothing_the_second_time(live_shaped):
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    once = _content(live_shaped)
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    assert _content(live_shaped) == once


def test_the_rollback_only_forgets_the_migration(live_shaped):
    live_shaped.executescript(MIG.read_text(encoding="utf-8"))
    before = _content(live_shaped)
    assert live_shaped.execute("SELECT COUNT(*) FROM schema_migrations WHERE filename = ?", (NAME,)).fetchone()[0] == 1
    live_shaped.executescript(ROLLBACK.read_text(encoding="utf-8"))
    after = _content(live_shaped)
    assert live_shaped.execute("SELECT COUNT(*) FROM schema_migrations WHERE filename = ?", (NAME,)).fetchone()[0] == 0
    del before["schema_migrations"], after["schema_migrations"]
    assert after == before
