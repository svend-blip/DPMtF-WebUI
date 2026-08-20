"""Tests for the supervisor's one-shot state report.

Every case here is a mistake that actually happened in llama_SG runs 004-008.
The report exists to make those mistakes impossible to repeat, so the tests
are written against the incidents rather than against the happy path.
"""

import importlib.util
import os
import sqlite3
from datetime import datetime, timezone
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
        CREATE TABLE bridge_roles (
            role_key TEXT, tmux_session TEXT, default_model_alias TEXT,
            default_model_source TEXT);
        CREATE TABLE bridge_id_counters (flow_key TEXT PRIMARY KEY, next_id INTEGER);
        """
    )
    conn.executemany(
        "INSERT INTO bridge_flow_steps VALUES (?,?,?,?)",
        [(FLOW, "a", ROLES[0], ROLES[1]),
         (FLOW, "b", ROLES[1], ROLES[2]),
         (FLOW, "c", ROLES[2], ROLES[0])],
    )
    # collect() reads sessions and model aliases from here, so the flow it is
    # asked about describes itself rather than a hardcoded one.
    conn.executemany(
        "INSERT INTO bridge_roles VALUES (?,?,?,?)",
        [(r, r, "laguna-local" if "llama" in r else "imple-fast", "model_allocator")
         for r in ROLES],
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

    def test_started_run_missing_goal_parks(self, env):
        """A run that started and then lost its contract is an anomaly.

        It must surface, not be skipped in favour of an older run: the
        ledger proves work happened that nothing now authorises.
        """
        _run(env, "008", ledger="## Wake-up (opened)")
        result = state.collect(FLOW)
        assert result["assessment"].startswith("PARK")
        assert any("GOAL.md" in m for m in result["missing"])

    def test_never_opened_directory_is_not_adopted(self, env):
        """A directory with no run artefact was never a run.

        Adopting one is how a draft contract left as GOAL.md was reported
        as the active run -- with no floor, so every handoff on disk was
        listed as its own.
        """
        _run(env, "007", goal="**First handoff id: 011**", end_report=True)
        _run(env, "008")
        result = state.collect(FLOW)
        assert result["run"] is None
        assert result["assessment"].startswith("NO ACTIVE RUN")
        assert result["owned_handoffs"] == []

    def test_draft_is_reported_but_not_adopted(self, env):
        """An unapproved draft is named so it is visible, never opened."""
        (env / FLOW / "runs" / "009").mkdir(parents=True)
        (env / FLOW / "runs" / "009" / "GOAL-DRAFT.md").write_text(
            "DRAFT — NOT APPROVED", encoding="utf-8"
        )
        result = state.collect(FLOW)
        assert result["run"] is None
        assert result["assessment"].startswith("NO ACTIVE RUN")
        assert any("009" in m and "draft" in m.lower() for m in result["missing"])

    def test_missing_floor_parks(self, env):
        _run(env, "008", goal="a contract with no floor stated")
        result = state.collect(FLOW)
        assert result["assessment"].startswith("PARK")


class TestStaleness:
    """preferred_cloud run 015: handoff 035 dispatched, never answered.

    The report said "HANDOFF 035 DISPATCHED — the implementer is working" for
    three and a half days. It was right that no result existed and wrong about
    what that meant: the implementer's session had been recycled the same
    evening. Nothing measured how long the absence had lasted, so a dispatch
    3.5 days old presented identically to one made a minute earlier.
    """

    @pytest.fixture
    def env(self, bridge, db, monkeypatch):
        monkeypatch.setattr(state.config, "get_bridge_dir", lambda: str(bridge))
        monkeypatch.setattr(state.config, "get_db_path", lambda: db)
        monkeypatch.setattr(state, "_probe", lambda *a, **k: True)
        monkeypatch.setattr(state, "_tmux_sessions", lambda names: {n: True for n in names})
        return bridge

    @staticmethod
    def _at(stamp):
        """Epoch for a UTC stamp, through the module's own parser."""
        return state.trace_epoch(stamp)

    @staticmethod
    def _age_files(paths, epoch):
        """Backdate files so a tmp_path fixture does not read as movement now."""
        for path in paths:
            os.utime(path, (epoch, epoch))

    def _dispatched(self, bridge, *, signal_at=None, handoff_at, run_at):
        """An open run whose current handoff has no result."""
        run = _run(bridge, "015", goal="**First handoff id: 011**", backlog=True,
                   ledger="- opened")
        handoff = bridge / FLOW / "handoffs" / "011-handoff.md"
        handoff.write_text("x")
        if signal_at is not None:
            (bridge / "trace.log").write_text(
                f"{signal_at} | {ROLES[0]}->{ROLES[1]} | 011 | dispatched | m | x\n",
                encoding="utf-8")
        self._age_files([handoff], handoff_at)
        self._age_files([run / "GOAL.md", run / "BACKLOG.md", run / "RUN-LEDGER.md"], run_at)
        return run

    def test_trace_stamps_are_read_as_utc(self):
        """Trace text is UTC, mtimes are local epoch.

        Comparing the two as rendered strings once invented a two-hour causal
        link that was not there. Everything downstream is epoch seconds.
        """
        line = "2026-08-09T21:07:39Z | a->b | 011 | dispatched | m | x"
        assert state.trace_epoch(line) == datetime(
            2026, 8, 9, 21, 7, 39, tzinfo=timezone.utc).timestamp()

    def test_a_line_without_a_stamp_yields_no_epoch(self):
        assert state.trace_epoch("no timestamp here") is None
        assert state.trace_epoch(None) is None

    def test_a_days_old_dispatch_is_stalled_not_working(self, env, bridge):
        """The run-015 incident itself."""
        old = self._at("2026-08-09T21:07:39Z")
        self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                         handoff_at=old, run_at=old)
        result = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert "STALLED" in result["assessment"]
        assert "working" not in result["assessment"]
        assert result["stale"] is True
        assert result["last_movement"]["source"] == "trace signal"
        assert any("no movement" in m for m in result["missing"])

    def test_a_stalled_dispatch_warns_against_dispatching(self, env, bridge):
        """The wrong reflex on a stall is to send the next handoff."""
        old = self._at("2026-08-09T21:07:39Z")
        self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                         handoff_at=old, run_at=old)
        result = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert "3d" in result["assessment"]
        assert "session" in result["assessment"].lower()

    def test_a_fresh_dispatch_still_reads_as_working(self, env, bridge):
        """A role thinking for twenty minutes is not a blockage."""
        now = self._at("2026-08-09T21:30:00Z")
        old = self._at("2026-08-09T21:07:39Z")
        self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                         handoff_at=old, run_at=old)
        result = state.collect(FLOW, now=now)
        assert "the implementer is working" in result["assessment"]
        assert "STALLED" not in result["assessment"]
        assert result["stale"] is False

    def test_the_age_is_visible_even_when_fresh(self, env, bridge):
        """Staleness the reader can see beats a threshold they cannot."""
        old = self._at("2026-08-09T21:07:39Z")
        self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                         handoff_at=old, run_at=old)
        result = state.collect(FLOW, now=self._at("2026-08-09T21:30:00Z"))
        assert "22m ago" in result["assessment"]
        assert "22m ago" in state.render(result)

    def test_a_slow_but_working_handoff_is_not_accused(self, env, bridge):
        """Handoff 034 legitimately took 128 minutes, stall and dialog included.

        The bound has to sit above a slow-but-working handoff, or the guard
        fires on a healthy chain — worse than having no guard at all.
        """
        old = self._at("2026-08-09T18:46:39Z")
        self._dispatched(bridge, signal_at="2026-08-09T18:46:39Z",
                         handoff_at=old, run_at=old)
        result = state.collect(FLOW, now=self._at("2026-08-09T20:54:43Z"))
        assert result["stale"] is False

    def test_a_handoff_never_recorded_in_trace_falls_back_to_its_mtime(self, env, bridge):
        """Only the trace line means delivered; a written handoff proves nothing."""
        old = self._at("2026-08-09T21:07:39Z")
        self._dispatched(bridge, signal_at=None, handoff_at=old, run_at=old)
        result = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert result["last_movement"]["source"] == "handoff file mtime"
        assert "STALLED" in result["assessment"]

    def test_the_latest_evidence_wins(self, env, bridge):
        """Under-report the age rather than accuse a chain that is moving."""
        self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                         handoff_at=self._at("2026-08-01T09:00:00Z"),
                         run_at=self._at("2026-08-01T09:00:00Z"))
        result = state.collect(FLOW, now=self._at("2026-08-09T21:30:00Z"))
        assert result["last_movement"]["source"] == "trace signal"
        assert result["stale"] is False

    def test_a_stale_result_names_the_verdict_not_the_implementer(self, env, bridge):
        """Blaming the wrong role is its own recorded bug class."""
        old = self._at("2026-08-09T21:07:39Z")
        run = self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                               handoff_at=old, run_at=old)
        result_file = bridge / FLOW / "results" / "011-result.md"
        result_file.write_text("x")
        self._age_files([result_file], old)
        assert run.exists()
        report = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert "STALLED" in report["assessment"]
        assert "verdict" in report["assessment"]

    def test_a_verdict_still_says_validate_however_old(self, env, bridge):
        """A waiting verdict needs acting on, not a stall warning."""
        old = self._at("2026-08-09T21:07:39Z")
        self._dispatched(bridge, signal_at="2026-08-09T21:07:39Z",
                         handoff_at=old, run_at=old)
        for sub, suffix in (("results", "result"), ("verdicts", "verdict")):
            path = bridge / FLOW / sub / f"011-{suffix}.md"
            path.write_text("x")
            self._age_files([path], old)
        report = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert "VERDICT READY" in report["assessment"]
        assert "STALLED" not in report["assessment"]

    def test_an_opened_run_that_never_dispatched_can_stall(self, env, bridge):
        """A run can sit open and unstarted just as silently."""
        run = _run(bridge, "015", goal="**First handoff id: 011**", backlog=True)
        old = self._at("2026-08-09T14:05:00Z")
        self._age_files([run / "GOAL.md", run / "BACKLOG.md"], old)
        result = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert "CHAIN NOT STARTED" in result["assessment"]
        assert result["stale"] is True
        assert any("no movement" in m for m in result["missing"])

    def test_the_threshold_is_configurable(self, env, bridge):
        old = self._at("2026-08-09T19:00:00Z")
        self._dispatched(bridge, signal_at="2026-08-09T19:00:00Z",
                         handoff_at=old, run_at=old)
        two_hours_later = self._at("2026-08-09T21:00:00Z")
        assert state.collect(FLOW, now=two_hours_later)["stale"] is False
        assert state.collect(FLOW, now=two_hours_later,
                             stale_after_seconds=3600)["stale"] is True

    def test_no_active_run_reports_no_staleness(self, env, bridge):
        """Nothing is stalling when nothing is open."""
        _run(bridge, "015", goal="**First handoff id: 011**", end_report=True)
        result = state.collect(FLOW, now=self._at("2026-08-13T07:23:00Z"))
        assert result["stale"] is False
        assert result["last_movement"] is None


