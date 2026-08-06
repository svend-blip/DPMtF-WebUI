"""Recover the supervisor's model when a sequential swap fails.

A crutch, not a fix. The defect is that `model_leases` records nothing, so
dispatch has nothing to release before starting the next model. Ollama evicts
its own previous model, which is why the swaps *within* a cycle succeed; but
Laguna is a separate llama.cpp server, so nothing evicts the reviewer's model
for it. Laguna then cannot fit, `llama-server` exits early, and dispatch
injects the callback anyway — waking the supervisor against an endpoint that
is not there. Measured twice, on 2026-08-06:

    run 006  GPU free 24630 MiB, Laguna needs 29901  -> "exited early"
    run 009  Laguna up 08:38:02, dead 08:38:52, GPU 32065/32607 with the
             reviewer's model squeezed from 22.4 GiB VRAM to 6.2

Remove backlog items 5, 6 and 7 and this file should be deleted with them.

## Why it watches state rather than a signal

The first version waited for `review01SG->supervisor01_llama | NNN |
signal_complete` in trace.log and then checked whether Laguna had come up.
That never fires in the failure it was written for: the trace entry is the
*last* thing a dispatch writes, after the model swap it was meant to protect,
so a dispatch that dies on the swap produces no signal at all. It sat waiting
for something that could not happen.

## The discriminator

Laguna being down is normal — it is down for most of every cycle, while a
worker model has the card. Stopping the worker's model then would destroy
work in progress. What distinguishes the failure is that **the supervisor is
awake and cannot reach its model**:

    supervisor session shows ConnectionRefused / 503 / Retrying
    AND laguna's port does not answer
    AND an ollama model is still resident

All three together occur only when a swap has failed. During normal worker
operation the supervisor is idle and silent.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

_LAGUNA_HEALTH = "http://127.0.0.1:8080/health"
_OLLAMA_PS = "http://127.0.0.1:11434/api/ps"
_ERROR_MARKERS = ("ConnectionRefused", "503 Loading model", "Unable to connect to API")


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


def supervisor_blocked(session):
    """True when the supervisor is awake and failing to reach its model."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", session],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False
    return any(marker in result.stdout for marker in _ERROR_MARKERS)


def failure_state(session):
    """All three conditions, in the cheapest order."""
    if laguna_up():
        return None
    if not supervisor_blocked(session):
        return None
    models = resident_models()
    return models or None


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
    if result.stdout.strip():
        log(result.stdout.strip().splitlines()[-1])
    return laguna_up()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--session", default="supervisor01_llama")
    parser.add_argument("--interval", type=int, default=20,
                        help="Seconds between checks (default 20)")
    parser.add_argument("--max-minutes", type=int, default=300,
                        help="Give up after this long (default 300)")
    parser.add_argument("--once", action="store_true",
                        help="Check once and exit — for testing")
    args = parser.parse_args()

    def log(message):
        print(f"[{time.strftime('%FT%TZ', time.gmtime())}] {message}", flush=True)

    deadline = time.time() + args.max_minutes * 60
    log(f"watching {args.session} for a failed swap back to laguna-local")

    while time.time() < deadline:
        models = failure_state(args.session)
        if models:
            log(f"FAILURE STATE — laguna down, supervisor blocked, resident: {models}")
            recovered = free_and_restart(models, log)
            log("laguna: UP" if recovered else "laguna: STILL DOWN — needs a Human")
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
