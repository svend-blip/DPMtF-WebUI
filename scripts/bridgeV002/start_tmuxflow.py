#!/usr/bin/env python3
"""start_tmuxflow.py — Ensure tmux sessions exist for a BridgeV002 flow.

Usage:
    python3 scripts/bridgeV002/start_tmuxflow.py <flow_key>

Example:
    python3 scripts/bridgeV002/start_tmuxflow.py strict_review
"""

import argparse
import os
import sqlite3
import subprocess
import sys


def get_required_sessions(db_path, flow_key):
    """Fetch all unique role tmux sessions for an active flow.

    Covers from_role AND to_role — the final role in a chain only ever
    appears as to_role (e.g. portfolio01_trade) and was previously
    skipped, leaving it with a stale session from the prior run."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sessions = set()
    rows = conn.execute(
        # A role with an execution_target runs on another machine. Creating a
        # session for it here produces a pane nobody uses and, worse, one that
        # misleads: an idle client waiting for a handoff dispatch will never
        # send it, because it routes the envelope to the worker instead.
        "SELECT DISTINCT r.tmux_session "
        "FROM bridge_flow_steps s "
        "JOIN bridge_roles r ON r.role_key IN (s.from_role, s.to_role) "
        "WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1 "
        "  AND (r.execution_target IS NULL OR TRIM(r.execution_target) = '')",
        (flow_key,),
    ).fetchall()

    for row in rows:
        ts = row["tmux_session"]
        if ts:
            sessions.add(ts)

    conn.close()
    return sessions


def session_exists(session_name):
    """Return True if a tmux session with the given name already exists."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", "=" + session_name],
        capture_output=True,
    )
    return result.returncode == 0


def create_session(session_name):
    """Create a detached tmux session with the given name."""
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Ensure tmux sessions exist for a BridgeV002 flow."
    )
    parser.add_argument("flow_key", help="Flow key (e.g. strict_review)")
    args = parser.parse_args()

    # Resolve database path — config.py lives TWO levels up from this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))

    # Directly import config from absolute path to avoid sys.path conflicts
    spec = __import__('importlib.util').util.spec_from_file_location(
        'config', os.path.join(project_root, 'config.py')
    )
    config_mod = __import__('importlib.util').util.module_from_spec(spec)
    spec.loader.exec_module(config_mod)

    db_path = config_mod.get_db_path()

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    # 1. Get all required tmux session names from flow
    required_sessions = get_required_sessions(db_path, args.flow_key)
    if not required_sessions:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. Ensure each session exists (create if missing)
    created = []
    existing = []
    print(f"Checking tmux sessions for flow '{args.flow_key}':")
    for s in sorted(required_sessions):
        if session_exists(s):
            print(f"  {s} — already running")
            existing.append(s)
        else:
            print(f"  {s} — creating")
            try:
                create_session(s)
                created.append(s)
                print(f"    created")
            except subprocess.CalledProcessError as e:
                print(f"    ERROR: Failed to create session: {e}")

    # 3. Summary
    print(f"\nDone: {len(existing)} existing, {len(created)} created "
          f"({len(required_sessions)} total).")


if __name__ == "__main__":
    main()
