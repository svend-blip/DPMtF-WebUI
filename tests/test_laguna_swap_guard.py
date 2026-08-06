"""Tests for the failed-swap recovery guard.

The guard stops a resident model and restarts Laguna, so the property that
matters is not that it fires — it is that it stays still. Two earlier versions
got this wrong in opposite directions, and both are pinned here as cases:

  v1 waited for `review01SG->supervisor01_llama | signal_complete` in
     trace.log. That entry is written after the swap it was meant to protect,
     so a dispatch that dies on the swap never produces it. It never fired.

  v2 watched the supervisor's tmux pane for ConnectionRefused. Dispatch stops
     Laguna as part of handing off, while the supervisor is still finishing
     its turn — so that state is ordinary after every dispatch. On 2026-08-06
     it stopped the implementer's model four seconds after handoff 013 was
     dispatched.

The signature it now looks for came from measuring run 009's failure: the
verdict file exists, has aged past a normal dispatch, and the trace still
shows no delivery for it.
"""

import importlib.util
import sys
import sqlite3
import time
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002"
_spec = importlib.util.spec_from_file_location("laguna_swap_guard",
                                               _HERE / "laguna_swap_guard.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

FLOW = "llama_SG"
ROLES = ("supervisor01_llama", "imple01SG", "review01SG")
DELIVERED = ("2026-08-06T08:40:17Z | review01SG->supervisor01_llama | 013 | "
             "signal_complete | manual | Callback dispatched\n")
REVIEWER_WORKING = ("2026-08-06T08:37:15Z | imple01SG->review01SG | 013 | "
                    "signal_complete | manual | Callback dispatched\n")


@pytest.fixture
def bridge(tmp_path):
    root = tmp_path / "flows"
    for sub in ("handoffs", "results", "verdicts", "runs"):
        (root / FLOW / sub).mkdir(parents=True)
    run = root / FLOW / "runs" / "010"
    run.mkdir()
    (run / "GOAL.md").write_text("**First handoff id: 013**", encoding="utf-8")
    (root / FLOW / "handoffs" / "013-handoff.md").write_text("x", encoding="utf-8")
    (root / "trace.log").write_text(REVIEWER_WORKING, encoding="utf-8")
    return root


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE bridge_flow_steps "
                 "(flow_key TEXT, from_role TEXT, to_role TEXT)")
    conn.executemany("INSERT INTO bridge_flow_steps VALUES (?,?,?)",
                     [(FLOW, ROLES[0], ROLES[1]), (FLOW, ROLES[1], ROLES[2]),
                      (FLOW, ROLES[2], ROLES[0])])
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def world(bridge, db, monkeypatch):
    """Laguna down and a model resident by default — the interesting half."""
    state = {"laguna": False, "models": ["qwen3.6:35b-a3b-64k"]}
    monkeypatch.setattr(guard, "laguna_up", lambda *a, **k: state["laguna"])
    monkeypatch.setattr(guard, "resident_models", lambda *a, **k: list(state["models"]))
    monkeypatch.setattr(guard.config, "get_bridge_dir", lambda: str(bridge))
    monkeypatch.setattr(guard._state.config, "get_db_path", lambda: db)
    state["bridge"] = bridge
    return state


def _write_verdict(bridge, age_seconds):
    path = bridge / FLOW / "verdicts" / "013-verdict.md"
    path.write_text("**Status:** APPROVED", encoding="utf-8")
    stamp = time.time() - age_seconds
    import os
    os.utime(path, (stamp, stamp))
    return path


