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
import sqlite3
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


def _db_path():
    """Absolute database path, independent of the working directory.

    config.get_db_path() returns "databases/dpmtf.db" — relative to the
    project root, not to wherever the watchdog was started. Combined with
    deliverable_dir being relative to the *bridge* root, the two paths
    could never be satisfied from the same directory: run from the project
    and the deliverables were invisible, run from the bridge dir and the
    database would not open. Both are resolved explicitly now.
    """
    p = config.get_db_path()
    if not os.path.isabs(p):
        p = os.path.join(str(PROJECT_ROOT), p)
    return p


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
# Fast path for the produced-nothing state: a receiver whose pane reads idle
# on this many CONSECUTIVE passes gets nudged without waiting out
# stall_minutes. Three passes at loop_seconds=60 is ~3 minutes of observed
# idleness -- long enough that tool-execution gaps and pane redraws cannot
# fake it (pane_active already double-samples), short enough that a model
# that acknowledged the injection and stopped is caught while the dispatch
# is still warm. preferred_cloud run 011: MiniMax answered "Context reset
# acknowledged." and idled; the Human saw it before the watchdog did,
# because nothing measured an idle pane against a delivered dispatch.
IDLE_PASSES = int(_WD.get("idle_passes", 3))
# A remote role proves life through execution heartbeats, not a pane. The
# worker beats every ~15s while waiting on its role; 90s of silence on a
# claimed execution means the worker died mid-execution.
REMOTE_HEARTBEAT_STALE_SECONDS = int(_WD.get("remote_heartbeat_stale_seconds", 90))
# A chain whose newest evidence (deliverable mtime or trace signal) is older
# than this is history, not a stall. The first --all-flows dry-run nudged
# strict_review's run 325 -- months old, surfaced only because the shared
# `human` session made the flow look "up". A stall watchdog must know when
# the run opened; measuring only "time since last signal" cannot tell an
# abandoned chain from a stalled one.
CHAIN_MAX_AGE_MINUTES = int(_WD.get("chain_max_age_minutes", 360))
# How long between repeat notifications for the same unresolved stall. The
# watchdog's most important conclusion — "the nudges are spent, a human is
# needed" — used to be a log line and nothing else. On 2026-08-09
# preferred_cloud's handoff 035 spent its budget at 21:17Z and the watchdog
# wrote that conclusion to journald 339 times over the next five hours and
# fifty minutes; nobody reads journald, the chain then aged past
# CHAIN_MAX_AGE_MINUTES, and the run stayed dead for three and a half days.
# Detection was never the gap.
#
# So it goes to the desktop instead, and repeats — a notification missed at
# 23:17 must not be the only one. Every 30 minutes inside the max-age window is
# roughly a dozen chances, which is enough to be noticed and few enough to stay
# an alarm rather than noise.
ESCALATION_REPEAT_MINUTES = int(_WD.get("escalation_repeat_minutes", 30))
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


def _notify(title, body):
    """Raise a desktop notification. Never let the absence of one matter.

    The watchdog is a systemd user unit; a logged-out or headless session has
    no notification bus, and an unhandled error here would take detection down
    for every flow at once. A failure to reach the desktop is logged and the
    pass continues — the journald line is the fallback, not the plan.
    """
    try:
        subprocess.run(
            ["notify-send", "--urgency=critical",
             "--app-name=chain-watchdog", title, body],
            capture_output=True, timeout=10,
        )
    except Exception as exc:  # noqa: BLE001 — notifying must never be fatal
        log(f"WARN: notify-send failed ({type(exc).__name__}: {exc}) — "
            f"escalation is in this log only")


