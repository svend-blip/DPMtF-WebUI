"""Tests for the DPMtF-WebUI oracle against harness-allocator's LaunchSpec+StopSpec.

Run 036 / handoff 136 / D5 — the agreement suite. The oracle is two new
functions in ``scripts/bridgeV002/harness.py``:

  - ``launch_spec(role_config)`` — a thin delegate that resolves the harness
    via the existing ``resolve_harness`` (which applies the opencode fallback
    for harness-less role configs) and returns the standalone's
    ``get_launch_spec`` answer.
  - ``launchspec_disagreements()`` — compares each LaunchSpec + StopSpec
    field against DPMtF's live behaviour, sourced independently of the
    spec (constants imported from DPMtF / allocator source, branches
    transcribed with line-range citations). Returns a list of
    "harness.field: spec=... dpmf=..." strings; empty list means full
    agreement.

The oracle is an ORACLE, not a switch (GOAL.md §(b) header): this test
file asserts the disagreements set is EMPTY today — the run's deliverable
is the evidence that the declared spec matches reality. NOTHING in the
live launch / teardown / watchdog path moves; the oracle is read-only
with respect to behaviour.

Hermetic: no subprocess, no filesystem existence checks, no network, no
env reads (the import surface reads env via _standalone / config, but no
test reads env directly to assert anything live), no live tmux / harness
launch. The harness-allocator package is imported via the same seam
``tests/test_harness_profile_launch.py`` uses (``HARNESS_ALLOCATOR_PATH``
env var setdefault).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

import harness  # noqa: E402


# ── TG5 — the oracle agrees with reality for every registered harness ──


def test_launchspec_disagreements_is_empty():
    """The oracle returns an EMPTY list — every registered harness's
    LaunchSpec + StopSpec matches DPMtF's live behaviour field-by-field.

    This is the run's central evidence: the declared description is honest
    (GOAL.md §(b) header, §1 D5, §2 binding constraints)."""
    disagreements = harness.launchspec_disagreements()
    assert disagreements == [], (
        "the oracle found disagreements between the declared spec and "
        "DPMtF's live behaviour; the spec is wrong until proven otherwise "
        "(GOAL.md §2). Disagreements:\n  "
        + "\n  ".join(disagreements)
    )


# ── launch_spec — thin delegate behaviour ────────────────────────────────


def test_launch_spec_delegates_to_resolved_harness():
    """``launch_spec({'harness': 'dsh'})`` returns the standalone's
    ``get_launch_spec('dsh')`` answer — mode == 'terminal_wrapped' — and
    the returned dict has EXACTLY the five bound LaunchSpec keys."""
    role_config = {"harness": "dsh"}
    spec = harness.launch_spec(role_config)
    expected_keys = {"mode", "needs_initial_prompt", "anchor", "required_env", "activity_markers"}
    assert set(spec.keys()) == expected_keys, (
        f"launch_spec returned keys {sorted(spec.keys())!r}, "
        f"expected exactly {sorted(expected_keys)!r}"
    )
    assert spec["mode"] == "terminal_wrapped", (
        f"launch_spec for dsh has mode {spec['mode']!r}, "
        f"expected 'terminal_wrapped'"
    )


def test_launch_spec_opencode_fallback_for_empty_role_config():
    """``launch_spec({})`` (a harness-less role config) resolves through
    the ``resolve_harness`` opencode fallback (handoff 133 §governance
    applies here too — opencode is the DPMtF-only explicit default), so
    the returned LaunchSpec is the standalone's answer for 'opencode',
    whose mode is 'resident_tui'."""
    role_config = {}
    spec = harness.launch_spec(role_config)
    assert spec["mode"] == "resident_tui", (
        f"launch_spec({{}}) (opencode fallback) has mode {spec['mode']!r}, "
        f"expected 'resident_tui'"
    )


@pytest.mark.parametrize(
    "role_config, expected_harness_key, expected_mode",
    [
        ({"harness": "dsh"}, "dsh", "terminal_wrapped"),
        ({"harness": "codex"}, "codex", "resident_tui"),
        ({"harness": "qwen"}, "qwen", "one_shot"),
        ({"harness": "goose"}, "goose", "one_shot"),
        ({"harness": "crush"}, "crush", "one_shot"),
        ({"harness": "sweagent"}, "sweagent", "one_shot"),
        ({"harness": "aider"}, "aider", "one_shot"),
    ],
)
def test_launch_spec_resolves_each_harness_to_its_declared_mode(
    role_config, expected_harness_key, expected_mode
):
    """``launch_spec`` returns the standalone's LaunchSpec for every named
    harness key — the resolved-harness path is the delegate's only job
    (the orchestrator side picks the harness key; this delegate only
    fetches the spec for that key)."""
    spec = harness.launch_spec(role_config)
    assert spec["mode"] == expected_mode, (
        f"launch_spec for {expected_harness_key!r} has mode "
        f"{spec['mode']!r}, expected {expected_mode!r}"
    )


# ── Disagreement descriptor format (contract sanity) ─────────────────────


def test_launchspec_disagreements_is_a_list_of_str_when_nonempty():
    """If the oracle disagrees, the descriptors are plain strings. We do
    NOT fabricate a non-empty disagreement here (that would falsify the
    evidence); this test just asserts the return-type contract — a list,
    possibly empty."""
    result = harness.launchspec_disagreements()
    assert isinstance(result, list), (
        f"launchspec_disagreements() returned {type(result).__name__}, "
        f"expected list"
    )
    for item in result:
        assert isinstance(item, str), (
            f"launchspec_disagreements() contains non-str item "
            f"{item!r} of type {type(item).__name__}"
        )
