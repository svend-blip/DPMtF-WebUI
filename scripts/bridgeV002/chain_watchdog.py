#!/usr/bin/env python3
"""Chain watchdog for the trade cockpit flow (hardening phase 1b).

Detects the recurring stall pattern — a role wrote its output file but
never ran signal-complete (observed flows 062/064) — and auto-nudges the
chain with the correct normalized --id. Also samples `ollama ps` each
cycle so context allocation and GPU/CPU split are logged per run
(context-tuning observability).

Runs alongside a flow (started by trade-cronjob.sh), never as a standing
service:  python3 chain_watchdog.py --loop-seconds 60 --max-minutes 90
Single pass for ad-hoc use: --once
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import config  # Father config — trade inbox dir, db path

FLOW_KEY = "trade_cockpit_simulation_v001"
# Chain order (matches bridge_flow_steps; kept inline so the watchdog has
# no hard DB dependency at 09:00 — verified against DB in tests).
CHAIN = [
    "trend01_trade",
    "market01_trade",
    "analyst01_trade",
    "risk01_trade",
    "review01_trade",
    "sim01_trade",
    "portfolio01_trade",
]

STALL_MINUTES_DEFAULT = 6
ACTIVITY_MARKERS = ("esc interrupt", "esc to interrupt", "↓")
LOG_DIR = PROJECT_ROOT / "logs"
STATE_PATH = LOG_DIR / "chain-watchdog-state.json"
MODEL_LOG = LOG_DIR / "model-usage.log"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    print(f"[{now_iso()}] {msg}", flush=True)


def inbox_dirs():
    inbox = Path(config.get_trade_inbox_dir())
    base = inbox.parent if inbox.name == "pending" else inbox
    return [base / "pending", base / "processed"]


def find_output(role, run_id):
    """Locate a role's output for the run (plain id or legacy polluted id)."""
    for d in inbox_dirs():
        for name in (f"{run_id}_{role}.json", f"{run_id}_humantrade_{role}.json"):
            p = d / name
            if p.exists():  # follows symlinks
                return p
    return None


def latest_run_id():
    """Newest numeric run id seen in the inbox (pending trigger or outputs)."""
    best = None
    for d in inbox_dirs():
        if not d.is_dir():
            continue
        for name in os.listdir(d):
            m = re.match(r"^(\d+)_", name)
            if m:
                n = int(m.group(1))
                if best is None or n > best:
                    best = n
    return f"{best:03d}" if best is not None else None


def pane_active(session):
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", "=" + session, "-p"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False
    tail = "\n".join(result.stdout.splitlines()[-25:]).lower()
    return any(m in tail for m in ACTIVITY_MARKERS)


def load_state():
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state):
    LOG_DIR.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


def sample_ollama():
    """Append `ollama ps` verbatim to the model-usage log (context +
    GPU/CPU split observability for the context-tuning project)."""
    result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    if result.returncode != 0:
        return
    lines = [ln for ln in result.stdout.strip().splitlines()[1:] if ln.strip()]
    if not lines:
        return
    LOG_DIR.mkdir(exist_ok=True)
    with open(MODEL_LOG, "a", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(f"{now_iso()} {ln}\n")


def nudge(role, run_id):
    log(f"NUDGE: {role} wrote output for {run_id} but never signaled — "
        f"running signal-complete")
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "dispatch.py"),
        "--db-flow", FLOW_KEY,
        "--signal-complete",
        "--from-role", role,
        "--id", run_id,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=120, cwd=str(PROJECT_ROOT))
        for line in (result.stdout or "").splitlines()[:8]:
            log(f"  dispatch: {line.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log("  dispatch timed out (known post-dispatch hang) — signal "
            "likely delivered; continuing")
        return True


def check_once(run_id, stall_minutes, state):
    """One watchdog pass. Returns 'complete' | 'active' | 'nudged' | 'idle'."""
    sample_ollama()
    if find_output(CHAIN[-1], run_id):
        return "complete"
    for i, role in enumerate(CHAIN[:-1]):
        next_role = CHAIN[i + 1]
        out = find_output(role, run_id)
        if out is None:
            # This step hasn't produced output yet — the chain is at or
            # before this step; if the role is actively working, all is well.
            return "active" if pane_active(role) else "idle"
        if find_output(next_role, run_id):
            continue  # step already advanced
        age_min = (time.time() - out.stat().st_mtime) / 60.0
        if pane_active(next_role):
            return "active"  # next role already working (signal made it)
        if age_min < stall_minutes:
            return "active"
        key = f"{run_id}:{role}"
        if state.get(key, 0) >= 2:
            log(f"SKIP: {key} already nudged twice — human attention needed")
            return "idle"
        state[key] = state.get(key, 0) + 1
        save_state(state)
        nudge(role, run_id)
        return "nudged"
    return "idle"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop-seconds", type=int, default=60)
    parser.add_argument("--max-minutes", type=int, default=90)
    parser.add_argument("--stall-minutes", type=int, default=STALL_MINUTES_DEFAULT)
    parser.add_argument("--run-id", default=None,
                        help="Run id to watch (default: newest in inbox)")
    args = parser.parse_args()

    run_id = args.run_id or latest_run_id()
    if run_id is None:
        log("No run id found in inbox — nothing to watch")
        return 0
    log(f"Watching flow {FLOW_KEY} run {run_id} "
        f"(stall threshold {args.stall_minutes} min)")

    state = load_state()
    deadline = time.monotonic() + args.max_minutes * 60
    while True:
        status = check_once(run_id, args.stall_minutes, state)
        if status == "complete":
            log(f"Run {run_id} complete (portfolio01 output present) — done")
            return 0
        if args.once:
            log(f"Single pass: status={status}")
            return 0
        if time.monotonic() >= deadline:
            log(f"Max runtime reached; last status={status}")
            return 0
        time.sleep(args.loop_seconds)


if __name__ == "__main__":
    sys.exit(main())