class TestFlowAwareness:
    """The report must describe the flow it was asked about.

    Hardcoding llama_SG's three sessions and its :8080 probe made this lie the
    moment preferred_cloud existed: it named the wrong sessions and reported a
    local model server missing for a flow that has none.
    """

    @pytest.fixture
    def two_flows(self, tmp_path):
        path = tmp_path / "two.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT, to_role TEXT);"
            "CREATE TABLE bridge_roles (role_key TEXT, tmux_session TEXT,"
            " default_model_alias TEXT, default_model_source TEXT);"
            "CREATE TABLE bridge_id_counters (flow_key TEXT PRIMARY KEY, next_id INTEGER);"
        )
        conn.executemany("INSERT INTO bridge_flow_steps VALUES (?,?,?)", [
            ("llama_SG", "supervisor01_llama", "imple01SG"),
            ("llama_SG", "imple01SG", "review01SG"),
            ("preferred_cloud", "Pre-super-cl", "Pre-imple-cl"),
            ("preferred_cloud", "Pre-imple-cl", "Pre-review-cl"),
        ])
        conn.executemany("INSERT INTO bridge_roles VALUES (?,?,?,?)", [
            ("supervisor01_llama", "supervisor01_llama", "laguna-local", "model_allocator"),
            ("imple01SG", "imple01SG", "imple-fast", "model_allocator"),
            ("review01SG", "review01SG", "review02-local", "model_allocator"),
            ("Pre-super-cl", "Pre-super-cl", "opus5", "model_allocator"),
            ("Pre-imple-cl", "Pre-imple-cl", "cloud_minimax", "model_allocator"),
            ("Pre-review-cl", "Pre-review-cl", "sonnet5", "model_allocator"),
        ])
        conn.commit()
        conn.close()
        return str(path)

    def test_sessions_come_from_the_flows_own_roles(self, two_flows):
        assert state.flow_tmux_sessions("preferred_cloud", db_path=two_flows) == {
            "Pre-super-cl", "Pre-imple-cl", "Pre-review-cl"}
        assert state.flow_tmux_sessions("llama_SG", db_path=two_flows) == {
            "supervisor01_llama", "imple01SG", "review01SG"}

    def test_cloud_flow_needs_no_local_model_server(self, two_flows):
        assert state.flow_uses_local_models("preferred_cloud", db_path=two_flows) is False

    def test_local_flow_still_wants_the_probe(self, two_flows):
        assert state.flow_uses_local_models("llama_SG", db_path=two_flows) is True

    def test_unknown_flow_claims_nothing(self, two_flows):
        assert state.flow_tmux_sessions("nope", db_path=two_flows) == set()
        assert state.flow_uses_local_models("nope", db_path=two_flows) is False
