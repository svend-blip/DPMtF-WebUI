"""The flow viewer must show roles that run on another machine.

`attach -t flow-<key>` exists so one attach shows the whole chain. A role
executing elsewhere was simply absent from it, and absence reads exactly like
a role that never started — which is the one thing a monitoring view must not
be ambiguous about.

A linked window belongs to one tmux server. A remote role's does not, so it
gets an ssh window instead.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import attach_tmux  # noqa: E402


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT,"
        " to_role TEXT, sort_order INTEGER, is_active INTEGER);"
        "CREATE TABLE bridge_roles (role_key TEXT, tmux_session TEXT,"
        " is_active INTEGER, execution_target TEXT);")
    conn.executemany("INSERT INTO bridge_flow_steps VALUES (?,?,?,?,1)", [
        ("f", "human", "impleR", 0), ("f", "impleR", "reviewL", 1),
        ("f", "reviewL", "human", 2)])
    conn.executemany("INSERT INTO bridge_roles VALUES (?,?,1,?)", [
        ("human", "human", None), ("impleR", "impleR", "svend3060"),
        ("reviewL", "reviewL", None)])
    conn.commit(); conn.close()
    return str(path)


def test_a_remote_role_is_not_linked_locally(db):
    """Linking it would attach a window that does not exist on this server."""
    assert "impleR" not in attach_tmux.get_flow_tmux_sessions(db, "f")


def test_a_remote_role_is_listed_once_not_twice(db):
    """It is the to_role of one step and the from_role of the next, so a
    DISTINCT over the row does not deduplicate it — and two windows onto one
    worker is two chances to read a stale one as live."""
    assert attach_tmux.get_remote_roles(db, "f") == [("impleR", "svend3060")]


def test_local_roles_are_still_linked(db):
    assert "reviewL" in attach_tmux.get_flow_tmux_sessions(db, "f")


def test_windows_follow_the_chain_not_the_machine(db):
    """Reading the viewer left to right has to be reading the flow.

    Placing local roles first and remote ones after put the implementer to
    the right of the reviewer that judges its work.
    """
    order = [r["role_key"] for r in attach_tmux.get_flow_roles(db, "f")]
    assert order == ["human", "impleR", "reviewL"]


def test_a_role_that_only_ever_receives_is_last_not_absent(db, tmp_path):
    """A terminal role is never a from_role. Ordering on send alone drops it
    from the viewer entirely, which is how portfolio01_trade went unseen."""
    import sqlite3
    path = tmp_path / "t2.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT,"
        " to_role TEXT, sort_order INTEGER, is_active INTEGER);"
        "CREATE TABLE bridge_roles (role_key TEXT, tmux_session TEXT,"
        " is_active INTEGER, execution_target TEXT);")
    conn.executemany("INSERT INTO bridge_flow_steps VALUES (?,?,?,?,1)", [
        ("g", "a", "b", 0), ("g", "b", "last", 1)])
    conn.executemany("INSERT INTO bridge_roles VALUES (?,?,1,NULL)", [
        ("a", "a"), ("b", "b"), ("last", "last")])
    conn.commit(); conn.close()
    assert attach_tmux.get_flow_tmux_sessions(str(path), "g") == [
        "a", "b", "last"]


def test_the_follow_command_is_valid_shell():
    """It carries a tmux format string — braces and a hash — inside an ssh
    argument. Quoting it wrong ends the argument early and the window dies
    silently."""
    cmd = attach_tmux.remote_follow_command("svend3060")
    assert subprocess.run(["bash", "-n", "-c", cmd],
                          capture_output=True).returncode == 0


def test_it_mirrors_rather_than_attaches():
    """`tmux attach` re-picks a session only when the attach exits, and an
    attach does not exit. The window latched onto the daemon at startup and
    stayed there through a whole execution, showing an idle poller while the
    role worked one session away."""
    cmd = attach_tmux.remote_follow_command("svend3060")
    assert "capture-pane" in cmd
    assert "attach" not in cmd


def test_the_follow_command_falls_back_to_the_daemon():
    """A worker makes a fresh session per execution and drops it on cleanup.
    Attaching to a fixed name shows an empty pane most of the time and
    nothing during the work."""
    cmd = attach_tmux.remote_follow_command("svend3060")
    assert "dpmtf-" in cmd and "lightworker-daemon" in cmd
