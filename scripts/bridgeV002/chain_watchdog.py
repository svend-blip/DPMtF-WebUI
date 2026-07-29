#!/usr/bin/env python3
"""Chain watchdog for BridgeV002 flows.

Detects the recurring stall pattern — a role wrote its output file but
never ran signal-complete (observed trade flows 062/064, supervised_review
handoff 5 / run goal-001) — and auto-nudges the chain with the correct
normalized --id. Also samples `ollama ps` each cycle so context allocation
and GPU/CPU split are logged per run (context-tuning observability).

Two modes, selected by --flow:
- trade_cockpit_simulation_v001 (default): original inbox-JSON detection,
  behavior unchanged (trade-cronjob.sh compatibility).
- any other flow key: generic DB-driven detection — chain steps, deliverable
  dirs/patterns from bridge_flow_steps, tmux sessions from bridge_roles.
  A step whose next deliverable is missing stalls in one of two ways, told
  apart by trace.log and timed by different clocks:
    * SENDER stall — no signal_complete for the step: from_role wrote its
      output and ended its turn without signalling. Timed by the file mtime.
    * RECEIVER stall — the signal WAS delivered: to_role was dispatched,
      produced nothing, and its pane went idle. Timed by the inbound
      signal's age (run goal-006, handoff 21). Both are repaired by
      re-delivering from_role's callback, but the log names the role the
      chain is actually waiting on.

Runs alongside a flow (started by trade-cronjob.sh or a supervisor run),
never as a standing service:
  python3 chain_watchdog.py --loop-seconds 60 --max-minutes 90
  python3 chain_watchdog.py --flow supervised_review --max-minutes 600
Single pass for ad-hoc use: --once (add --dry-run to report without nudging)
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

import config  # Father config — trade inbox dir, db path, bridge dir

TRADE_FLOW_KEY = "trade_cockpit_simulation_v001"
FLOW_KEY = TRADE_FLOW_KEY  # legacy alias — trade helpers below use it
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
    # rejected/ is included on purpose: a role that delivered output which
    # the import gate rejected HAS advanced the chain (flow 070: risk01's
    # rejected file made the watchdog re-nudge an already-completed step,
    # double-dispatching risk01 mid-run). The watchdog tracks chain
    # progression, not import success.
    inbox = Path(config.get_trade_inbox_dir())
    base = inbox.parent if inbox.name == "pending" else inbox
    return [base / "pending", base / "processed", base / "rejected"]


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


def _capture_pane_tail(session):
    """Lowercased last 25 pane lines, or None when capture fails."""
    # capture-pane needs a window spec on grouped sessions — bare
    # `=session` fails silently (see dispatch._pane_target).
    target = "=" + session if ":" in session else "=" + session + ":0"
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target, "-p"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return "\n".join(result.stdout.splitlines()[-25:]).lower()


def pane_active(session):
    """Markers OR pane-content change between two captures 2 s apart.

    Marker matching alone missed opencode's tool-execution state (no
    'esc interrupt' in the tail) and nudged a working role.
    """
    first = _capture_pane_tail(session)
    if first is None:
        return False
    if any(m in first for m in ACTIVITY_MARKERS):
        return True
    time.sleep(2)
    second = _capture_pane_tail(session)
    if second is None:
        return False
    if any(m in second for m in ACTIVITY_MARKERS):
        return True
    return first != second


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


def nudge(role, run_id, flow_key=FLOW_KEY, dry_run=False, stalled=None,
          why=None):
    """Re-deliver `role`'s signal-complete for `run_id`.

    `stalled` and `why` name the role the chain is actually waiting on,
    which is not always `role`: when a receiver was dispatched and produced
    nothing, the repair is still to re-send the SENDER's callback (that is
    what re-prompts the receiver), but the log must point at the receiver.
    """
    stalled = stalled or role
    why = why or "wrote output but never signaled"
    log(f"NUDGE: {stalled} {why} (run {run_id}) — re-delivering "
        f"{role}'s signal-complete")
    if dry_run:
        log("  dry-run: signal-complete NOT sent")
        return True
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "dispatch.py"),
        "--db-flow", flow_key,
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


def signal_age_minutes(role, next_role, run_id):
    """Minutes since the last signal_complete for this step on trace.log,
    or None when the step has no such line.

    The age of the INBOUND signal is the only honest clock for a receiver:
    it says how long the role has had the work, which the sender's file
    mtime does not (run goal-006, handoff 21)."""
    trace = Path(config.get_bridge_dir()) / "trace.log"
    try:
        lines = trace.read_text(encoding="utf-8").splitlines()[-200:]
    except OSError:
        return None
    needle = f"| {role}->{next_role} | {run_id} | signal_complete |"
    for line in reversed(lines):
        if needle not in line:
            continue
        try:
            ts = datetime.strptime(line.split(" | ")[0],
                                   "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return 0.0  # unparseable timestamp: assume just delivered
        ts = ts.replace(tzinfo=timezone.utc)
        return (time.time() - ts.timestamp()) / 60.0
    return None


def recent_signal_delivered(role, next_role, run_id, within_minutes):
    """True when trace.log shows a signal_complete for this step recently —
    the callback WAS delivered; the next role is just slow (model load /
    long generation). Prevents duplicate-callback nudges (flow 066).
    `within_minutes=None` matches a signal of any age."""
    age = signal_age_minutes(role, next_role, run_id)
    if age is None:
        return False
    return within_minutes is None or age <= within_minutes


# ---------------------------------------------------------------------------
# Generic DB-driven mode — any flow whose steps carry deliverable_dir and
# deliverable_pattern in bridge_flow_steps (e.g. supervised_review). The
# trade flow keeps the inbox-JSON logic above; run-ids here are used exactly
# as they appear in deliverable filenames (no zero-padding).

def load_flow_steps(flow_key):
    """Active steps (from_role, to_role, dir, pattern) in chain order."""
    import sqlite3
    conn = sqlite3.connect(config.get_db_path())
    rows = conn.execute(
        "SELECT from_role, to_role, deliverable_dir, deliverable_pattern "
        "FROM bridge_flow_steps WHERE flow_key = ? AND is_active = 1 "
        "ORDER BY sort_order",
        (flow_key,),
    ).fetchall()
    conn.close()
    return [
        {"from_role": r[0], "to_role": r[1], "dir": r[2], "pattern": r[3]}
        for r in rows
    ]


def load_tmux_sessions():
    """role_key -> tmux session for pane-activity checks (agents only)."""
    import sqlite3
    conn = sqlite3.connect(config.get_db_path())
    rows = conn.execute(
        "SELECT role_key, tmux_session FROM bridge_roles "
        "WHERE is_active = 1 AND role_type != 'human'"
    ).fetchall()
    conn.close()
    return dict(rows)


def step_deliverable(step, run_id):
    """Path of a step's deliverable if present and non-empty, else None.

    Partial markdown writes are tolerated: the stall threshold (age check
    in check_once_generic) is minutes, far above any single-file write."""
    if not step["dir"] or not step["pattern"]:
        return None
    p = Path(step["dir"]) / step["pattern"].replace("{ID}", str(run_id))
    try:
        return p if p.stat().st_size > 0 else None
    except OSError:
        return None


def latest_generic_id(steps):
    """Newest {ID} seen in the first step's deliverable dir."""
    first = steps[0]
    if not first["dir"] or "{ID}" not in (first["pattern"] or ""):
        return None
    rx = re.compile(
        "^" + re.escape(first["pattern"]).replace(r"\{ID\}", r"(\d+)") + "$")
    best = None
    try:
        names = os.listdir(first["dir"])
    except OSError:
        return None
    for name in names:
        m = rx.match(name)
        if m:
            n = int(m.group(1))
            if best is None or n > best:
                best = n
    return str(best) if best is not None else None


