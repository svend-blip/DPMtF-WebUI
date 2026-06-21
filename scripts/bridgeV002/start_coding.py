#!/usr/bin/env python3
"""start_coding.py — Execute start_cmd for all roles in a BridgeV002 flow.

Usage:
    python3 scripts/bridgeV002/start_coding.py <flow_key>

Iterates through all active steps in the given flow, looks up each step's
FROM-ROLE and executes its start_cmd in the role's dedicated tmux session.

**Assumes sessions are already created** (use start_tmuxflow.py first).
If a role has no start_cmd defined, it is skipped with a warning.

Example:
    python3 scripts/bridgeV002/start_coding.py strict_review
"""

import argparse
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bridge_lib import resolve_placeholders  # noqa: E402


def get_flow_roles(db_path, flow_key):
    """Fetch all from_role role data for active steps in a flow.

    Returns a list of dicts sorted by sort_order:
        [{role_key, tmux_session, start_cmd}, ...]
    Duplicate roles are deduplicated (first occurrence wins).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT r.role_key, r.tmux_session, r.start_cmd
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.from_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
        ORDER BY s.sort_order
        """,
        (flow_key,),
    ).fetchall()

    # Deduplicate by role_key (first occurrence wins)
    seen = set()
    result = []
    for row in rows:
        rk = row["role_key"]
        if rk not in seen:
            seen.add(rk)
            result.append({
                "role_key": row["role_key"],
                "tmux_session": row["tmux_session"],
                "start_cmd": row["start_cmd"],
            })

    conn.close()
    return result


def ensure_session_exists(session_name):
    """Check if a tmux session exists. Returns True if it does."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_cmd_in_session(session_name, start_cmd, bridge_dir, project_root):
    """Run a resolved command in an existing tmux session via send-keys.

    Assumes the session already exists (use start_tmuxflow.py to create it).
    Prints the resolved command before executing.
    Returns True on success.
    """
    # Resolve placeholders in start_cmd via bridge_lib
    resolved = resolve_placeholders(start_cmd, bridge_dir=bridge_dir, project_root=project_root)

    print(f"  Command: {resolved}")

    cmd = ["tmux", "send-keys", "-t", session_name, resolved, "Enter"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Start coding frontends for all roles in a BridgeV002 flow."
    )
    parser.add_argument("flow_key", help="Flow key (e.g. strict_review)")
    args = parser.parse_args()

    # Resolve paths — config.py lives TWO levels up from this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_derived = os.path.dirname(os.path.dirname(script_dir))

    # Directly import config from absolute path to avoid sys.path conflicts
    spec = __import__("importlib.util").util.spec_from_file_location(
        "config", os.path.join(project_root_derived, "config.py")
    )
    config_mod = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(config_mod)

    db_path = config_mod.get_db_path()
    project_root = config_mod.get_project_root()
    bridge_dir = config_mod.get_bridge_base_path()

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    # 1. Get all roles for this flow (deduplicated, sorted by step order)
    roles = get_flow_roles(db_path, args.flow_key)
    if not roles:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. Process each role — execute start_cmd in existing tmux session
    started = []
    skipped = []
    errors = []
    for role in roles:
        session_name = role["tmux_session"]
        start_cmd = role["start_cmd"]

        if not start_cmd:
            print(f"  {role['role_key']:15s} → '{session_name}'  (skipped — no start_cmd)")
            skipped.append(role["role_key"])
            continue

        # Verify session exists before trying to run
        if not ensure_session_exists(session_name):
            msg = f"ERROR: tmux session '{session_name}' does not exist. Run start_tmuxflow.py first."
            print(f"  {role['role_key']:15s} → '{session_name}'")
            print(f"    {msg}", file=sys.stderr)
            errors.append(role["role_key"])
            continue

        # Execute the role's start command in the existing tmux session
        print(f"  {role['role_key']:15s} → '{session_name}'  (start_cmd) ...")
        ok = run_cmd_in_session(session_name, start_cmd, bridge_dir, project_root)
        if ok:
            started.append(session_name)
            print(f"    Command sent to session.")
        else:
            print(f"    ERROR running command in '{session_name}'.", file=sys.stderr)
            errors.append(role["role_key"])

    # Summary
    parts = []
    if started:
        parts.append(f"{len(started)} start_cmd(s) executed")
    if skipped:
        parts.append(f"{len(skipped)} role(s) skipped (no start_cmd)")
    if errors:
        parts.append(f"{len(errors)} error(s)")
    if not parts:
        print(f"\nDone: no roles with start_cmd in flow '{args.flow_key}'.")
    else:
        print(f"\nDone: {'; '.join(parts)}.")


if __name__ == "__main__":
    main()
