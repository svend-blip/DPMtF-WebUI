#!/usr/bin/env python3
"""Cron-tick entry point for the Job Queue scheduler.

Run via cron every 30 seconds (two staggered entries, flock prevents
overlapping ticks):
    * * * * * flock -n /tmp/dpmtf-cron-tick.lock python3 .../cron_tick.py
    * * * * * sleep 30 && flock -n /tmp/dpmtf-cron-tick.lock python3 .../cron_tick.py

One tick = one scheduler pass: recover expired leases → claim oldest
APPROVED job → context-fit preflight → dispatch → check completion →
write checkpoint → transition state.
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))

from scheduler import Scheduler


def main():
    sched = Scheduler()
    result = sched.tick()
    print(f"Tick: claimed={result.get('claimed', False)} "
          f"recovered={result.get('recovered', 0)} "
          f"outcome={result.get('outcome', 'none')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
