"""Migration 120 renames the one card key that was named after a person."""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIG = PROJECT_ROOT / "scripts" / "db" / "120_card_key_home_dir_disk.sql"


def _db(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE v2_panel_requirements (requirement_id TEXT UNIQUE NOT NULL, "
                 "target_project_key TEXT NOT NULL, panel_key TEXT NOT NULL, card_key TEXT NOT NULL, "
                 "card_title TEXT NOT NULL, updated_at TIMESTAMP)")
    conn.executemany("INSERT INTO v2_panel_requirements (requirement_id, target_project_key, panel_key, "
                     "card_key, card_title) VALUES (?, ?, ?, ?, ?)", rows)
    return conn


def _keys(conn):
    return sorted(conn.execute("SELECT requirement_id, card_key, card_title FROM v2_panel_requirements"))


def test_the_key_is_renamed_and_nothing_else():
    conn = _db([("VPR-1000003", "ai_pc_resource_webui_v2", "system_resources", "home_svend_disk", "/home/someone"),
                ("VPR-1000004", "ai_pc_resource_webui_v2", "system_resources", "ai_data_disk", "/data")])
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert _keys(conn) == [("VPR-1000003", "home_dir_disk", "/home/someone"),
                           ("VPR-1000004", "ai_data_disk", "/data")]


def test_a_database_that_already_has_the_new_key_is_left_alone():
    # init_db.py seeded first (a fresh install), or 120 ran before
    rows = [("VPR-1000003", "ai_pc_resource_webui_v2", "system_resources", "home_dir_disk", "/home/someone")]
    conn = _db(rows)
    conn.executescript(MIG.read_text(encoding="utf-8"))
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert _keys(conn) == [("VPR-1000003", "home_dir_disk", "/home/someone")]


def test_it_does_not_rename_into_a_key_the_panel_already_has():
    conn = _db([("VPR-1000003", "ai_pc_resource_webui_v2", "system_resources", "home_svend_disk", "old"),
                ("VPR-9000001", "ai_pc_resource_webui_v2", "system_resources", "home_dir_disk", "made by hand")])
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert [k for _, k, _ in _keys(conn)] == ["home_svend_disk", "home_dir_disk"]


def test_the_file_names_no_path():
    statements = "\n".join(l for l in MIG.read_text(encoding="utf-8").splitlines() if not l.startswith("--"))
    assert "/home/" not in statements
