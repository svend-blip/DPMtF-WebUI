#!/usr/bin/env python3
"""start_tmuxflow.py — Ensure all tmux sessions for a flow exist.

Usage:
    python3 scripts/bridgeV002/start_tmuxflow.py <flow_key>

Iterates through all active steps in the given flow, looks up each
FROM-ROLE's tmux_session, checks if the session exists via `tmux ls`,
and creates any missing sessions.

Example:
    python3 scripts/bridgeV002/start_tmuxflow.py strict_review
"""

import argparse
import os
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def get_active_flow_roles(db_path, flow_key):
    """Fetch all unique FROM-ROLE tmux sessions for active steps in a flow."""
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


def list_existing_tmux_sessions():
    """Return a set of existing tmux session names."""
    try:
        output = subprocess.check_output(
            ["tmux", "list-sessions"], stderr=subprocess.DEVNULL, text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

    pattern = re.compile(r"^(\S+):")
    sessions = set()
    for line in output.strip().split("\n"):
        m = pattern.match(line)
        if m:
            sessions.add(m.group(1))
    return sessions


def create_missing_sessions(required, existing):
    """Create any missing tmux sessions (detached).

    Returns a list of session names that were created.
    """
    created = []
    for session_name in sorted(required - existing):
        cmd = ["tmux", "new-session", "-d", "-s", session_name]
        print(f"  Creating tmux session: {session_name}")
        subprocess.run(cmd, check=True)
        created.append(session_name)
    return created


def main():
    parser = argparse.ArgumentParser(
        description="Ensure all tmux sessions for a BridgeV002 flow exist."
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
    required_sessions = get_active_flow_roles(db_path, args.flow_key)
    if not required_sessions:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. What already exists?
    existing_sessions = list_existing_tmux_sessions()

    # 3. What's missing?
    missing = required_sessions - existing_sessions

    if not missing:
        print(f"All {len(required_sessions)} tmux sessions exist for '{args.flow_key}'.")
        return

    # 4. Create them
    created = create_missing_sessions(missing, existing_sessions)
    print(f"\nDone: {len(created)} session(s) created.")


if __name__ == "__main__":
    main()
