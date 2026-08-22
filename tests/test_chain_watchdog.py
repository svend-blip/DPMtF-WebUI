"""Tests for the generic (DB-driven) detection in chain_watchdog.py.

Focus: the receiver-stall case discovered in supervised_review run goal-006,
handoff 21 — review01 received imple01's callback, produced NO deliverable,
and went idle. The detector could only reason about the SENDER's file age,
so it neither named the stalled role nor fired until roughly twice the stall
threshold had passed.
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import chain_watchdog as cw  # noqa: E402


STALL_MINUTES = 12


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def flow(tmp_path, monkeypatch):
    """An isolated supervised_review-shaped flow on disk.

    Returns a helper object with the step list, the deliverable writers and
    a trace.log writer, all rooted in tmp_path.
    """
    bridge = tmp_path / "flows"
    root = bridge / "supervised_review"
    for sub in ("handoffs", "results", "reviews", "verdicts"):
        (root / sub).mkdir(parents=True)

    steps = [
        {"from_role": "supervisor_auto", "to_role": "imple01",
         "dir": str(root / "handoffs"), "pattern": "{ID}-handoff.md"},
        {"from_role": "imple01", "to_role": "review01",
         "dir": str(root / "results"), "pattern": "{ID}-result.md"},
        {"from_role": "review01", "to_role": "review02",
         "dir": str(root / "reviews"), "pattern": "{ID}-review01.md"},
        {"from_role": "review02", "to_role": "supervisor_auto",
         "dir": str(root / "verdicts"), "pattern": "{ID}-verdict.md"},
    ]

    monkeypatch.setattr(cw.config, "get_bridge_dir", lambda: str(bridge))
    monkeypatch.setattr(cw, "sample_ollama", lambda: None)
    # Every dry_run=False test calls save_state(), and STATE_PATH used to be
    # the LIVE watchdog's file. The suite was writing real nudge budgets into
    # /home/svend/DPMtF-WebUI/logs/chain-watchdog-state.json — so a genuine
    # supervised_review handoff 21 would have found its budget already spent
    # and its stall silently un-nudged. Tests must not be able to blind
    # production.
    monkeypatch.setattr(cw, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cw, "STATE_PATH", tmp_path / "logs" / "state.json")
    # Default: every pane is idle. Individual tests widen this.
    monkeypatch.setattr(cw, "pane_active", lambda session: False)
    # No remote roles by default, and NEVER the live database: a fixture
    # that reads production state fails when operations change, not when
    # code does.
    monkeypatch.setattr(cw, "load_remote_targets", lambda: {})

    class Flow:
        def __init__(self):
            self.steps = steps
            self.sessions = {r: r for r in
                             ("supervisor_auto", "imple01", "review01",
                              "review02")}
            self.trace = bridge / "trace.log"
            self.nudges = []

        def write(self, step_index, run_id, age_minutes=0):
            """Create a step's deliverable, backdated by age_minutes."""
            step = self.steps[step_index]
            p = Path(step["dir"]) / step["pattern"].replace("{ID}", str(run_id))
            p.write_text("deliverable content\n", encoding="utf-8")
            if age_minutes:
                stamp = time.time() - age_minutes * 60
                import os
                os.utime(p, (stamp, stamp))
            return p

        def signal(self, from_role, to_role, run_id, age_minutes,
                   signal_type="signal_complete"):
            """Append a signal line to trace.log, backdated."""
            ts = (datetime.now(timezone.utc)
                  - timedelta(minutes=age_minutes)).strftime(
                      "%Y-%m-%dT%H:%M:%SZ")
            with open(self.trace, "a", encoding="utf-8") as fh:
                fh.write(f"{ts} | {from_role}->{to_role} | {run_id} | "
                         f"{signal_type} | manual | Callback dispatched\n")

        def dispatch(self, from_role, to_role, run_id, age_minutes):
            """Append the dispatcher's `dispatched` line (the type the
            supervisor->imple handoff dispatch actually logs)."""
            self.signal(from_role, to_role, run_id, age_minutes,
                        signal_type="dispatched")

        def active_panes(self, *roles, monkeypatch=monkeypatch):
            monkeypatch.setattr(cw, "pane_active",
                                lambda session: session in roles)

        def record_nudges(self, monkeypatch=monkeypatch):
            def fake_nudge(role, run_id, flow_key=cw.FLOW_KEY, dry_run=False,
                           stalled=None, why=None, force=False):
                self.nudges.append({"role": role, "run_id": run_id,
                                    "stalled": stalled or role, "why": why,
                                    "force": force})
                return True
            monkeypatch.setattr(cw, "nudge", fake_nudge)

        def check(self, run_id="21", state=None, dry_run=True):
            return cw.check_once_generic(
                "supervised_review", self.steps, self.sessions, run_id,
                STALL_MINUTES, state if state is not None else {},
                dry_run=dry_run)

    return Flow()


