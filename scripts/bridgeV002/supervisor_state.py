"""One-shot state report for a flow's supervisor.

Rebuilding context used to be about ten shell commands with reasoning between
each: resolve the bridge directory, find the active run, read GOAL/ledger/
backlog, read the counter, work out which handoffs belong to this run, check
whether anything is running. All of it is deterministic, and on a slow local
model the reasoning between the commands costs more than the commands do —
measured at 7 to 35 minutes from cold start to first dispatch across runs
005-008, against a worker chain that completes a full cycle in six.

This answers all of it at once, and applies the run floor while doing so.
`chain_watchdog` cannot: it locks onto the newest handoff id on disk
regardless of which run owns it, which is how run 004 adopted run 003's
handoff and parked on a budget that was already spent.

Read-only. It opens the database, reads files and probes two local ports; it
writes nothing and dispatches nothing.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

# "**First handoff id: 011**", "First handoff id: 11", with or without markup.
_FIRST_ID = re.compile(r"First handoff id:\s*\**\s*(\d+)", re.IGNORECASE)
_HANDOFF_FILE = re.compile(r"^(\d+)-handoff\.md$")


def _probe(url, timeout=3):
    """True if the URL answers at all. A 503 still means something is there."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def _tmux_sessions(names):
    out = {}
    for name in names:
        rc = subprocess.run(
            ["tmux", "has-session", "-t", name],
            capture_output=True,
        ).returncode
        out[name] = rc == 0
    return out


def run_dir(bridge_dir, flow_key):
    return Path(bridge_dir) / flow_key / "runs"


def active_run(bridge_dir, flow_key):
    """Newest run directory without an END-REPORT.md, or None.

    Sorted by name, which is why runs are numbered rather than named.
    """
    base = run_dir(bridge_dir, flow_key)
    if not base.is_dir():
        return None
    runs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name)
    for path in reversed(runs):
        if not (path / "END-REPORT.md").exists():
            return path
    return None


def first_handoff_id(run_path):
    """The run's floor, from GOAL.md, falling back to the opening ledger entry.

    Returns None when neither states it — which means the run must not adopt
    whatever happens to be on disk. Ask instead.
    """
    for name in ("GOAL.md", "RUN-LEDGER.md"):
        path = run_path / name
        if not path.exists():
            continue
        match = _FIRST_ID.search(path.read_text(encoding="utf-8"))
        if match:
            return int(match.group(1))
    return None


