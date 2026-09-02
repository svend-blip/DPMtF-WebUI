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
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge_lib  # noqa: E402  — the ONE artifact-root resolver (two-flow spec §2)

# "**First handoff id: 011**", "First handoff id: 11", "first handoff id is
# 22" -- with or without markup, case-insensitive. A colon or "is" joins the
# phrase to the number; anything else ("First handoff id: set by the kickoff
# dispatch.", the promoted-GOAL placeholder) is not a floor.
_FIRST_ID = re.compile(r"First handoff id\s*(?::|\bis\b)\s*\**\s*(\d+)", re.IGNORECASE)
_HANDOFF_FILE = re.compile(r"^(\d+)-handoff\.md$")
_TRACE_TS = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z")

# How long a run may show no movement before the report calls it stalled rather
# than working. Three hours, chosen against measured chain times rather than
# taste: preferred_cloud run 015's handoff 034 legitimately took 128 minutes
# including a stall and an OpenCode permission dialog, and 30 minutes of a role
# thinking is ordinary. A bound below a slow-but-working handoff would fire on a
# healthy chain, and a guard that acts on the wrong signal is worse than no
# guard — one such guard stopped a working implementer's model four seconds
# after its handoff was dispatched.
_STALE_AFTER_SECONDS = 3 * 60 * 60


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
    # Effective artifact root, not the flow key (two-flow spec §2): flows
    # sharing a root share their runs/ namespace. NULL root = flow key.
    return Path(bridge_dir) / bridge_lib.get_effective_artifact_root(flow_key) / "runs"


#: Artefacts that prove a run was actually opened, whatever else is missing.
#: A directory holding none of these was never started -- a draft parked for
#: the Human, or a directory made ahead of time.
_OPENED_MARKERS = ("GOAL.md", "RUN-LEDGER.md", "BACKLOG.md")


def was_opened(path):
    """True when this directory belongs to a run that actually started.

    A Human-approved ``GOAL.md`` is what authorises a run, so an unapproved
    draft is named ``GOAL-DRAFT.md`` and this returns False for it. The other
    two markers matter for the anomaly: a run whose ``GOAL.md`` went missing
    mid-flight still has a ledger, and must surface as PARK rather than be
    skipped over in favour of an older run.
    """
    return any((path / name).exists() for name in _OPENED_MARKERS)


def active_run(bridge_dir, flow_key):
    """Newest opened run directory without an END-REPORT.md, or None.

    Sorted by name, which is why runs are numbered rather than named.

    Directories that were never opened are skipped rather than adopted. Before
    that rule existed, a draft contract left as ``GOAL.md`` was reported as the
    active run -- with no floor, so every handoff on disk was listed as its
    own, which is exactly the mistake the floor exists to prevent.
    """
    base = run_dir(bridge_dir, flow_key)
    if not base.is_dir():
        return None
    runs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name)
    for path in reversed(runs):
        if (path / "END-REPORT.md").exists():
            continue
        if not was_opened(path):
            continue
        return path
    return None


def ledger_says_opened(run_path):
    """True when RUN-LEDGER.md carries a heading with "opened" in it.

    The opening entry is written as ``## <stamp> — Run NNN opened (...)``.
    Only headings count: a later entry's prose may mention that something
    was opened without this run ever having been.
    """
    path = run_path / "RUN-LEDGER.md"
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") and "opened" in line.lower():
            return True
    return False


