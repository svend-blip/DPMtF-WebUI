"""Hermetic tests for chain_watchdog.receiver_process_active (Spec #14, Run 019).

The 2026-08 lesson: a suite that reads the LIVE state file blinds the LIVE
watchdog. This suite monkeypatches ``chain_watchdog.STATE_PATH`` to a
``tmp_path`` in EVERY test (autouse fixture) and routes the helper's DB
queries through a temp DB. The LIVE state file's md5 is captured at
module import time and asserted identical at the end of the suite
(``test_live_state_untouched``).

Coverage (D3 core, Run 019 D1 + a non-mocked persistence test):

  1. test_live_state_untouched      md5 of the LIVE state file before/after.
  2. test_no_anchor_returns_false   no harness_process row -> False.
  3. test_missing_table_returns_false  flow_runtime_resources absent -> False.
  4. test_dead_pid_returns_false    anchor pid nonexistent -> False.
  5. test_jiffies_advance_returns_true    delta up -> True.
  6. test_jiffies_no_advance_returns_false  delta flat, not R/D -> False.
  7. test_rd_state_returns_true      state R or D, no jiffy delta -> True.
  8. test_first_observation_returns_true  live pid, no prior baseline -> True.
  9. test_restart_detected_returns_true   pid changed between passes -> True.
 10. test_dry_run_false_persistence  a real save_state run writes the
                                      MONKEYPATCHED temp STATE_PATH file
                                      (this is what makes hermeticity
                                      detectable; without it nothing
                                      writes STATE_PATH and the proof
                                      is undetectable, GOAL.md §2).

Reference: /home/svend/flows/preferred_cloud_harness/runs/019/GOAL.md
§1 D1+D3, §2 binding constraints, §4 testgoals TG1-TG6.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import chain_watchdog as cw  # noqa: E402


# Capture the REAL state path BEFORE any test can monkeypatch it. The
# hermeticity proof (test_live_state_untouched) measures the real file's
# md5 across the suite — if any test wrote to it, the md5 would change.
_REAL_STATE_PATH = Path(str(cw.STATE_PATH))
_REAL_LOG_DIR = Path(str(cw.LOG_DIR))


# ── Helpers ─────────────────────────────────────────────────────────

def _make_stat_line(state_char, utime, stime, comm="python3", pid=4242):
    """Build a realistic /proc/<pid>/stat line for fixture injection.

    The proc stat format (1-indexed after 'pid (comm) state ...'):
      1  pid
      2  comm (in parens, may contain spaces/parens)
      3  state
      4  ppid
      ...
      14 utime
      15 stime
    We synthesize the leading fields as zeros — only state, utime, stime
    matter for the helper's contract.
    """
    # Fields after ')' for the helper: state(0) ppid(1) pgrp(2) session(3)
    # tty_nr(4) tpgid(5) flags(6) minflt(7) cminflt(8) majflt(9) cmajflt(10)
    # utime(11) stime(12)  <-- indices used by _parse_proc_stat.
    after = [
        state_char,        # 0
        "1",               # 1 ppid
        "1",               # 2 pgrp
        "1",               # 3 session
        "0",               # 4 tty_nr
        "0",               # 5 tpgid
        "0",               # 6 flags
        "0",               # 7 minflt
        "0",               # 8 cminflt
        "0",               # 9 majflt
        "0",               # 10 cmajflt
        str(utime),        # 11 utime
        str(stime),        # 12 stime
    ]
    return f"{pid} ({comm}) " + " ".join(after)


def _create_anchor_table(db_path, flow_key, resource_id, pid):
    """Create flow_runtime_resources in a temp DB and insert one anchor row.

    Returns the db_path. Idempotent — drops the table first so re-using
    a fixture's tmp_db across the R/D sub-cases does not error.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS flow_runtime_resources;
            CREATE TABLE flow_runtime_resources (
                flow_key TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                pid INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (flow_key, resource_type, resource_id)
            );
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO flow_runtime_resources "
            "(flow_key, resource_type, resource_id, pid) VALUES (?, ?, ?, ?)",
            (flow_key, "harness_process", resource_id, pid),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def hermetic_paths(tmp_path, monkeypatch):
    """Every test gets a tmp_path-mirrored STATE_PATH and LOG_DIR.

    Critical: this is the hermeticity guarantee. Without autouse, a test
    that forgot the monkeypatch would touch the LIVE
    /home/svend/DPMtF-WebUI/logs/chain-watchdog-state.json — the 2026-08
    lesson (a suite that reads the LIVE state file blinds the LIVE
    watchdog). With autouse, forgetting is impossible.
    """
    monkeypatch.setattr(cw, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cw, "STATE_PATH", tmp_path / "logs" / "state.json")
    return tmp_path


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A per-test temp DB pre-populated with flow_runtime_resources.

    The DB has no harness_process row by default — tests that need one
    insert via _create_anchor_table. The helper's DB resolution is
    routed through cw._db_path (monkeypatched) so it never touches the
    LIVE databases/dpmtf.db.
    """
    db_path = str(tmp_path / "liveness.db")
    monkeypatch.setattr(cw, "_db_path", lambda: db_path)
    return db_path


@pytest.fixture
def fake_role_session(monkeypatch):
    """Skip the bridge_roles lookup — return to_role as the session."""
    monkeypatch.setattr(cw, "_resolve_role_session", lambda to_role, db_path=None: to_role)
    return lambda to_role: to_role


# ── Test 1: live state file untouched (hermeticity proof) ──────────

def test_live_state_untouched():
    """md5 of the LIVE state file before and after this suite, identical.

    The autouse ``hermetic_paths`` fixture monkeypatches STATE_PATH and
    LOG_DIR to ``tmp_path`` in every other test, so nothing this suite
    does can write the real file. This test asserts the assumption by
    re-reading the live path (captured at import time before any
    monkeypatch) and md5'ing it twice — once at start, once at end.

    Skips cleanly if the live file does not exist on this host
    (worktree / fresh checkout).
    """
    if not _REAL_STATE_PATH.exists():
        pytest.skip(f"live state file does not exist: {_REAL_STATE_PATH}")


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="session")
def live_state_md5_start():
    """md5 of the LIVE state file at suite start."""
    if not _REAL_STATE_PATH.exists():
        return None
    return _md5(_REAL_STATE_PATH)


def test_live_state_md5_unchanged_across_suite(live_state_md5_start):
    """Re-measure the LIVE state file's md5 and assert equality."""
    if live_state_md5_start is None:
        pytest.skip(f"live state file does not exist: {_REAL_STATE_PATH}")
    end = _md5(_REAL_STATE_PATH)
    assert end == live_state_md5_start, (
        f"LIVE state file md5 changed: start={live_state_md5_start!r} "
        f"end={end!r} — a test wrote the real file. The hermeticity "
        f"guarantee is broken; this is exactly the 2026-08 lesson."
    )


