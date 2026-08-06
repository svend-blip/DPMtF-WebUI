"""Tests for the supervisor's one-shot state report.

Every case here is a mistake that actually happened in llama_SG runs 004-008.
The report exists to make those mistakes impossible to repeat, so the tests
are written against the incidents rather than against the happy path.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_MODULE = (Path(__file__).resolve().parent.parent
           / "scripts" / "bridgeV002" / "supervisor_state.py")
_spec = importlib.util.spec_from_file_location("supervisor_state", _MODULE)
state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(state)

FLOW = "llama_SG"
ROLES = ("supervisor01_llama", "imple01SG", "review01SG")


@pytest.fixture
def bridge(tmp_path):
    """A bridge directory with the flow's three deliverable dirs."""
    root = tmp_path / "flows"
    for sub in ("handoffs", "results", "verdicts", "runs"):
        (root / FLOW / sub).mkdir(parents=True)
    return root


@pytest.fixture
def db(tmp_path):
    """A database with just enough for flow_role_keys and flow_counter."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE bridge_flow_steps (
            flow_key TEXT, step_key TEXT, from_role TEXT, to_role TEXT);
        CREATE TABLE bridge_id_counters (flow_key TEXT PRIMARY KEY, next_id INTEGER);
        """
    )
    conn.executemany(
        "INSERT INTO bridge_flow_steps VALUES (?,?,?,?)",
        [(FLOW, "a", ROLES[0], ROLES[1]),
         (FLOW, "b", ROLES[1], ROLES[2]),
         (FLOW, "c", ROLES[2], ROLES[0])],
    )
    conn.execute("INSERT INTO bridge_id_counters VALUES (?,?)", (FLOW, 12))
    conn.commit()
    conn.close()
    return str(path)


def _run(bridge, name, goal=None, end_report=False, backlog=False, ledger=None):
    path = bridge / FLOW / "runs" / name
    path.mkdir(parents=True)
    if goal is not None:
        (path / "GOAL.md").write_text(goal, encoding="utf-8")
    if ledger is not None:
        (path / "RUN-LEDGER.md").write_text(ledger, encoding="utf-8")
    if backlog:
        (path / "BACKLOG.md").write_text("# backlog", encoding="utf-8")
    if end_report:
        (path / "END-REPORT.md").write_text("# closed", encoding="utf-8")
    return path


class TestActiveRun:

    def test_newest_without_end_report_wins(self, bridge):
        _run(bridge, "006", goal="x", end_report=True)
        _run(bridge, "007", goal="x", end_report=True)
        open_run = _run(bridge, "008", goal="x")
        assert state.active_run(bridge, FLOW) == open_run

    def test_all_closed_means_no_active_run(self, bridge):
        _run(bridge, "007", goal="x", end_report=True)
        _run(bridge, "008", goal="x", end_report=True)
        assert state.active_run(bridge, FLOW) is None

    def test_a_closed_newer_run_does_not_reopen_an_older_one(self, bridge):
        """Run 007 closed after 006; 006 must not become active again."""
        _run(bridge, "006", goal="x", end_report=True)
        _run(bridge, "007", goal="x", end_report=True)
        assert state.active_run(bridge, FLOW) is None


