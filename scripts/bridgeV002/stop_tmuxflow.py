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
    """Local session names for a flow's roles.

    A role with an execution_target has no local session — its tmux lives
    on the worker. Killing its session NAME here hit nothing ("Already
    dead") while the real sessions kept running remotely, so Stop tmux
    looked successful and stopped half the flow.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT DISTINCT r.tmux_session
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON r.role_key IN (s.from_role, s.to_role)
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
          AND r.tmux_session IS NOT NULL
          AND (r.execution_target IS NULL OR TRIM(r.execution_target) = '')
        """,
        (flow_key,),
    ).fetchall()

    conn.close()
    return {row["tmux_session"] for row in rows}


def get_remote_roles(db_path, flow_key):
    """(role_key, execution_target) for the flow's remote roles."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT DISTINCT r.role_key, r.execution_target
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON r.role_key IN (s.from_role, s.to_role)
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
          AND r.execution_target IS NOT NULL
          AND TRIM(r.execution_target) != ''
        """,
        (flow_key,),
    ).fetchall()
    conn.close()
    return sorted({(r["role_key"], r["execution_target"]) for r in rows})


def kill_remote_sessions(remote_roles):
    """Kill the worker-side tmux for each remote role: the per-execution
    `dpmtf-<role>-*` sessions and the `lightworker-daemon` shell.

    Stopping the daemon stops the polling loop, so nothing new is claimed
    after the button is pressed — which is what "stop" means. Restart is
    documented in DPMtF-LightWorker's README (the daemon runs in a tmux
    session the steward starts). Best-effort with a short timeout: an
    unreachable worker must not hang the endpoint.
    """
    killed = []
    for role_key, target in remote_roles:
        print(f"  Remote role {role_key} on {target}:")
        script = (
            "for s in $(tmux ls -F '#{session_name}' 2>/dev/null "
            f"| grep '^dpmtf-'); do tmux kill-session -t \"$s\"; "
            "echo \"killed $s\"; done; "
            # The daemon may run either way: as the systemd user unit
            # (deploy/lightworker-daemon.service — Restart=always, so
            # killing only a process would resurrect it behind the
            # button's back) or hand-started in a tmux session for
            # debugging. Stop both; each reports only if it acted.
            "systemctl --user stop lightworker-daemon 2>/dev/null "
            "&& echo 'stopped lightworker-daemon.service'; "
            "tmux kill-session -t =lightworker-daemon 2>/dev/null "
            "&& echo 'killed lightworker-daemon' || true"
        )
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
             target, script],
            capture_output=True, text=True, timeout=30,
        )
        out = (result.stdout or "").strip()
        for line in out.splitlines():
            print(f"    {line}")
            killed.append(f"{target}:{line.replace('killed ', '')}")
        if result.returncode != 0 and not out:
            print(f"    WARNING: could not reach {target}: "
                  f"{(result.stderr or '').strip()[:120]}")
    return killed


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
    remote = get_remote_roles(db_path, args.flow_key)
    if remote:
        killed += kill_remote_sessions(remote)
    print(f"\nDone: {len(killed)} session(s) killed.")


if __name__ == "__main__":
    main()
