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


class TestPredecessorRule:
    """The predecessor is the highest existing run below N, not N-1 (024 -> 027 is a real order)."""

    def _mod(self):
        import importlib
        sys.path.insert(0, str(ROOT / "scripts" / "bridgeV002"))
        sys.path.insert(0, str(ROOT / "scripts"))
        return importlib.import_module("kickoff_packet")

    def test_predecessor_skips_missing_numbers(self, tmp_path, monkeypatch):
        kp = self._mod()
        runs = tmp_path / "fam" / "runs"
        (runs / "024").mkdir(parents=True)
        (runs / "024" / "END-REPORT.md").write_text("# END-REPORT\n**Status: SUCCESS**\n")
        monkeypatch.setattr(kp.config, "get_bridge_dir", lambda: str(tmp_path))
        closed, text = kp._previous_run_closed("fam", 27)
        assert closed is True
        assert "024" in text and "SUCCESS" in text

    def test_open_predecessor_refuses(self, tmp_path, monkeypatch):
        kp = self._mod()
        runs = tmp_path / "fam" / "runs"
        (runs / "024").mkdir(parents=True)
        (runs / "024" / "END-REPORT.md").write_text("**Status: SUCCESS**\n")
        (runs / "025").mkdir()  # open run, no END-REPORT
        monkeypatch.setattr(kp.config, "get_bridge_dir", lambda: str(tmp_path))
        closed, text = kp._previous_run_closed("fam", 27)
        assert closed is False and "025" in text

    def test_no_lower_run_is_first_run(self, tmp_path, monkeypatch):
        kp = self._mod()
        (tmp_path / "fam" / "runs" / "030").mkdir(parents=True)
        monkeypatch.setattr(kp.config, "get_bridge_dir", lambda: str(tmp_path))
        closed, text = kp._previous_run_closed("fam", 27)
        assert closed is True and "first run" in text

    def test_father_db_is_not_dirt(self, tmp_path, monkeypatch):
        """databases/dpmtf.db modified alone must read as a clean tree."""
        import subprocess as sp
        kp = self._mod()
        repo = tmp_path / "repo"
        (repo / "databases").mkdir(parents=True)
        sp.run(["git", "init", "-q", str(repo)], check=True)
        db = repo / "databases" / "dpmtf.db"
        db.write_text("v1")
        sp.run(["git", "-C", str(repo), "add", "."], check=True)
        sp.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
        db.write_text("v2")
        monkeypatch.setattr(kp.config, "get_db_path", lambda: str(db))
        _sha, _branch, state = kp._git_state(str(repo))
        assert state == "clean"
        (repo / "other.txt").write_text("x")
        assert kp._git_state(str(repo))[2] == "dirty"