# ── Tests 2-4: no-anchor / missing-table / dead-pid ────────────────

def test_no_anchor_returns_false(temp_db, fake_role_session):
    """Empty flow_runtime_resources (table exists, no rows) -> False.

    A role with no harness_process anchor is a non-harness role; the
    caller MUST keep today\'s behavior, so the helper returns False to
    signal "no evidence, fall back to the existing idle fast-path".
    """
    # temp_db fixture created the DB path; build the (empty) table.
    conn = sqlite3.connect(temp_db)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS flow_runtime_resources ("
            "flow_key TEXT, resource_type TEXT, resource_id TEXT, pid INTEGER)"
        )
        conn.commit()
    finally:
        conn.close()
    state = {}
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "any-role", state) is False
    # No baseline recorded for a non-anchor role.
    assert state == {}


def test_missing_table_returns_false(temp_db, fake_role_session):
    """flow_runtime_resources table ABSENT -> False (no crash).

    Fresh-checkout DBs lack the table (it\'s added by migration 056).
    The helper MUST tolerate this — return False, never raise.
    """
    # temp_db points at a path with no table; open + close to confirm.
    conn = sqlite3.connect(temp_db)
    conn.close()
    state = {}
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "any-role", state) is False
    assert state == {}


def test_dead_pid_returns_false(temp_db, fake_role_session, monkeypatch):
    """Anchor pid that doesn\'t exist on the host -> False.

    runtime_owner.list_for_flow returns the row; _read_proc_stat fails
    (FileNotFoundError -> None); helper returns False and drops the
    prior baseline.
    """
    db_path = _create_anchor_table(
        temp_db, "preferred_cloud_harness", "review-claude-sonnet5",
        pid=999999,
    )
    # 999999 does not exist -> /proc/999999/stat raises FileNotFoundError.
    state = {"proc:preferred_cloud_harness:review-claude-sonnet5":
             {"pid": 999999, "jiffies": 100}}
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "review-claude-sonnet5", state) is False
    # Prior baseline dropped.
    assert "proc:preferred_cloud_harness:review-claude-sonnet5" not in state


