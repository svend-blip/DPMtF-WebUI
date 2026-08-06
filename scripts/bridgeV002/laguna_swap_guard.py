"""Recover the supervisor's model when the swap back to Laguna fails.

A crutch, not a fix. The defect is that `model_leases` records nothing, so
dispatch has nothing to release before starting the next model. Ollama evicts
its own previous model, which is why the swaps *within* a cycle succeed; but
Laguna is a separate llama.cpp server, so nothing evicts the reviewer's model
for it. Laguna then cannot fit and `llama-server` exits early. Backlog items
5, 6 and 7 — when those are fixed, delete this file with them.

## The trigger, and why the first two were wrong

**Version 1 waited for a trace signal.** It watched for
`review01SG->supervisor01_llama | {ID} | signal_complete` and then checked
whether Laguna had come up. That entry is the *last* thing a dispatch writes,
after the model swap it was meant to protect — so a dispatch that dies on the
swap never produces it. In run 009 the signal appeared only at 08:40:17Z,
after the memory had been freed by hand. The guard sat waiting for something
that could not happen.

**Version 2 watched the supervisor's tmux pane** for ConnectionRefused, on the
reasoning that a supervisor awake and unable to reach its model must mean a
failed swap. That is false, and it did real damage: on 2026-08-06 at 09:29:01,
four seconds after handoff 013 was dispatched, it stopped the implementer's
model mid-work. Dispatch stops Laguna as *part of* handing off, while the
supervisor is still finishing its turn — so "Laguna down and the supervisor
blocked" is the ordinary state after every dispatch, not a failure. Fourteen
tests asserted it would stay still; all fourteen were written against the same
wrong assumption, and all fourteen passed.

## What is actually observable during the failure

Run 009, measured:

    10:37:40 local   review01SG writes verdicts/012-verdict.md
    (no review01SG->supervisor01_llama entry in trace.log)
    Laguna down, reviewer's model still resident
    08:40:17Z        delivery signal — only after a Human intervened

So the signature is: **the verdict exists, it has aged, and the trace still
shows no delivery for it.** During normal review work the verdict file does
not exist yet, which is what separates the two. The age threshold covers the
40-60 seconds a dispatch legitimately takes.

This also fires when the reviewer writes a verdict and never signals at all
(backlog item 8, seen three times). That is not this guard's problem to fix,
but freeing the card and starting Laguna is still the right move, and the log
says which of the two it saw.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
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

_LAGUNA_HEALTH = "http://127.0.0.1:8080/health"
_OLLAMA_PS = "http://127.0.0.1:11434/api/ps"


def laguna_up(timeout=5):
    """True if the port answers at all. A 503 means loading, which is 'there'."""
    try:
        urllib.request.urlopen(_LAGUNA_HEALTH, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def resident_models(timeout=5):
    try:
        with urllib.request.urlopen(_OLLAMA_PS, timeout=timeout) as response:
            data = json.load(response)
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def undelivered_verdict(bridge_dir, flow_key, floor, min_age):
    """The handoff whose verdict is written, aged, and still not delivered.

    Returns (handoff_id, age_seconds) or None. Only the newest handoff at or
    above the run's floor is considered — an older one belongs to a settled
    part of the run.
    """
    ids = _state.handoffs_at_or_above(bridge_dir, flow_key, floor)
    if not ids:
        return None
    current = ids[-1]

    verdict = Path(bridge_dir) / flow_key / "verdicts" / f"{current:03d}-verdict.md"
    if not verdict.exists():
        return None                      # reviewer still working — normal
    age = time.time() - verdict.stat().st_mtime
    if age < min_age:
        return None                      # dispatch may simply be in progress

    last = _state.last_trace_signal(bridge_dir, flow_key, current)
    if last and "review01SG->supervisor01_llama" in last and "signal_complete" in last:
        return None                      # delivered; nothing owed
    return current, int(age)


def failure_state(flow_key, min_age):
    """All conditions, cheapest first. Returns a dict or None."""
    if laguna_up():
        return None

    bridge_dir = config.get_bridge_dir()
    run_path = _state.active_run(bridge_dir, flow_key)
    if run_path is None:
        return None                      # no run — nothing to protect
    floor = _state.first_handoff_id(run_path)

    pending = undelivered_verdict(bridge_dir, flow_key, floor, min_age)
    if not pending:
        return None

    models = resident_models()
    if not models:
        return None                      # nothing to free; a different failure

    handoff_id, age = pending
    return {"handoff": handoff_id, "verdict_age": age, "models": models}


def free_and_restart(models, log):
    for name in models:
        log(f"stopping {name}")
        subprocess.run(["ollama", "stop", name], capture_output=True)
    time.sleep(5)

    allocator = Path(config.get_home_dir()) / "model-allocator"
    result = subprocess.run(
        [str(allocator / "venv" / "bin" / "python3"), "-m", "model_allocator",
         "start", "--alias", "laguna-local", "--timeout", "900"],
        capture_output=True, text=True, cwd=str(allocator), timeout=960,
    )
    log(f"allocator start rc={result.returncode}")
    return laguna_up()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--flow", default="llama_SG")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--min-age", type=int, default=180,
                        help="Seconds a verdict must sit undelivered before "
                             "this counts as a failed swap (default 180; a "
                             "dispatch legitimately takes 40-60)")
    parser.add_argument("--max-minutes", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what it would do and change nothing. Two "
                             "earlier triggers had green tests and were still "
                             "wrong; run a whole flow this way and compare the "
                             "decisions against what happened before arming it.")
    args = parser.parse_args()

    def log(message):
        print(f"[{time.strftime('%FT%TZ', time.gmtime())}] {message}", flush=True)

    deadline = time.time() + args.max_minutes * 60
    mode = "DRY RUN — will change nothing" if args.dry_run else "ARMED"
    log(f"watching {args.flow} for a verdict that cannot reach the supervisor "
        f"(min-age {args.min_age}s) — {mode}")

    announced = set()
    while time.time() < deadline:
        found = failure_state(args.flow, args.min_age)
        if found:
            log(f"FAILURE STATE — verdict {found['handoff']:03d} written "
                f"{found['verdict_age']}s ago, never delivered; laguna down; "
                f"resident: {found['models']}")
            if args.dry_run:
                # Say it once per handoff, then keep quiet. A dry run that
                # repeats every interval buries the one line worth reading.
                if found["handoff"] not in announced:
                    log(f"WOULD stop {found['models']} and start laguna-local "
                        f"— not doing it")
                    announced.add(found["handoff"])
                if args.once:
                    return 0
                time.sleep(args.interval)
                continue
            recovered = free_and_restart(found["models"], log)
            log("laguna: UP — the callback should now go through"
                if recovered else "laguna: STILL DOWN — needs a Human")
            if args.once:
                return 0 if recovered else 1
        elif args.once:
            log("no failure state")
            return 0
        time.sleep(args.interval)

    log("deadline reached")
    return 0


if __name__ == "__main__":
    sys.exit(main())
