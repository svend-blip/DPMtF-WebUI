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


# ── every key the frontend asks for resolves ─────────────────────────────

def _frontend_keys():
    """Literal lbl("key", ...) keys and data-slot attributes, plus the one
    family of keys the frontend builds at run time."""
    import re
    keys = set()
    for js in sorted((PROJECT_ROOT / "static" / "js").glob("*.js")):
        src = js.read_text(encoding="utf-8")
        keys |= set(re.findall(r"""\blbl\(\s*["']([A-Za-z0-9_.-]+)["']\s*[,)]""", src))
        sections = re.search(r"_systemSetupSections\s*=\s*\[(.*?)\]", src, re.S)
        if sections:
            keys |= {"system_setup_run_" + s for s in re.findall(r'"([a-z_]+)"', sections.group(1))}
    for html in sorted((PROJECT_ROOT / "templates").glob("*.html")):
        keys |= set(re.findall(r'data-slot="([^"]+)"', html.read_text(encoding="utf-8")))
    return keys


def test_the_key_scan_finds_the_frontend():
    keys = _frontend_keys()
    assert len(keys) > 300
    assert {"lbl_page_title", "pg_setup", "system_setup_run_paths"} <= keys


@pytest.mark.parametrize("locale", MANDATORY_LOCALES)
def test_every_key_the_frontend_asks_for_resolves(fresh_db, locale):
    # The frontend loads /api/ui-labels/main and nothing else, and the API
    # walks slot -> binding -> label (domain main) -> translation. Found
    # 2026-09-20: 104 keys fell out of that walk — 28 labels no slot was
    # bound to, 20 labels in a domain nothing fetches, and 56 keys with no
    # label at all — and the UI had shown their hardcoded fallbacks since.
    resolved = {r[0] for r in _q(fresh_db, """
        SELECT s.slot_key FROM ui_text_slots s
        JOIN ui_text_slot_labels sl ON sl.slot_key = s.slot_key
        JOIN ui_labels l ON l.label_key = sl.label_key AND l.label_domain = 'main' AND l.is_active = 1
        JOIN ui_label_translations t ON t.label_id = l.label_id AND t.locale = ? AND t.is_active = 1
        WHERE COALESCE(t.translated_text, '') != ''""", locale)}
    unresolved = sorted(_frontend_keys() - resolved)
    assert unresolved == [], f"{len(unresolved)} keys do not resolve in {locale}, e.g. {unresolved[:8]}"


# ── the core flows are part of a fresh install ───────────────────────────

CORE_FLOWS = {"strict_review": 4, "cloud_llm": 4, "cloud_pay": 4, "1010-01-PLOOP": 2, "1010-02-ELOOP": 3}


def test_the_core_flows_are_installed_with_their_steps(fresh_db):
    # strict_review, cloud_llm and cloud_pay are the flows the governance
    # 40x/41x/42x files describe; they and the 1010 family were made by hand
    # in the production database and existed nowhere else until migration 119.
    steps = dict(_q(fresh_db, "SELECT flow_key, COUNT(*) FROM bridge_flow_steps WHERE is_active = 1 GROUP BY 1"))
    flows = {r[0] for r in _q(fresh_db, "SELECT flow_key FROM bridge_flows WHERE is_active = 1")}
    assert set(CORE_FLOWS) <= flows, sorted(set(CORE_FLOWS) - flows)
    assert {k: steps.get(k) for k in CORE_FLOWS} == CORE_FLOWS


def test_every_role_a_flow_names_exists(fresh_db):
    # Found 2026-09-20: the role `human` existed only in production, and 20
    # steps in 10 migrated flows named it.
    dangling = _q(fresh_db, """
        SELECT flow_key, step_key, from_role, to_role FROM bridge_flow_steps
        WHERE from_role NOT IN (SELECT role_key FROM bridge_roles)
           OR to_role   NOT IN (SELECT role_key FROM bridge_roles)""")
    assert dangling == [], f"{len(dangling)} steps name a role that does not exist, e.g. {dangling[:3]}"
    supervisors = _q(fresh_db, """
        SELECT flow_key, supervisor_role FROM bridge_flows
        WHERE COALESCE(supervisor_role, '') != '' AND supervisor_role NOT IN (SELECT role_key FROM bridge_roles)""")
    assert supervisors == []