# ── signal_age_minutes ───────────────────────────────────────────────

def test_signal_age_is_none_when_the_step_never_signalled(flow):
    flow.trace.write_text("", encoding="utf-8")

    assert cw.signal_age_minutes("imple01", "review01", "21") is None


def test_signal_age_measures_the_most_recent_matching_line(flow):
    flow.signal("imple01", "review01", "21", age_minutes=40)
    flow.signal("imple01", "review01", "21", age_minutes=15)

    age = cw.signal_age_minutes("imple01", "review01", "21")

    assert age == pytest.approx(15, abs=1)


def test_signal_age_ignores_other_runs_and_other_steps(flow):
    flow.signal("imple01", "review01", "20", age_minutes=5)
    flow.signal("review01", "review02", "21", age_minutes=5)

    assert cw.signal_age_minutes("imple01", "review01", "21") is None


# ── Dispatch step: the dispatcher logs `dispatched`, not
# `signal_complete` (run goal-016, watchdog-063: the step-1 receiver
# branch never fired and the pass fell through to sender-stall timing
# on the handoff file's mtime) ────────────────────────────────────────

def test_signal_age_counts_the_dispatchers_dispatched_line(flow):
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=15)

    age = cw.signal_age_minutes("supervisor_auto", "imple01", "21")

    assert age == pytest.approx(15, abs=1)


def test_step1_receiver_is_timed_by_the_dispatch_not_the_handoff_mtime(flow):
    """The handoff was authored long before the dispatch went out (063:
    12 min gap). Inside the receiver's window this is 'active', however
    old the handoff file is."""
    flow.write(0, "21", age_minutes=30)   # handoff authored, then queued
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=5)
    flow.record_nudges()

    assert flow.check() == "active"
    assert flow.nudges == []


def test_step1_receiver_stall_names_imple_not_the_supervisor(flow):
    """Dispatched, produced nothing, pane idle, window elapsed — the
    stalled role is the receiver, not the sender the old fallback blamed."""
    flow.write(0, "21", age_minutes=30)
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=15)
    flow.record_nudges()

    assert flow.check() == "nudged"
    assert flow.nudges[0]["stalled"] == "imple01"
    assert "dispatched" in flow.nudges[0]["why"]


# ── Receiver stall: dispatched, produced nothing, pane idle ──────────