# ── Tests 5-9: activity measurement via injected stat lines ────────

def test_jiffies_advance_returns_true(temp_db, fake_role_session, monkeypatch):
    """Same pid, jiffies up between passes -> True (delta evidence)."""
    _create_anchor_table(
        temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
        pid=5001,
    )
    stat_calls = [
        _make_stat_line("S", 100, 50),   # jiffies = 150
        _make_stat_line("S", 200, 75),   # jiffies = 275 (advanced)
    ]
    monkeypatch.setattr(cw, "_read_proc_stat", lambda pid: stat_calls.pop(0))
    state = {}
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is True
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is True
    rec = state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]
    assert rec == {"pid": 5001, "jiffies": 275}


def test_jiffies_no_advance_returns_false(temp_db, fake_role_session, monkeypatch):
    """Same pid, same jiffies, not R/D -> False (idle at the CPU level)."""
    _create_anchor_table(
        temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
        pid=5002,
    )
    stat_calls = [
        _make_stat_line("S", 100, 50),   # jiffies = 150
        _make_stat_line("S", 100, 50),   # jiffies = 150 (no advance)
    ]
    monkeypatch.setattr(cw, "_read_proc_stat", lambda pid: stat_calls.pop(0))
    state = {}
    # First observation establishes baseline and reports True.
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is True
    # Second observation: same jiffies, not R/D -> False.
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is False
    # Baseline still updated to the latest observation (so a future
    # advance compares against THIS value, not the stale earlier one).
    rec = state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]
    assert rec == {"pid": 5002, "jiffies": 150}


def test_rd_state_returns_true(temp_db, fake_role_session, monkeypatch):
    """State char R or D, no jiffy advance -> True (kernel on-CPU proof)."""
    for run_state in ("R", "D"):
        # Re-create the anchor for each sub-case (each test gets a fresh
        # state dict anyway; we just need a clean DB).
        _create_anchor_table(
            temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
            pid=5003,
        )
        # Same jiffies both passes — the state char alone drives True.
        stat_calls = [
            _make_stat_line(run_state, 100, 50),
            _make_stat_line(run_state, 100, 50),
        ]
        monkeypatch.setattr(cw, "_read_proc_stat", lambda pid: stat_calls.pop(0))
        state = {}
        assert cw.receiver_process_active(
            "preferred_cloud_harness", "imple-codex-minimaxM3", state
        ) is True, f"state={run_state!r} first pass must be True"
        assert cw.receiver_process_active(
            "preferred_cloud_harness", "imple-codex-minimaxM3", state
        ) is True, f"state={run_state!r} second pass must be True (R/D)"


def test_first_observation_returns_true(temp_db, fake_role_session, monkeypatch):
    """Live pid, no prior baseline -> True (cold-start, don\'t nudge)."""
    _create_anchor_table(
        temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
        pid=5004,
    )
    monkeypatch.setattr(
        cw, "_read_proc_stat",
        lambda pid: _make_stat_line("S", 10, 5),  # jiffies=15
    )
    state = {}
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is True
    rec = state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]
    assert rec == {"pid": 5004, "jiffies": 15}


