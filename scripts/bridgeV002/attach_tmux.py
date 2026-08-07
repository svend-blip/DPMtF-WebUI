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


def get_flow_roles(db_path, flow_key):
    """Every role in the flow, in the order the chain visits them.

    One query, because the window order has to be one order. A role's
    position is the earliest step it takes part in: as a sender that is the
    step's own sort_order, as a receiver it is half a step later, so the role
    that receives a handoff comes after the one that sends it. That places
    the terminal role, which is never a sender, last instead of nowhere.

    Returns dicts with role_key, tmux_session and execution_target.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.role_key, r.tmux_session, r.execution_target,
               MIN(CASE WHEN s.from_role = r.role_key
                        THEN s.sort_order * 2 ELSE s.sort_order * 2 + 1 END) AS pos
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON r.role_key IN (s.from_role, s.to_role)
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
        GROUP BY r.role_key, r.tmux_session, r.execution_target
        ORDER BY pos
        """,
        (flow_key,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def is_remote(role):
    """A role executes elsewhere if it names a machine to execute on."""
    return bool((role["execution_target"] or "").strip())


def get_flow_tmux_sessions(db_path, flow_key):
    """Local session names for a flow, in chain order.

    A role with an execution_target has no session on this machine — its pane
    lives on the worker — so linking one here would show an empty window that
    reads exactly like a role that never started.
    """
    return [r["tmux_session"] for r in get_flow_roles(db_path, flow_key)
            if r["tmux_session"] and not is_remote(r)]


def get_remote_roles(db_path, flow_key):
    """Roles in this flow that execute on another machine, in chain order.

    Their panes cannot be linked — a linked window is one tmux server's
    window, and theirs is on a different host. They get a window that ssh's
    in and attaches to the worker's own tmux instead, so one
    `attach -t flow-<key>` shows the whole chain regardless of where each
    role runs.
    """
    return [(r["role_key"], r["execution_target"])
            for r in get_flow_roles(db_path, flow_key) if is_remote(r)]


def remote_follow_command(worker):
    """Shell that shows the live execution if there is one, the daemon if not.

    A worker creates a fresh `dpmtf-<role>-<execution>` session per execution
    and drops it on cleanup, so attaching to a fixed name would show an empty
    pane most of the time and nothing during the work. This follows whatever
    is there.
    """
    # Mirrors the pane rather than attaching to it.
    #
    # `tmux attach` was the obvious thing and it is wrong here: it re-picks a
    # session only when the attach *exits*, and an attach does not exit. The
    # window latched onto the daemon at startup and stayed there through a
    # whole execution, showing an idle poller while the role worked one
    # session away.
    #
    # Capturing re-picks every cycle, so the window follows the worker from
    # daemon to execution and back without anyone touching it. It is
    # read-only, which is the right shape anyway — typing into a role's
    # session mid-run is the thing a monitoring view must not make easy.
    #
    # Double quotes inside, single quotes outside: the tmux format string
    # carries braces and a hash, and single-quoting it would end the ssh
    # argument early.
    inner = (
        'while true; do '
        's=$(tmux ls -F "#{session_name}" 2>/dev/null | grep "^dpmtf-" | head -1); '
        '[ -z "$s" ] && s=lightworker-daemon; '
        'out=$(tmux capture-pane -p -t "$s" 2>/dev/null); '
        'clear; '
        'printf "%s  [%s]\\n\\n" "$s" "$(date +%H:%M:%S)"; '
        'printf "%s\\n" "$out" | tail -n $((${LINES:-40} - 3)); '
        'sleep 2; '
        'done'
    )
    # The retry loop above lives INSIDE ssh. If the connection itself drops,
    # ssh exits, the window command ends, and tmux closes the window -- the
    # role silently disappears from the viewer, which is exactly the
    # ambiguity this window exists to remove (an absent role reads as one
    # that never started). So ssh is wrapped in a second, local loop: a
    # dropped connection becomes a visible "reconnecting" line and a retry,
    # not a vanished window.
    return (
        f"while true; do ssh -t {worker} '{inner}'; "
        f'printf "\\n[%s] forbindelsen til {worker} røg — prøver igen om 5s\\n" '
        '"$(date +%H:%M:%S)"; sleep 5; done'
    )


def session_exists(session_name):
    """Check if a tmux session is running."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", "=" + session_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def build_viewer_session(viewer_name, roles):
    """One window per role, in chain order, whichever machine it runs on.

    Local roles get their own window linked in, so the viewer shows exactly
    what the role sees. A remote role's window cannot be linked — a linked
    window belongs to one tmux server — so it ssh's into the worker instead.
    Both kinds are placed at the role's position in the chain: reading the
    viewer left to right has to be reading the flow.

    A role whose session is not running leaves its index empty rather than
    pulling the rest forward. tmux does not require contiguous indices, and
    the alternative is a viewer whose order silently changes with whatever
    happened to be up.
    """
    if session_exists(viewer_name):
        subprocess.run(
            ["tmux", "kill-session", "-t", "=" + viewer_name],
            capture_output=True, text=True,
        )

    subprocess.run(
        ["tmux", "new-session", "-d", "-s", viewer_name, "-n", "dummy"],
        capture_output=True, text=True,
    )

    shown = []
    for index, role in enumerate(roles):
        target = f"{viewer_name}:{index}"
        if is_remote(role):
            worker = role["execution_target"].strip()
            name = f"{role['role_key']}@{worker}"
            # -k replaces whatever occupies the index, including the dummy
            # window, exactly as the link path does.
            result = subprocess.run(
                ["tmux", "new-window", "-d", "-k", "-t", target,
                 "-n", name, remote_follow_command(worker)],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                shown.append(role["role_key"])
                print(f"  Attached '{role['role_key']}' on {worker} "
                      f"→ window {index}")
            else:
                print(f"  WARNING: could not attach '{role['role_key']}' on "
                      f"{worker}: {result.stderr.strip()}")
            continue

        session = role["tmux_session"]
        if not session or not session_exists(session):
            print(f"  Skipping '{role['role_key']}' — session not running")
            continue

        result = subprocess.run(
            ["tmux", "link-window", "-k", "-s", f"{session}:0", "-t", target],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            subprocess.run(
                ["tmux", "rename-window", "-t", target, session],
                capture_output=True, text=True,
            )
            shown.append(session)
            print(f"  Linked '{session}' → window {index}")
        else:
            print(f"  WARNING: Failed to link '{session}': "
                  f"{result.stderr.strip()}")

    return shown


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

    roles = get_flow_roles(db_path, args.flow_key)
    roles = [r for r in roles if r["tmux_session"] or is_remote(r)]

    if not roles:
        print(f"No roles found for flow '{args.flow_key}'. Nothing to do.")
        return

    viewer_name = f"{VIEWER_SESSION_PREFIX}{args.flow_key}"

    print(f"Building viewer session '{viewer_name}' for flow '{args.flow_key}':")
    linked = build_viewer_session(viewer_name, roles)

    if linked:
        print(f"\nDone: {len(linked)} session(s) linked into '{viewer_name}'.")
        print(f"Attach from your terminal: tmux attach -t {viewer_name}")
    else:
        print(f"\nNo running sessions to link for '{args.flow_key}'.")


if __name__ == "__main__":
    main()