def test_receiver_stall_is_nudged_once_the_inbound_signal_ages_out(flow):
    """Handoff 21 verbatim: imple01 delivered and signalled; review01 wrote
    nothing and went idle. Today this returns 'active' until 2x the stall
    threshold, because the sender's callback was 'recent'."""
    flow.write(0, "21", age_minutes=60)   # handoff
    flow.write(1, "21", age_minutes=15)   # result.md
    flow.signal("supervisor_auto", "imple01", "21", age_minutes=60)
    flow.signal("imple01", "review01", "21", age_minutes=15)
    flow.record_nudges()

    status = flow.check()

    assert status == "nudged"
    assert flow.nudges == [{"role": "imple01", "run_id": "21",
                            "stalled": "review01",
                            "why": flow.nudges[0]["why"],
                            "force": True}]
    assert "review01" != flow.nudges[0]["role"], "re-delivery goes via sender"
    assert flow.nudges[0]["why"], "the nudge must state why review01 is stalled"
    # The transition imple01->review01 #21 is already on trace.log as
    # delivered, so an unforced re-delivery is suppressed as a duplicate and
    # the receiver is never re-prompted. Without this the repair is a no-op.
    assert flow.nudges[0]["force"] is True, (
        "a receiver stall must force past the idempotency guard"
    )


def test_receiver_stall_names_the_receiver_not_the_sender(flow):
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=15)
    flow.signal("imple01", "review01", "21", age_minutes=15)
    flow.record_nudges()

    flow.check()

    assert flow.nudges[0]["stalled"] == "review01"


def test_receiver_stall_ignores_the_senders_file_age(flow):
    """The sender's deliverable is FRESH (just rewritten) but the inbound
    signal is old and the receiver is idle — still a stall."""
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=0)    # freshly touched
    flow.signal("imple01", "review01", "21", age_minutes=20)
    flow.record_nudges()

    assert flow.check() == "nudged"
    assert flow.nudges[0]["stalled"] == "review01"


def test_receiver_is_not_flagged_while_its_pane_is_working(flow):
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=15)
    flow.signal("imple01", "review01", "21", age_minutes=15)
    flow.active_panes("review01")
    flow.record_nudges()

    assert flow.check() == "active"
    assert flow.nudges == []


def test_receiver_is_not_flagged_before_the_stall_threshold(flow):
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=5)
    flow.signal("imple01", "review01", "21", age_minutes=5)
    flow.record_nudges()

    assert flow.check() == "active"
    assert flow.nudges == []


# ── Sender stall: wrote output, never signalled (existing behaviour) ──

def test_sender_stall_is_still_detected_when_no_signal_was_sent(flow):
    """review02 wrote the verdict but never signalled the supervisor."""
    for i in range(4):
        flow.write(i, "21", age_minutes=30)
    flow.signal("supervisor_auto", "imple01", "21", age_minutes=60)
    flow.signal("imple01", "review01", "21", age_minutes=50)
    flow.signal("review01", "review02", "21", age_minutes=40)
    flow.record_nudges()

    assert flow.check() == "nudged"
    assert flow.nudges[0]["role"] == "review02"
    assert flow.nudges[0]["stalled"] == "review02"
    # A sender stall never signalled, so no guard entry exists to bypass.
    # Forcing here would only widen what the guard is meant to contain.
    assert flow.nudges[0]["force"] is False, (
        "a sender stall must not force past the idempotency guard"
    )


def test_flow_owner_is_never_reported_as_the_stalled_role(flow):
    """supervisor_auto produces no chain deliverable and its pane proves
    nothing — the final step may only ever blame review02."""
    for i in range(4):
        flow.write(i, "21", age_minutes=30)
    flow.record_nudges()

    flow.check()

    assert flow.nudges[0]["stalled"] != "supervisor_auto"


def test_run_is_complete_when_the_final_signal_was_delivered(flow):
    for i in range(4):
        flow.write(i, "21", age_minutes=30)
    flow.signal("review02", "supervisor_auto", "21", age_minutes=1)

    assert flow.check() == "complete"


# ── Nudge budget ─────────────────────────────────────────────────────

def test_a_stalled_receiver_is_nudged_at_most_twice(flow):
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=15)
    flow.signal("imple01", "review01", "21", age_minutes=15)
    flow.record_nudges()
    state = {}

    first = flow.check(state=state, dry_run=False)
    second = flow.check(state=state, dry_run=False)
    third = flow.check(state=state, dry_run=False)

    assert [first, second, third] == ["nudged", "nudged", "escalated"]
    assert len(flow.nudges) == 2