def executing_run(bridge_dir, flow_key):
    """Lowest opened run without an END-REPORT.md, as a run id string, or None.

    Differs from ``active_run`` on purpose. When the Human promotes a batch of
    drafts at once (9000: runs 011-033 promoted in one go while 011 was the
    one executing), every promoted directory holds a GOAL.md and a ledger, so
    the *newest* opened directory is the last promotion rather than the run
    the chain is working. The executing run is the lowest one that has a
    Human-approved GOAL.md, has not closed, and shows evidence of a kickoff:
    a numeric first-handoff floor, or a ledger heading saying it was opened.
    A promoted-but-not-kicked-off run has neither -- its ledger heading says
    "GOAL promoted" and its GOAL.md floor reads "set by the kickoff dispatch".

    ``active_run`` keeps its behaviour: other cold-start skills read it.
    """
    base = run_dir(bridge_dir, flow_key)
    if not base.is_dir():
        return None
    runs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name)
    for path in runs:
        if (path / "END-REPORT.md").exists():
            continue
        if not (path / "GOAL.md").exists():
            continue
        if first_handoff_id(path) is not None or ledger_says_opened(path):
            return path.name
    return None


def draft_runs(bridge_dir, flow_key):
    """Run directories holding a GOAL-DRAFT.md and no opened-run artefact.

    Reported so a draft is visible without being adopted. A draft is a
    contract the Human has not approved; approving it means renaming it to
    ``GOAL.md``.
    """
    base = run_dir(bridge_dir, flow_key)
    if not base.is_dir():
        return []
    return sorted(
        p.name
        for p in base.iterdir()
        if p.is_dir() and (p / "GOAL-DRAFT.md").exists() and not was_opened(p)
    )


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
    base = Path(bridge_dir) / bridge_lib.get_effective_artifact_root(flow_key) / "handoffs"
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


def id_forms(handoff_id):
    """The two spellings a handoff id has on disk and in trace.log.

    dispatch.py has written the unpadded form (``22-handoff.md``, trace field
    ``22``) since 2026-08-29; everything before it is zero-padded (``022``).
    Both are the same id and both must match -- by whole field, never by
    substring (100_BRIDGE Security Rules 7).
    """
    value = int(handoff_id)
    return (str(value), f"{value:03d}")


