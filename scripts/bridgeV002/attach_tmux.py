#!/usr/bin/env python3
"""attach_tmux.py — Create a viewer tmux session grouping all flow sessions.

Power script: builds a single tmux session with one window per flow role.
No GUI terminal needed — works from server context.
The user attaches manually: tmux attach -t flow-<flow_key>

Usage:
    python3 scripts/bridgeV002/attach_tmux.py <flow_key>

Example:
    python3 scripts/bridgeV002/attach_tmux.py strict_review
    # Then in your terminal: tmux attach -t flow-strict_review
"""

import argparse
import os
import sqlite3
import subprocess
import sys


VIEWER_SESSION_PREFIX = "flow-"


def get_flow_tmux_sessions(db_path, flow_key):
    """Fetch all tmux session names for active steps in a flow, in step order."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT DISTINCT r.tmux_session, s.sort_order
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.from_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
          AND r.tmux_session IS NOT NULL
        ORDER BY s.sort_order
        """,
        (flow_key,),
    ).fetchall()

    conn.close()
    return [row["tmux_session"] for row in rows]


def session_exists(session_name):
    """Check if a tmux session is running."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", "=" + session_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def build_viewer_session(viewer_name, flow_sessions):
    """Create a viewer tmux session with one window per flow session.

    Each window is linked from the corresponding flow session, so the
    user sees exactly what each role sees.
    """
    # Kill existing viewer session if present (from a previous run)
    if session_exists(viewer_name):
        subprocess.run(
            ["tmux", "kill-session", "-t", "=" + viewer_name],
            capture_output=True, text=True,
        )

    # Create fresh viewer session (detached, one empty window)
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", viewer_name, "-n", "dummy"],
        capture_output=True, text=True,
    )

    linked = []
    for i, session in enumerate(flow_sessions):
        if not session_exists(session):
            print(f"  Skipping '{session}' — not running")
            continue

        # Link flow session's window 0 into viewer at index i
        # -k kills the target window first if it exists (e.g. the dummy window at index 0)
        result = subprocess.run(
            ["tmux", "link-window", "-k", "-s", f"{session}:0", "-t", f"{viewer_name}:{i}"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            # Rename window to show which session it belongs to
            subprocess.run(
                ["tmux", "rename-window", "-t", f"{viewer_name}:{i}", session],
                capture_output=True, text=True,
            )
            linked.append(session)
            print(f"  Linked '{session}' → window {i}")
        else:
            print(f"  WARNING: Failed to link '{session}': {result.stderr.strip()}")

    return linked


def main():
    parser = argparse.ArgumentParser(
        description="Build viewer tmux session for a BridgeV002 flow."
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

    if not subprocess.run(["which", "tmux"], capture_output=True).returncode == 0:
        print("ERROR: tmux not found")
        sys.exit(1)

    flow_sessions = get_flow_tmux_sessions(db_path, args.flow_key)

    if not flow_sessions:
        print(f"No tmux sessions found for flow '{args.flow_key}'. Nothing to do.")
        return

    viewer_name = f"{VIEWER_SESSION_PREFIX}{args.flow_key}"

    print(f"Building viewer session '{viewer_name}' for flow '{args.flow_key}':")
    linked = build_viewer_session(viewer_name, flow_sessions)

    if linked:
        print(f"\nDone: {len(linked)} session(s) linked into '{viewer_name}'.")
        print(f"Attach from your terminal: tmux attach -t {viewer_name}")
    else:
        print(f"\nNo running sessions to link for '{args.flow_key}'.")


if __name__ == "__main__":
    main()
