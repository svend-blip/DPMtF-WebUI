"""Activation-invariant tests for codex_context_release (Spec #13, Run 029).

Run 029 D2 deliverable. Pins the activation invariants GOAL.md §1 D2
calls out, scratch-proven under ENV-SCOPED work_unit, never against
the live chain.

T-A (work_unit full path): under work_unit + a codex role, run_release
   runs the full verified-stop + relaunch + re-anchor path; the anchor
   row is OVERWRITTEN with the injected _child_pid (record()'s
   INSERT OR REPLACE same-PK semantics).

T-B (off -> byte-identical no-op, PINNED): under "off" + a codex
   role, the orchestrator MUST NOT call stop_anchor, relaunch_in_session,
   or re_anchor AT ALL — the injected seams record ZERO invocations.
   NODE ID MUST contain "off_path" so `-k "off_path"` selects it and
   only it (GOAL.md TG3).

T-C (anchor OVERWRITTEN, never released — re-asserts the run-018
   hazard pin under work_unit): when BOTH the tmux_session and
   harness_process rows share a resource_id, re_anchor's record()
   must OVERWRITE only the harness_process row in place — the
   tmux_session row MUST STAY (release() deletes by
   (flow_key, resource_id) ACROSS resource types).

Reference: /home/svend/flows/preferred_cloud_harness/runs/029/GOAL.md
   (§1 D2, §4 TG2/TG3).
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

# Ensure the harness-allocator package is locatable. The seam calls
# (harness.build_launch_command, harness.resolve_harness,
# harness.get_codex_fresh_context_policy) delegate to it via
# config.get_project_path('harness-allocator'). If HARNESS_ALLOCATOR_PATH
# is already set (CI / pre-existing shell) we honor it; otherwise the
# project's config decides.
os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

import config  # noqa: E402
import bridge_lib  # noqa: E402
import codex_context_release as ccr  # noqa: E402
import runtime_owner  # noqa: E402


# ---------------------------------------------------------------------------
# Isolated DB fixture — minimal compatible bridge_roles + bridge_flows +
# bridge_flow_steps + the runtime_owner-owned flow_runtime_resources table.
# runtime_owner.record() (called by tests) lazily creates the
# flow_runtime_resources table via _TABLE_DDL, so we don't pre-create it
# here.
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_db(tmp_path) -> str:
    db_path = str(tmp_path / "activation_test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE bridge_roles (
            role_key TEXT PRIMARY KEY,
            tmux_session TEXT NOT NULL,
            setup_script TEXT,
            teardown_script TEXT,
            deliver_error_msg TEXT,
            is_active INTEGER DEFAULT 1,
            default_harness_source TEXT,
            default_harness_profile TEXT
        );
        CREATE TABLE bridge_flows (
            flow_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            step_order TEXT,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE bridge_flow_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_key TEXT,
            step_key TEXT,
            from_role TEXT,
            to_role TEXT
        );
    """)
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name) VALUES (?, ?)",
        ("preferred_cloud_harness", "Preferred Cloud Harness (test)"),
    )
    conn.commit()
    conn.close()
    return db_path


# The role used across all three tests: a codex role named
# "imple-codex-minimaxM3" with a tmux_session that matches the role_key.
# This mirrors the live chain's role naming convention.
CODEX_ROLE_KEY = "imple-codex-minimaxM3"
CODEX_SESSION = "imple-codex-minimaxM3"
CODEX_FLOW = "preferred_cloud_harness"


@pytest.fixture
def seeded_codex_role(isolated_db: str) -> str:
    """Insert a codex role row into bridge_roles; return db_path."""
    conn = sqlite3.connect(isolated_db)
    conn.execute(
        "INSERT INTO bridge_roles "
        "(role_key, tmux_session, default_harness_source, is_active) "
        "VALUES (?, ?, ?, 1)",
        (CODEX_ROLE_KEY, CODEX_SESSION, "codex"),
    )
    conn.commit()
    conn.close()
    return isolated_db