def test_every_rule_a_step_names_exists(fresh_db):
    dangling = _q(fresh_db, """
        SELECT flow_key, step_key, rule_key FROM bridge_flow_steps
        WHERE COALESCE(rule_key, '') != '' AND rule_key NOT IN (SELECT rule_key FROM bridge_convention_rules)""")
    assert dangling == []


def test_the_core_flows_name_no_home_directory(fresh_db):
    # The repository is public. In production cloud_pay and the 1010 family
    # carry a target path under the author's home directory; the migration
    # installs them without one (no target = the flow works in Father, and
    # the path is set per installation in the flow editor). Seven older
    # migrations do write such a path — that is theirs, and not measured here.
    flows = tuple(CORE_FLOWS)
    marks = ",".join("?" * len(flows))
    rows = _q(fresh_db, f"SELECT * FROM bridge_flows WHERE flow_key IN ({marks})", *flows)
    rows += _q(fresh_db, f"SELECT * FROM bridge_flow_steps WHERE flow_key IN ({marks})", *flows)
    rows += _q(fresh_db, f"""SELECT * FROM bridge_roles WHERE role_key IN (
        SELECT from_role FROM bridge_flow_steps WHERE flow_key IN ({marks})
        UNION SELECT to_role FROM bridge_flow_steps WHERE flow_key IN ({marks}))""", *flows, *flows)
    assert len(rows) > 30
    hits = [str(v)[:80] for row in rows for v in row
            if isinstance(v, str) and ("/home/" in v or "/Users/" in v or "svend" in v.lower())]
    assert hits == []
    assert _q(fresh_db, f"SELECT DISTINCT target_project_path FROM bridge_flows WHERE flow_key IN ({marks})",
              *flows) == [(None,)]


# ── a fresh install targets no directory this machine does not have ──────

def _targets(db):
    return dict(_q(db, "SELECT flow_key, target_project_path FROM bridge_flows "
                       "WHERE COALESCE(target_project_path, '') != ''"))


def test_clear_missing_target_paths_clears_what_is_not_here(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE bridge_flows (flow_key TEXT PRIMARY KEY, target_project_path TEXT, updated_at TEXT)")
    conn.executemany("INSERT INTO bridge_flows (flow_key, target_project_path) VALUES (?, ?)",
                     [("here", str(tmp_path)), ("gone", str(tmp_path / "nobody" / "project")),
                      ("father", None), ("blank", "")])
    conn.commit()
    conn.close()
    cleared = migrate.clear_missing_target_paths(str(db))
    assert cleared == [("gone", str(tmp_path / "nobody" / "project"))]
    assert _targets(db) == {"here": str(tmp_path)}
    assert migrate.clear_missing_target_paths(str(db)) == []


def test_a_fresh_install_on_another_machine_targets_nothing_it_lacks(tmp_path, monkeypatch):
    # Seven flow migrations (010, 016, 032, 043, 077, 090 ...) write the
    # author's target paths. On the machine they were written on those are
    # right; anywhere else every dispatch of those flows stops at
    # "targets project path ..., which does not exist". A fresh install keeps
    # a target only if the directory is there; without one the flow works in
    # Father, and the path is set in the flow editor.
    monkeypatch.setattr(migrate, "_dir_exists", lambda path: False)
    db = tmp_path / "elsewhere.db"
    _run_init_db(db, monkeypatch)
    assert _q(db, "SELECT COUNT(*) FROM bridge_flows")[0][0] > 20
    assert _targets(db) == {}


def test_an_existing_database_keeps_every_target_path(fresh_db, tmp_path, monkeypatch):
    # Not fresh: even a path that is missing right now (an unmounted disk, a
    # repository being moved) is the installation's own and stays.
    target = tmp_path / "existing.db"
    src, dst = sqlite3.connect(fresh_db), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
    dst.execute("UPDATE bridge_flows SET target_project_path = '/mnt/unmounted/project' WHERE flow_key = 'strict_review'")
    dst.commit()
    dst.close()
    before = _targets(target)
    monkeypatch.setattr(migrate, "_dir_exists", lambda path: False)
    _run_init_db(target, monkeypatch)
    assert _targets(target) == before and before["strict_review"] == "/mnt/unmounted/project"
