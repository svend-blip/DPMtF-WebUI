"""Stop tmux must reach a flow's remote roles.

The local query killed a session NAMED like the remote role -- which does
not exist locally, printed "Already dead", and left the worker's daemon and
execution sessions running. Stop looked successful and stopped half the flow.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "stop_tmuxflow", ROOT / "scripts" / "bridgeV002" / "stop_tmuxflow.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


def _db(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT,"
        " to_role TEXT, sort_order INTEGER, is_active INTEGER);"
        "CREATE TABLE bridge_roles (role_key TEXT, tmux_session TEXT,"
        " is_active INTEGER, execution_target TEXT);")
    conn.executemany("INSERT INTO bridge_flow_steps VALUES (?,?,?,?,1)", [
        ("f", "human", "impleR", 0), ("f", "impleR", "reviewL", 1)])
    conn.executemany("INSERT INTO bridge_roles VALUES (?,?,1,?)", [
        ("human", "human", None), ("impleR", "impleR", "worker9"),
        ("reviewL", "reviewL", "")])
    conn.commit(); conn.close()
    return str(db)


def test_remote_roles_are_not_killed_as_local_sessions(tmp_path):
    sessions = st.get_flow_tmux_sessions(_db(tmp_path), "f")
    assert "impleR" not in sessions
    assert sessions == {"human", "reviewL"}


def test_remote_roles_are_listed_for_the_ssh_kill(tmp_path):
    assert st.get_remote_roles(_db(tmp_path), "f") == [("impleR", "worker9")]