# ---------------------------------------------------------------------------
# Seam recorders — every injected seam appends a tuple. T-B's no-op
# assertion checks the recorder is empty.
# ---------------------------------------------------------------------------
class _SeamRecorder:
    """Records every injected-seam invocation as an ordered tuple."""

    def __init__(self, kill_result: bool = True, new_child_pid: int = 77777):
        self.calls: list[tuple] = []
        self._kill_result = kill_result
        self._new_child_pid = new_child_pid

    def kill(self, pid):
        self.calls.append(("kill", pid))
        return self._kill_result

    def build_launch(self, harness_key, role_config):
        self.calls.append(("build_launch", harness_key))
        return "codex --fake-launch"

    def send_keys(self, session, cmd):
        self.calls.append(("send_keys", session, cmd))
        return (True, "launched")

    def child_pid(self, session):
        self.calls.append(("child_pid", session))
        return self._new_child_pid


# ---------------------------------------------------------------------------
# Helper — fake the tmux has-session subprocess.run call that
# relaunch_in_session makes BEFORE reaching the injected _send_keys
# seam. The orchestrator's has-session check is not injectable via the
# _send_keys seam; it always goes through subprocess.run. Mock it here.
# ---------------------------------------------------------------------------
class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_subprocess_run(args, *args_list, **kwargs):
    """Return rc=0 for tmux has-session (so relaunch reaches _send_keys)."""
    if isinstance(args, (list, tuple)) and len(args) >= 2 and args[0] == "tmux" and args[1] == "has-session":
        return _FakeCompleted(returncode=0)
    # Fall back to the real subprocess.run for anything else (the
    # _send_keys / _build_launch / _child_pid injections handle the
    # real subprocess work the orchestrator would otherwise do).
    import subprocess as _sp
    return _sp.run(args, *args_list, **kwargs)


# ---------------------------------------------------------------------------
# T-A: work_unit full path
# ---------------------------------------------------------------------------
def test_work_unit_runs_full_verified_path(monkeypatch, seeded_codex_role: str):
    """Under work_unit + codex role, run_release runs the full path:
    stop_anchor → relaunch_in_session (build_launch, send_keys) →
    re_anchor (child_pid). Anchor OVERWRITTEN via record() with the
    new child pid.
    """
    db_path = seeded_codex_role

    # Seed a recorded harness_process anchor (the orchestrator will
    # _kill this pid and overwrite it with the new child pid).
    runtime_owner.record(
        CODEX_FLOW, "harness_process", CODEX_SESSION, pid=99999, db_path=db_path,
    )

    # Env-scope the policy to work_unit.
    monkeypatch.setenv("CODEX_FRESH_CONTEXT_POLICY", "work_unit")

    # Mock ccr.subprocess.run so the orchestrator's tmux has-session
    # check returns rc=0 (the has-session check happens BEFORE the
    # injected _send_keys seam is reached).
    monkeypatch.setattr(ccr.subprocess, "run", _fake_subprocess_run)

    recorder = _SeamRecorder(kill_result=True, new_child_pid=77777)

    rc = ccr.run_release(
        CODEX_FLOW, CODEX_ROLE_KEY, db_path=db_path,
        _kill=recorder.kill,
        _send_keys=recorder.send_keys,
        _build_launch=recorder.build_launch,
        _child_pid=recorder.child_pid,
    )

    assert rc == 0
    # All four seams called, in this exact order.
    assert [c[0] for c in recorder.calls] == [
        "kill", "build_launch", "send_keys", "child_pid",
    ]
    assert recorder.calls[0][1] == 99999  # _kill on the recorded anchor pid
    assert recorder.calls[1][1] == "codex"  # _build_launch for harness "codex"
    assert recorder.calls[2][1] == CODEX_SESSION  # _send_keys to the session
    assert recorder.calls[3][1] == CODEX_SESSION  # _child_pid for the session

    # Anchor row OVERWRITTEN with the new child pid (record() = INSERT OR REPLACE).
    rows = runtime_owner.list_for_flow(
        CODEX_FLOW, resource_type="harness_process", db_path=db_path,
    )
    assert len(rows) == 1
    assert rows[0]["resource_id"] == CODEX_SESSION
    assert rows[0]["pid"] == 77777


