"""Regression tests for chain_watchdog run-id derivation.

latest_generic_id() converted the newest {ID} through int() and back with
str(), stripping zero-padding ("058" on disk became "58"). Every downstream
consumer builds strings from the run id — step_deliverable() paths
("58-handoff.md" never exists), trace.log needles ("| 58 |" never matches
"| 058 |"), and nudge --id — so for padded runs the watchdog could neither
see deliverables, detect the final signal ("complete"), nor time stalls.
Observed live on supervised_review runs 057/058 (2026-08-01): the watchdog
reported "active"/"idle" forever after chain completion.

The id must be returned EXACTLY as written on disk.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

import chain_watchdog


def _steps_for(tmp_path):
    return [{"dir": str(tmp_path), "pattern": "{ID}-handoff.md",
             "from_role": "supervisor_auto", "to_role": "imple01sup"}]


def test_padded_id_preserved(tmp_path):
    """Zero-padded ids on disk come back zero-padded ("058", not "58")."""
    (tmp_path / "057-handoff.md").write_text("x", encoding="utf-8")
    (tmp_path / "058-handoff.md").write_text("x", encoding="utf-8")
    assert chain_watchdog.latest_generic_id(_steps_for(tmp_path)) == "058"


def test_unpadded_id_preserved(tmp_path):
    """Legacy unpadded ids keep working unchanged."""
    (tmp_path / "5-handoff.md").write_text("x", encoding="utf-8")
    (tmp_path / "21-handoff.md").write_text("x", encoding="utf-8")
    assert chain_watchdog.latest_generic_id(_steps_for(tmp_path)) == "21"


def test_numeric_comparison_beats_lexicographic(tmp_path):
    """Newest is picked numerically: 102 > 099 even though '099' < '102'
    holds lexicographically too — but '99' vs '102' does not."""
    (tmp_path / "99-handoff.md").write_text("x", encoding="utf-8")
    (tmp_path / "102-handoff.md").write_text("x", encoding="utf-8")
    assert chain_watchdog.latest_generic_id(_steps_for(tmp_path)) == "102"


def test_non_matching_files_ignored(tmp_path):
    """current.md and other non-pattern files never become run ids."""
    (tmp_path / "current.md").write_text("x", encoding="utf-8")
    assert chain_watchdog.latest_generic_id(_steps_for(tmp_path)) is None