def escalate(key, why, state, dry_run=False):
    """Tell the Human a chain needs them, at most once per backoff window.

    Returns True when a notification was raised. The last-notified epoch lives
    in the state file per key, so a watchdog restart does not restart the
    popups and a five-hour stall does not produce three hundred of them.
    """
    stamp_key = f"escalated:{key}"
    last = state.get(stamp_key)
    if last is not None and (time.time() - last) / 60.0 < ESCALATION_REPEAT_MINUTES:
        return False
    log(f"ESCALATION: {key} needs the Human — {why}")
    if dry_run:
        return False
    state[stamp_key] = time.time()
    save_state(state)
    _notify(f"BridgeV002 stalled: {key}", why)
    return True


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
          why=None, force=False):
    """Re-deliver `role`'s signal-complete for `run_id`.

    `stalled` and `why` name the role the chain is actually waiting on,
    which is not always `role`: when a receiver was dispatched and produced
    nothing, the repair is still to re-send the SENDER's callback (that is
    what re-prompts the receiver), but the log must point at the receiver.

    `force` bypasses dispatch's idempotency guard, and ONLY a receiver stall
    may set it. Without it a receiver stall could never be repaired at all:
    the guard treats a transition as delivered forever (correctly — ids do
    not repeat), and the repair for a receiver stall IS that same
    transition. Every attempt was therefore suppressed, and the trace log
    recorded the fact plainly and was not read:

      Rev_Supervisor->Rev_Imple | 010 | signal_complete_skipped |
      Duplicate delivery suppressed by idempotency guard

    Four such lines per handoff, on seven of the nine reveng handoffs of
    2026-08-11/12, and a human typed "continue" every time.

    Forcing is safe here and nowhere else. The damage the guard prevents —
    preferred_cloud runs 004 and 005 — was a late signal racing a role that
    was *still working*: it re-validated a live handoff and injected into a
    busy session. The receiver-stall branch excludes exactly that state
    before it calls us; it requires the deliverable to be missing AND the
    receiver's pane to have read idle on consecutive passes. That is the
    case dispatch's own --force documentation names: a `dispatched` that was
    logged but genuinely did not land. MAX_NUDGES_PER_STEP still caps the
    attempts, so a role that cannot be revived escalates to a human rather
    than being re-prompted forever.
    """
    stalled = stalled or role
    why = why or "wrote output but never signaled"
    log(f"NUDGE: {stalled} {why} (run {run_id}) — re-delivering "
        f"{role}'s signal-complete{' (--force)' if force else ''}")
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
    if force:
        cmd.append("--force")
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
    """Minutes since this step's last delivery line on trace.log, or None
    when the step has no such line.

    Both line types are delivery evidence: role-to-role callbacks log
    `signal_complete`, but the flow owner's handoff dispatch logs
    `dispatched` (run goal-016, watchdog-063: matching only the former
    made the step-1 receiver branch unreachable, so step-1 stalls were
    mistimed by the handoff file's mtime and blamed on the sender).

    The age of the INBOUND signal is the only honest clock for a receiver:
    it says how long the role has had the work, which the sender's file
    mtime does not (run goal-006, handoff 21)."""
    trace = Path(config.get_bridge_dir()) / "trace.log"
    try:
        lines = trace.read_text(encoding="utf-8").splitlines()[-200:]
    except OSError:
        return None
    # signal_complete_to_human is how a chain ENDS when its last receiver
    # is the Human: dispatch files the deliverable instead of injecting.
    # Without it here, a finished human-terminated chain (lightworker 015)
    # read as "review wrote output but never signaled" and drew a nudge.
    # Field-delimited needles, deliberately: signal_complete_failed also
    # contains the substring signal_complete (CLAUDE.md §11).
    needles = tuple(f"| {role}->{next_role} | {run_id} | {sig} |"
                    for sig in ("signal_complete", "dispatched",
                                "signal_complete_to_human"))
    for line in reversed(lines):
        if not any(n in line for n in needles):
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

def load_remote_targets():
    """role_key -> execution_target for roles that run on another machine.

    Their liveness cannot be read from a local pane -- there is none -- and
    nudging them is actively dangerous: the nudge re-sends the sender's
    signal-complete, which for a remote receiver creates a SECOND execution
    offer. Detection yes, auto-repair no.
    """
    try:
        conn = sqlite3.connect(_db_path())
        rows = conn.execute(
            "SELECT role_key, execution_target FROM bridge_roles "
            "WHERE is_active = 1 AND execution_target IS NOT NULL "
            "AND TRIM(execution_target) != ''").fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except sqlite3.Error:
        return {}


