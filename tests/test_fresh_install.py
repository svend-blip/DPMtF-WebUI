"""A fresh install is what the migrations make of the seeds — not the seeds alone.

Found 2026-09-20. init_db.py ran every migration first and seeded afterwards.
The live database grew the other way round: its rows existed, and each
migration changed them. On a fresh database a data migration that reads or
updates seeded rows therefore found none, did nothing, and was recorded as
applied; the seeds then arrived in their original form. Measured: 118 of 434
labels had a Spanish text (migration 036 translates the labels that exist —
there were none yet), the `handoff` template was the 559-character seed rather
than the 1 432-character form migrations 095/098/101 had made of it, and 761
rows the migrations name were missing.

The order on a fresh database is now: the baseline migration (the schema the
seeds were written for), the seeds, then every other migration — the order in
which the live database came to be. An existing database is migrated exactly
as before.

Hermetic: one fresh database is built per module; nothing reads the live one.
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
import migrate  # noqa: E402

MANDATORY_LOCALES = ("en-US", "da-DK", "de-DE", "es-ES")


def _run_init_db(db_path, mp):
    mp.setattr(config, "get_db_path", lambda: str(db_path))
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(str(PROJECT_ROOT / "scripts" / "init_db.py"), run_name="__main__")


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("fresh") / "fresh.db"
    mp = pytest.MonkeyPatch()
    try:
        _run_init_db(db, mp)
    finally:
        mp.undo()
    return db


def _q(db, sql, *args):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_every_migration_is_recorded(fresh_db):
    recorded = {r[0] for r in _q(fresh_db, "SELECT filename FROM schema_migrations")}
    assert recorded == {p.name for p in migrate._discover_migrations()}


def test_a_migration_that_updates_a_seeded_row_takes_effect(fresh_db):
    # Migrations 095/098/101 rewrote the seeded `handoff` template; 101 added
    # the README Impact block. Applied before the seed existed, they did
    # nothing, and a fresh install dispatched with the template of 2026-06.
    handoff = _q(fresh_db, "SELECT content_template FROM bridge_convention_rules WHERE rule_key='handoff'")
    assert handoff and "## README Impact" in (handoff[0][0] or "")


def test_a_migration_that_reads_seeded_rows_finds_them(fresh_db):
    # Migration 036 writes a Spanish text for every label that exists.
    labels = _q(fresh_db, "SELECT COUNT(*) FROM ui_labels WHERE is_active = 1")[0][0]
    spanish = _q(fresh_db,
                 "SELECT COUNT(*) FROM ui_label_translations t JOIN ui_labels l ON l.label_id = t.label_id "
                 "WHERE l.is_active = 1 AND t.locale = 'es-ES' AND COALESCE(t.translated_text, '') != ''")[0][0]
    assert labels > 400
    assert spanish == labels, f"{labels - spanish} of {labels} active labels have no es-ES text"


# Surrogate keys and clocks. Several seeds are INSERT OR REPLACE, which gives
# an unchanged row a new autoincrement id and a new timestamp; nothing refers
# to these tables by id (the i18n layers join on keys), so that is not a
# change of content and is not what this test is about.
VOLATILE = {"id", "created_at", "updated_at", "applied_at", "granted_at"}


def _content(db):
    conn = sqlite3.connect(db)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        out = {}
        for t in tables:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")') if r[1] not in VOLATILE]
            if not cols:
                continue
            select = ", ".join(f'"{c}"' for c in cols)
            out[t] = sorted(map(repr, conn.execute(f'SELECT {select} FROM "{t}"')))
        return out
    finally:
        conn.close()


def test_running_init_db_again_changes_nothing(fresh_db, tmp_path):
    # The second run is the "existing database" path, and it must leave the
    # content of every table alone — a seed that rewrites what a migration
    # made of it is the same defect from the other side. Measured before the
    # fix: the label seed was INSERT OR REPLACE without is_active, so every
    # run re-activated the three duplicates migration 038 had retired, and the
    # mapping seed bound their slots a second time.
    target = tmp_path / "again.db"
    src, dst = sqlite3.connect(fresh_db), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()

    before = _content(target)
    mp = pytest.MonkeyPatch()
    try:
        _run_init_db(target, mp)
    finally:
        mp.undo()
    after = _content(target)
    changed = {t: (len(set(before[t]) - set(after.get(t, []))), len(set(after.get(t, [])) - set(before[t])))
               for t in before if before[t] != after.get(t)}
    assert changed == {}, f"a second init_db run changed (rows gone, rows new): {changed}"


def test_every_active_label_has_the_four_mandatory_locales(fresh_db):
    missing = _q(fresh_db, """
        SELECT l.label_key, loc.locale FROM ui_labels l
        JOIN (SELECT 'en-US' AS locale UNION SELECT 'da-DK' UNION SELECT 'de-DE' UNION SELECT 'es-ES') loc
        LEFT JOIN ui_label_translations t
               ON t.label_id = l.label_id AND t.locale = loc.locale AND t.is_active = 1
        WHERE l.is_active = 1 AND COALESCE(t.translated_text, '') = ''
        ORDER BY 1, 2""")
    assert missing == [], f"{len(missing)} label/locale pairs have no text, e.g. {missing[:5]}"


def test_a_label_says_what_its_key_says(fresh_db):
    # LBL-1000319..329 (System Setup) carried the texts of the role-editor
    # model fields in every locale but Danish: "Default Model Source" under
    # system_setup_machine_profile. Migration 036 had translated that wrong
    # English into Spanish, so a fresh install had it too.
    rows = dict(_q(fresh_db, """
        SELECT t.locale, t.translated_text FROM ui_label_translations t
        JOIN ui_labels l ON l.label_id = t.label_id
        WHERE l.label_key = 'system_setup_machine_profile'"""))
    assert rows["en-US"] == "Machine Profile"
    assert rows["de-DE"] == "Maschinenprofil"
    assert rows["es-ES"] == "Perfil de máquina"


def test_a_slot_is_bound_to_one_label(fresh_db):
    # The i18n API builds {slot_key: text}; with two labels on a slot the text
    # is whichever row the query returns last.
    double = _q(fresh_db, "SELECT slot_key, COUNT(*) FROM ui_text_slot_labels GROUP BY 1 HAVING COUNT(*) > 1")
    assert double == []


def test_every_convention_rule_the_live_database_dispatches_with_is_installed(fresh_db):
    rules = {r[0] for r in _q(fresh_db, "SELECT rule_key FROM bridge_convention_rules")}
    assert {"callback", "json_output"} <= rules, sorted(rules)


def test_an_existing_database_gets_its_pending_migrations(fresh_db, tmp_path):
    # Not fresh: forget the newest migration and run init_db. It is applied
    # again through the ordinary path, not skipped and not re-seeded around.
    target = tmp_path / "existing.db"
    src, dst = sqlite3.connect(fresh_db), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    newest = migrate._discover_migrations()[-1].name
    conn = sqlite3.connect(target)
    conn.execute("DELETE FROM schema_migrations WHERE filename = ?", (newest,))
    conn.commit()
    conn.close()
    assert migrate.is_fresh(str(target)) is False
    assert migrate.pending_migrations(str(target))["pending"] == [newest]
    mp = pytest.MonkeyPatch()
    try:
        _run_init_db(target, mp)
    finally:
        mp.undo()
    assert migrate.pending_migrations(str(target))["pending"] == []


def test_is_fresh(tmp_path):
    assert migrate.is_fresh(str(tmp_path / "absent.db")) is True
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert migrate.is_fresh(str(empty)) is True
    used = tmp_path / "used.db"
    conn = sqlite3.connect(used)
    conn.execute("CREATE TABLE anything (id INTEGER)")
    conn.commit()
    conn.close()
    assert migrate.is_fresh(str(used)) is False
    # asking must not create the file
    assert not (tmp_path / "absent.db").exists()


def test_stop_after_applies_the_baseline_only(tmp_path):
    db = tmp_path / "partial.db"
    baseline = migrate.baseline_migration()
    summary = migrate.run_migrations(str(db), stop_after=baseline)
    assert summary["applied"] == [baseline]
    assert len(migrate.pending_migrations(str(db))["pending"]) == len(migrate._discover_migrations()) - 1