def flow_counter(flow_key, db_path=None):
    conn = sqlite3.connect(db_path or config.get_db_path())
    try:
        row = conn.execute(
            "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
            (flow_key,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def handoffs_at_or_above(bridge_dir, flow_key, floor):
    """Handoff ids this run owns. Everything below the floor is a closed run's."""
    base = Path(bridge_dir) / flow_key / "handoffs"
    if not base.is_dir():
        return []
    ids = []
    for path in base.iterdir():
        match = _HANDOFF_FILE.match(path.name)
        if match:
            value = int(match.group(1))
            if floor is None or value >= floor:
                ids.append(value)
    return sorted(ids)


def deliverables_for(bridge_dir, flow_key, handoff_id):
    """Which of the three chain artefacts exist for one handoff."""
    base = Path(bridge_dir) / flow_key
    padded = f"{handoff_id:03d}"
    return {
        "handoff": (base / "handoffs" / f"{padded}-handoff.md").exists(),
        "result": (base / "results" / f"{padded}-result.md").exists(),
        "verdict": (base / "verdicts" / f"{padded}-verdict.md").exists(),
    }


def last_trace_signal(bridge_dir, flow_key, handoff_id, db_path=None):
    """The final trace line for this handoff, or None.

    The trace is flow-wide and spans every era of the bridge, so the id alone
    is not enough to match on — ids repeat across flows. Require the flow's
    role names on the line too.
    """
    path = Path(bridge_dir) / "trace.log"
    if not path.exists():
        return None

    roles = flow_role_keys(flow_key, db_path=db_path)
    padded = f"{handoff_id:03d}"
    found = None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4 or parts[2] != padded:
                continue
            # The id alone is not enough: trace.log spans every flow and every
            # era of the bridge, and ids repeat. On 2026-08-06 a grep for
            # " 009 " matched entries from 2026-06-14's claude-bridge. Require
            # one of this flow's own role keys on the line.
            if any(role in parts[1] for role in roles):
                found = line.strip()
    return found


def flow_role_keys(flow_key, db_path=None):
    """Role keys belonging to a flow, from its steps."""
    conn = sqlite3.connect(db_path or config.get_db_path())
    try:
        rows = conn.execute(
            "SELECT from_role, to_role FROM bridge_flow_steps WHERE flow_key = ?",
            (flow_key,),
        ).fetchall()
    finally:
        conn.close()
    return {role for row in rows for role in row if role}


def collect(flow_key):
    bridge_dir = config.get_bridge_dir()
    run_path = active_run(bridge_dir, flow_key)

    state = {
        "flow": flow_key,
        "bridge_dir": bridge_dir,
        "project_root": config.get_project_root(),
        "run": None,
        "artefacts": {},
        "first_handoff_id": None,
        "counter": flow_counter(flow_key),
        "owned_handoffs": [],
        "current": None,
        "deliverables": {},
        "last_signal": None,
        "environment": {},
        "assessment": None,
        "missing": [],
    }

    if run_path is not None:
        state["run"] = run_path.name
        state["artefacts"] = {
            name: (run_path / name).exists()
            for name in ("GOAL.md", "RUN-LEDGER.md", "BACKLOG.md", "END-REPORT.md")
        }
        state["first_handoff_id"] = first_handoff_id(run_path)

    floor = state["first_handoff_id"]
    # With no active run there is nothing to own. Listing every handoff on
    # disk would invite exactly the mistake the floor exists to prevent.
    if run_path is not None:
        state["owned_handoffs"] = handoffs_at_or_above(bridge_dir, flow_key, floor)
    if state["owned_handoffs"]:
        state["current"] = state["owned_handoffs"][-1]
        state["deliverables"] = deliverables_for(bridge_dir, flow_key, state["current"])
        state["last_signal"] = last_trace_signal(bridge_dir, flow_key, state["current"])

    state["environment"] = {
        "webui": _probe(f"http://localhost:{config.get_port()}/api/health"),
        "database": Path(config.get_db_path()).exists(),
        "laguna": _probe("http://127.0.0.1:8080/health"),
        "tmux": _tmux_sessions(["supervisor01_llama", "imple01SG", "review01SG"]),
    }

    state["missing"], state["assessment"] = _assess(state)
    return state


def _assess(state):
    """What is missing, and the one-line conclusion. Order matters."""
    missing = []

    if state["run"] is None:
        return (["no active run — every run directory has an END-REPORT"],
                "NO ACTIVE RUN — a new run needs a Human-approved GOAL.md")

    if not state["artefacts"].get("GOAL.md"):
        missing.append("GOAL.md — the run has no Mission Contract")
        return missing, "PARK — a run without an approved GOAL.md must not start"

    if state["first_handoff_id"] is None:
        missing.append("First handoff id — stated in neither GOAL.md nor the ledger")
        return missing, "PARK — without a floor this run cannot tell its work from a closed run's"

    env = state["environment"]
    for name, ok in env["tmux"].items():
        if not ok:
            missing.append(f"tmux session {name} is not running")
    if not env["laguna"]:
        missing.append("laguna-local is not reachable on :8080")
    if not env["webui"]:
        missing.append(f"WebUI is not answering on :{config.get_port()}")

    if not state["artefacts"].get("BACKLOG.md"):
        missing.append("BACKLOG.md — author it as the first action")

    if not state["owned_handoffs"]:
        return missing, ("RUN OPENED, CHAIN NOT STARTED — author BACKLOG.md and "
                         "dispatch the first handoff per GOAL.md Standing Approvals")

    d = state["deliverables"]
    current = state["current"]
    if d.get("verdict"):
        return missing, (f"VERDICT READY for {current:03d} — validate the testgoals "
                         f"yourself, then act per 461")
    if d.get("result"):
        return missing, f"RESULT DELIVERED for {current:03d} — the reviewer is working"
    return missing, f"HANDOFF {current:03d} DISPATCHED — the implementer is working"


def render(state):
    lines = []
    add = lines.append
    add(f"Flow            {state['flow']}")
    add(f"Bridge dir      {state['bridge_dir']}")
    add(f"Active run      {state['run'] or '(none)'}")

    if state["artefacts"]:
        present = [n for n, ok in state["artefacts"].items() if ok]
        absent = [n for n, ok in state["artefacts"].items() if not ok]
        add(f"  present       {', '.join(present) or '(none)'}")
        add(f"  absent        {', '.join(absent) or '(none)'}")

    floor = state["first_handoff_id"]
    add(f"First handoff   {floor if floor is not None else '(NOT STATED)'}")
    add(f"Flow counter    {state['counter']}")

    owned = state["owned_handoffs"]
    add(f"This run's ids  {', '.join(f'{i:03d}' for i in owned) if owned else '(none yet)'}")
    if floor is not None:
        add(f"                ids below {floor:03d} belong to a closed run — ignore them")

    if state["current"] is not None:
        d = state["deliverables"]
        have = [k for k, ok in d.items() if ok]
        add(f"Current {state['current']:03d}      {', '.join(have) or '(nothing written)'}")
        add(f"Last signal     {state['last_signal'] or '(none in trace.log)'}")

    env = state["environment"]
    tmux = ", ".join(f"{n}{'' if ok else ' NOT RUNNING'}" for n, ok in env["tmux"].items())
    add(f"WebUI           {'ok' if env['webui'] else 'NOT ANSWERING'}")
    add(f"Database        {'ok' if env['database'] else 'MISSING'}")
    add(f"laguna-local    {'reachable' if env['laguna'] else 'NOT REACHABLE'}")
    add(f"tmux            {tmux}")

    if state["missing"]:
        add("Missing")
        for item in state["missing"]:
            add(f"  - {item}")

    add(f"Assessment      {state['assessment']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--flow", default="llama_SG", help="Flow key (default: llama_SG)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report")
    args = parser.parse_args()

    state = collect(args.flow)
    print(json.dumps(state, indent=2) if args.json else render(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