def remote_activity(flow_key, role, run_id):
    """'active' | 'stale' | 'unclaimed' | 'missing' for a remote role.

    Grounded in the LightWorker store: the newest execution for this
    handoff+role, and the age of its newest heartbeat. The worker beats
    every ~15s while its role runs, so a claimed execution with 90s of
    heartbeat silence is a dead worker, not a slow one.
    """
    conn = None
    try:
        conn = sqlite3.connect(_db_path())
        row = conn.execute(
            "SELECT execution_id, state, updated_at FROM lightworker_executions "
            "WHERE handoff_id = ? AND target_role = ? "
            "ORDER BY rowid DESC LIMIT 1", (str(run_id), role)).fetchone()
        if row is None:
            return "missing"
        eid, state_, updated = row
        if state_ in ("completed", "failed"):
            return "active"          # terminal: the chain moves on its own
        hb = conn.execute(
            "SELECT MAX(heartbeat_at) FROM lightworker_execution_heartbeats "
            "WHERE execution_id = ?", (eid,)).fetchone()[0]
        newest = hb or updated
        try:
            ts = datetime.fromisoformat(newest.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                # SQLite datetime('now') stores naive UTC; subtracting a
                # naive stamp from an aware now is a TypeError, not an age.
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
        except (ValueError, AttributeError):
            return "stale"
        if state_ in ("offered", "delivered"):
            return "unclaimed" if age > 120 else "active"
        return "stale" if age > REMOTE_HEARTBEAT_STALE_SECONDS else "active"
    except sqlite3.Error:
        return "missing"
    finally:
        if conn is not None:
            conn.close()


def load_flow_steps(flow_key):
    """Active steps (from_role, to_role, dir, pattern) in chain order."""
    import sqlite3
    conn = sqlite3.connect(_db_path())
    rows = conn.execute(
        "SELECT from_role, to_role, deliverable_dir, deliverable_pattern "
        "FROM bridge_flow_steps WHERE flow_key = ? AND is_active = 1 "
        "ORDER BY sort_order",
        (flow_key,),
    ).fetchall()
    conn.close()
    # deliverable_dir is stored relative to the bridge root
    # ("llama_SG/handoffs"). Resolving it against the process CWD is what
    # made the watchdog blind to generic flows' deliverables and report a
    # working chain as idle all night.
    bridge_dir = config.get_bridge_dir()
    steps = []
    for r in rows:
        deliverable_dir = r[2]
        if deliverable_dir and not os.path.isabs(deliverable_dir):
            deliverable_dir = os.path.join(bridge_dir, deliverable_dir)
        steps.append({"from_role": r[0], "to_role": r[1],
                      "dir": deliverable_dir, "pattern": r[3]})
    return steps


def load_tmux_sessions():
    """role_key -> tmux session for pane-activity checks (agents only)."""
    import sqlite3
    conn = sqlite3.connect(_db_path())
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
    """Newest {ID} seen in the first step's deliverable dir.

    Returns the id EXACTLY as written on disk (zero-padding preserved):
    every downstream lookup — deliverable paths, trace.log needles, nudge
    --id — must use the same string the dispatcher used, and that is the
    padded one ("058", not "58"). Stripping the padding made the watchdog
    blind to deliverables and signals for padded runs."""
    first = steps[0]
    if not first["dir"] or "{ID}" not in (first["pattern"] or ""):
        return None
    rx = re.compile(
        "^" + re.escape(first["pattern"]).replace(r"\{ID\}", r"(\d+)") + "$")
    best = None
    best_raw = None
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
                best_raw = m.group(1)
    return best_raw


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
        remote_targets = load_remote_targets()
        idle_key = f"idle:{flow_key}:{run_id}:{step['to_role']}"
        if not is_last:
            to_role = step["to_role"]
            if to_role in remote_targets:
                # A remote role has no local pane. Its liveness is the
                # execution heartbeat, and it is NEVER auto-nudged: the
                # nudge re-sends the sender's signal-complete, which for a
                # remote receiver mints a second execution offer.
                ra = remote_activity(flow_key, to_role, run_id)
                if ra == "active":
                    state.pop(idle_key, None)
                    return "active"
                crit_key = f"remote:{flow_key}:{run_id}:{to_role}"
                if not state.get(crit_key):
                    state[crit_key] = now_iso()
                    if not dry_run:
                        save_state(state)
                    log(f"CRITICAL: remote role {to_role} on "
                        f"{remote_targets[to_role]} is {ra} for run {run_id}"
                        f" — no auto-nudge possible, human attention needed")
                return "idle"
            session = sessions.get(to_role, to_role)
            if pane_active(session):
                state.pop(idle_key, None)
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
                # PRODUCED-NOTHING FAST PATH. The classic threshold treats
                # an idle pane like a thinking one and waits stall_minutes.
                # But we only reach this line when the pane already read
                # idle THIS pass — so count consecutive idle observations,
                # and nudge once there are IDLE_PASSES of them. A model
                # that acknowledged the injection and stopped is caught in
                # ~IDLE_PASSES minutes instead of twelve
                # (preferred_cloud run 011).
                n = state.get(idle_key, 0) + 1
                state[idle_key] = n
                if not dry_run:
                    save_state(state)
                if n < IDLE_PASSES:
                    log(f"WATCH: {step['to_role']} idle {n}/{IDLE_PASSES} "
                        f"passes, dispatched {signal_age:.0f} min ago "
                        f"(run {run_id})")
                    return "active"
                stalled = step["to_role"]
                why = (f"was dispatched {signal_age:.0f} min ago, produced "
                       f"nothing, and its pane read idle on {n} consecutive "
                       f"passes")
            else:
                stalled = step["to_role"]
                why = (f"was dispatched {signal_age:.0f} min ago but "
                       f"produced no deliverable and its pane is idle")
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
            # Not a SKIP. The nudges are spent and the chain is still stopped,
            # which is the one state that genuinely needs a person.
            escalate(key,
                     f"{stalled} {why}; {MAX_NUDGES_PER_STEP} nudges did not "
                     f"move it. Verify the session still holds the dispatch — "
                     f"a recycled session cannot answer.",
                     state, dry_run=dry_run)
            return "escalated"
        if not dry_run:
            state[key] = state.get(key, 0) + 1
            save_state(state)
        state.pop(idle_key, None)
        # Only a receiver stall needs --force: its transition is already on
        # trace.log as delivered. A sender stall never signalled, so nothing
        # suppresses it and forcing would only widen the blast radius.
        nudge(step["from_role"], run_id, flow_key, dry_run,
              stalled=stalled, why=why,
              force=(stalled == step["to_role"]))
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
            escalate(key,
                     f"{role} has not advanced the chain and "
                     f"{MAX_NUDGES_PER_STEP} nudges did not move it.",
                     state, dry_run=dry_run)
            return "escalated"
        if not dry_run:
            state[key] = state.get(key, 0) + 1
            save_state(state)
        nudge(role, run_id, dry_run=dry_run)
        return "nudged"
    return "idle"


def _session_exists(name):
    return subprocess.run(["tmux", "has-session", "-t", "=" + name],
                          capture_output=True).returncode == 0


def load_all_flow_keys():
    try:
        conn = sqlite3.connect(_db_path())
        rows = conn.execute(
            "SELECT DISTINCT flow_key FROM bridge_flow_steps "
            "WHERE is_active = 1 ORDER BY flow_key").fetchall()
        conn.close()
        return [r[0] for r in rows]
    except sqlite3.Error:
        return []


def _chain_age_minutes(steps, run_id):
    """Minutes since the chain's newest evidence, or None when it has none.

    Newest of: every step deliverable's mtime and every step's trace
    signal. A chain mid-step always has one of the two fresh.
    """
    newest = None
    for step in steps:
        out = step_deliverable(step, run_id)
        if out is not None:
            age = (time.time() - out.stat().st_mtime) / 60.0
            newest = age if newest is None else min(newest, age)
        sig = signal_age_minutes(step["from_role"], step["to_role"], run_id)
        if sig is not None:
            newest = sig if newest is None else min(newest, sig)
    return newest


def check_all_flows(stall_minutes, state, dry_run=False):
    """One pass over every active flow. Returns a {flow: status} dict.

    The watchdog existed through every produced-nothing incident this
    project has logged -- and was armed for none of them, because arming
    was a per-run manual step. This mode watches everything so that
    "nobody armed it" stops being a failure mode.

    A flow is skipped when it has no chain id yet, or when none of its
    local role sessions exist AND it has no remote roles -- a flow that is
    not up is not stalled. Skips are quiet: logging them every pass would
    bury the one line that matters.
    """
    remote_targets = load_remote_targets()
    sessions = load_tmux_sessions()
    statuses = {}
    for flow_key in load_all_flow_keys():
        steps = load_flow_steps(flow_key)
        if not steps:
            continue
        run_id = latest_generic_id(steps)
        if run_id is None:
            continue
        roles = {s["from_role"] for s in steps} | {s["to_role"] for s in steps}
        local = [r for r in roles if r not in remote_targets]
        if local and not any(_session_exists(sessions.get(r, r))
                             for r in local):
            continue        # flow not up — absent is not stalled
        age = _chain_age_minutes(steps, run_id)
        if age is None or age > CHAIN_MAX_AGE_MINUTES:
            continue        # history, not a stall
        statuses[flow_key] = check_once_generic(
            flow_key, steps, sessions, run_id, stall_minutes, state,
            dry_run=dry_run)
    return statuses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--all-flows", action="store_true",
                        help="Watch every active flow with a live session; "
                             "run ids re-resolved every pass")
    parser.add_argument("--forever", action="store_true",
                        help="No max-minutes deadline (for the systemd unit)")
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

    if args.all_flows:
        state = load_state()
        log(f"Watching ALL active flows (stall {args.stall_minutes} min, "
            f"idle fast-path {IDLE_PASSES} passes"
            f"{', dry-run' if args.dry_run else ''})")
        last_line = None
        deadline = (None if args.forever
                    else time.monotonic() + args.max_minutes * 60)
        while True:
            statuses = check_all_flows(args.stall_minutes, state,
                                       dry_run=args.dry_run)
            interesting = {f: s for f, s in statuses.items()
                           if s != "complete"}
            line = " ".join(f"{f}={s}" for f, s in sorted(interesting.items())) \
                   or "(alle kæder complete/nede)"
            if line != last_line:
                log(f"pass: {line}")
                last_line = line
            if args.once:
                return 0
            if deadline is not None and time.monotonic() >= deadline:
                log("Max runtime reached")
                return 0
            time.sleep(args.loop_seconds)

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
