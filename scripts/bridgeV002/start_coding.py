#!/usr/bin/env python3
"""start_coding.py — Start coding frontends for each role in a flow.

Usage:
    python3 scripts/bridgeV002/start_coding.py <flow_key>

Iterates through all active steps in the given flow, looks up each step's
TO-ROLE, resolves the model via Model Allocator, and starts the coding
frontend (opencode/claude-code/freebuff) in the role's tmux session.

**Assumes sessions are already created** (use start_tmuxflow.py first).
Roles without a model_allocator alias are skipped with a warning.

Example:
    python3 scripts/bridgeV002/start_coding.py strict_review
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bridge_lib import (  # noqa: E402
    ensure_opencode_model_field,
    get_effective_model_source,
    resolve_placeholders,
)

# Phase 2: direct command_builder path removed — all roles use model_allocator.
# render_tmux_shell_string is still needed for the allocator run command output.
from command_builder import render_tmux_shell_string  # noqa: E402


def get_flow_roles(db_path, flow_key):
    """Fetch all role data for active steps in a flow (both from_role and to_role).

    Returns a list of dicts sorted by sort_order:
        [{role_key, tmux_session, default_model_source, default_model_alias,
          max_output_tokens, config_dir}, ...]
    Duplicate roles are deduplicated (first occurrence wins).

    Includes the last step's to_role so the final role in the chain
    also gets its coding frontend started.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Fetch from_role entries
    from_rows = conn.execute(
        """
        SELECT r.role_key, r.tmux_session,
               r.default_model_source, r.default_model_alias,
               r.max_output_tokens,
               r.config_dir,
               s.sort_order
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.from_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
        """,
        (flow_key,),
    ).fetchall()

    # Fetch the last step's to_role (final role in chain, never a from_role)
    to_rows = conn.execute(
        """
        SELECT r.role_key, r.tmux_session,
               r.default_model_source, r.default_model_alias,
               r.max_output_tokens,
               r.config_dir,
               s.sort_order + 0.5 AS sort_order
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.to_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
        ORDER BY s.sort_order DESC
        LIMIT 1
        """,
        (flow_key,),
    ).fetchall()

    # Combine and deduplicate by role_key (first occurrence wins)
    all_rows = list(from_rows) + list(to_rows)
    all_rows.sort(key=lambda r: r["sort_order"])

    seen = set()
    result = []
    for row in all_rows:
        rk = row["role_key"]
        if rk not in seen:
            seen.add(rk)
            result.append({
                "role_key": row["role_key"],
                "tmux_session": row["tmux_session"],
                "default_model_source": row["default_model_source"],
                "default_model_alias": row["default_model_alias"],
                "max_output_tokens": row["max_output_tokens"],
                "config_dir": row["config_dir"],
            })

    conn.close()
    return result


