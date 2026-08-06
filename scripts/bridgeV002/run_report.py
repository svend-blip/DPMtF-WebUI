"""Emit the skeleton of a ledger entry or an END-REPORT, with the facts filled in.

On 2026-08-06 run 009 the supervisor wrote: "Let me check if there's an
example END-REPORT from a previous run to match the expected format", and
spent 1m53s reading two closed runs to work it out. Then it wrote the testgoal
table by hand from commands it had already run. The format is fixed, the
numbers are already known, and neither is a judgement.

This prints the skeleton. **It deliberately leaves the judgement blank** —
every field a supervisor must actually decide is a `TODO` for it to replace.
The facts are filled in because they are facts: which run, which handoffs,
what each testgoal criterion returned, how long the chain worked.

    python3 scripts/bridgeV002/run_report.py ledger --event verdict-012-APPROVED
    python3 scripts/bridgeV002/run_report.py end-report

Nothing is written to disk. It prints; the supervisor reviews, edits and
saves. A report it has not read is worse than one it wrote slowly.
"""

import argparse
import importlib.util
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = str(_HERE.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load("supervisor_state")
_testgoals = _load("check_testgoals")

_TITLE = re.compile(r"^#\s*GOAL\.md\s*—\s*(.+?)\s*$", re.MULTILINE)


def run_title(goal_path):
    text = Path(goal_path).read_text(encoding="utf-8")
    match = _TITLE.search(text)
    return match.group(1) if match else "(title not stated in GOAL.md)"


def chain_timings(bridge_dir, flow_key, handoff_ids):
    """Signal lines for this run's handoffs, in order. The active-time record."""
    path = Path(bridge_dir) / "trace.log"
    if not path.exists():
        return []
    roles = _state.flow_role_keys(flow_key)
    wanted = {f"{i:03d}" for i in handoff_ids}
    out = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5 or parts[2] not in wanted:
                continue
            if any(role in parts[1] for role in roles):
                out.append((parts[0], parts[1], parts[2], parts[3]))
    return out


def _active_minutes(timings):
    if len(timings) < 2:
        return None
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        first = datetime.strptime(timings[0][0], fmt)
        last = datetime.strptime(timings[-1][0], fmt)
    except ValueError:
        return None
    return round((last - first).total_seconds() / 60, 1)


def gather(flow_key):
    state = _state.collect(flow_key)
    if state["run"] is None:
        raise SystemExit("No active run — nothing to report on.")

    run_path = (Path(state["bridge_dir"]) / flow_key / "runs" / state["run"])
    goal = run_path / "GOAL.md"

    results = _testgoals.check(goal) if goal.exists() else []
    timings = chain_timings(state["bridge_dir"], flow_key, state["owned_handoffs"])

    return {
        "state": state,
        "run_path": run_path,
        "title": run_title(goal) if goal.exists() else "(no GOAL.md)",
        "results": results,
        "timings": timings,
        "active_minutes": _active_minutes(timings),
        "now": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _testgoal_rows(results):
    if not results:
        return ["| — | GOAL.md carries no ```testgoals block | — | validate by hand per 461 |"]
    rows = []
    for r in results:
        status = "**GREEN**" if r["passed"] else "**RED**"
        rows.append(f"| {r['id']} | {r['what'] or 'TODO describe'} | {status} | "
                    f"`{r['run']}` → {r['detail']} |")
    return rows


def render_ledger(data, event):
    s = data["state"]
    green = sum(1 for r in data["results"] if r["passed"])
    total = len(data["results"])
    dirty = subprocess.run(["git", "status", "--short"], capture_output=True,
                           text=True, cwd=config.get_project_root()).stdout
    tracked = [l for l in dirty.splitlines() if not l.startswith("??")]

    lines = [
        f"## Wake-up {data['now']} ({event})",
        f"- Event: {event} — TODO: what arrived, and from which role",
        f"- Action: TODO: what you did about it",
        f"- Budget: handoffs {len(s['owned_handoffs'])}/TODO, "
        f"active {data['active_minutes'] or 'TODO'} min from trace.log",
        f"- Testgoals: {green}/{total} green"
        + (" — verified mechanically, re-read the content yourself" if total else ""),
        "- Notes:",
    ]
    for r in data["results"]:
        mark = "GREEN" if r["passed"] else "RED"
        lines.append(f"  - {r['id']} {mark} — `{r['run']}` → {r['detail']}")
    lines.append(f"  - Working tree (tracked): "
                 + (", ".join(x.strip() for x in tracked) if tracked else "clean"))
    if s["last_signal"]:
        lines.append(f"  - Last signal: {s['last_signal']}")
    lines.append("  - TODO: the judgement — is the content right, not just the count?")
    return "\n".join(lines)


def render_end_report(data):
    s = data["state"]
    green = sum(1 for r in data["results"] if r["passed"])
    total = len(data["results"])
    closed = total and green == total

    lines = [
        f"# END-REPORT — {data['title']}",
        "",
        f"**Status:** {'CLOSED' if closed else 'TODO — not all testgoals are green'}"
        f" — {green}/{total} testgoals GREEN",
        f"**Handoffs:** {len(s['owned_handoffs'])} used "
        f"({', '.join(f'{i:03d}' for i in s['owned_handoffs']) or 'none'})",
        f"**Date:** {data['now'][:10]}",
        "",
        "## Testgoals",
        "",
        "Verified against the working tree, not taken from any verdict.",
        "",
        "| TG | Subject | Status | Evidence |",
        "|----|---------|--------|----------|",
    ]
    lines += _testgoal_rows(data["results"])
    lines += [
        "",
        f"**{green} of {total} green.**",
        "",
        "## What Happened",
        "",
        "TODO: one paragraph per handoff — who did what, and what you checked.",
        "",
        "## Chain Timings",
        "",
        "```",
    ]
    for ts, roles, hid, event in data["timings"]:
        lines.append(f"{ts}  {hid}  {roles:40s} {event}")
    lines += [
        "```",
        "",
        f"Active chain time: {data['active_minutes'] or 'TODO'} minutes"
        " — measured from trace.log, not the wall clock.",
        "",
        "## Action Items for Human",
        "",
        "1. TODO: review and commit the deliverable.",
        "2. Do NOT commit `databases/dpmtf.db` — flow exhaust, not deliverable.",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("kind", choices=("ledger", "end-report"))
    parser.add_argument("--flow", default="llama_SG")
    parser.add_argument("--event", default="TODO-event",
                        help="Ledger only: the event key, e.g. verdict-012-APPROVED")
    args = parser.parse_args()

    data = gather(args.flow)
    print(render_ledger(data, args.event) if args.kind == "ledger"
          else render_end_report(data))
    print(f"\n<!-- skeleton for {data['run_path']} — review, replace every TODO, "
          f"then save it yourself -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