def check_once_generic(flow_key, steps, sessions, run_id, stall_minutes,
                       state, dry_run=False):
    """One generic pass. Returns 'complete' | 'active' | 'nudged' | 'idle'.

    Step k counts as advanced when step k+1's deliverable exists. The FINAL
    step counts only via its signal_complete line in trace.log: its to_role
    (the flow owner, e.g. supervisor_auto) produces no chain deliverable,
    and its pane may be busy with the Human — pane activity proves nothing
    there (run goal-001, handoff 5: verdict written, signal never sent)."""
    sample_ollama()
    last = steps[-1]
    if recent_signal_delivered(last["from_role"], last["to_role"], run_id,
                               None):
        return "complete"
    for i, step in enumerate(steps):
        out = step_deliverable(step, run_id)
        if out is None:
            # Chain is at or before this step — from_role should be working.
            session = sessions.get(step["from_role"], step["from_role"])
            return "active" if pane_active(session) else "idle"
        is_last = i == len(steps) - 1
        if not is_last and step_deliverable(steps[i + 1], run_id):
            continue  # step already advanced
        if not is_last:
            session = sessions.get(step["to_role"], step["to_role"])
            if pane_active(session):
                return "active"  # next role already working
        signal_age = signal_age_minutes(step["from_role"], step["to_role"],
                                        run_id)
        if signal_age is not None:
            # RECEIVER STALL: the callback WAS delivered, so the missing
            # deliverable belongs to to_role — it was dispatched, produced
            # nothing, and its pane went idle (run goal-006, handoff 21).
            # Time it by the inbound signal, NOT by the sender's file age:
            # the sender did its job and its mtime says nothing about how
            # long the receiver has been silent.
            if signal_age < stall_minutes:
                return "active"  # receiver still inside its working window
            stalled = step["to_role"]
            why = (f"was dispatched {signal_age:.0f} min ago but produced no "
                   f"deliverable and its pane is idle")
        else:
            # SENDER STALL: no callback on trace.log — from_role wrote its
            # output and ended its turn without signal-complete.
            age_min = (time.time() - out.stat().st_mtime) / 60.0
            if age_min < stall_minutes:
                return "active"
            stalled = step["from_role"]
            why = "wrote output but never signaled"
        key = f"{flow_key}:{run_id}:{stalled}"
        if state.get(key, 0) >= MAX_NUDGES_PER_STEP:
            log(f"SKIP: {key} already nudged twice — human attention needed")
            return "idle"
        if not dry_run:
            state[key] = state.get(key, 0) + 1
            save_state(state)
        nudge(step["from_role"], run_id, flow_key, dry_run,
              stalled=stalled, why=why)
        return "nudged"
    return "idle"