class TestFloor:

    def test_reads_first_handoff_id_from_goal(self, bridge):
        run = _run(bridge, "008", goal="**First handoff id: 011**\n")
        assert state.first_handoff_id(run) == 11

    def test_falls_back_to_the_ledger(self, bridge):
        run = _run(bridge, "008", goal="no floor here",
                   ledger="- **First handoff id: 011.** The counter reads 11.")
        assert state.first_handoff_id(run) == 11

    def test_absent_floor_is_none_not_a_guess(self, bridge):
        """Without a floor the run must ask, never adopt what is on disk."""
        run = _run(bridge, "008", goal="no floor anywhere")
        assert state.first_handoff_id(run) is None

    def test_handoffs_below_the_floor_are_excluded(self, bridge):
        """Run 004 adopted run 003's handoff 006 and parked on a spent budget."""
        for i in (9, 10, 11):
            (bridge / FLOW / "handoffs" / f"{i:03d}-handoff.md").write_text("x")
        assert state.handoffs_at_or_above(bridge, FLOW, 11) == [11]

    def test_no_active_run_owns_nothing(self, bridge, db, monkeypatch):
        """Listing every handoff on disk invites the mistake the floor prevents."""
        _run(bridge, "008", goal="**First handoff id: 011**", end_report=True)
        for i in (9, 10, 11):
            (bridge / FLOW / "handoffs" / f"{i:03d}-handoff.md").write_text("x")
        monkeypatch.setattr(state.config, "get_bridge_dir", lambda: str(bridge))
        monkeypatch.setattr(state.config, "get_db_path", lambda: db)
        monkeypatch.setattr(state, "_probe", lambda *a, **k: True)
        monkeypatch.setattr(state, "_tmux_sessions", lambda names: {n: True for n in names})
        result = state.collect(FLOW)
        assert result["owned_handoffs"] == []
        assert "NO ACTIVE RUN" in result["assessment"]


class TestTraceMatching:

    def test_ignores_a_matching_id_from_another_era(self, bridge, db):
        """A bare id grep matched 2026-06-14 claude-bridge lines for handoff 009.

        trace.log is flow-wide and spans every version of the bridge; ids
        repeat. Only a line carrying one of this flow's role keys counts.
        """
        (bridge / "trace.log").write_text(
            "2026-06-14T18:03:07Z | C→L | 009 | sent | Handoff sendt til claude_implementer\n"
            "2026-06-14T18:12:11Z | L→C | 009 | completed | Signal sendt til claude_review\n",
            encoding="utf-8",
        )
        assert state.last_trace_signal(bridge, FLOW, 9, db_path=db) is None

    def test_returns_the_last_matching_line(self, bridge, db):
        (bridge / "trace.log").write_text(
            "2026-08-06T07:12:30Z | supervisor01_llama->imple01SG | 011 | dispatched | m | x\n"
            "2026-08-06T07:15:58Z | imple01SG->review01SG | 011 | signal_complete | m | x\n"
            "2026-08-06T07:18:36Z | review01SG->supervisor01_llama | 011 | signal_complete | m | y\n",
            encoding="utf-8",
        )
        line = state.last_trace_signal(bridge, FLOW, 11, db_path=db)
        assert "review01SG->supervisor01_llama" in line


class TestAssessment:

    @pytest.fixture
    def env(self, bridge, db, monkeypatch):
        monkeypatch.setattr(state.config, "get_bridge_dir", lambda: str(bridge))
        monkeypatch.setattr(state.config, "get_db_path", lambda: db)
        monkeypatch.setattr(state, "_probe", lambda *a, **k: True)
        monkeypatch.setattr(state, "_tmux_sessions", lambda names: {n: True for n in names})
        return bridge

    def test_opened_but_not_started_says_dispatch(self, env):
        _run(env, "008", goal="**First handoff id: 011**")
        result = state.collect(FLOW)
        assert "CHAIN NOT STARTED" in result["assessment"]
        assert any("BACKLOG.md" in m for m in result["missing"])

    def test_verdict_present_says_validate(self, env):
        _run(env, "008", goal="**First handoff id: 011**", backlog=True)
        for sub, suffix in (("handoffs", "handoff"), ("results", "result"),
                            ("verdicts", "verdict")):
            (env / FLOW / sub / f"011-{suffix}.md").write_text("x")
        result = state.collect(FLOW)
        assert "VERDICT READY" in result["assessment"]

    def test_missing_goal_parks(self, env):
        _run(env, "008")
        result = state.collect(FLOW)
        assert result["assessment"].startswith("PARK")

    def test_missing_floor_parks(self, env):
        _run(env, "008", goal="a contract with no floor stated")
        result = state.collect(FLOW)
        assert result["assessment"].startswith("PARK")