# ---------------------------------------------------------------------------
# T-B: off -> byte-identical no-op, PINNED
#
# NODE ID MUST contain "off_path" so `-k "off_path"` selects it and
# only it (GOAL.md TG3). DO NOT rename without the substring.
# ---------------------------------------------------------------------------
def test_off_path_is_byte_identical_noop(monkeypatch, seeded_codex_role: str):
    """Under 'off' policy + codex role, run_release MUST NOT call
    stop_anchor / relaunch_in_session / re_anchor at all — the injected
    seams record ZERO invocations. Pins the run-018 "chain unaffected at
    off" guarantee.
    """
    db_path = seeded_codex_role

    # Env-scope the policy to 'off'. (Default in production is also 'off',
    # but explicit env keeps the test independent of the live ini.)
    monkeypatch.setenv("CODEX_FRESH_CONTEXT_POLICY", "off")

    recorder = _SeamRecorder()

    rc = ccr.run_release(
        CODEX_FLOW, CODEX_ROLE_KEY, db_path=db_path,
        _kill=recorder.kill,
        _send_keys=recorder.send_keys,
        _build_launch=recorder.build_launch,
        _child_pid=recorder.child_pid,
    )

    assert rc == 0
    # Byte-identical no-op: NONE of the seams were invoked.
    assert recorder.calls == []


# ---------------------------------------------------------------------------
# T-C: anchor OVERWRITTEN, never released
#
# Re-asserts the run-018 hazard pin under work_unit: release() would
# silently drop the tmux_session ownership row that SHARES the resource_id
# with the harness_process anchor. record()'s INSERT OR REPLACE same-PK
# MUST overwrite only the harness_process row in place.
# ---------------------------------------------------------------------------
def test_work_unit_anchor_overwritten_not_released(monkeypatch, seeded_codex_role: str):
    """Under work_unit, with BOTH the tmux_session and harness_process
    rows pre-seeded (sharing resource_id = the session name), after
    run_release:
      (a) the harness_process row STILL EXISTS, OVERWRITTEN with the
          new child pid (record() = INSERT OR REPLACE on the same PK);
      (b) the tmux_session row STILL EXISTS with its original pid
          (record() of harness_process did NOT touch it).
    """
    db_path = seeded_codex_role

    # Seed BOTH rows that share resource_id.
    runtime_owner.record(
        CODEX_FLOW, "tmux_session", CODEX_SESSION, pid=11111, db_path=db_path,
    )
    runtime_owner.record(
        CODEX_FLOW, "harness_process", CODEX_SESSION, pid=22222, db_path=db_path,
    )

    monkeypatch.setenv("CODEX_FRESH_CONTEXT_POLICY", "work_unit")

    # Mock ccr.subprocess.run so the orchestrator's tmux has-session
    # check returns rc=0 (the has-session check happens BEFORE the
    # injected _send_keys seam is reached).
    monkeypatch.setattr(ccr.subprocess, "run", _fake_subprocess_run)

    recorder = _SeamRecorder(kill_result=True, new_child_pid=33333)

    rc = ccr.run_release(
        CODEX_FLOW, CODEX_ROLE_KEY, db_path=db_path,
        _kill=recorder.kill,
        _send_keys=recorder.send_keys,
        _build_launch=recorder.build_launch,
        _child_pid=recorder.child_pid,
    )

    assert rc == 0

    # (a) harness_process row STILL EXISTS, OVERWRITTEN with new pid 33333.
    hp_rows = runtime_owner.list_for_flow(
        CODEX_FLOW, resource_type="harness_process", db_path=db_path,
    )
    assert len(hp_rows) == 1
    assert hp_rows[0]["resource_id"] == CODEX_SESSION
    assert hp_rows[0]["pid"] == 33333  # the NEW pid, not the old 22222

    # (b) tmux_session row STILL EXISTS with its original pid (NOT
    # silently dropped by a misdirected release()).
    tm_rows = runtime_owner.list_for_flow(
        CODEX_FLOW, resource_type="tmux_session", db_path=db_path,
    )
    assert len(tm_rows) == 1
    assert tm_rows[0]["resource_id"] == CODEX_SESSION
    assert tm_rows[0]["pid"] == 11111  # UNCHANGED
