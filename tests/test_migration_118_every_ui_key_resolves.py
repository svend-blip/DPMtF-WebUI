"""Migration 118: every key the frontend asks for resolves.

That they do resolve on a fresh install, in the four mandatory locales, is
measured in test_fresh_install.py against the keys scanned from the code.
Here: what the migration does to a database that is not fresh — the three
statements one by one, on a small database with the real column layout.
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NAME = "118_every_ui_key_resolves.sql"
MIG = PROJECT_ROOT / "scripts" / "db" / NAME
ROLLBACK = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "118_every_ui_key_resolves_rollback.sql"
LOCALES = ("en-US", "da-DK", "de-DE", "es-ES")


def _db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE ui_labels (id INTEGER PRIMARY KEY AUTOINCREMENT, label_id TEXT UNIQUE NOT NULL,
            label_key TEXT UNIQUE NOT NULL, label_domain TEXT NOT NULL, default_text TEXT NOT NULL,
            description TEXT, is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE ui_label_translations (id INTEGER PRIMARY KEY AUTOINCREMENT, label_id TEXT NOT NULL,
            locale TEXT NOT NULL, translated_text TEXT NOT NULL, is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(label_id, locale));
        CREATE TABLE ui_text_slots (id INTEGER PRIMARY KEY AUTOINCREMENT, slot_key TEXT UNIQUE NOT NULL,
            description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE ui_text_slot_labels (id INTEGER PRIMARY KEY AUTOINCREMENT, slot_key TEXT NOT NULL,
            label_key TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(slot_key, label_key));
        CREATE TABLE schema_migrations (filename TEXT PRIMARY KEY);
    """)
    labels = [
        # in a domain nothing fetches, with slot and binding
        ("LBL-1000212", "lbl_btn_assign_handoff_id", "template_manager", "Assign Handoff ID", 1),
        # template-manager label the main page does not use: stays where it is
        ("LBL-1000100", "lbl_target_session", "template_manager", "Target Session", 1),
        # main label no slot reaches
        ("LBL-1000330", "system_setup_run_paths", "main", "Run paths", 1),
        # main label reached through a slot of another name: already shown
        ("LBL-1000050", "lbl_btn_add_step", "main", "Add Step", 1),
        # retired duplicate (migration 038): must not get a slot back
        ("LBL-1000257", "lbl_bridge_step_add", "main", "Add Step", 0),
    ]
    conn.executemany("INSERT INTO ui_labels (label_id, label_key, label_domain, default_text, is_active) "
                     "VALUES (?, ?, ?, ?, ?)", labels)
    conn.executemany("INSERT INTO ui_text_slots (slot_key) VALUES (?)",
                     [("lbl_btn_assign_handoff_id",), ("lbl_bridge_step_add",), ("pg_job_queue",)])
    conn.executemany("INSERT INTO ui_text_slot_labels (slot_key, label_key) VALUES (?, ?)", [
        ("lbl_btn_assign_handoff_id", "lbl_btn_assign_handoff_id"),
        ("lbl_bridge_step_add", "lbl_btn_add_step"),
        # a slot bound to a label that does not exist yet
        ("pg_job_queue", "pg_job_queue"),
    ])
    conn.commit()
    return conn


def _resolve(conn, locale):
    return dict(conn.execute("""
        SELECT s.slot_key, t.translated_text FROM ui_text_slots s
        JOIN ui_text_slot_labels sl ON sl.slot_key = s.slot_key
        JOIN ui_labels l ON l.label_key = sl.label_key AND l.label_domain = 'main' AND l.is_active = 1
        JOIN ui_label_translations t ON t.label_id = l.label_id AND t.locale = ?""", (locale,)))


def _apply(conn):
    conn.executescript(MIG.read_text(encoding="utf-8"))
    conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (?)", (NAME,))
    conn.commit()


def _snapshot(conn):
    return {t: sorted(map(repr, conn.execute(f"SELECT * FROM {t}")))
            for t in ("ui_labels", "ui_label_translations", "ui_text_slots", "ui_text_slot_labels")}


def test_the_template_manager_labels_the_main_page_uses_move_to_main():
    conn = _db()
    _apply(conn)
    domains = dict(conn.execute("SELECT label_key, label_domain FROM ui_labels"))
    assert domains["lbl_btn_assign_handoff_id"] == "main"
    assert domains["lbl_target_session"] == "template_manager"


