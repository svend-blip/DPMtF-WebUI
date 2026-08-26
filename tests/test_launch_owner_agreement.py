"""Tests for DPMtF's oracle coverage of the ``launch_owner`` field.

Run 037 — handoff 141 — D5. The DPMtF-side counterpart of the allocator's
``tests/test_launch_owner.py`` (handoff 138 / D2): where D2 binds the two
registries on the allocator side, D5 binds the DPMtF ORACLE
(``scripts/bridgeV002/harness.py::launchspec_disagreements`` /
``_today_behavior``) to the same contract.

Bound requirements (GOAL.md §1 D5, §2 binding constraints, TG4):

- (a) The oracle covers ``launch_owner``: every registered harness's
      today-side LaunchSpec carries the key, and
      ``launchspec_disagreements()`` finds no ``.launch_owner:`` entry.
- (b) Correct derivation — the today-side ``launch_owner`` is
      ``"harness_allocator"`` iff ``harness_allocator.definition.is_native(h)``
      is True, else ``"model_allocator"``. The allocator's
      ``NATIVE_HARNESSES`` is the SEVEN-harness tuple
      ``("dsh","codex","qwen","goose","sweagent","aider","crush")``. A
      regression that falls back to the stale TWO-element
      ``harness.NATIVE_HARNESSES == ("dsh","codex")`` must FAIL — it would
      mark qwen / goose / sweagent / aider / crush as
      ``"model_allocator"`` and disagree with the standalone's spec.
- (c) The roster is DERIVED from the imported tuples — never a hand-listed
      harness name list. A hand-listed roster silently stops covering the
      next adapter someone registers.

The disagreement-descriptor format is ``"<harness>.<field>: spec=... dpmf=..."``,
so any launch_owner disagreement contains the substring ``".launch_owner:"``.

Stdlib + pytest only (the package's standing constraint). HERMETIC: no
subprocess, no filesystem existence checks, no network, no env reads
beyond the import seam's setdefault, no live harness launch. The oracle
reads the standalone's modules in-process; nothing else is touched.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Import seam IDENTICAL to tests/test_launchspec_agreement.py:
#   - PROJECT_ROOT sys.path inserts (root + scripts/bridgeV002)
#   - HARNESS_ALLOCATOR_PATH env var override
#   - `import harness`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

import harness  # noqa: E402

# The allocator submodules live on a path that harness.py resolves lazily
# via ``_standalone()`` (called inside ``launchspec_disagreements`` and the
# other lazy callers). Eagerly trigger it ONCE here at import time so the
# test functions can import the allocator's submodules directly (the same
# seam harness.py uses for its own late imports).
harness._standalone()  # noqa: SLF001 — the test file's job is to exercise the oracle

from harness_allocator.capabilities import (  # noqa: E402
    EXPERIMENTAL_HARNESSES,
    SUPPORTED_HARNESSES,
)
from harness_allocator.definition import is_native  # noqa: E402
from harness_allocator.launchspec import get_launch_spec  # noqa: E402


# ── Derived roster — the contract (GOAL.md §1 D5). NEVER hand-list harness
# names; walk the imported tuples. ───────────────────────────────────────
REGISTERED_HARNESSES = tuple(SUPPORTED_HARNESSES) + tuple(EXPERIMENTAL_HARNESSES)
assert len(REGISTERED_HARNESSES) >= 1, (
    "registered roster must be non-empty — capabilities.py is unread or empty"
)


def _today_modules():
    """The same module bundle ``launchspec_disagreements`` passes into
    ``_today_behavior``: the allocator's submodules (definition, adapter,
    invoke, launchspec) and DPMtF's chain_watchdog + runtime_owner.
    Imported the way ``harness.py`` does — late, after the import seam
    above has populated ``sys.path``."""
    # The allocator submodules first — the import surface inside
    # harness.py does them in this order.
    import harness_allocator.definition  # noqa: F401
    import harness_allocator.adapter  # noqa: F401
    import harness_allocator.invoke  # noqa: F401
    import harness_allocator.launchspec  # noqa: F401
    # Then the DPMtF-side modules _today_behavior takes as arguments.
    import chain_watchdog  # noqa: F401
    import runtime_owner  # noqa: F401
    return (
        harness_allocator.definition,
        harness_allocator.adapter,
        harness_allocator.invoke,
        chain_watchdog,
        runtime_owner,
    )


def test_today_side_launch_owner_is_present_for_every_registered_harness():
    """(c) COVERAGE — the oracle's today-side LaunchSpec carries the
    ``launch_owner`` key for every registered harness. A missing key on
    any registered harness means the oracle silently stopped comparing
    that field, which is the exact failure mode this test exists to
    catch."""
    hdef, hadapter, hinvoke, chain_watchdog, runtime_owner = _today_modules()
    missing = []
    for harness_key in REGISTERED_HARNESSES:
        today = harness._today_behavior(
            harness_key, hdef, hadapter, hinvoke, chain_watchdog, runtime_owner
        )
        launch = today.get("launch", {})
        if "launch_owner" not in launch:
            missing.append(harness_key)
    assert missing == [], (
        "the oracle's today-side LaunchSpec is missing the "
        f"'launch_owner' key for: {missing!r}"
    )


def test_today_side_launch_owner_agrees_with_allocator_is_native():
    """(d) CORRECT DERIVATION — for every registered harness, the
    today-side ``launch_owner`` is ``"harness_allocator"`` iff
    ``harness_allocator.definition.is_native(h)`` is True, else
    ``"model_allocator"``. This binds the DPMtF oracle to the
    SEVEN-harness ``NATIVE_HARNESSES`` — a regression that uses the
    stale TWO-element ``harness.NATIVE_HARNESSES == ("dsh","codex")``
    will mark qwen / goose / sweagent / aider / crush as
    ``"model_allocator"`` and FAIL this assertion."""
    hdef, hadapter, hinvoke, chain_watchdog, runtime_owner = _today_modules()
    mismatches = []
    for harness_key in REGISTERED_HARNESSES:
        today = harness._today_behavior(
            harness_key, hdef, hadapter, hinvoke, chain_watchdog, runtime_owner
        )
        today_owner = today["launch"]["launch_owner"]
        expected_owner = (
            "harness_allocator" if is_native(harness_key) else "model_allocator"
        )
        if today_owner != expected_owner:
            mismatches.append((harness_key, today_owner, expected_owner))
    assert mismatches == [], (
        "today-side launch_owner disagrees with "
        "harness_allocator.definition.is_native for: "
        f"{mismatches!r}"
    )


def test_today_side_launch_owner_matches_standalone_declared_owner():
    """(d, belt-and-braces) The today-side ``launch_owner`` agrees with
    the standalone's ``get_launch_spec(h)['launch_owner']`` for every
    registered harness. Catches a divergence where both sides disagree
    with ``is_native`` in opposite ways — the oracle's coverage test
    (next test) would still pass, but the today side would be lying
    about both the spec AND the registry."""
    hdef, hadapter, hinvoke, chain_watchdog, runtime_owner = _today_modules()
    mismatches = []
    for harness_key in REGISTERED_HARNESSES:
        today = harness._today_behavior(
            harness_key, hdef, hadapter, hinvoke, chain_watchdog, runtime_owner
        )
        today_owner = today["launch"]["launch_owner"]
        spec_owner = get_launch_spec(harness_key)["launch_owner"]
        if today_owner != spec_owner:
            mismatches.append((harness_key, today_owner, spec_owner))
    assert mismatches == [], (
        "today-side launch_owner disagrees with the standalone spec for: "
        f"{mismatches!r}"
    )


def test_oracle_finds_no_launch_owner_disagreement():
    """(e) NO DISAGREEMENT — ``launchspec_disagreements()`` returns an
    empty list today, and at minimum contains no ``.launch_owner:``
    entry. This is the central evidence: the oracle's today-side
    derivation matches the standalone's declared LaunchSpec for every
    field, including ``launch_owner``."""
    disagreements = harness.launchspec_disagreements()
    launch_owner_disagreements = [
        d for d in disagreements if ".launch_owner:" in d
    ]
    assert launch_owner_disagreements == [], (
        "the oracle found launch_owner disagreements:\n  "
        + "\n  ".join(launch_owner_disagreements)
    )


def test_oracle_is_fully_agreed_today():
    """(e, full) The oracle's full disagreements list is empty today —
    the run's central evidence (matches the binding in
    ``test_launchspec_agreement.py::test_launchspec_disagreements_is_empty``).
    Asserted again here so a regression that adds a non-launch_owner
    disagreement doesn't sneak past the focused test above."""
    disagreements = harness.launchspec_disagreements()
    assert disagreements == [], (
        "the oracle found disagreements between the declared spec and "
        "DPMtF's live behaviour; the spec is wrong until proven otherwise "
        "(GOAL.md §2). Disagreements:\n  "
        + "\n  ".join(disagreements)
    )