def check_once(run_id, stall_minutes, state, dry_run=False):
    """One trade-flow pass. Returns 'complete' | 'active' | 'nudged' | 'idle'."""
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
        if not dry_run:
            state[key] = state.get(key, 0) + 1
            save_state(state)
        nudge(role, run_id, dry_run=dry_run)
        return "nudged"
    return "idle"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--flow", default=TRADE_FLOW_KEY,
                        help="Flow key to watch (default: trade cockpit; "
                             "other keys use generic DB-driven detection)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report stalls without sending signal-complete")
    parser.add_argument("--loop-seconds", type=int, default=LOOP_SECONDS_DEFAULT)
    parser.add_argument("--max-minutes", type=int, default=MAX_MINUTES_DEFAULT)
    parser.add_argument("--stall-minutes", type=int, default=STALL_MINUTES_DEFAULT)
    parser.add_argument("--run-id", default=None,
                        help="Run id to watch (default: newest seen)")
    args = parser.parse_args()

    if args.flow == TRADE_FLOW_KEY:
        run_id = args.run_id or latest_run_id()
        if run_id is None:
            log("No run id found in inbox — nothing to watch")
            return 0
        completion_msg = "portfolio01 output present"

        def pass_once():
            return check_once(run_id, args.stall_minutes, state,
                              dry_run=args.dry_run)
    else:
        steps = load_flow_steps(args.flow)
        if not steps:
            log(f"No active steps found for flow '{args.flow}' — check the "
                f"flow key against bridge_flow_steps")
            return 1
        sessions = load_tmux_sessions()
        run_id = args.run_id or latest_generic_id(steps)
        if run_id is None:
            log(f"No run id found in {steps[0]['dir']} — nothing to watch")
            return 0
        completion_msg = (f"final signal {steps[-1]['from_role']}->"
                          f"{steps[-1]['to_role']} delivered")

        def pass_once():
            return check_once_generic(args.flow, steps, sessions, run_id,
                                      args.stall_minutes, state,
                                      dry_run=args.dry_run)

    log(f"Watching flow {args.flow} run {run_id} "
        f"(stall threshold {args.stall_minutes} min"
        f"{', dry-run' if args.dry_run else ''})")

    state = load_state()
    deadline = time.monotonic() + args.max_minutes * 60
    while True:
        status = pass_once()
        if status == "complete":
            log(f"Run {run_id} complete ({completion_msg}) — done")
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
