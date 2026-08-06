"""Tests for the failed-swap recovery guard.

The guard stops a resident model and restarts Laguna, so the property that
matters is not that it fires — it is that it stays still. Laguna is down for
most of every cycle while a worker model has the card, and firing then would
kill work in progress.

The first version of this guard waited for a trace-log signal and therefore
never fired at all: the signal is written after the model swap it was meant to
protect, so a dispatch that dies on the swap produces none. These tests are
written against the state combinations instead.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE = (Path(__file__).resolve().parent.parent
           / "scripts" / "bridgeV002" / "laguna_swap_guard.py")
_spec = importlib.util.spec_from_file_location("laguna_swap_guard", _MODULE)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

SESSION = "supervisor01_llama"


@pytest.fixture
def world(monkeypatch):
    """Set the three observable conditions independently."""
    state = {"laguna": True, "blocked": False, "models": []}
    monkeypatch.setattr(guard, "laguna_up", lambda *a, **k: state["laguna"])
    monkeypatch.setattr(guard, "supervisor_blocked", lambda s: state["blocked"])
    monkeypatch.setattr(guard, "resident_models", lambda *a, **k: list(state["models"]))
    return state


class TestWhenItStaysStill:

    def test_laguna_up_never_fires(self, world):
        """The common healthy case, whatever else is true."""
        world.update(laguna=True, blocked=True, models=["qwen3.6:35b-a3b-64k"])
        assert guard.failure_state(SESSION) is None

    def test_worker_running_normally_does_not_fire(self, world):
        """THE case that matters.

        Laguna is down for most of every cycle while imple01SG or review01SG
        has the card. The supervisor is idle and silent. Stopping the worker's
        model here would destroy the handoff in progress.
        """
        world.update(laguna=False, blocked=False, models=["qwen3.6:27b-q4_K_M"])
        assert guard.failure_state(SESSION) is None

    def test_nothing_resident_does_not_fire(self, world):
        """Laguna down and the supervisor blocked, but no model to free.

        A different failure — the allocator refused, the binary is missing,
        the port is taken. There is nothing this guard can usefully do, and
        guessing would make it harder to diagnose.
        """
        world.update(laguna=False, blocked=True, models=[])
        assert guard.failure_state(SESSION) is None

    def test_quiet_machine_does_not_fire(self, world):
        world.update(laguna=False, blocked=False, models=[])
        assert guard.failure_state(SESSION) is None


class TestWhenItFires:

    def test_all_three_conditions(self, world):
        """Runs 006 and 009: laguna down, supervisor awake and erroring,
        the reviewer's model still holding the card."""
        world.update(laguna=False, blocked=True, models=["qwen3.6:35b-a3b-64k"])
        assert guard.failure_state(SESSION) == ["qwen3.6:35b-a3b-64k"]

    def test_reports_every_resident_model(self, world):
        world.update(laguna=False, blocked=True,
                     models=["qwen3.6:35b-a3b-64k", "qwen3-coder:30b-256k"])
        assert len(guard.failure_state(SESSION)) == 2


class TestSupervisorBlockedDetection:

    @pytest.mark.parametrize("pane,expected", [
        ("API Error: Unable to connect to API (ConnectionRefused)", True),
        ("API Error: 503 Loading model. This is a server-side issue", True),
        ("✻ Concocting… (20m 33s · ↓ 14.8k tokens)", False),
        ("● Verdict 012 written and signal-complete sent.", False),
        ("", False),
    ])
    def test_markers(self, monkeypatch, pane, expected):
        class Result:
            returncode = 0
            stdout = pane
        monkeypatch.setattr(guard.subprocess, "run", lambda *a, **k: Result())
        assert guard.supervisor_blocked(SESSION) is expected

    def test_missing_session_is_not_blocked(self, monkeypatch):
        """A dead session is a different problem; do not act on it."""
        class Result:
            returncode = 1
            stdout = ""
        monkeypatch.setattr(guard.subprocess, "run", lambda *a, **k: Result())
        assert guard.supervisor_blocked(SESSION) is False


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
