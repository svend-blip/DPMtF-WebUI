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
# Fallback chain order — the live order is read from bridge_flow_steps
# (config-consolidation: DB is the single source of truth for flow structure).
CHAIN_FALLBACK = [
    "trend01_trade",
    "market01_trade",
    "analyst01_trade",
    "risk01_trade",
    "review01_trade",
    "sim01_trade",
    "portfolio01_trade",
]


def load_chain():
    """Role order from bridge_flow_steps; falls back to the inline list
    if the DB is unavailable at runtime (09:00 cron must never die here)."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(PROJECT_ROOT / "databases" / "dpmtf.db"))
        rows = conn.execute(
            "SELECT from_role, to_role FROM bridge_flow_steps "
            "WHERE flow_key = ? AND is_active = 1 ORDER BY sort_order",
            (FLOW_KEY,),
        ).fetchall()
        conn.close()
        chain = []
        for from_role, to_role in rows:
            for role in (from_role, to_role):
                if role and role != "humantrade" and role not in chain:
                    chain.append(role)
        return chain or CHAIN_FALLBACK
    except Exception:
        return CHAIN_FALLBACK


CHAIN = load_chain()


def _watchdog_profile():
    """Watchdog defaults from the machine profile [watchdog] section."""
    try:
        path = PROJECT_ROOT / "profiles" / "machine.local.json"
        return json.loads(path.read_text()).get("watchdog", {})
    except (OSError, json.JSONDecodeError):
        return {}


_WD = _watchdog_profile()
STALL_MINUTES_DEFAULT = int(_WD.get("stall_minutes", 12))
MAX_NUDGES_PER_STEP = int(_WD.get("max_nudges_per_step", 2))
LOOP_SECONDS_DEFAULT = int(_WD.get("loop_seconds", 60))
MAX_MINUTES_DEFAULT = int(_WD.get("max_minutes", 90))
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
    """Locate a role's COMPLETE output for the run.

    Roles write incrementally (432 chunked-write discipline), so mere file
    existence is not completion — flow 067's watchdog nudged the chain on
    an 817-byte partial market file. The file must parse as JSON and carry
    a status field before it counts."""
    for d in inbox_dirs():
        for name in (f"{run_id}_{role}.json", f"{run_id}_humantrade_{role}.json"):
            p = d / name
            if not p.exists():  # follows symlinks
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue  # partial/in-progress write
            if isinstance(data, dict) and data.get("status"):
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


def recent_signal_delivered(role, next_role, run_id, within_minutes):
    """True when trace.log shows a signal_complete for this step recently —
    the callback WAS delivered; the next role is just slow (model load /
    long generation). Prevents duplicate-callback nudges (flow 066)."""
    bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR",
                                os.path.expanduser("~/.bridge"))
    trace = Path(bridge_dir) / "trace.log"
    try:
        lines = trace.read_text(encoding="utf-8").splitlines()[-200:]
    except OSError:
        return False
    needle = f"| {role}->{next_role} | {run_id} | signal_complete |"
    cutoff = time.time() - within_minutes * 60
    for line in reversed(lines):
        if needle not in line:
            continue
        try:
            ts = datetime.strptime(line.split(" | ")[0],
                                   "%Y-%m-%dT%H:%M:%SZ")
            ts = ts.replace(tzinfo=timezone.utc)
            return ts.timestamp() >= cutoff
        except ValueError:
            return True  # unparseable timestamp: assume recent, stay safe
    return False


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
        if recent_signal_delivered(role, next_role, run_id, stall_minutes * 2):
            return "active"  # callback delivered; role is loading/slow
        if age_min < stall_minutes:
            return "active"
        key = f"{run_id}:{role}"
        if state.get(key, 0) >= MAX_NUDGES_PER_STEP:
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
    parser.add_argument("--loop-seconds", type=int, default=LOOP_SECONDS_DEFAULT)
    parser.add_argument("--max-minutes", type=int, default=MAX_MINUTES_DEFAULT)
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
