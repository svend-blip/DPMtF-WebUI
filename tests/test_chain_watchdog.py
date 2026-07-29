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
    # Default: every pane is idle. Individual tests widen this.
    monkeypatch.setattr(cw, "pane_active", lambda session: False)

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

        def signal(self, from_role, to_role, run_id, age_minutes):
            """Append a signal_complete line to trace.log, backdated."""
            ts = (datetime.now(timezone.utc)
                  - timedelta(minutes=age_minutes)).strftime(
                      "%Y-%m-%dT%H:%M:%SZ")
            with open(self.trace, "a", encoding="utf-8") as fh:
                fh.write(f"{ts} | {from_role}->{to_role} | {run_id} | "
                         f"signal_complete | manual | Callback dispatched\n")

        def active_panes(self, *roles, monkeypatch=monkeypatch):
            monkeypatch.setattr(cw, "pane_active",
                                lambda session: session in roles)

        def record_nudges(self, monkeypatch=monkeypatch):
            def fake_nudge(role, run_id, flow_key=cw.FLOW_KEY, dry_run=False,
                           stalled=None, why=None):
                self.nudges.append({"role": role, "run_id": run_id,
                                    "stalled": stalled or role, "why": why})
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
                            "why": flow.nudges[0]["why"]}]
    assert "review01" != flow.nudges[0]["role"], "re-delivery goes via sender"
    assert flow.nudges[0]["why"], "the nudge must state why review01 is stalled"


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

    assert [first, second, third] == ["nudged", "nudged", "idle"]
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