class TestWhenItStaysStill:

    def test_implementer_mid_handoff(self, world):
        """v2's exact failure: Laguna down four seconds after a dispatch.

        No verdict exists — the implementer has not even reached the reviewer.
        Stopping its model here destroyed work in run 010.
        """
        world["models"] = ["qwen3.6:27b-q4_K_M"]
        assert guard.failure_state(FLOW, 180) is None

    def test_reviewer_still_working(self, world):
        """Laguna down, reviewer's model loaded, no verdict written yet."""
        assert guard.failure_state(FLOW, 180) is None

    def test_verdict_too_young_to_judge(self, world):
        """A dispatch legitimately takes 40-60 seconds. Do not race it."""
        _write_verdict(world["bridge"], age_seconds=30)
        assert guard.failure_state(FLOW, 180) is None

    def test_verdict_already_delivered(self, world):
        _write_verdict(world["bridge"], age_seconds=600)
        (world["bridge"] / "trace.log").write_text(
            REVIEWER_WORKING + DELIVERED, encoding="utf-8")
        assert guard.failure_state(FLOW, 180) is None

    def test_laguna_up(self, world):
        world["laguna"] = True
        _write_verdict(world["bridge"], age_seconds=600)
        assert guard.failure_state(FLOW, 180) is None

    def test_nothing_resident_is_a_different_failure(self, world):
        world["models"] = []
        _write_verdict(world["bridge"], age_seconds=600)
        assert guard.failure_state(FLOW, 180) is None

    def test_no_active_run(self, world):
        (world["bridge"] / FLOW / "runs" / "010" / "END-REPORT.md").write_text("closed")
        _write_verdict(world["bridge"], age_seconds=600)
        assert guard.failure_state(FLOW, 180) is None

    def test_verdict_below_the_run_floor_is_not_ours(self, world):
        """A verdict from a closed run must not trigger anything."""
        (world["bridge"] / FLOW / "runs" / "010" / "GOAL.md").write_text(
            "**First handoff id: 020**", encoding="utf-8")
        _write_verdict(world["bridge"], age_seconds=600)
        assert guard.failure_state(FLOW, 180) is None


class TestWhenItFires:

    def test_run_009_signature(self, world):
        """Verdict written, aged, no delivery in the trace, model still held."""
        _write_verdict(world["bridge"], age_seconds=600)
        found = guard.failure_state(FLOW, 180)
        assert found["handoff"] == 13
        assert found["models"] == ["qwen3.6:35b-a3b-64k"]
        assert found["verdict_age"] >= 600

    def test_reviewer_never_signalled(self, world):
        """Backlog item 8. Not this guard's problem, but freeing the card is
        still right, and the log distinguishes it."""
        (world["bridge"] / "trace.log").write_text("", encoding="utf-8")
        _write_verdict(world["bridge"], age_seconds=400)
        assert guard.failure_state(FLOW, 180) is not None


class TestLagunaProbe:

    def test_http_error_counts_as_up(self, monkeypatch):
        """A 503 means the server is there and loading — not absent."""
        import urllib.error

        def raise_503(*a, **k):
            raise urllib.error.HTTPError("u", 503, "Loading model", {}, None)

        monkeypatch.setattr(guard.urllib.request, "urlopen", raise_503)
        assert guard.laguna_up() is True

    def test_connection_refused_counts_as_down(self, monkeypatch):
        def refuse(*a, **k):
            raise ConnectionRefusedError()

        monkeypatch.setattr(guard.urllib.request, "urlopen", refuse)
        assert guard.laguna_up() is False


class TestDryRun:
    """A dry run must reach the same decision and touch nothing.

    The point of the mode is to earn trust after two wrong triggers, so the
    thing to prove is that its judgement is identical — only the action is
    withheld.
    """

    def test_reaches_the_same_verdict(self, world, monkeypatch):
        _write_verdict(world["bridge"], age_seconds=600)
        called = []
        monkeypatch.setattr(guard, "free_and_restart",
                            lambda m, log: called.append(m) or True)

        found = guard.failure_state(FLOW, 180)
        assert found is not None          # the decision itself is unchanged
        assert called == []               # and nothing acted on it

    def test_does_not_stop_anything(self, world, monkeypatch, capsys):
        _write_verdict(world["bridge"], age_seconds=600)
        stopped = []
        monkeypatch.setattr(guard.subprocess, "run",
                            lambda *a, **k: stopped.append(a) or None)
        monkeypatch.setattr(sys, "argv",
                            ["laguna_swap_guard.py", "--once", "--dry-run"])
        assert guard.main() == 0
        assert stopped == []
        assert "WOULD stop" in capsys.readouterr().out

    def test_armed_run_does_act(self, world, monkeypatch):
        """The contrast — without --dry-run the same state triggers recovery."""
        _write_verdict(world["bridge"], age_seconds=600)
        called = []
        monkeypatch.setattr(guard, "free_and_restart",
                            lambda m, log: called.append(m) or True)
        monkeypatch.setattr(sys, "argv", ["laguna_swap_guard.py", "--once"])
        assert guard.main() == 0
        assert called == [["qwen3.6:35b-a3b-64k"]]
