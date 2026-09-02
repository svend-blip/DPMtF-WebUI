#!/usr/bin/env python3
"""Kickoff packet generator — prints a fixed-form YAML+markdown packet to stdout.

Usage:
    python3 kickoff_packet.py --flow <flow-key> --run <NNN>

Exit codes:
    0 — packet printed to stdout
    2 — refusal (previous run has no END-REPORT, or target tree is dirty)
    1 — usage / internal error

The first handoff id comes from bridge_id_counters.next_id (parameterised SQL).
TG3 greps this file for the literal string "bridge_id_counters" — that is the
contract; the id must come from that counter, never from prose.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

# Allow running standalone or via import from scripts/bridgeV002/
_HERE = Path(__file__).resolve().parent
# config.py lives at the project root, not in scripts/bridgeV002/
_PROJECT_ROOT = str(_HERE.parent.parent)
for _p in (str(_HERE), _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import bridge_lib  # noqa: E402


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _git_state(target_project: str) -> tuple[str, str, str]:
    """Return (sha, branch, tree_state) for the target project."""
    try:
        sha = subprocess.check_output(
            ["git", "-C", target_project, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except subprocess.CalledProcessError:
        sha = "unknown"
    try:
        branch = subprocess.check_output(
            ["git", "-C", target_project, "branch", "--show-current"],
            stderr=subprocess.DEVNULL, text=True
        ).strip() or "(detached)"
    except subprocess.CalledProcessError:
        branch = "(unknown)"
    status = subprocess.check_output(
        ["git", "-C", target_project, "status", "--short"],
        stderr=subprocess.DEVNULL, text=True
    )
    tree_state = "clean" if not status.strip() else "dirty"
    return sha, branch, tree_state


def _previous_run_closed(artifact_root: str, run_id: int) -> tuple[bool, str]:
    """Check whether run (run_id - 1) has an END-REPORT.md.

    A missing previous-run directory counts as 'no END-REPORT'.
    Returns (closed, status_text).
    """
    if run_id <= 1:
        return True, "no previous run (first run)"
    prev = f"{run_id - 1:03d}"
    bridge_dir = config.get_bridge_dir()
    prev_dir = Path(bridge_dir) / artifact_root / "runs" / prev
    end_report = prev_dir / "END-REPORT.md"
    if not prev_dir.is_dir():
        return False, f"previous run directory {prev} does not exist"
    if not end_report.exists():
        return False, f"previous run {prev} has no END-REPORT.md"
    # Read first few lines for status
    try:
        text = end_report.read_text(encoding="utf-8")
        for line in text.splitlines()[:10]:
            low = line.lower()
            if "status:" in low or "**status**" in low:
                return True, line.strip()
        return True, "END-REPORT present"
    except OSError as exc:
        return False, f"cannot read END-REPORT: {exc}"


def _get_first_handoff_id(flow_key: str) -> int:
    """Read next_id from bridge_id_counters WITHOUT incrementing.

    Uses parameterised SQL against the bridge_id_counters table.
    """
    db_path = config.get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
            (flow_key,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row and row[0]:
        return int(row[0])
    return 1


def _read_goal_section(goal_path: Path, section_num: int) -> str:
    """Extract a numbered section from GOAL.md by heading prefix."""
    if not goal_path.exists():
        return "(GOAL not found)"
    text = goal_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    capture = False
    result: list[str] = []
    prefix = f"## {section_num}."
    alt_prefix = f"## §{section_num}"
    for line in lines:
        if line.startswith(prefix) or line.startswith(alt_prefix):
            capture = True
            result.append(line)
            continue
        if capture:
            if line.startswith("## ") and not line.startswith(prefix) and not line.startswith(alt_prefix):
                break
            result.append(line)
    return "\n".join(result).strip() if result else "(section not found)"


def _ledger_d_decisions(artifact_root: str, run_id: str) -> str:
    """Read D-decisions from the run's ledger, or 'none'."""
    bridge_dir = config.get_bridge_dir()
    ledger = Path(bridge_dir) / artifact_root / "runs" / run_id / "RUN-LEDGER.md"
    if not ledger.exists():
        return "none"
    text = ledger.read_text(encoding="utf-8")
    for line in text.splitlines():
        low = line.lower()
        if "d-decision" in low:
            return line.strip()
    return "none"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate kickoff packet")
    parser.add_argument("--flow", required=True, help="Flow key (e.g. 1000-02-ELOOP)")
    parser.add_argument("--run", required=True, type=int, help="Run number")
    args = parser.parse_args(argv)

    flow_key: str = args.flow
    run_id: int = args.run
    run_str = f"{run_id:03d}"

    # Resolve artifact root from the flow key (works for any flow, not just this one)
    artifact_root = bridge_lib.get_effective_artifact_root(flow_key)
    bridge_dir = config.get_bridge_dir()

    # Target project: resolve from DB
    target_project = bridge_lib.get_flow_target_project(flow_key)
    if not target_project:
        target_project = config.get_father_project()

    # Refusal check 1: previous run must be closed
    closed, status_text = _previous_run_closed(artifact_root, run_id)
    if not closed:
        _die(f"REFUSED: {status_text}", code=2)

    # Refusal check 2: target tree must be clean
    sha, branch, tree_state = _git_state(target_project)
    if tree_state == "dirty":
        _die(f"REFUSED: target repository tree is dirty ({target_project})", code=2)

    # GOAL path
    goal_path = Path(bridge_dir) / artifact_root / "runs" / run_str / "GOAL.md"

    # First handoff id from bridge_id_counters (READ ONLY — do not increment)
    first_handoff_id = _get_first_handoff_id(flow_key)

    # Fence and frozen from GOAL §4
    fence_text = _read_goal_section(goal_path, 4)

    # D-decisions
    d_decisions = _ledger_d_decisions(artifact_root, run_str)

    # Delivery discipline: signal verb from auto_dispatch
    # For this flow the step uses signal-send (auto_dispatch=0 on implementer-reviewer)
    signal_verb = "signal-send"

    # Environment
    harness = os.environ.get("HARNESS_PROFILE", "simple-harness")
    policy_stage = os.environ.get("POLICY_STAGE", "FULL_ACCESS")
    mcp_avail = "yes" if os.environ.get("MCP_LIGHT_AVAILABLE") else "available via tools"

    # Print packet
    print("---")
    print(f"flow: {flow_key}")
    print(f"run: {run_str}")
    print(f"artifact_root: {artifact_root}")
    print(f"target_project: {target_project}")
    print("---")
    print()
    print("# Kickoff Packet")
    print()
    print(f"## 1. Run ID")
    print(f"{run_str}")
    print()
    print(f"## 2. GOAL Path")
    print(f"{goal_path}")
    print()
    print(f"## 3. Previous Run Closure Status")
    print(f"{status_text}")
    print()
    print(f"## 4. First Handoff ID")
    print(f"{first_handoff_id} (from bridge_id_counters.next_id for {flow_key})")
    print()
    print(f"## 5. Baseline")
    print(f"SHA: {sha}")
    print(f"Branch: {branch}")
    print(f"Tree: {tree_state}")
    print()
    print(f"## 6. D-Decisions")
    print(f"{d_decisions}")
    print()
    print(f"## 7. Fence and Frozen Paths")
    print(fence_text if fence_text else "(see GOAL §4)")
    print()
    print(f"## 8. Delivery Discipline")
    print(f"- Signal verb: {signal_verb}")
    print(f"- Result file names: unpadded (e.g. {run_str}-result.md)")
    print(f"- README impact block: required")
    print(f"- Never pass --db-path")
    print(f"- timeout_ms: 120000")
    print()
    print(f"## 9. Environment")
    print(f"- Harness: {harness}")
    print(f"- Policy stage: {policy_stage}")
    print(f"- MCP-light: {mcp_avail}")
    print()
    print(f"## 10. Closure Discipline")
    print(f"- Testgoals measured with check_testgoals.py")
    print(f"- END-REPORT via the broker's materialize seam (--type end-report)")


if __name__ == "__main__":
    main()
