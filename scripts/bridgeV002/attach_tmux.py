#!/usr/bin/env python3
"""attach_tmuxflow.py — Attach to all tmux sessions for a BridgeV002 flow.

Usage:
    python3 scripts/bridgeV002/attach_tmux.py <flow_key>

Iterates through all active steps in the given flow, looks up each
FROM-ROLE's tmux_session, and opens each existing session in a new
terminal tab or window.

Requires a terminal emulator (xfce4-terminal, gnome-terminal, or x-terminal-emulator).

Example:
    python3 scripts/bridgeV002/attach_tmux.py strict_review
"""

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def get_active_flow_roles(db_path, flow_key):
    """Fetch all unique FROM-ROLE tmux sessions for active steps in a flow.

    Returns a sorted list of session name strings.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sessions = set()
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
            sessions.add(ts)

    conn.close()
    return sorted(sessions)


def find_terminal():
    """Find an available terminal emulator."""
    for name in ("xfce4-terminal", "gnome-terminal", "x-terminal-emulator"):
        path = shutil.which(name)
        if path:
            return name, path
    return None, None


def attach_in_new_tab(terminal_name, session_name):
    """Open a tmux attach command in a new tab/window of the terminal."""
    if "xfce4-terminal" in terminal_name:
        cmd = [
            "xfce4-terminal",
            "--title", f"tmux:{session_name}",
            "--command", f"tmux attach -t {session_name}"
        ]
    elif "gnome-terminal" in terminal_name:
        cmd = [
            "gnome-terminal",
            "--title", f"tmux:{session_name}",
            "--", "tmux", "attach", "-t", session_name
        ]
    else:
        # Generic x-terminal-emulator — try --command first, fall back to -e
        cmd = [shutil.which("x-terminal-emulator"), "-e", f"tmux attach -t {session_name}"]

    subprocess.Popen(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Attach to all tmux sessions for a BridgeV002 flow."
    )
    parser.add_argument("flow_key", help="Flow key (e.g. strict_review)")
    args = parser.parse_args()

    # Resolve database path — config.py lives TWO levels up from this script
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

    # 1. Get all tmux session names from flow
    sessions = get_active_flow_roles(db_path, args.flow_key)
    if not sessions:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. Find a terminal emulator
    term_name, term_path = find_terminal()
    if not term_path:
        print("ERROR: No supported terminal found (xfce4-terminal, gnome-terminal, or x-terminal-emulator)")
        sys.exit(1)

    if not shutil.which("tmux"):
        print("ERROR: tmux not found")
        sys.exit(1)

    # 3. Attach to each session in a new tab/window
    attached = []
    for session_name in sessions:
        # Check session exists before trying to attach
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            print(f"  Attaching to tmux session: {session_name}")
            attach_in_new_tab(term_name, session_name)
            attached.append(session_name)
        else:
            print(f"  Skipped (not running): {session_name}")

    if attached:
        print(f"\nDone: {len(attached)} session(s) attached.")
    else:
        print(f"\nNo running sessions to attach for '{args.flow_key}'.")


if __name__ == "__main__":
    main()
