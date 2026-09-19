"""Migration 115: a per-role context budget (bridge_roles.context_budget).

A model's context window says what the model CAN hold; on a 1,000,000-token
window that bounds nothing a run will ever reach, and every turn resends the
whole history. The budget is what the role MAY use. NULL means the window.
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIG = PROJECT_ROOT / "scripts" / "db" / "115_role_context_budget.sql"
ROLLBACK = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "115_role_context_budget_rollback.sql"
SLOTS = ("lbl_bridge_role_context_budget", "lbl_bridge_role_context_budget_help")
LOCALES = {"en-US", "da-DK", "de-DE", "es-ES"}


def _db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE bridge_roles (role_key TEXT PRIMARY KEY, max_turns INTEGER);
        INSERT INTO bridge_roles (role_key) VALUES ('r1');
        CREATE TABLE ui_text_slots (slot_key TEXT PRIMARY KEY, description TEXT);
        CREATE TABLE ui_text_slot_labels (slot_key TEXT, label_key TEXT, PRIMARY KEY (slot_key, label_key));
        CREATE TABLE ui_labels (label_id TEXT PRIMARY KEY, label_key TEXT, label_domain TEXT,
                                default_text TEXT, description TEXT, is_active INTEGER);
        CREATE TABLE ui_label_translations (label_id TEXT, locale TEXT, translated_text TEXT,
                                            is_active INTEGER, PRIMARY KEY (label_id, locale));
        CREATE TABLE schema_migrations (filename TEXT PRIMARY KEY);
    """)
    return conn


def _columns(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(bridge_roles)")}


def test_the_column_is_added_and_empty_for_existing_roles():
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert "context_budget" in _columns(conn)
    # No value is invented for anyone: a budget is an operating decision.
    assert conn.execute("SELECT context_budget FROM bridge_roles WHERE role_key='r1'").fetchone()[0] is None


def test_both_labels_exist_in_the_four_mandatory_locales():
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    for slot in SLOTS:
        label_id = conn.execute(
            "SELECT l.label_id FROM ui_text_slots s JOIN ui_text_slot_labels sl ON sl.slot_key = s.slot_key "
            "JOIN ui_labels l ON l.label_key = sl.label_key WHERE s.slot_key = ?", (slot,)).fetchone()
        assert label_id, f"{slot}: the four-layer chain is broken"
        locales = {r[0] for r in conn.execute(
            "SELECT locale FROM ui_label_translations WHERE label_id = ? AND translated_text != ''", label_id)}
        assert locales == LOCALES, (slot, locales)


def test_the_rollback_leaves_nothing_behind():
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    conn.executescript(ROLLBACK.read_text(encoding="utf-8"))
    assert "context_budget" not in _columns(conn)
    for table in ("ui_text_slots", "ui_text_slot_labels", "ui_labels", "ui_label_translations"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


def test_the_label_ids_are_not_taken_by_an_earlier_migration():
    mine = set()
    for line in MIG.read_text(encoding="utf-8").splitlines():
        for token in line.replace("'", " ").replace(",", " ").split():
            if token.startswith("LBL-"):
                mine.add(token)
    assert mine, "the migration declares no label ids"
    for other in sorted((PROJECT_ROOT / "scripts" / "db").glob("*.sql")):
        if other == MIG:
            continue
        text = other.read_text(encoding="utf-8")
        for label_id in mine:
            assert label_id not in text, f"{label_id} is also used by {other.name}"