def test_receiver_and_sender_budgets_are_counted_separately(flow):
    """A receiver stall must not spend the sender's nudge budget."""
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=15)
    flow.signal("imple01", "review01", "21", age_minutes=15)
    flow.record_nudges()
    state = {"supervised_review:21:imple01": cw.MAX_NUDGES_PER_STEP}

    assert flow.check(state=state, dry_run=False) == "nudged"


# ── Chain not started ────────────────────────────────────────────────

def test_missing_first_deliverable_reports_idle_not_a_stall(flow):
    flow.record_nudges()

    assert flow.check(run_id="99") == "idle"
    assert flow.nudges == []


# ── The produced-nothing fast path ───────────────────────────────────
#
# preferred_cloud run 011: MiniMax answered the injected handoff with
# "Context reset acknowledged." and idled. No signal, no deliverable, no
# error -- the Human spotted it before any instrument did, because the
# classic threshold treats an idle pane like a thinking one and waits out
# stall_minutes. An idle pane observed on consecutive passes is not
# thinking.


def test_fast_path_nudges_after_consecutive_idle_passes(flow, monkeypatch):
    # Pin the pass threshold: IDLE_PASSES is machine-local configuration
    # (profiles/machine.local.json), and this test must not change meaning
    # when the operator tunes it — it did on 2026-08-21, when the host
    # raised idle_passes 3 -> 10 after the fast path nudged a working
    # Codex implementer, and this test silently went red.
    import chain_watchdog as _cw
    monkeypatch.setattr(_cw, "IDLE_PASSES", 3)
    flow.write(0, "21")
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=3)
    flow.record_nudges()
    state = {}
    assert flow.check(state=state) == "active"   # pass 1: watching
    assert flow.check(state=state) == "active"   # pass 2: watching
    assert flow.check(state=state) == "nudged"   # pass 3: produced nothing
    assert "consecutive passes" in flow.nudges[0]["why"]
    assert flow.nudges[0]["stalled"] == "imple01"


def test_fast_path_counter_resets_when_the_pane_works(flow, monkeypatch):
    """A role that thinks between passes must never accumulate toward a
    nudge -- the 2026-08-05 scar: a guard acting on the wrong signal is
    worse than no guard."""
    flow.write(0, "21")
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=3)
    flow.record_nudges()
    state = {}
    flow.check(state=state)                      # idle 1
    flow.check(state=state)                      # idle 2
    flow.active_panes("imple01")                 # now it works
    assert flow.check(state=state) == "active"
    flow.active_panes()                          # idle again
    assert flow.check(state=state) == "active"   # counter restarted at 1
    assert flow.nudges == []


def test_fast_path_respects_the_nudge_budget(flow):
    flow.write(0, "21")
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=3)
    flow.record_nudges()
    state = {"supervised_review:21:imple01": cw.MAX_NUDGES_PER_STEP}
    for _ in range(cw.IDLE_PASSES):
        status = flow.check(state=state)
    assert status == "escalated"
    assert flow.nudges == []


# ── Escalation ───────────────────────────────────────────────────────
#
# preferred_cloud run 015, handoff 035: the watchdog detected the stall within
# four minutes, spent both nudges, and concluded "human attention needed" --
# then wrote that conclusion to journald 339 times across five hours and fifty
# minutes. Nobody reads journald. The chain then aged past
# CHAIN_MAX_AGE_MINUTES, the watchdog went quiet, and the run stayed dead for
# three and a half days.
#
# Detection was never the gap. The conclusion had no channel to a human, which
# is the failure mode CLAUDE.md 11 states outright: a monitor that writes to a
# file is not a monitor.


@pytest.fixture
def notes(monkeypatch):
    """Capture escalations instead of raising desktop notifications."""
    captured = []
    monkeypatch.setattr(cw, "_notify",
                        lambda title, body: captured.append((title, body)))
    return captured


