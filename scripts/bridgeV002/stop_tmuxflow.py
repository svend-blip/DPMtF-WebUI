#!/usr/bin/env python3
"""stop_tmuxflow.py — Stop all tmux sessions for a BridgeV002 flow.

Power script: kills tmux sessions without hesitation.
No Ollama checks, no model unloading, no inspection — just kill.

Usage:
    python3 scripts/bridgeV002/stop_tmuxflow.py <flow_key>

Example:
    python3 scripts/bridgeV002/stop_tmuxflow.py strict_review
"""

import argparse
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attach_tmux import VIEWER_SESSION_PREFIX  # noqa: E402


def get_flow_tmux_sessions(db_path, flow_key):
    """Fetch all tmux session names for active steps in a flow."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT DISTINCT r.tmux_session
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON r.role_key IN (s.from_role, s.to_role)
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
          AND r.tmux_session IS NOT NULL
        """,
        (flow_key,),
    ).fetchall()

    conn.close()
    return {row["tmux_session"] for row in rows}


def kill_tmux_sessions(sessions):
    """Kill all given tmux sessions. No questions asked."""
    killed = []
    for session in sorted(sessions):
        print(f"  Killing tmux session '{session}'...")
        result = subprocess.run(
            ["tmux", "kill-session", "-t", "=" + session],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            killed.append(session)
            print(f"    Killed.")
        else:
            msg = result.stderr.strip()
            if "can't find session" in msg.lower():
                print(f"    Already dead.")
                killed.append(session)  # not an error — session already gone
            else:
                print(f"    WARNING: {msg}")
    return killed


def main():
    parser = argparse.ArgumentParser(
        description="Stop all tmux sessions for a BridgeV002 flow."
    )
    parser.add_argument("flow_key", help="Flow key (e.g. strict_review)")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))

    spec = __import__('importlib.util').util.spec_from_file_location(
        'config', os.path.join(project_root, 'config.py')
    )
    config_mod = __import__('importlib.util').util.module_from_spec(spec)
    spec.loader.exec_module(config_mod)

    db_path = config_mod.get_db_path()

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    sessions = get_flow_tmux_sessions(db_path, args.flow_key)

    # The viewer session created by attach_tmux.py groups the role sessions
    # as linked windows — it survives its members and must be killed too,
    # or every Start/Stop cycle leaves an orphaned flow-<flow_key> session.
    sessions.add(f"{VIEWER_SESSION_PREFIX}{args.flow_key}")

    if not sessions:
        print(f"No tmux sessions found for flow '{args.flow_key}'. Nothing to do.")
        return

    print(f"Stopping {len(sessions)} tmux session(s) for flow '{args.flow_key}':")
    killed = kill_tmux_sessions(sessions)
    print(f"\nDone: {len(killed)} session(s) killed.")


if __name__ == "__main__":
    main()
