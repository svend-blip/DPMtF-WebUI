"""A busy marker means "busy" only in the status bar, not in conversation text.

Measured 2026-08-27, run 015: the Implementer sat idle and was refused for six
minutes because its own output contained the sentence "the signal-send is
refused by design when the reviewer pane has an 'esc interrupt'". The marker
was in line 3 of a 24-line tail; the status bar showed the working directory.

The asymmetry that shapes the fix: a false "busy" costs a refused delivery,
which is retried and visible. A false "idle" injects into a working role and
destroys its turn. So the narrowing applies ONLY when a status bar is
positively identified.
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "bridgeV002"))

from dispatch import busy_search_text  # noqa: E402

BUSY_BAR = "   ⬝⬝⬝⬝⬝⬝⬝⬝  esc interrupt      46.6k (71%)  ctrl+p commands    • opencode 1.18.23"
IDLE_BAR = "   /home/svend/dpmtf-webui        46.6k (71%)  ctrl+p commands    • opencode 1.18.23"
QUOTING = "  the signal-send is refused by design when the reviewer pane has an 'esc interrupt'"


def _tail(*lines):
    return "\n".join(lines)


def test_idle_pane_quoting_the_marker_is_not_busy():
    tail = _tail(QUOTING, "", "  some other output", "", IDLE_BAR)
    assert "esc interrupt" not in busy_search_text(tail, "opencode")


def test_busy_pane_is_still_busy():
    tail = _tail("  ordinary output", "", BUSY_BAR)
    assert "esc interrupt" in busy_search_text(tail, "opencode")


def test_busy_pane_that_also_quotes_the_marker_is_busy():
    tail = _tail(QUOTING, "", BUSY_BAR)
    assert "esc interrupt" in busy_search_text(tail, "opencode")


def test_trailing_blank_lines_do_not_hide_the_status_bar():
    tail = _tail(QUOTING, BUSY_BAR, "", "   ", "")
    assert "esc interrupt" in busy_search_text(tail, "opencode")


def test_unknown_tool_keeps_the_whole_tail():
    """Fail-safe: a tool whose status bar we cannot identify is unchanged."""
    tail = _tail(QUOTING, "", IDLE_BAR)
    assert busy_search_text(tail, "some-other-harness") == tail
    assert "esc interrupt" in busy_search_text(tail, "some-other-harness")


def test_last_line_without_the_signature_falls_back_to_the_whole_tail():
    """If the final line is not a status bar, do not trust it as one."""
    tail = _tail(QUOTING, "", "  a wrapped sentence with no status bar at all")
    assert busy_search_text(tail, "opencode") == tail


def test_empty_tail_is_returned_unchanged():
    assert busy_search_text("", "opencode") == ""
