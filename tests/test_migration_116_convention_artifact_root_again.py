"""Migration 116 puts back what init_db.py had undone of migration 084.

084 moved the path root of five convention templates from {flow_key} to
{artifact_root}. init_db.py then rewrote three of them on every run (fixed
2026-09-20, see test_init_db_keeps_convention_templates.py). 084 is recorded
as applied and does not run again, so the live rows need a new migration.
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIG = PROJECT_ROOT / "scripts" / "db" / "116_convention_artifact_root_again.sql"
ROLLBACK = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "116_convention_artifact_root_again_rollback.sql"
FK, AR = "{bridge_dir}/{flow_key}/", "{bridge_dir}/{artifact_root}/"


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bridge_convention_rules (rule_key TEXT PRIMARY KEY, content_template TEXT)")
    conn.executemany("INSERT INTO bridge_convention_rules VALUES (?, ?)", [
        ("verdict", f"in: {FK}reviews/x.md\nout: {FK}verdicts/x.md"),
        ("technical_review", f"in: {FK}results/x.md"),
        ("human_delivery", f"in: {FK}verdicts/x.md"),
        ("callback", f"already right: {AR}results/x.md"),
        # FENCE (Run 015 TG3): here {flow_key} is a --flow argument, not a path.
        ("json_output", "python3 bridge_broker.py enqueue --flow {flow_key} --action signal-send"),
        ("handoff", "no path and no command"),
    ])
    conn.execute("CREATE TABLE schema_migrations (filename TEXT PRIMARY KEY)")
    return conn


def _all(conn):
    return dict(conn.execute("SELECT rule_key, content_template FROM bridge_convention_rules"))


def test_no_template_keeps_the_flow_key_as_a_path_root():
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    rows = _all(conn)
    assert not any(FK in t for t in rows.values())
    assert rows["verdict"].count(AR) == 2 and rows["technical_review"].count(AR) == 1
    assert rows["callback"] == f"already right: {AR}results/x.md"


def test_the_flow_argument_is_not_a_path_and_is_left_alone():
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert _all(conn)["json_output"] == "python3 bridge_broker.py enqueue --flow {flow_key} --action signal-send"


def test_it_is_a_no_op_on_a_database_that_is_already_right():
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    once = _all(conn)
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert _all(conn) == once


def test_the_rollback_only_forgets_the_migration():
    # The rows are not put back to the wrong root: a rollback that restored a
    # defect would be a second defect.
    conn = _db()
    conn.executescript(MIG.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_migrations VALUES ('116_convention_artifact_root_again.sql')")
    after = _all(conn)
    conn.executescript(ROLLBACK.read_text(encoding="utf-8"))
    assert _all(conn) == after
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0