def _receiver_stall(flow):
    flow.write(0, "21", age_minutes=60)
    flow.write(1, "21", age_minutes=15)
    flow.signal("imple01", "review01", "21", age_minutes=15)
    flow.record_nudges()


def test_a_spent_nudge_budget_reaches_the_human(flow, notes):
    _receiver_stall(flow)
    state = {}

    flow.check(state=state, dry_run=False)
    flow.check(state=state, dry_run=False)
    assert notes == []                      # budget not spent yet — no alarm

    assert flow.check(state=state, dry_run=False) == "escalated"
    assert len(notes) == 1
    title, body = notes[0]
    assert "review01" in body               # names the stalled role, not the flow only
    assert "supervised_review" in title


def test_escalation_does_not_fire_once_per_pass(flow, notes):
    """339 identical lines is precisely how the last conclusion was missed."""
    _receiver_stall(flow)
    state = {"supervised_review:21:review01": cw.MAX_NUDGES_PER_STEP}

    for _ in range(20):
        assert flow.check(state=state, dry_run=False) == "escalated"

    assert len(notes) == 1


def test_escalation_repeats_after_the_backoff(flow, notes):
    """A missed or dismissed notification must not be the end of it."""
    _receiver_stall(flow)
    key = "supervised_review:21:review01"
    state = {key: cw.MAX_NUDGES_PER_STEP}

    flow.check(state=state, dry_run=False)
    assert len(notes) == 1

    stale = time.time() - (cw.ESCALATION_REPEAT_MINUTES + 1) * 60
    state[f"escalated:{key}"] = stale
    flow.check(state=state, dry_run=False)

    assert len(notes) == 2


def test_the_repeat_stamp_survives_in_state(flow, notes):
    """A watchdog restart must not restart the popups."""
    _receiver_stall(flow)
    key = "supervised_review:21:review01"
    state = {key: cw.MAX_NUDGES_PER_STEP}

    flow.check(state=state, dry_run=False)

    assert f"escalated:{key}" in state


def test_a_dry_run_notifies_nobody(flow, notes):
    _receiver_stall(flow)
    state = {"supervised_review:21:review01": cw.MAX_NUDGES_PER_STEP}

    assert flow.check(state=state, dry_run=True) == "escalated"
    assert notes == []


def test_the_fast_path_escalates_when_its_budget_is_spent(flow, notes):
    """The produced-nothing path is the one run 015 actually took."""
    flow.write(0, "21")
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=3)
    flow.record_nudges()
    state = {"supervised_review:21:imple01": cw.MAX_NUDGES_PER_STEP}

    for _ in range(cw.IDLE_PASSES):
        status = flow.check(state=state, dry_run=False)

    assert status == "escalated"
    assert len(notes) == 1
    assert "imple01" in notes[0][1]


def test_notify_survives_a_missing_notification_daemon(monkeypatch):
    """No desktop is a reason to log, never a reason to die.

    The watchdog runs as a systemd user unit; a headless or logged-out session
    has no notification bus, and an unhandled OSError there would take out
    detection for every flow at once.
    """
    def boom(*args, **kwargs):
        raise OSError("no session bus")

    monkeypatch.setattr(cw.subprocess, "run", boom)
    cw._notify("title", "body")      # must not raise


# ── Remote roles ─────────────────────────────────────────────────────


def test_a_remote_receiver_is_never_auto_nudged(flow, monkeypatch):
    """The nudge re-sends the sender's signal-complete, which for a remote
    receiver mints a SECOND execution offer. Detection yes, repair no."""
    monkeypatch.setattr(cw, "load_remote_targets",
                        lambda: {"imple01": "svend3060"})
    monkeypatch.setattr(cw, "remote_activity",
                        lambda flow_key, role, run_id: "stale")
    flow.write(0, "21")
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=60)
    flow.record_nudges()
    state = {}
    for _ in range(cw.IDLE_PASSES + 2):
        assert flow.check(state=state) == "idle"
    assert flow.nudges == []