def deliverable_path(base, subdir, suffix, handoff_id):
    """The path of one chain artefact, whichever spelling exists.

    The unpadded canonical name is checked first, then the padded one. When
    neither exists the canonical name is returned so callers can still name
    the file that would be written.
    """
    candidates = [base / subdir / f"{form}-{suffix}.md" for form in id_forms(handoff_id)]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def deliverables_for(bridge_dir, flow_key, handoff_id):
    """Which of the three chain artefacts exist for one handoff.

    True when either spelling of the file exists: ``21-handoff.md`` (the
    canonical form) or ``021-handoff.md`` (pre-2026-08-29). Checking only the
    padded name reported a delivered result as "(nothing written)" on the
    9000 flows.
    """
    base = Path(bridge_dir) / bridge_lib.get_effective_artifact_root(flow_key)
    return {
        "handoff": deliverable_path(base, "handoffs", "handoff", handoff_id).exists(),
        "result": deliverable_path(base, "results", "result", handoff_id).exists(),
        "verdict": deliverable_path(base, "verdicts", "verdict", handoff_id).exists(),
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
    # Field comparison against both spellings: dispatch.py writes "22" since
    # 2026-08-29, older eras wrote "022". A substring test would let "22"
    # match "122" or "220"; a padded-only test matched nothing on the 9000
    # flows and reported "(none in trace.log)" for a handoff that had been
    # dispatched minutes earlier.
    forms = id_forms(handoff_id)
    found = None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4 or parts[2] not in forms:
                continue
            # The id alone is not enough: trace.log spans every flow and every
            # era of the bridge, and ids repeat. On 2026-08-06 a grep for
            # " 009 " matched entries from 2026-06-14's claude-bridge. Require
            # one of this flow's own role keys on the line.
            if any(role in parts[1] for role in roles):
                found = line.strip()
    return found


def trace_epoch(line):
    """Epoch seconds for a trace line's UTC stamp, or None.

    trace.log is UTC text; file mtimes are local-clock epochs. Comparing the
    two as rendered strings invented a two-hour causal link that was not there,
    so every time value in this module is an epoch and no formatted timestamp is
    ever compared to another.
    """
    if not line:
        return None
    match = _TRACE_TS.search(line)
    if not match:
        return None
    naive = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    return naive.replace(tzinfo=timezone.utc).timestamp()


def last_movement(bridge_dir, flow_key, run_path, current, last_signal):
    """When this run last visibly moved, and what proves it.

    The anchor is the LATEST evidence of movement, never the earliest. A stall
    watcher written for llama_SG measured "time since the last signal" and
    reported a stall forty-six minutes into a run six minutes old; measuring
    from the later of the run's opening and the last signal is the fix. Where
    the two disagree this deliberately under-reports the age, because accusing
    a chain that is working costs more than noticing a stall late.

    Returns {"epoch": float, "source": str} or None when nothing dates the run.
    """
    candidates = []

    epoch = trace_epoch(last_signal)
    if epoch is not None:
        candidates.append((epoch, "trace signal"))

    if current is not None:
        handoff = deliverable_path(
            Path(bridge_dir) / bridge_lib.get_effective_artifact_root(flow_key),
            "handoffs", "handoff", current)
        if handoff.exists():
            # A written handoff is not a delivered one — only the trace line
            # means delivered. It still dates the attempt, which is what a
            # dispatch that never reached trace.log needs.
            candidates.append((handoff.stat().st_mtime, "handoff file mtime"))

    if run_path is not None:
        for name, label in (("RUN-LEDGER.md", "RUN-LEDGER.md mtime"),
                            ("GOAL.md", "GOAL.md mtime (run opening)")):
            path = run_path / name
            if path.exists():
                candidates.append((path.stat().st_mtime, label))

    if not candidates:
        return None
    epoch, source = max(candidates, key=lambda pair: pair[0])
    return {"epoch": epoch, "source": source}


def humanize_age(seconds):
    """A duration a reader can judge at a glance. Never a bare number of seconds."""
    if seconds is None:
        return "age unknown"
    seconds = max(0, int(seconds))
    if seconds < 90:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return f"{hours}h {minutes:02d}m ago"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h ago"


def flow_tmux_sessions(flow_key, db_path=None):
    """tmux session names for a flow's roles, from bridge_roles."""
    roles = flow_role_keys(flow_key, db_path=db_path)
    if not roles:
        return set()
    conn = sqlite3.connect(db_path or config.get_db_path())
    try:
        marks = ",".join("?" * len(roles))
        rows = conn.execute(
            f"SELECT tmux_session FROM bridge_roles WHERE role_key IN ({marks})",
            tuple(roles),
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows if row[0]}


def flow_uses_local_models(flow_key, db_path=None):
    """True if any role in the flow runs a locally served model.

    Read from the alias name rather than the allocator: a cloud flow probing
    a local port reports a failure that means nothing, and a local flow that
    skipped the probe would hide a real one.
    """
    roles = flow_role_keys(flow_key, db_path=db_path)
    if not roles:
        return False
    conn = sqlite3.connect(db_path or config.get_db_path())
    try:
        marks = ",".join("?" * len(roles))
        rows = conn.execute(
            f"SELECT default_model_source, default_model_alias "
            f"FROM bridge_roles WHERE role_key IN ({marks})",
            tuple(roles),
        ).fetchall()
    finally:
        conn.close()
    cloud = ("opus5", "sonnet5", "fable5", "cloud_minimax", "review-cloud",
             "archi-pay", "imple-pay", "company-knowledge", "openrouter-test")
    # A harness-backed source ('harness' legacy, 'harness_provider' replacement;
    # Run 021 §1 D1, GOAL.md Run 021) talks to a hosted API (dsh, codex), never a
    # local model server, so it must not trigger the :8080 probe — same reason
    # the cloud aliases are excluded. Legacy NULL source keeps the old behaviour.
    return any(
        r[1] and (r[0] or "") not in ("harness", "harness_provider") and r[1] not in cloud
        for r in rows
    )


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


def collect(flow_key, now=None, stale_after_seconds=_STALE_AFTER_SECONDS):
    bridge_dir = config.get_bridge_dir()
    run_path = active_run(bridge_dir, flow_key)
    now = time.time() if now is None else now

    state = {
        "flow": flow_key,
        "bridge_dir": bridge_dir,
        "project_root": config.get_project_root(),
        # The Human's standing mandate to this flow's resident supervisor
        # (migration 096). Read here so a cold-started supervisor sees the
        # bound it works under in the same report that tells it where it
        # is; empty mandate = planning only, cadence "none" = the Human
        # commits. Defaults on a database predating the columns.
        "mandate": bridge_lib.get_flow_supervisor_mandate(flow_key),
        "run": None,
        # The lowest opened, unclosed run -- the one the chain is working.
        # Distinct from "run" (the newest) whenever drafts were promoted in
        # bulk; see executing_run().
        "executing_run": executing_run(bridge_dir, flow_key),
        "artefacts": {},
        "first_handoff_id": None,
        "counter": flow_counter(flow_key),
        "owned_handoffs": [],
        "current": None,
        "deliverables": {},
        "last_signal": None,
        "last_movement": None,
        "stale": False,
        "stale_after_seconds": int(stale_after_seconds),
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
    # disk would invite exactly the mistake the floor exists to prevent -- and
    # so would listing them because the floor is unknown, which is why an
    # unstated floor owns nothing rather than everything.
    if run_path is not None and floor is not None:
        state["owned_handoffs"] = handoffs_at_or_above(bridge_dir, flow_key, floor)
    if state["owned_handoffs"]:
        state["current"] = state["owned_handoffs"][-1]
        state["deliverables"] = deliverables_for(bridge_dir, flow_key, state["current"])
        state["last_signal"] = last_trace_signal(bridge_dir, flow_key, state["current"])

    # How long since anything moved. Without this the report described a
    # 3.5-day-old dispatch with a recycled target session in exactly the words
    # it used for one made a minute ago (preferred_cloud run 015, handoff 035).
    if run_path is not None:
        movement = last_movement(bridge_dir, flow_key, run_path,
                                 state["current"], state["last_signal"])
        if movement is not None:
            movement = dict(movement)
            movement["seconds_ago"] = max(0, int(now - movement["epoch"]))
            movement["ago"] = humanize_age(movement["seconds_ago"])
            state["last_movement"] = movement
            state["stale"] = movement["seconds_ago"] > state["stale_after_seconds"]

    # A flow needs a local model server only if one of its roles resolves to a
    # locally served alias. preferred_cloud's three are all cloud_noop, so
    # probing :8080 there reports a failure that means nothing.
    local = flow_uses_local_models(flow_key)

    state["environment"] = {
        "webui": _probe(f"http://localhost:{config.get_port()}/api/health"),
        "database": Path(config.get_db_path()).exists(),
        # Sessions come from the flow's own roles. Hardcoding llama_SG's three
        # made this report lie the moment a second flow existed: it named the
        # wrong sessions and probed a local model server that preferred_cloud
        # does not have.
        "local_model": _probe("http://127.0.0.1:8080/health") if local else None,
        "tmux": _tmux_sessions(sorted(flow_tmux_sessions(flow_key))),
    }

    state["missing"], state["assessment"] = _assess(state)
    return state


def _assess(state):
    """What is missing, and the one-line conclusion. Order matters."""
    missing = []

    if state["run"] is None:
        note = ["no active run — every run directory has an END-REPORT or was never opened"]
        drafts = draft_runs(state["bridge_dir"], state["flow"])
        if drafts:
            note.append(
                "drafts awaiting the Human (not opened, not adopted): "
                + ", ".join(drafts)
            )
        return note, "NO ACTIVE RUN — a new run needs a Human-approved GOAL.md"

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
    if env["local_model"] is False:
        missing.append("the local model server is not reachable on :8080")
    if not env["webui"]:
        missing.append(f"WebUI is not answering on :{config.get_port()}")

    if not state["artefacts"].get("BACKLOG.md"):
        missing.append("BACKLOG.md — author it as the first action")

    movement = state["last_movement"]
    ago = movement["ago"] if movement else "age unknown"
    if state["stale"]:
        missing.append(
            f"no movement for {ago.removesuffix(' ago')} — newest evidence is the "
            f"{movement['source']}"
        )

    if not state["owned_handoffs"]:
        opened = f"RUN OPENED {ago}" if movement else "RUN OPENED"
        return missing, (f"{opened}, CHAIN NOT STARTED — author BACKLOG.md and "
                         f"dispatch the first handoff per GOAL.md Standing Approvals")

    d = state["deliverables"]
    current = state["current"]

    # A waiting verdict needs acting on whatever its age, so staleness informs
    # it rather than replacing it. The two working states are the ones that lie:
    # "no result yet" and "no verdict yet" are indistinguishable from a chain
    # that has silently stopped.
    if d.get("verdict"):
        return missing, (f"VERDICT READY for {current:03d} ({ago}) — validate the "
                         f"testgoals yourself, then act per 461")

    if d.get("result"):
        if state["stale"]:
            return missing, (
                f"STALLED — result {current:03d} was delivered {ago} and no verdict "
                f"has landed. Check the reviewer's session is alive and that its "
                f"delivery was not lost before you act; do not dispatch."
            )
        return missing, (f"RESULT DELIVERED for {current:03d} ({ago}) — the reviewer "
                         f"is working")

    if state["stale"]:
        return missing, (
            f"STALLED — handoff {current:03d} was dispatched {ago} and nothing has "
            f"come back. Verify the target session still holds the dispatch (a "
            f"recycled session cannot answer) and that the handoff is still "
            f"runnable against the current tree; do not dispatch the next one."
        )
    return missing, (f"HANDOFF {current:03d} DISPATCHED ({ago}) — the implementer "
                     f"is working")


def render(state):
    lines = []
    add = lines.append
    add(f"Flow            {state['flow']}")
    add(f"Bridge dir      {state['bridge_dir']}")

    mandate = state.get("mandate") or {}
    add(f"Supervisor role {mandate.get('supervisor_role') or '(none)'}")
    add(f"Mandate         {mandate.get('supervisor_mandate') or '(none — planning only)'}")
    add(f"Commit cadence  {mandate.get('commit_cadence') or 'none'}")

    add(f"Active run      {state['run'] or '(none)'}")
    add(f"Executing run   {state.get('executing_run') or '(none)'}")

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

    movement = state["last_movement"]
    if movement is not None:
        flag = "  ** STALLED **" if state["stale"] else ""
        add(f"Last movement   {movement['ago']} ({movement['source']}){flag}")

    env = state["environment"]
    tmux = ", ".join(f"{n}{'' if ok else ' NOT RUNNING'}" for n, ok in env["tmux"].items())
    add(f"WebUI           {'ok' if env['webui'] else 'NOT ANSWERING'}")
    add(f"Database        {'ok' if env['database'] else 'MISSING'}")
    if env["local_model"] is not None:
        add(f"local model     {'reachable' if env['local_model'] else 'NOT REACHABLE'}")
    add(f"tmux            {tmux}")

    if state["missing"]:
        add("Missing")
        for item in state["missing"]:
            add(f"  - {item}")

    add(f"Assessment      {state['assessment']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Required on purpose: a default flow silently reports ANOTHER flow's
    # state when a skill forgets the argument — no error, wrong answer.
    parser.add_argument("--flow", required=True,
                        help="Flow key (e.g. llama_SG, supervised_review)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report")
    parser.add_argument(
        "--stale-after", type=float, default=_STALE_AFTER_SECONDS / 60,
        metavar="MINUTES",
        help="Minutes without movement before a working state reads as STALLED "
             f"(default: {int(_STALE_AFTER_SECONDS / 60)})",
    )
    args = parser.parse_args()

    state = collect(args.flow, stale_after_seconds=args.stale_after * 60)
    print(json.dumps(state, indent=2) if args.json else render(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
