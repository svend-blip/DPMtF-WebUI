"""A Pi pane must be read with Pi's own markers, not OpenCode's.

Two distinct failures are guarded here, and both have precedent in this
project rather than being hypothetical.

`get_pane_command` classifying pi as "claude" would route its prompts down
the raw send-keys branch — no XML stripping, no soft-clear preamble — which
is the shape that left nine consecutive reveng handoffs waiting for a human
to type "continue" on 2026-08-11/12.

Reading a Pi pane with OpenCode's activity markers is the mirror image. Pi's
footer permanently carries a token counter of the form "↑11 ↓81 R1.5k
CH99.3%" once its first turn has finished, and "↓" is one of those markers.
An idle Pi role would read as busy forever — the same false-active reading
that let a dead role sit unrepaired for two hours the same afternoon.
"""

import sys
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002"
sys.path.insert(0, str(BRIDGE))

import dispatch  # noqa: E402


PI_IDLE_PANE = (
    "/tmp/work\n"
    "↑11 ↓81 R1.5k CH99.3% 2.4%/66k (auto)   (llama-local) glm-4.5-air-derestricted\n"
)
PI_BUSY_PANE = (
    "The user wants me to count to five.\n"
    "⠦ Working...\n"
    "/tmp/work\n"
    "0.0%/66k (auto)   (llama-local) glm-4.5-air-derestricted\n"
)


def _as_pane(monkeypatch, tool, tail):
    monkeypatch.setattr(dispatch, "get_pane_command", lambda _s: tool)
    monkeypatch.setattr(dispatch, "_pane_tail", lambda _s: tail.lower())


def test_pi_is_not_classified_as_claude(monkeypatch):
    """pi is a node program; matching "node" first would mislabel it."""
    class _Result:
        returncode = 0
        stdout = "pi\n"

    monkeypatch.setattr(dispatch.subprocess, "run", lambda *a, **k: _Result())
    assert dispatch.get_pane_command("whatever") == "pi"


def test_pi_gets_its_own_activity_markers(monkeypatch):
    monkeypatch.setattr(dispatch, "get_pane_command", lambda _s: "pi")
    assert dispatch.activity_markers("s") == ("working...",)


def test_opencode_markers_are_unchanged(monkeypatch):
    monkeypatch.setattr(dispatch, "get_pane_command", lambda _s: "opencode")
    assert dispatch.activity_markers("s") == dispatch._ACTIVITY_MARKERS


def test_idle_pi_pane_does_not_read_as_busy(monkeypatch):
    """The regression: "↓" in Pi's token counter is not activity."""
    _as_pane(monkeypatch, "pi", PI_IDLE_PANE)
    tail = dispatch._pane_tail("s")

    assert any(m in tail for m in dispatch._ACTIVITY_MARKERS), (
        "fixture no longer reproduces the false positive it exists to cover"
    )
    assert not any(m in tail for m in dispatch.activity_markers("s")), (
        "an idle Pi pane still reads as busy; a stalled Pi role would never "
        "be repaired"
    )


def test_busy_pi_pane_reads_as_busy(monkeypatch):
    _as_pane(monkeypatch, "pi", PI_BUSY_PANE)
    tail = dispatch._pane_tail("s")
    assert any(m in tail for m in dispatch.activity_markers("s"))
