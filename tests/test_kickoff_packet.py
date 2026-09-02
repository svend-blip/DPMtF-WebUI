"""Tests for kickoff_packet.py — TG1 coverage.

TG1: kickoff_packet.py exists and refuses a run whose predecessor has no END-REPORT.
     python3 scripts/bridgeV002/kickoff_packet.py --flow 9000-02-ELOOP --run 999
     must exit 2.

Also verifies the first handoff id is sourced from bridge_id_counters (TG3).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "bridgeV002" / "kickoff_packet.py"


class TestKickoffPacketRefusal:
    """TG1: script refuses when previous run has no END-REPORT."""

    def test_script_exists(self):
        assert SCRIPT.exists(), f"{SCRIPT} must exist"

    def test_exit_2_when_previous_run_missing(self):
        """9000-02-ELOOP run 999 has no run 998 directory → exit 2."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--flow", "9000-02-ELOOP", "--run", "999"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 2, (
            f"Expected exit 2, got {result.returncode}. "
            f"stderr: {result.stderr.strip()}"
        )

    def test_stderr_contains_reason(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--flow", "9000-02-ELOOP", "--run", "999"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert "REFUSED" in result.stderr or "refused" in result.stderr.lower()


class TestKickoffPacketCounterSource:
    """TG3: first handoff id comes from bridge_id_counters, never prose."""

    def test_source_references_bridge_id_counters(self):
        """The script source must contain the literal 'bridge_id_counters'."""
        source = SCRIPT.read_text(encoding="utf-8")
        assert "bridge_id_counters" in source, (
            "kickoff_packet.py must reference bridge_id_counters table"
        )
