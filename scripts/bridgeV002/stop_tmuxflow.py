#!/usr/bin/env python3
"""stop_tmuxflow.py — Kill all tmux sessions for a BridgeV002 flow.

Usage:
    python3 scripts/bridgeV002/stop_tmuxflow.py <flow_key>

Iterates through all active steps in the given flow, looks up each
FROM-ROLE's tmux_session, and kills any existing sessions via
`tmux kill-session -t`.

Example:
    python3 scripts/bridgeV002/stop_tmuxflow.py strict_review
"""

import argparse
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def get_active_flow_roles(db_path, flow_key):
    """Fetch all unique FROM-ROLE tmux sessions for active steps in a flow.

    Returns a set of session name strings.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    roles = set()
    rows = conn.execute(
        """
        SELECT DISTINCT r.tmux_session
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.from_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
        """,
        (flow_key,),
    ).fetchall()

    for row in rows:
        ts = row["tmux_session"]
        if ts:
            roles.add(ts)

    conn.close()
    return roles


def stop_sessions(session_names):
    """Kill tmux sessions by name.

    Returns a list of session names that were successfully killed.
    Sessions that don't exist are silently skipped.
    """
    stopped = []
    for session_name in sorted(session_names):
        cmd = ["tmux", "kill-session", "-t", session_name]
        print(f"  Stopping tmux session: {session_name}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            stopped.append(session_name)
        else:
            stderr = result.stderr.strip() or "unknown error"
            print(f"    WARNING: Failed to stop '{session_name}': {stderr}")
    return stopped


def main():
    parser = argparse.ArgumentParser(
        description="Kill all tmux sessions for a BridgeV002 flow."
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

    # 1. Get all tmux session names from flow
    sessions_to_stop = get_active_flow_roles(db_path, args.flow_key)
    if not sessions_to_stop:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. Kill them
    stopped = stop_sessions(sessions_to_stop)
    print(f"\nDone: {len(stopped)} session(s) stopped.")


if __name__ == "__main__":
    main()
