"""Migration 119 installs the core flows and leaves an installation's own alone.

That a fresh install ends up with the flows, with every role its steps name
and with no home directory in them is measured in test_fresh_install.py.
Here: the production case — the rows exist already, with their own target
paths, models and counters — and the migration file read as text.
"""
import contextlib
import io
import re
import runpy
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import config  # noqa: E402

NAME = "119_core_flows.sql"
MIG = PROJECT_ROOT / "scripts" / "db" / NAME
ROLLBACK = PROJECT_ROOT / "scripts" / "db" / "rollbacks" / "119_core_flows_rollback.sql"
FLOWS = ("strict_review", "cloud_llm", "cloud_pay", "1010-01-PLOOP", "1010-02-ELOOP")
TABLES = ("bridge_flows", "bridge_roles", "bridge_flow_steps", "bridge_id_counters")


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("fresh119") / "fresh.db"
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(config, "get_db_path", lambda: str(db))
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(PROJECT_ROOT / "scripts" / "init_db.py"), run_name="__main__")
    finally:
        mp.undo()
    return db


@pytest.fixture()
def conn(fresh_db, tmp_path):
    src, dst = sqlite3.connect(fresh_db), sqlite3.connect(tmp_path / "copy.db")
    try:
        src.backup(dst)
    finally:
        src.close()
    yield dst
    dst.close()


def _rows(conn):
    out = {}
    for t in TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})") if r[1] not in ("id", "created_at", "updated_at")]
        out[t] = sorted(map(repr, conn.execute(f"SELECT {', '.join(cols)} FROM {t}")))
    return out


def test_the_file_names_nobody(tmp_path):
    text = MIG.read_text(encoding="utf-8")
    statements = "\n".join(line for line in text.splitlines() if not line.startswith("--"))
    for needle in ("/home/", "/Users/", "C:\\", "svend"):
        assert needle.lower() not in statements.lower(), needle
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", statements), "an address"
    # every statement can be repeated
    assert set(re.findall(r"^(INSERT[A-Z ]*) INTO", statements, re.M)) == {"INSERT OR IGNORE"}
    assert not re.search(r"^\s*(UPDATE|DELETE|DROP|ALTER)\b", statements, re.M)


def test_an_installations_own_values_survive(conn):
    # the production shape: a target path, another model, a counter that has run
    conn.execute("UPDATE bridge_flows SET target_project_path = '/srv/work/trade-ui', name = 'Ours' "
                 "WHERE flow_key = 'cloud_pay'")
    conn.execute("UPDATE bridge_roles SET default_model_alias = 'our-model', is_active = 0 WHERE role_key = 'imple01'")
    conn.execute("UPDATE bridge_flow_steps SET auto_chain_to_next = 0 "
                 "WHERE flow_key = 'strict_review' AND step_key = 'archi01-imple01'")
    conn.execute("UPDATE bridge_id_counters SET next_id = 327 WHERE flow_key = 'strict_review'")
    conn.commit()
    before = _rows(conn)
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert _rows(conn) == before
    assert conn.execute("SELECT next_id FROM bridge_id_counters WHERE flow_key = 'strict_review'").fetchone()[0] == 327


def test_a_database_without_them_gets_them_whole(conn):
    marks = ",".join("?" * len(FLOWS))
    want = _rows(conn)
    roles = [r[0] for r in conn.execute(
        f"SELECT from_role FROM bridge_flow_steps WHERE flow_key IN ({marks}) "
        f"UNION SELECT to_role FROM bridge_flow_steps WHERE flow_key IN ({marks})", FLOWS + FLOWS)]
    roles.append("1010-escalation-supervisor")
    conn.execute(f"DELETE FROM bridge_flow_steps WHERE flow_key IN ({marks})", FLOWS)
    conn.execute(f"DELETE FROM bridge_id_counters WHERE flow_key IN ({marks})", FLOWS)
    conn.execute(f"DELETE FROM bridge_flows WHERE flow_key IN ({marks})", FLOWS)
    conn.execute(f"DELETE FROM bridge_roles WHERE role_key IN ({','.join('?' * len(roles))})", roles)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM bridge_roles WHERE role_key = 'human'").fetchone()[0] == 0
    conn.executescript(MIG.read_text(encoding="utf-8"))
    assert _rows(conn) == want


def test_what_it_installs_refers_only_to_what_exists(conn):
    conn.executescript(MIG.read_text(encoding="utf-8"))
    marks = ",".join("?" * len(FLOWS))
    dangling = conn.execute(f"""
        SELECT flow_key, step_key FROM bridge_flow_steps WHERE flow_key IN ({marks}) AND (
              from_role NOT IN (SELECT role_key FROM bridge_roles)
           OR to_role NOT IN (SELECT role_key FROM bridge_roles)
           OR (COALESCE(rule_key, '') != '' AND rule_key NOT IN (SELECT rule_key FROM bridge_convention_rules))
           OR (COALESCE(pre_dispatch_script, '') != '' AND pre_dispatch_script NOT IN (SELECT script_key FROM bridge_scripts))
           OR (COALESCE(post_dispatch_script, '') != '' AND post_dispatch_script NOT IN (SELECT script_key FROM bridge_scripts)))
        """, FLOWS).fetchall()
    assert dangling == []
    # a governance file a role or step names is in the repository
    gov = PROJECT_ROOT / config.get_governance_dir()
    named = {r[0] for r in conn.execute(
        f"SELECT governance_file FROM bridge_flow_steps WHERE flow_key IN ({marks}) AND COALESCE(governance_file,'') != ''",
        FLOWS)}
    assert named and all(any(gov.rglob(n)) for n in named), sorted(n for n in named if not any(gov.rglob(n)))


def test_the_rollback_only_forgets_the_migration(conn):
    before = _rows(conn)
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE filename = ?", (NAME,)).fetchone()[0] == 1
    conn.executescript(ROLLBACK.read_text(encoding="utf-8"))
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE filename = ?", (NAME,)).fetchone()[0] == 0
    assert _rows(conn) == before