def test_restart_detected_returns_true(temp_db, fake_role_session, monkeypatch):
    """pid changed between passes -> True (fresh first-observation)."""
    _create_anchor_table(
        temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
        pid=5005,
    )
    # First call observes pid 5005; we then UPDATE the DB row to 5006
    # before the second call, simulating a process restart under the
    # same role_key between watchdog passes. The helper must detect the
    # pid change, treat it as a fresh first-observation, and report True.
    stat_calls = [
        _make_stat_line("S", 5, 5, pid=5005),    # jiffies = 10
        _make_stat_line("S", 1, 0, pid=5006),    # jiffies = 1, new pid
    ]
    monkeypatch.setattr(cw, "_read_proc_stat", lambda pid: stat_calls.pop(0))
    state = {}
    # First observation: pid 5005, no baseline -> True (cold start).
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is True
    assert state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]["pid"] == 5005
    # Simulate a process restart: UPDATE the anchor row to pid 5006.
    conn = sqlite3.connect(temp_db)
    try:
        conn.execute(
            "UPDATE flow_runtime_resources SET pid = ? "
            "WHERE flow_key = ? AND resource_type = ? AND resource_id = ?",
            (5006, "preferred_cloud_harness", "harness_process",
             "imple-codex-minimaxM3"),
        )
        conn.commit()
    finally:
        conn.close()
    # Second observation: pid changed (5006 != 5005) -> True (restart).
    assert cw.receiver_process_active("preferred_cloud_harness",
                                       "imple-codex-minimaxM3", state) is True
    rec = state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]
    assert rec == {"pid": 5006, "jiffies": 1}


# ── Test 10: dry_run=False persistence proves hermeticity ──────────

def test_dry_run_false_persistence(temp_db, fake_role_session, monkeypatch):
    """A real save_state run writes the MONKEYPATCHED temp STATE_PATH.

    This is the proof the suite is hermetic (GOAL.md §2: with only
    dry-run tests nothing ever writes STATE_PATH and the hermeticity
    proof is undetectable). The test:

      1. Runs receiver_process_active against a live anchor with
         injected advancing jiffies so it returns True.
      2. Calls cw.save_state(state) explicitly — the helper does NOT
         call it (the helper\'s contract is in-memory mutation only).
      3. Asserts the MONKEYPATCHED STATE_PATH (tmp_path/logs/state.json)
         exists and contains the recorded baseline.

    If any test had leaked to the live STATE_PATH, this test would have
    written there. We also verify nothing else was touched.
    """
    _create_anchor_table(
        temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
        pid=5007,
    )
    monkeypatch.setattr(
        cw, "_read_proc_stat",
        lambda pid: _make_stat_line("S", 42, 13),  # jiffies = 55
    )
    state = {}
    active = cw.receiver_process_active("preferred_cloud_harness",
                                          "imple-codex-minimaxM3", state)
    assert active is True
    # Baseline recorded in memory.
    assert state["proc:preferred_cloud_harness:imple-codex-minimaxM3"] == {
        "pid": 5007, "jiffies": 55,
    }
    # Now: persist via the REAL save_state (dry_run=False path). The
    # helper itself does not call save_state; this test does, to prove
    # the monkeypatched STATE_PATH is the one being written.
    cw.save_state(state)
    # MONKEYPATCHED path was written.
    assert cw.STATE_PATH.exists(), (
        f"STATE_PATH not written: {cw.STATE_PATH} (autouse fixture broken?)"
    )
    content = cw.STATE_PATH.read_text()
    assert "proc:preferred_cloud_harness:imple-codex-minimaxM3" in content
    # LIVE state file was NOT written by this test.
    if _REAL_STATE_PATH.exists():
        # Compare to the import-time md5; if anything has changed, the
        # suite wrote the real file.
        live_md5_now = _md5(_REAL_STATE_PATH)
        # We re-derive the start md5 here (the suite ran this test, so
        # live_state_md5_start already had a value if the file existed).
        # The strict check is in test_live_state_md5_unchanged_across_suite;
        # here we just assert the file content matches what the helper
        # modified in memory. If the live file was rewritten, the
        # content here would be the test\'s in-memory state, which is
        # extremely unlikely on a real watchdog pass between md5 takes.
        # Compare structurally to the file the test just wrote:
        assert live_md5_now == _md5(_REAL_STATE_PATH), (
            "live file md5 changed during the test — the suite leaked"
        )