def test_a_remote_receiver_with_fresh_heartbeats_is_working(flow, monkeypatch):
    monkeypatch.setattr(cw, "load_remote_targets",
                        lambda: {"imple01": "svend3060"})
    monkeypatch.setattr(cw, "remote_activity",
                        lambda flow_key, role, run_id: "active")
    flow.write(0, "21")
    flow.dispatch("supervisor_auto", "imple01", "21", age_minutes=60)
    flow.record_nudges()
    assert flow.check(state={}) == "active"
    assert flow.nudges == []


@pytest.fixture
def lightworker_db(tmp_path, monkeypatch):
    """A real-schema LightWorker store, built from the live migration file.

    remote_activity spent its first weeks querying a column named
    created_at on lightworker_execution_heartbeats; the schema names it
    heartbeat_at, the sqlite3.Error was swallowed, and every healthy
    remote worker was reported 'missing'. The earlier tests monkeypatched
    remote_activity away, so only a fixture built from the actual SQL
    could have caught it — hence this one.
    """
    import sqlite3
    db = tmp_path / "dpmtf.db"
    sql = (PROJECT_ROOT / "scripts" / "db"
           / "030_lightworker_executions.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    monkeypatch.setattr(cw, "_db_path", lambda: str(db))

    class Store:
        def execution(self, state="claimed", updated_age_seconds=0):
            # SQLite's datetime('now') format: naive UTC, space-separated.
            stamp = (datetime.now(timezone.utc)
                     - timedelta(seconds=updated_age_seconds)).strftime(
                         "%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO lightworker_executions (execution_id, handoff_id,"
                " worker_id, target_role, state, attempt_id, payload_json,"
                " updated_at) VALUES ('EXEC-21-IMPLE01', '21', 'w1',"
                " 'imple01', ?, 'a1', '{}', ?)", (state, stamp))
            conn.commit()

        def heartbeat(self, age_seconds):
            stamp = (datetime.now(timezone.utc)
                     - timedelta(seconds=age_seconds)).strftime(
                         "%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT OR REPLACE INTO lightworker_execution_heartbeats"
                " (execution_id, worker_id, attempt_id, heartbeat_at)"
                " VALUES ('EXEC-21-IMPLE01', 'w1', 'a1', ?)", (stamp,))
            conn.commit()

    yield Store()
    conn.close()


def test_a_beating_remote_worker_reads_active_from_the_real_schema(
        lightworker_db):
    lightworker_db.execution(state="claimed", updated_age_seconds=600)
    lightworker_db.heartbeat(age_seconds=10)
    assert cw.remote_activity("lightworker", "imple01", "21") == "active"


def test_a_silent_claimed_execution_reads_stale(lightworker_db):
    lightworker_db.execution(state="claimed", updated_age_seconds=600)
    lightworker_db.heartbeat(age_seconds=600)
    assert cw.remote_activity("lightworker", "imple01", "21") == "stale"


def test_an_undelivered_offer_reads_unclaimed(lightworker_db):
    lightworker_db.execution(state="offered", updated_age_seconds=600)
    assert cw.remote_activity("lightworker", "imple01", "21") == "unclaimed"


def test_no_execution_at_all_reads_missing(lightworker_db):
    assert cw.remote_activity("lightworker", "imple01", "21") == "missing"


def test_a_human_terminated_chain_counts_as_complete(flow):
    """dispatch logs `signal_complete_to_human` when the last receiver is
    the Human. The first --all-flows dry-run read a finished lightworker
    chain as 'wrote output but never signaled' and drew a nudge, because
    the needle tuple knew only signal_complete and dispatched."""
    for i in range(4):
        flow.write(i, "21")
    flow.signal("review02", "supervisor_auto", "21", age_minutes=2,
                signal_type="signal_complete_to_human")
    flow.record_nudges()
    assert flow.check(state={}) == "complete"
    assert flow.nudges == []
