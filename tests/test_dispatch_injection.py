"""Tests for inject_prompt / verify_injection_submitted busy/menu guards.

These tests cover Run 006 D6(b) (inject_prompt refuses a busy or menu
pane) and D6(c) (verify_injection_submitted never presses Enter into a
menu/selector pane). All tmux subprocess calls are MOCKED so the suite
runs hermetically with no live tmux session.

The m3 mutation guard (preferred_cloud_harness Run 006 GOAL.md §5)
binds here: removing the menu-refusal condition must make these
tests go RED.

The handoff's required cases (preferred_cloud_harness/handoffs/023):

  a. inject_prompt refuses (does not paste) into a pane whose tail
     shows activity markers (busy pane);
  b. inject_prompt refuses (does not paste) into a pane whose tail
     shows a menu/selector;
  c. inject_prompt proceeds when the pane is idle (no markers, no
     menu);
  d. verify_injection_submitted does NOT send Enter into a
     menu/selector pane;
  e. verify_injection_submitted still resends Enter on a stuck-paste
     hint (non-menu).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Make the bridgeV002 package importable.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))

import dispatch as _dispatch  # noqa: E402


# ── tmux subprocess mock helpers ───────────────────────────────


class _FakeTmuxRun:
    """A mock for dispatch.subprocess.run that simulates a tmux session.

    Records every tmux call so tests can assert which side-effects
    happened. The pane tail (returned by `tmux capture-pane`) is
    configurable per test via `set_pane_tail`.
    """

    def __init__(self) -> None:
        self.pane_tail = ""  # default: empty / idle pane
        self.calls: list[list[str]] = []

    def set_pane_tail(self, tail: str) -> None:
        self.pane_tail = tail

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        # `tmux capture-pane` returns the configured tail.
        if cmd and cmd[0] == "tmux" and "capture-pane" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=self.pane_tail, stderr="",
            )
        # `tmux list-panes` returns "unknown" (no special tool).
        if cmd and cmd[0] == "tmux" and "list-panes" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="unknown", stderr="",
            )
        # Everything else (send-keys, load-buffer, paste-buffer) is a
        # successful no-op.
        return subprocess.CompletedProcess(
            cmd, 0, stdout="", stderr="",
        )


@pytest.fixture()
def fake_tmux(monkeypatch: pytest.MonkeyPatch):
    """Install a FakeTmuxRun as dispatch.subprocess.run."""
    fake = _FakeTmuxRun()
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))
    return fake


def _send_keys_calls(fake: _FakeTmuxRun) -> list[list[str]]:
    """Extract tmux send-keys invocations."""
    return [c for c in fake.calls if c and c[0] == "tmux"
            and "send-keys" in c]


def _paste_buffer_calls(fake: _FakeTmuxRun) -> list[list[str]]:
    """Extract tmux paste-buffer / load-buffer invocations."""
    return [c for c in fake.calls if c and c[0] == "tmux"
            and ("paste-buffer" in c or "load-buffer" in c)]


# ── D6(b): inject_prompt busy/menu/idle guards ─────────────────


def test_inject_prompt_refuses_busy_pane(fake_tmux: _FakeTmuxRun) -> None:
    """inject_prompt refuses to paste into a pane that shows activity
    markers (mid-turn). No load-buffer, no paste-buffer, no send-keys."""
    fake_tmux.set_pane_tail("...")
    # Insert an OpenCode-style activity marker (the default markers set
    # includes 'esc interrupt' — exact substring per dispatch.py).
    fake_tmux.pane_tail = "...\n>>> doing something\n... esc to interrupt\n"

    with pytest.raises(_dispatch.PaneBusyRefused):
        _dispatch.inject_prompt("review-claude-sonnet5", "task body")

    # No paste happened: load-buffer / paste-buffer never invoked.
    assert _paste_buffer_calls(fake_tmux) == []
    assert _send_keys_calls(fake_tmux) == []


def test_inject_prompt_refuses_menu_pane(fake_tmux: _FakeTmuxRun) -> None:
    """inject_prompt refuses to paste into a pane that shows an
    interactive menu/selector (the live failure mode: an Enter would
    select an arbitrary menu option)."""
    # Numbered option list — matches `_MENU_PATTERNS`.
    fake_tmux.set_pane_tail(
        "Choose an action:\n"
        "  1. yes - approve the plan\n"
        "  2. no  - reject and revise\n"
        "  3. cancel\n"
    )

    with pytest.raises(_dispatch.PaneBusyRefused):
        _dispatch.inject_prompt("review-claude-sonnet5", "task body")

    assert _paste_buffer_calls(fake_tmux) == []
    assert _send_keys_calls(fake_tmux) == []


def test_inject_prompt_refuses_y_n_prompt(fake_tmux: _FakeTmuxRun) -> None:
    """A '(y/n)' prompt is also a menu — Enter selects yes/no."""
    fake_tmux.set_pane_tail("Apply this change? (y/n)")

    with pytest.raises(_dispatch.PaneBusyRefused):
        _dispatch.inject_prompt("review-claude-sonnet5", "task body")

    assert _paste_buffer_calls(fake_tmux) == []


def test_inject_prompt_proceeds_on_idle_pane(fake_tmux: _FakeTmuxRun) -> None:
    """inject_prompt proceeds normally when the pane is idle (no
    activity markers, no menu/selector). load-buffer + paste-buffer +
    submit-key send-keys are invoked."""
    fake_tmux.set_pane_tail(
        "task completion footer: model=claude-sonnet-5 session=abc"
    )

    rc = _dispatch.inject_prompt(
        "review-claude-sonnet5", "task body short",
        enter_command="default",
    )
    # Returns None on success.
    assert rc is None
    # load-buffer + paste-buffer + send-keys Enter all happened.
    paste_calls = _paste_buffer_calls(fake_tmux)
    send_calls = _send_keys_calls(fake_tmux)
    assert len(paste_calls) >= 2  # load-buffer + paste-buffer
    assert any("Enter" in c for c in send_calls)


def test_inject_prompt_idle_footer_with_token_totals_is_not_a_menu(
    fake_tmux: _FakeTmuxRun,
) -> None:
    """Idle footers contain generic glyphs and token totals (e.g. the
    Pi footer '↑11 ↓81 R1.5k CH99.3%' contains '↓'). The default
    activity markers deliberately exclude '↓' for Pi to avoid this
    false-active reading. inject_prompt must NOT match the footer as
    a menu or as busy for Claude Code sessions (whose markers do
    include '↓' but the footer DOES NOT)."""
    # Claude Code idle footer (no activity markers from the default set).
    fake_tmux.set_pane_tail(
        "...\n... 1 file changed, ↑42 tokens\n"
        "session=review-claude-sonnet5 model=claude-sonnet-5\n"
    )

    rc = _dispatch.inject_prompt(
        "review-claude-sonnet5", "task body short",
        enter_command="default",
    )
    assert rc is None
    # Paste happened.
    assert _paste_buffer_calls(fake_tmux)


# ── D6(c): verify_injection_submitted guards ───────────────────


def test_verify_injection_does_not_enter_menu_pane(
    fake_tmux: _FakeTmuxRun,
) -> None:
    """verify_injection_submitted must NEVER press Enter into a
    menu/selector pane — that Enter selects an arbitrary option.
    Instead it reports UNCONFIRMED and leaves the pane alone."""
    fake_tmux.set_pane_tail(
        "Choose an action:\n"
        "  1. yes\n"
        "  2. no\n"
    )
    confirmed = _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=3, settle_seconds=0,
    )
    assert confirmed is False
    # No Enter sent into the menu pane.
    enter_calls = [c for c in _send_keys_calls(fake_tmux)
                   if "Enter" in c]
    assert enter_calls == []


def test_verify_injection_still_resends_enter_on_stuck_paste(
    fake_tmux: _FakeTmuxRun,
) -> None:
    """The existing stuck-paste remedy (resending Enter on the
    'paste again to expand' hint) MUST still work — that hint is not
    a menu. Run 006 D6(c) preserves this behavior."""
    fake_tmux.set_pane_tail(
        "... your message is in the buffer — paste again to expand ...\n"
    )
    confirmed = _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=1, settle_seconds=0,
    )
    # The paste-expand hint is NOT a menu, so the existing Enter
    # remedy fires (Enter was sent). The function then returns
    # False because subsequent attempts were not configured; what we
    # assert is that an Enter was actually sent.
    enter_calls = [c for c in _send_keys_calls(fake_tmux)
                   if "Enter" in c]
    assert len(enter_calls) >= 1


def test_verify_injection_returns_true_on_activity(
    fake_tmux: _FakeTmuxRun,
) -> None:
    """When activity markers are present in the pane tail, the verify
    function returns True (the prompt was accepted) and does NOT press
    Enter."""
    fake_tmux.set_pane_tail("... esc to interrupt ...\n")
    confirmed = _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=1, settle_seconds=0,
    )
    assert confirmed is True
    # No Enter sent — activity means the prompt was already accepted.
    enter_calls = [c for c in _send_keys_calls(fake_tmux)
                   if "Enter" in c]
    assert enter_calls == []


# ── shared helpers: panic-on-real-tmux safety ──────────────────


def test_pane_busy_refused_carries_reason() -> None:
    """PaneBusyRefused carries a human-readable reason so the broker's
    REFUSED_INJECTION log line is informative."""
    exc = _dispatch.PaneBusyRefused("pane busy")
    assert "pane busy" in str(exc)


def test_pane_has_menu_or_selector_recognizes_patterns() -> None:
    """The helper recognizes the canonical menu patterns but does NOT
    match ordinary idle footers."""
    # Numbered option.
    assert _dispatch._pane_has_menu_or_selector(
        "Choose:\n  1. yes\n  2. no\n"
    ) is True
    # y/n.
    assert _dispatch._pane_has_menu_or_selector(
        "Apply change? (y/n)"
    ) is True
    # Select prompt.
    assert _dispatch._pane_has_menu_or_selector(
        "Please select an option below:"
    ) is True
    # Idle footer (token totals etc.) — NOT a menu.
    assert _dispatch._pane_has_menu_or_selector(
        "... 1 file changed, ↑42 tokens\n"
    ) is False
    # Empty pane — NOT a menu.
    assert _dispatch._pane_has_menu_or_selector("") is False
