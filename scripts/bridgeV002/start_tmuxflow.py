#!/usr/bin/env python3
"""start_tmuxflow.py — Ensure tmux sessions exist for a BridgeV002 flow.

Usage:
    python3 scripts/bridgeV002/start_tmuxflow.py <flow_key>

Example:
    python3 scripts/bridgeV002/start_tmuxflow.py strict_review
"""

import argparse
import os
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime_owner  # noqa: E402


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


def _native_harness_env_names():
    """Credential env names the natively launched harnesses declare.

    Imported defensively: harness.py pulls in the standalone allocator, and
    an optional dependency missing there must never stop a flow starting.
    """
    try:
        import harness  # noqa: E402 -- late and optional by design
    except Exception:
        return set()
    names = set()
    for mapping in getattr(harness, "REQUIRED_ENV", {}).values():
        names.update(mapping)
    return names


def _allocator_env_names(config_mod):
    """Credential env names the model allocator's runtime profiles declare.

    Derived from runtime_profiles.yaml rather than listed here: the allocator
    owns which credential each backend reads, and a copy kept in this script
    would rot silently the next time a profile is added. Parsed with a regex
    on purpose -- PyYAML is not a DPMtF dependency, and starting a flow must
    not require one.
    """
    try:
        root = config_mod.get_project_path("model-allocator")
    except Exception:
        return set()
    path = os.path.join(root, "runtime_profiles.yaml")
    if not os.path.exists(path):
        return set()
    pattern = re.compile(r"^\s*api_key_env:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$")
    names = set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            match = pattern.match(line)
            if match:
                names.add(match.group(1))
    return names


def propagate_credentials(names):
    """Copy credentials this process holds into the tmux SERVER environment.

    A tmux session inherits the server's global environment at the moment it
    is created, and that environment is fixed when the server starts. config
    loads .env into THIS process only, so without this step a key that lives
    in .env never reaches a chain role's pane: the role fails at dispatch
    with an auth error while .env looks perfectly correct. Pushing the values
    in here, before any session is created below, closes that gap and makes
    .env the durable source it is meant to be.

    Values are never printed -- only the name and whether one was found. The
    value does pass through the tmux argv, so it is briefly visible to this
    same user in `ps`; that is the same exposure the environment already has
    on a single-user host. Sessions that already exist keep the environment
    they were created with; only sessions created from here inherit these.
    """
    # start-server is a no-op when a server is already up, and without it
    # set-environment has no server to write to on a cold machine.
    subprocess.run(["tmux", "start-server"], capture_output=True)

    propagated, missing = [], []
    for name in sorted(names):
        value = os.environ.get(name)
        if not value:
            missing.append(name)
            continue
        result = subprocess.run(
            ["tmux", "set-environment", "-g", name, value],
            capture_output=True,
        )
        if result.returncode == 0:
            propagated.append(name)
        else:
            err = result.stderr.decode("utf-8", "replace").strip()
            print(f"  {name} - WARNING: tmux set-environment failed: {err}")
    return propagated, missing


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

    # 2. Push the credentials this process holds into the tmux server
    #    environment BEFORE any session is created, so every session made
    #    below inherits them. Without this, .env reaches only this process.
    cred_names = _native_harness_env_names() | _allocator_env_names(config_mod)
    if cred_names:
        print(f"\nCredentials for flow '{args.flow_key}':")
        propagated, missing = propagate_credentials(cred_names)
        for name in propagated:
            print(f"  {name} - propagated to the tmux server")
        for name in missing:
            print(f"  {name} - not set in this process, skipped")

    # 3. Ensure each session exists (create if missing)
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
                # Ownership rule: a session DPMtF created is a session DPMtF
                # may later tear down. Record it so Stop servers never has to
                # guess, and never touches an externally created session.
                runtime_owner.record(args.flow_key, "tmux_session", s)
                print(f"    created")
            except subprocess.CalledProcessError as e:
                print(f"    ERROR: Failed to create session: {e}")

    # 4. Rebuild the flow viewer. Recreating sessions silently breaks the
    # viewer's linked windows, and the Human's `tmux attach -t flow-<key>`
    # then shows dead panes -- indistinguishable from a stalled chain.
    # Best-effort: the sessions themselves are already up.
    if created:
        viewer = os.path.join(script_dir, "attach_tmux.py")
        try:
            subprocess.run(["python3", viewer, args.flow_key],
                           capture_output=True, timeout=30)
            print(f"Viewer rebuilt: tmux attach -t flow-{args.flow_key}")
        except Exception as exc:
            print(f"WARNING: viewer rebuild failed: {exc}")

    # 5. Summary
    print(f"\nDone: {len(existing)} existing, {len(created)} created "
          f"({len(required_sessions)} total).")


if __name__ == "__main__":
    main()
