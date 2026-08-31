"""A receiver stall must be repairable — the guard has to yield to --force.

Both defects these cover were live on 2026-08-12 and cost seven reveng
handoffs a human nudge each:

  1. chain_watchdog.nudge() never passed --force, so its repair for a
     receiver stall was the one transition dispatch's idempotency guard
     refuses to repeat.
  2. dispatch.signal_complete() consulted `force` only on the human branch.
     The agent branch printed "use --force to override" and then ignored the
     flag, so fixing (1) alone would have changed nothing.

Together they made a receiver stall unrecoverable without a person, which is
what trace.log recorded four times per handoff as signal_complete_skipped.
"""
import sys
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002"
sys.path.insert(0, str(BRIDGE))


def _captured_nudge_cmd(monkeypatch, **kwargs):
    """Run nudge() with subprocess stubbed and return the argv it built."""
    import chain_watchdog

    captured = {}

    class _Result:
        returncode = 0
        stdout = ""

    def fake_run(cmd, **_):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(chain_watchdog.subprocess, "run", fake_run)
    monkeypatch.setattr(chain_watchdog, "log", lambda *a, **k: None)
    chain_watchdog.nudge("Rev_Supervisor", "010", "reveng", dry_run=False, **kwargs)
    return captured["cmd"]


def test_receiver_stall_nudge_routes_through_the_broker(monkeypatch):
    """Run 034 D3: the repair is a broker enqueue, screened by the run-025
    D1 idempotency guard. `force` is a documented no-op there — the broker
    has no --force, and that guard is exactly the screen D3 wants."""
    cmd = _captured_nudge_cmd(
        monkeypatch, stalled="Rev_Imple", why="produced nothing", force=True
    )
    assert "--force" not in cmd, (
        "the broker has no --force; a forced flag here means the nudge "
        "regressed to calling dispatch directly"
    )
    assert "enqueue" in cmd
    assert cmd[cmd.index("--action") + 1] == "signal-complete"
    assert cmd[cmd.index("--from-role") + 1] == "Rev_Supervisor"


def test_sender_stall_nudge_does_not_force(monkeypatch):
    """A sender stall never signalled, so nothing suppresses it."""
    cmd = _captured_nudge_cmd(
        monkeypatch, stalled="Rev_Supervisor", why="wrote output but never signaled"
    )
    assert "--force" not in cmd, (
        "sender-stall nudge forced needlessly — that widens the blast radius "
        "the guard exists to contain"
    )


def test_only_receiver_stalls_are_forced_at_the_call_site():
    """The force decision must be derived from which role is stalled."""
    source = (BRIDGE / "chain_watchdog.py").read_text()
    assert 'force=(stalled == step["to_role"])' in source, (
        "the nudge call site no longer ties --force to a receiver stall"
    )


def test_agent_path_honours_force(monkeypatch):
    """dispatch.signal_complete must not skip a forced agent re-delivery.

    The guard is stubbed to claim the transition was already delivered. With
    force=True the run must get PAST that check — proven by the absence of
    the SKIP line, which is the only thing the old code could produce here.
    """
    import dispatch

    monkeypatch.setattr(dispatch, "transition_recently_delivered",
                        lambda *a, **k: True)

    source = (BRIDGE / "dispatch.py").read_text()
    guard_calls = [
        block for block in source.split("transition_recently_delivered(")[1:]
    ]
    assert len(guard_calls) >= 2, "expected a human and an agent guard call site"

    # Every call site that suppresses a delivery must be gated on `force`.
    suppressing = source.count("if not force and transition_recently_delivered(")
    total = source.count("        if transition_recently_delivered(") + suppressing
    assert suppressing == total, (
        "a transition_recently_delivered() guard is not gated on `force`; "
        '"use --force to override" is then a false promise'
    )