def ensure_session_exists(session_name):
    """Check if a tmux session exists. Returns True if it does."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", "=" + session_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_cmd_in_session(session_name, cmd_str, bridge_dir, project_root):
    """Send the start command string to an existing tmux session via send-keys.

    The cmd_str is expected to be a fully-formed shell command (typically
    built by the Machine Profile command_builder). Returns True on success,
    False on failure.
    """
    if not cmd_str:
        print(f"  ERROR: No command string to send")
        return False

    resolved = resolve_placeholders(
        cmd_str, bridge_dir=bridge_dir, project_root=project_root
    )
    print(f"  Command: {resolved}")
    cmd = ["tmux", "send-keys", "-t", "=" + session_name + ":0", resolved, "Enter"]
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

    # Machine Profile — always used for command building
    machine_profile = config_mod.get_machine_profile()
    if not machine_profile:
        print("ERROR: No valid Machine Profile found.")
        print("  Create profiles/machine.local.json or set DPMTF_MACHINE_PROFILE in .env.")
        return 1

    # 2. Process each role — send the built start command to its tmux session
    started = []
    skipped = []
    errors = []
    for role in roles:
        session_name = role["tmux_session"]

        if not role.get("default_model_source"):
            print(f"  {role['role_key']:15s} → '{session_name}'  (skipped — no model_source)")
            skipped.append(role["role_key"])
            continue

        # Verify session exists before trying to run
        if not ensure_session_exists(session_name):
            msg = f"ERROR: tmux session '{session_name}' does not exist. Run start_tmuxflow.py first."
            print(f"  {role['role_key']:15s} → '{session_name}'")
            print(f"    {msg}", file=sys.stderr)
            errors.append(role["role_key"])
            continue

        # Derive allocator client from model_source
        allocator_client = "opencode"

        # V1B pilot: use Model Allocator when role opts in.
        model_source, model_alias = get_effective_model_source(
            role["role_key"], db_path=db_path
        )
        if model_source == "model_allocator":
            model_allocator_path = os.path.join(
                config_mod.get_project_path("model-allocator"),
                "scripts",
                "model-allocator",
            )

            # V2.2: regenerate role-specific opencode.json so the OpenCode TUI
            # uses the allocator-selected model. This is only needed/correct for
            # the opencode client; other clients follow the existing path.
            if allocator_client == "opencode":
                config_dir = role.get("config_dir") or role["role_key"]
                opencode_json_path = os.path.expanduser(
                    f"~/.config/opencode-roles/{config_dir}/opencode.json"
                )
                try:
                    subprocess.run(
                        [
                            model_allocator_path,
                            "render-config",
                            "--role", role["role_key"],
                            "--client", "opencode",
                            "--output", opencode_json_path,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=60,
                    )
                    print(f"    Regenerated opencode.json at {opencode_json_path}")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    print(f"    WARNING: render-config failed; continuing with start command")
                    if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                        print(f"      stderr: {exc.stderr.strip()}")

            try:
                run_cmd = [
                    model_allocator_path,
                    "run",
                    "--role", role["role_key"],
                    "--client", allocator_client,
                ]
                # Pass per-role max_output_tokens from DB
                if role.get("max_output_tokens"):
                    run_cmd += ["--max-output-tokens", str(role["max_output_tokens"])]
                result = subprocess.run(
                    run_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,
                )
                shell_str = result.stdout.strip()
                # cwd: same fallback as the Machine-Profile path.
                cwd = project_root
                mp_paths = machine_profile.get("paths", {})
                cwd = mp_paths.get("project_root", project_root)
                cmd_str = f"cd {cwd} && {shell_str}"
                print(f"  {role['role_key']:15s} → '{session_name}'  (model_allocator) ...")
                ok = run_cmd_in_session(
                    session_name,
                    cmd_str,
                    bridge_dir,
                    project_root,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                print(f"  {role['role_key']:15s} → '{session_name}'")
                print(f"  ERROR calling model-allocator: {exc}")
                if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                    print(f"    stderr: {exc.stderr.strip()}")
                errors.append(role["role_key"])
                continue

            if ok:
                started.append(session_name)
                print(f"    Command sent to session.")
            else:
                print(f"    ERROR running command in '{session_name}'.", file=sys.stderr)
                errors.append(role["role_key"])
            continue

        # Phase 2: direct/command_builder path removed — all roles use model_allocator.
        # If a role reaches here, it has an unknown model_source.
        print(f"  {role['role_key']:15s} → '{session_name}'")
        print(f"  ERROR: role has model_source='{model_source}' — expected 'model_allocator'")
        errors.append(role["role_key"])

    # Summary
    parts = []
    if started:
        parts.append(f"{len(started)} start command(s) executed")
    if skipped:
        parts.append(f"{len(skipped)} role(s) skipped (no model_source)")
    if errors:
        parts.append(f"{len(errors)} error(s)")
    if not parts:
        print(f"\nDone: no roles with model_source in flow '{args.flow_key}'.")
    else:
        print(f"\nDone: {'; '.join(parts)}.")


if __name__ == "__main__":
    main()
