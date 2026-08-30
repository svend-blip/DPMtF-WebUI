"""Frozen-literal regression suite for retired LaunchSpec/StopSpec fields.

Run 041 D4 (GOAL.md §1 D4, §2 honesty rule) -- the oracle RETIRES the
compared field set when a field's today-side now reads the spec (so the
oracle would agree with itself vacuously). Every retired field gets a
hand-written TODAY value in this file, and the regression contract is:

    ``get_launch_spec(h)[<field>] == <frozen literal>``

A future spec edit that changes a retired field turns the matching test
RED -- the frozen literal replaces the disagreement path the oracle used
to provide. The literal side is HAND-WRITTEN, never imported from the
spec or from ``start_coding`` / ``chain_watchdog`` / ``runtime_owner``
(reading the spec to COMPARE against the literal is exactly the point;
the LITERAL side must be independent of the spec).

Retired fields (every retired field has a frozen table here):
  - Launch `mode`
  - Launch `needs_initial_prompt`
  - Launch `anchor`
  - Launch `activity_markers`
  - Stop `signals`, `grace_seconds`, `verify` for RESIDENT harnesses only
    (terminal_wrapped + one_shot stop fields are STILL compared; their
    today-side reads invoke.py's cancel ladder, which is OUT of scope
    and unchanged -- the oracle still guards them).

Fields STILL compared by the oracle (and therefore NOT in this file):
  - Launch `required_env` (and the launch_owner field).

Import seam identical to tests/test_launchspec_agreement.py: PROJECT_ROOT
sys.path inserts, ``os.environ.setdefault("HARNESS_ALLOCATOR_PATH", ...)``,
``import harness``, ``harness._standalone()``, then the allocator
submodule imports. The roster is DERIVED
(``tuple(SUPPORTED_HARNESSES) + tuple(EXPERIMENTAL_HARNESSES)``), never
hand-listed -- a missing entry in the frozen tables is a hard assertion
failure, not a skip.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

import harness  # noqa: E402

# Eagerly trigger _standalone() so the allocator submodules below resolve.
harness._standalone()  # noqa: SLF001 -- same import seam the agreement tests use

from harness_allocator.capabilities import (  # noqa: E402
    EXPERIMENTAL_HARNESSES,
    SUPPORTED_HARNESSES,
)
from harness_allocator.launchspec import (  # noqa: E402
    get_launch_spec,
    get_stop_spec,
)

# DERIVED roster -- never hand-list harness names.
REGISTERED = tuple(SUPPORTED_HARNESSES) + tuple(EXPERIMENTAL_HARNESSES)
assert len(REGISTERED) >= 1, (
    "registered roster must be non-empty -- capabilities.py is unread or empty"
)


# ── FROZEN LITERALS (hand-written TODAY's values; NEVER imported from the
# spec or the consuming code; the comparison side reads the spec via
# get_launch_spec / get_stop_spec below) ───────────────────────────────────

_FROZEN_MODE = {
    "dsh": "terminal_wrapped",
    "codex": "resident_tui", "claude-code": "resident_tui", "opencode": "resident_tui",
    "qwen": "one_shot", "goose": "one_shot", "crush": "one_shot",
    "sweagent": "one_shot", "aider": "one_shot",
    # Roster growth after the freeze: whip (run 020/023) and simple-harness
    # (the eleventh harness) — frozen 2026-08-30 from the live spec.
    "whip": "one_shot", "simple-harness": "one_shot",
}
_FROZEN_NEEDS_INITIAL_PROMPT = {
    "dsh": True,
    "codex": False, "claude-code": False, "opencode": False,
    "qwen": False, "goose": False, "crush": False, "sweagent": False, "aider": False,
    "whip": False, "simple-harness": False,
}
_FROZEN_ANCHOR = {
    "codex": "child",
    "dsh": "none", "claude-code": "none", "opencode": "none",
    "qwen": "none", "goose": "none", "crush": "none", "sweagent": "none", "aider": "none",
    "whip": "none", "simple-harness": "none",
}
# Every harness today declares the same three markers -- the SORTED union
# is what chain_watchdog._derive_activity_markers() returns.
_FROZEN_ACTIVITY_MARKERS = ["esc interrupt", "esc to interrupt", "\u2193"]
# Resident stop (consumed by runtime_owner._kill_by_spec in D2): int 3, NOT 3.0.
_FROZEN_RESIDENT_STOP = {"signals": ["SIGTERM"], "grace_seconds": 3, "verify": "pid_gone"}


# ── Tests (plain ``==`` comparisons so the failure message names the
# divergence; a future spec edit that changes a retired field goes red
# here) ───────────────────────────────────────────────────────────────────


def test_frozen_mode_matches_spec_for_every_harness():
    """Launch `mode` retired field still equals the frozen literal for every harness."""
    for h in REGISTERED:
        assert h in _FROZEN_MODE, f"missing frozen mode for {h!r}"
        assert get_launch_spec(h)["mode"] == _FROZEN_MODE[h], (
            f"spec mode for {h!r} disagrees with frozen literal: "
            f"spec={get_launch_spec(h)['mode']!r}, literal={_FROZEN_MODE[h]!r}"
        )


def test_frozen_needs_initial_prompt_matches_spec():
    """Launch `needs_initial_prompt` retired field still equals the frozen literal."""
    for h in REGISTERED:
        assert h in _FROZEN_NEEDS_INITIAL_PROMPT, (
            f"missing frozen needs_initial_prompt for {h!r}"
        )
        assert (
            get_launch_spec(h)["needs_initial_prompt"]
            == _FROZEN_NEEDS_INITIAL_PROMPT[h]
        ), (
            f"spec needs_initial_prompt for {h!r} disagrees with frozen literal"
        )


def test_frozen_anchor_matches_spec():
    """Launch `anchor` retired field still equals the frozen literal."""
    for h in REGISTERED:
        assert h in _FROZEN_ANCHOR, f"missing frozen anchor for {h!r}"
        assert get_launch_spec(h)["anchor"] == _FROZEN_ANCHOR[h], (
            f"spec anchor for {h!r} disagrees with frozen literal"
        )


def test_frozen_activity_markers_match_spec():
    """Launch `activity_markers` retired field still equals the (sorted) frozen literal."""
    for h in REGISTERED:
        spec_markers = sorted(get_launch_spec(h)["activity_markers"])
        assert spec_markers == sorted(_FROZEN_ACTIVITY_MARKERS), (
            f"spec activity_markers for {h!r} disagrees with frozen literal: "
            f"spec={spec_markers!r}, literal={sorted(_FROZEN_ACTIVITY_MARKERS)!r}"
        )


def test_frozen_resident_stop_matches_spec():
    """Stop `signals`/`grace_seconds`/`verify` retired for resident harnesses equals the frozen literal.

    Iterates ONLY the resident-tui harnesses (where the retired stop fields
    live -- terminal_wrapped + one_shot stop fields are STILL compared by
    the oracle and are NOT in this suite).
    """
    resident = [h for h in REGISTERED if _FROZEN_MODE[h] == "resident_tui"]
    assert resident, "no resident harnesses in the frozen mode table"
    for h in resident:
        spec = get_stop_spec(h)
        assert spec["signals"] == _FROZEN_RESIDENT_STOP["signals"], (
            f"spec stop signals for {h!r} disagrees: "
            f"spec={spec['signals']!r}, literal={_FROZEN_RESIDENT_STOP['signals']!r}"
        )
        assert spec["grace_seconds"] == _FROZEN_RESIDENT_STOP["grace_seconds"], (
            f"spec stop grace_seconds for {h!r} disagrees: "
            f"spec={spec['grace_seconds']!r}, literal={_FROZEN_RESIDENT_STOP['grace_seconds']!r}"
        )
        assert spec["verify"] == _FROZEN_RESIDENT_STOP["verify"], (
            f"spec stop verify for {h!r} disagrees: "
            f"spec={spec['verify']!r}, literal={_FROZEN_RESIDENT_STOP['verify']!r}"
        )
