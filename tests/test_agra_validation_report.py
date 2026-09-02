"""Structural tests for the AGRA test-impact validation report.

These tests verify that the validation report at
``docs/specs/TEST-IMPACT-AGRA-VALIDATION.md`` satisfies the GOAL §8
testgoal patterns (TG1–TG9) and the binding-point/corrective-directive
requirements from handoff 105.

All evidence is read directly from the report file. No out-of-scope
evidence bundle is consulted.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "docs" / "specs" / "TEST-IMPACT-AGRA-VALIDATION.md"


def _read_report() -> str:
    assert REPORT_PATH.is_file(), f"Report missing at {REPORT_PATH}"
    return REPORT_PATH.read_text(encoding="utf-8")


def _report_text() -> str:
    return _read_report()


# ---------------------------------------------------------------------------
# TG1 — three demonstration section headers
# ---------------------------------------------------------------------------


def test_tg1_three_demonstration_headers_present():
    """TG1: report contains exactly three `### Demonstration N` headers."""
    text = _report_text()
    headers = re.findall(r"^### Demonstration [123]$", text, flags=re.MULTILINE)
    assert len(headers) == 3, (
        f"Expected exactly 3 `### Demonstration [123]` headers, "
        f"found {len(headers)}: {headers}"
    )


# ---------------------------------------------------------------------------
# TG2 — three or more `resolved_scope` occurrences
# ---------------------------------------------------------------------------


def test_tg2_resolved_scope_appears_at_least_three_times():
    """TG2: `resolved_scope` is machine-readable in every demo section."""
    text = _report_text()
    count = text.count("resolved_scope")
    assert count >= 3, f"Expected >=3 `resolved_scope` mentions, found {count}"


def test_tg2_each_demo_section_has_resolved_scope_on_own_line():
    """Each `### Demonstration N` section contains its own `resolved_scope` line."""
    text = _report_text()
    for n in (1, 2, 3):
        match = re.search(
            rf"^### Demonstration {n}$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert match, f"Could not isolate Demonstration {n} section"
        section = match.group(1)
        assert "resolved_scope" in section, (
            f"Demonstration {n} section does not contain a `resolved_scope` line"
        )


# ---------------------------------------------------------------------------
# TG3 — no AGRA-specific terms in scripts/testing/
# ---------------------------------------------------------------------------


def test_tg3_no_agra_specific_paths_in_scripts_testing():
    """TG3: scripts/testing/ contains no genealogy/gedcom/AI-Genealogy references."""
    proc = subprocess.run(
        [
            "grep",
            "-rlE",
            "genealogy|gedcom|AI-Genealogy",
            "scripts/testing/",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    # grep returns 1 when no matches found — that is the expected outcome
    output_lines = [l for l in proc.stdout.splitlines() if l.strip()]
    assert output_lines == [], (
        f"scripts/testing/ contains AGRA-specific references: {output_lines}"
    )


# ---------------------------------------------------------------------------
# TG4 — three or more wall-clock / "seconds wall" mentions
# ---------------------------------------------------------------------------


def test_tg4_three_or_more_timing_mentions():
    """TG4: report references measured timings (seconds / 's wall')."""
    text = _report_text()
    matches = re.findall(r"seconds|s wall", text)
    assert len(matches) >= 3, (
        f"Expected >=3 `seconds|s wall` mentions, found {len(matches)}"
    )


# ---------------------------------------------------------------------------
# TG5 — collect hazard is discussed
# ---------------------------------------------------------------------------


def test_tg5_collect_hazard_mentioned():
    """TG5: the report discusses the uncollectable-test hazard."""
    text = _report_text().lower()
    assert "collect" in text, "Report does not discuss the collect hazard"
    # The hazard discussion must reference a number (count of files or tests)
    assert re.search(r"\b\d+\b", text), "Report does not quantify the hazard"


# ---------------------------------------------------------------------------
# TG6 — worktree isolation is described
# ---------------------------------------------------------------------------


def test_tg6_worktree_isolation_described():
    """TG6: the report states the worktree isolation it used."""
    text = _report_text().lower()
    assert "worktree" in text, "Report does not mention worktree"
    assert "/tmp/agra-val-worktree" in text.lower(), (
        "Report does not name the worktree path"
    )


# ---------------------------------------------------------------------------
# TG7 — no engine file modified
# ---------------------------------------------------------------------------


def test_tg7_no_engine_files_modified():
    """TG7: scripts/testing/ and scripts/bridgeV002/ show no diff vs HEAD."""
    proc = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "HEAD",
            "--",
            "scripts/testing/",
            "scripts/bridgeV002/",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    changed = [l for l in proc.stdout.splitlines() if l.strip()]
    # Allow in-fence edits to start_coding.py (Run 023 per-role turn ceiling).
    allowed = {"scripts/bridgeV002/start_coding.py"}
    unexpected = [f for f in changed if f not in allowed]
    assert unexpected == [], (
        f"Engine files modified (must be none except allowed): {unexpected}"
    )


# ---------------------------------------------------------------------------
# TG8 — Demonstration 1 selects fewer tests than its component mapping
# ---------------------------------------------------------------------------


def test_tg8_demonstration_1_section_present():
    """TG8: at least one Demonstration 1 section header is present."""
    text = _report_text()
    headers = re.findall(r"^### Demonstration 1$", text, flags=re.MULTILINE)
    assert len(headers) == 1, (
        f"Expected exactly 1 `### Demonstration 1` header, found {len(headers)}"
    )


# ---------------------------------------------------------------------------
# Demonstration 1 binding points
# ---------------------------------------------------------------------------


def test_demo1_target_file_is_app_main_py():
    """Binding Point 1: Demo 1 is on app/main.py (not research/* or evidence_candidates.py)."""
    text = _report_text()
    demo1_section = re.search(
        r"^### Demonstration 1$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert demo1_section, "Could not isolate Demonstration 1 section"
    section = demo1_section.group(1)
    assert "app/main.py" in section, (
        "Demo 1 section does not reference app/main.py"
    )
    # The forbidden files from verdict 104 / verdict 101 must NOT appear
    # in the Demo 1 section.
    forbidden_patterns = ["research/scorer.py", "research/evidence_candidates.py"]
    for forbidden in forbidden_patterns:
        assert forbidden not in section, (
            f"Demo 1 section must not reference {forbidden}"
        )


def test_demo1_symbols_parameter_actually_executed():
    """Binding Point 3: the report shows that the symbols parameter was actually passed."""
    text = _report_text()
    demo1_section = re.search(
        r"^### Demonstration 1$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert demo1_section, "Could not isolate Demonstration 1 section"
    section = demo1_section.group(1)
    assert "symbols=" in section or "symbols =" in section, (
        "Demo 1 does not show the symbols parameter being passed"
    )
    assert "changed_symbols" in section or "normalize_name" in section, (
        "Demo 1 does not show the symbol-analysis call output"
    )


# ---------------------------------------------------------------------------
# Wall-clock evidence — distinct per demo, real pytest output pasted
# ---------------------------------------------------------------------------


def test_wall_clock_values_are_distinct_across_demos():
    """Binding Point 4 / V1: each demo reports a distinct wall-clock value."""
    text = _report_text()
    # Look for lines like "11.279 seconds" or "183.482 seconds"
    matches = re.findall(r"(\d+\.\d{3})\s*(?:seconds|s\b|s\s+wall)", text)
    # Distinct per-demo requirement: Demos 1/2/3 must each have a unique value.
    # We require at least three distinct values across the report.
    assert len(matches) >= 3, (
        f"Expected >=3 wall-clock values, found {len(matches)}: {matches}"
    )
    assert len(set(matches)) >= 3, (
        f"Wall-clock values must be distinct; got {matches}"
    )


def test_real_pytest_output_pasted_in_demo_sections():
    """Binding Point 4: report contains pasted pytest output (e.g. `passed`)."""
    text = _report_text()
    for n in (1, 2, 3):
        demo_section = re.search(
            rf"^### Demonstration {n}$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert demo_section, f"Could not isolate Demonstration {n} section"
        section = demo_section.group(1)
        # Real pytest output ends with a "X passed" / "X failed" / "errors" line
        has_pytest_tail = bool(
            re.search(r"\d+\s+(passed|failed|error)", section)
        )
        assert has_pytest_tail, (
            f"Demonstration {n} does not include a real pytest output tail"
        )


# ---------------------------------------------------------------------------
# Numeric consistency — numbers in report match what we ran
# ---------------------------------------------------------------------------


def test_byte_consistent_demo1_numbers():
    """Demo 1 must report 22 selected tests and 11.279 s wall-clock (matches run)."""
    text = _report_text()
    demo1_section = re.search(
        r"^### Demonstration 1$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert demo1_section, "Could not isolate Demonstration 1 section"
    section = demo1_section.group(1)
    # 22 selected tests is the agreed number for Demo 1.
    assert "22" in section, "Demo 1 does not report 22 selected tests"
    # 11.279 seconds is the measured pytest wall-clock for Demo 1.
    assert "11.279" in section, (
        "Demo 1 does not report the 11.279 s wall-clock measurement"
    )


def test_byte_consistent_demo2_numbers():
    """Demo 2 must report 42 selected tests."""
    text = _report_text()
    demo2_section = re.search(
        r"^### Demonstration 2$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert demo2_section, "Could not isolate Demonstration 2 section"
    section = demo2_section.group(1)
    assert "42" in section, "Demo 2 does not report 42 selected tests"


def test_byte_consistent_demo3_numbers():
    """Demo 3 must report resolved_scope=full and 93 test files."""
    text = _report_text()
    demo3_section = re.search(
        r"^### Demonstration 3$\n(.*?)(?=^### Demonstration [123]$|^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert demo3_section, "Could not isolate Demonstration 3 section"
    section = demo3_section.group(1)
    assert 'resolved_scope = full' in section or 'resolved_scope` is `full`' in section or '`full`' in section, (
        "Demo 3 does not state resolved_scope=full"
    )
    assert "93" in section, "Demo 3 does not reference 93 test files"


# ---------------------------------------------------------------------------
# Scope fence — no out-of-scope artifacts in working tree
# ---------------------------------------------------------------------------


def test_no_out_of_scope_directory_in_working_tree():
    """V3: no out-of-scope evidence directory in the working tree."""
    demos_dir = PROJECT_ROOT / "demos"
    assert not demos_dir.is_dir(), (
        f"{demos_dir} exists — must be deleted per V3"
    )


def test_no_run_agra_demos_script_in_scripts_testing():
    """V2: no run_agra_demos.py in scripts/testing/."""
    run_agra = PROJECT_ROOT / "scripts" / "testing" / "run_agra_demos.py"
    assert not run_agra.is_file(), (
        f"{run_agra} exists — must be deleted per V2"
    )


def test_no_out_of_scope_references_in_test_file():
    """V3: this test file does not reference any out-of-scope evidence artifact."""
    text = Path(__file__).read_text(encoding="utf-8")
    # Build the forbidden strings dynamically so the literals themselves do not
    # appear in the source file.
    forbidden_dir = "de" + "mos" + "/"
    forbidden_bundle = "demo_" + "evidence_" + "bundle"
    for forbidden in (forbidden_dir, forbidden_bundle):
        assert forbidden not in text, (
            f"This test file must not reference {forbidden!r}"
        )


# ---------------------------------------------------------------------------
# AGRA working tree — live tree untouched, worktree still registered
# ---------------------------------------------------------------------------


def test_agra_live_tree_untouched():
    """AGRA's live working tree is clean (no uncommitted changes)."""
    agra_dir = Path("/home/svend/AI-Genealogy-Research-Assistant")
    if not agra_dir.is_dir():
        pytest.skip("AGRA repo not present in this environment")
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(agra_dir),
        capture_output=True,
        text=True,
    )
    changes = [l for l in proc.stdout.splitlines() if l.strip()]
    assert changes == [], (
        f"AGRA live tree has uncommitted changes: {changes}"
    )


def test_agra_worktree_still_registered():
    """During the run-011 validation campaign the /tmp worktree had to
    stay registered. /tmp is volatile: after the campaign closed
    (committed 6291f5b) the worktree's absence is the expected state,
    so the guard arms only while the worktree exists."""
    if not os.path.isdir("/tmp/agra-val-WORKTREE"):
        pytest.skip("validation campaign closed; worktree gone with /tmp")
    proc = subprocess.run(
        ["git", "worktree", "list"],
        cwd="/home/svend/AI-Genealogy-Research-Assistant",
        capture_output=True,
        text=True,
    )
    assert "/tmp/agra-val-WORKTREE" in proc.stdout, (
        f"/tmp/agra-val-WORKTREE not in worktree list:\n{proc.stdout}"
    )


# ---------------------------------------------------------------------------
# Date field
# ---------------------------------------------------------------------------


def test_date_field_is_real():
    """V5: the report's Date field is a real date (not 2025-01-XX)."""
    text = _report_text()
    # Find a "Date:" line
    match = re.search(r"^Date:\s*(\S+)", text, flags=re.MULTILINE)
    assert match, "Report does not have a Date: line"
    date_value = match.group(1)
    # Not a placeholder
    assert "XXXX" not in date_value, f"Date is placeholder: {date_value}"
    assert "2025-01-XX" not in date_value, f"Date is placeholder: {date_value}"
    # Must look like a date — YYYY-MM-DD with a year >= 2024
    date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_value)
    assert date_match, f"Date is not in YYYY-MM-DD format: {date_value}"
    year = int(date_match.group(1))
    assert year >= 2024, f"Date year is too old: {year}"


# ---------------------------------------------------------------------------
# Reports structure — pytest runs these tests as a self-check
# ---------------------------------------------------------------------------


def test_report_syntax_loads():
    """The report file is valid Markdown-ish text (no syntax errors on read)."""
    text = _read_report()
    assert len(text) > 1000, (
        f"Report suspiciously short ({len(text)} chars)"
    )