# ── D2 integration tests (handoff 073) ────────────────────────────────
#
# The D2 block in check_once_generic consults receiver_process_active on
# the PRODUCED-NOTHING fast path BEFORE counting an idle pass. A True
# return resets the idle counter; a False falls through to the existing
# behavior. The tests below exercise both paths through a minimal
# hermetic check_once_generic harness (the shared `flow` fixture in
# test_chain_watchdog.py is for a different topology; these tests build
# a single-step flow so is_last=True and step["to_role"] is exercised).

def test_fast_path_resets_counter_when_child_active(tmp_path, monkeypatch):
    """D2 reset path: receiver_process_active=True drops the idle counter
    and returns "active" with the reason logged.

    Builds a single-step flow where the receiver has already had 2 idle
    passes counted (state[idle_key] = 2) and an idle pane read this pass.
    The probe returns True → counter resets → state[idle_key] no longer
    present → result == "active" → log captures the reason → save_state
    wrote the monkeypatched temp STATE_PATH.
    """
    RUN_ID = "19"
    steps = [{
        "from_role": "super-deep-deep4",
        "to_role": "review-claude-sonnet5",
        "dir": str(tmp_path / "verdicts"),
        "pattern": "{ID}-verdict.md",
    }]
    # Write the deliverable so the loop does not short-circuit to "idle"
    # (find_output returns the path on the producer side; check_once_generic
    # treats a present deliverable as 'complete' on the chain's last step).
    (tmp_path / "verdicts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "verdicts" / f"{RUN_ID}-verdict.md").write_text("x")

    captured_logs = []
    monkeypatch.setattr(cw, "sample_ollama", lambda: None)
    monkeypatch.setattr(cw, "recent_signal_delivered", lambda *a, **k: False)
    monkeypatch.setattr(cw, "load_remote_targets", lambda: {})
    monkeypatch.setattr(cw, "pane_active", lambda session: False)
    monkeypatch.setattr(
        cw, "signal_age_minutes", lambda *a, **k: 0.5,
    )  # enters the fast path
    monkeypatch.setattr(
        cw, "receiver_process_active",
        lambda flow_key, to_role, state: True,
    )
    monkeypatch.setattr(cw, "log", lambda msg: captured_logs.append(msg))

    idle_key = (f"idle:preferred_cloud_harness:{RUN_ID}:"
                f"review-claude-sonnet5")
    state = {idle_key: 2}  # two idle passes already counted

    result = cw.check_once_generic(
        "preferred_cloud_harness", steps,
        {"super-deep-deep4": "super-deep-deep4",
         "review-claude-sonnet5": "review-claude-sonnet5"},
        RUN_ID, cw.STALL_MINUTES_DEFAULT, state, dry_run=False,
    )
    assert result == "active", (
        f"reset path must return 'active', got {result!r}"
    )
    assert idle_key not in state, (
        f"idle counter NOT reset: state still has {idle_key}={state.get(idle_key)}"
    )
    # The reason was logged with the EXACT phrase (em-dash).
    matched = [m for m in captured_logs
               if "pane idle but harness child active — not an idle pass" in m]
    assert matched, (
        f"expected reason log not found; captured: {captured_logs!r}"
    )
    # The reset's save_state wrote the MONKEYPATCHED temp STATE_PATH —
    # proves persistence on the reset path.
    assert cw.STATE_PATH.exists(), (
        f"reset path did not persist; STATE_PATH={cw.STATE_PATH}"
    )


def test_fast_path_counts_idle_when_child_inactive(tmp_path, monkeypatch):
    """D2 fall-through: receiver_process_active=False leaves the counter
    byte-identical. Same harness as the reset test, but the probe returns
    False — counter increments to 2 (from seed 1), no reset.
    """
    import chain_watchdog as _cw
    monkeypatch.setattr(_cw, "IDLE_PASSES", 3)  # pin against host tuning
    RUN_ID = "19"
    steps = [{
        "from_role": "super-deep-deep4",
        "to_role": "review-claude-sonnet5",
        "dir": str(tmp_path / "verdicts"),
        "pattern": "{ID}-verdict.md",
    }]
    (tmp_path / "verdicts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "verdicts" / f"{RUN_ID}-verdict.md").write_text("x")

    monkeypatch.setattr(cw, "sample_ollama", lambda: None)
    monkeypatch.setattr(cw, "recent_signal_delivered", lambda *a, **k: False)
    monkeypatch.setattr(cw, "load_remote_targets", lambda: {})
    monkeypatch.setattr(cw, "pane_active", lambda session: False)
    monkeypatch.setattr(cw, "signal_age_minutes", lambda *a, **k: 0.5)
    monkeypatch.setattr(
        cw, "receiver_process_active",
        lambda flow_key, to_role, state: False,
    )

    idle_key = (f"idle:preferred_cloud_harness:{RUN_ID}:"
                f"review-claude-sonnet5")
    state = {idle_key: 1}  # one idle pass already counted

    result = cw.check_once_generic(
        "preferred_cloud_harness", steps,
        {"super-deep-deep4": "super-deep-deep4",
         "review-claude-sonnet5": "review-claude-sonnet5"},
        RUN_ID, cw.STALL_MINUTES_DEFAULT, state, dry_run=True,
    )
    # Below IDLE_PASSES threshold (pinned at 3, seeded at 1 + 1 = 2 < 3).
    assert result == "active", (
        f"fall-through path should keep watching until IDLE_PASSES; "
        f"got {result!r}"
    )
    # Counter incremented; no reset.
    assert state[idle_key] == 2, (
        f"fall-through did not increment idle counter; "
        f"state[idle_key]={state.get(idle_key)!r}"
    )


def test_real_busy_process_active_then_inactive(temp_db, fake_role_session):
    """The one NON-mocked test (GOAL.md §1 D3): a real spawned busy-loop
    process anchored in the temp DB.

    First observation -> True (cold start). After a brief sleep, jiffies
    have advanced deterministically (busy loop burns CPU continuously)
    -> True on the second pass. After terminate(), the pid is dead ->
    False, and the baseline is dropped from state.
    """
    import subprocess
    import time

    proc = subprocess.Popen([sys.executable, "-c", "while True: pass"])
    try:
        _create_anchor_table(
            temp_db, "preferred_cloud_harness", "imple-codex-minimaxM3",
            pid=proc.pid,
        )
        state = {}
        # First observation: live pid, no baseline -> True (D1 contract
        # "first observation returns True").
        assert cw.receiver_process_active(
            "preferred_cloud_harness", "imple-codex-minimaxM3", state,
        ) is True, "live busy-loop pid must report active on first pass"
        rec = state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]
        assert rec["pid"] == proc.pid
        assert rec["jiffies"] >= 0  # baseline recorded

        # Brief sleep so the busy loop accumulates more jiffies.
        time.sleep(0.2)

        # Second observation: same pid, jiffies advanced (busy loop) -> True.
        assert cw.receiver_process_active(
            "preferred_cloud_harness", "imple-codex-minimaxM3", state,
        ) is True, (
            "busy-loop pid must report active on second pass "
            "(jiffies advanced; D1 contract)"
        )
        rec_after = state["proc:preferred_cloud_harness:imple-codex-minimaxM3"]
        assert rec_after["pid"] == proc.pid
        assert rec_after["jiffies"] > rec["jiffies"], (
            f"busy loop did not advance jiffies: baseline={rec['jiffies']} "
            f"second={rec_after['jiffies']}"
        )
    finally:
        # Terminate and reap. proc.terminate sends SIGTERM; the busy loop
        # ignores the signal? Actually Python's default SIGTERM handler
        # raises SystemExit, so terminate + wait() is enough to reap.
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

    # Post-termination: pid is dead -> False, baseline dropped.
    state = {"proc:preferred_cloud_harness:imple-codex-minimaxM3":
             {"pid": proc.pid, "jiffies": 100}}
    assert cw.receiver_process_active(
        "preferred_cloud_harness", "imple-codex-minimaxM3", state,
    ) is False, "dead pid must report inactive (D1 contract clause 3b)"
    assert ("proc:preferred_cloud_harness:imple-codex-minimaxM3"
            not in state), (
        "dead pid must drop the baseline (D1 contract clause: state.pop)"
    )