def test_a_key_without_a_label_gets_one_in_the_four_locales():
    conn = _db()
    _apply(conn)
    for locale, text in zip(LOCALES, ("📋 Job Queue", "📋 Jobkø", "📋 Job-Warteschlange", "📋 Cola de trabajos")):
        assert _resolve(conn, locale)["pg_job_queue"] == text
    new = conn.execute("SELECT COUNT(*) FROM ui_labels WHERE label_id BETWEEN 'LBL-1000546' AND 'LBL-1000604'").fetchone()[0]
    texts = conn.execute("SELECT COUNT(*) FROM ui_label_translations "
                         "WHERE label_id BETWEEN 'LBL-1000546' AND 'LBL-1000604' AND translated_text != ''").fetchone()[0]
    assert new == 59 and texts == 59 * 4


def test_a_placeholder_survives_translation():
    conn = _db()
    _apply(conn)
    rows = conn.execute("SELECT t.translated_text FROM ui_label_translations t JOIN ui_labels l "
                        "ON l.label_id = t.label_id WHERE l.label_key = 'lbl_confirm_stop_servers'").fetchall()
    assert len(rows) == 4 and all("'{flowKey}'" in r[0] for r in rows)
    # used as the default project NAME, not only as a hint: the same everywhere
    names = {r[0] for r in conn.execute("SELECT t.translated_text FROM ui_label_translations t JOIN ui_labels l "
                                        "ON l.label_id = t.label_id WHERE l.label_key = 'lbl_compiler_project_placeholder'")}
    assert names == {"DPMtF-WebUI"}


def test_a_main_label_no_slot_reaches_gets_a_slot_of_its_own_name():
    conn = _db()
    _apply(conn)
    assert conn.execute("SELECT label_key FROM ui_text_slot_labels WHERE slot_key = 'system_setup_run_paths'"
                        ).fetchall() == [("system_setup_run_paths",)]


def test_a_label_that_is_already_shown_or_retired_gets_no_second_slot():
    conn = _db()
    _apply(conn)
    # reached through lbl_bridge_step_add: no slot of its own
    assert conn.execute("SELECT COUNT(*) FROM ui_text_slots WHERE slot_key = 'lbl_btn_add_step'").fetchone()[0] == 0
    # retired by 038: its slot stays bound to the kept label, and only to it
    assert conn.execute("SELECT label_key FROM ui_text_slot_labels WHERE slot_key = 'lbl_bridge_step_add'"
                        ).fetchall() == [("lbl_btn_add_step",)]
    assert conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM ui_text_slot_labels GROUP BY slot_key "
                        "HAVING COUNT(*) > 1)").fetchone()[0] == 0


def test_an_existing_label_is_not_overwritten():
    conn = _db()
    conn.execute("INSERT INTO ui_labels (label_id, label_key, label_domain, default_text) "
                 "VALUES ('LBL-9000001', 'lbl_compiler_goal', 'main', 'Edited by hand')")
    _apply(conn)
    assert conn.execute("SELECT label_id, default_text FROM ui_labels WHERE label_key = 'lbl_compiler_goal'"
                        ).fetchall() == [("LBL-9000001", "Edited by hand")]


def test_it_does_nothing_the_second_time():
    conn = _db()
    _apply(conn)
    once = _snapshot(conn)
    _apply(conn)
    assert _snapshot(conn) == once


def test_the_rollback_removes_the_labels_and_returns_the_domain():
    conn = _db()
    _apply(conn)
    conn.executescript(ROLLBACK.read_text(encoding="utf-8"))
    assert conn.execute("SELECT COUNT(*) FROM ui_labels WHERE label_id >= 'LBL-1000546' "
                        "AND label_id <= 'LBL-1000604'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ui_label_translations WHERE label_id >= 'LBL-1000546' "
                        "AND label_id <= 'LBL-1000604'").fetchone()[0] == 0
    assert conn.execute("SELECT label_domain FROM ui_labels WHERE label_key = 'lbl_btn_assign_handoff_id'"
                        ).fetchone()[0] == "template_manager"
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0
