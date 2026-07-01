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

# Machine Profile Fase 2A — command builder
from command_builder import build_start_command, render_tmux_shell_string  # noqa: E402


def get_flow_roles(db_path, flow_key):
    """Fetch all role data for active steps in a flow (both from_role and to_role).

    Returns a list of dicts sorted by sort_order:
        [{role_key, tmux_session, start_cmd}, ...]
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
               r.default_runtime, r.default_provider, r.default_model,
               r.config_dir,
               s.runtime_override, s.provider_override, s.model_override,
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
               r.default_runtime, r.default_provider, r.default_model,
               r.config_dir,
               s.runtime_override, s.provider_override, s.model_override,
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
                "default_runtime": row["default_runtime"],
                "default_provider": row["default_provider"],
                "default_model": row["default_model"],
                "config_dir": row["config_dir"],
                "runtime_override": row["runtime_override"],
                "provider_override": row["provider_override"],
                "model_override": row["model_override"],
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


def run_cmd_in_session(session_name, start_cmd, bridge_dir, project_root,
                       start_cmd_suffix=None, target_project=None):
    """Run a start command in an existing tmux session via send-keys.

    If start_cmd_suffix is set, builds aggregated command from:
      cd {target_project} {suffix}
    Otherwise falls back to the existing start_cmd field.

    Returns True on success, False on failure.
    """
    if start_cmd_suffix and target_project:
        # New decomposed mode: build aggregated command
        resolved_suffix = resolve_placeholders(
            start_cmd_suffix, bridge_dir=bridge_dir, project_root=project_root
        )
        resolved_target = resolve_placeholders(
            target_project, bridge_dir=bridge_dir, project_root=project_root
        )
        cmd_str = build_aggregated_cmd(resolved_target, resolved_suffix)
        print(f"  Aggregated: {cmd_str}")
        # Send as separate arguments — no shell quoting needed with subprocess
        cmd = ["tmux", "send-keys", "-t", session_name, cmd_str, "Enter"]
    elif start_cmd:
        # Fallback: use existing start_cmd as before
        resolved = resolve_placeholders(
            start_cmd, bridge_dir=bridge_dir, project_root=project_root
        )
        print(f"  Command: {resolved}")
        cmd = ["tmux", "send-keys", "-t", session_name, resolved, "Enter"]
    else:
        print(f"  ERROR: No start_cmd or start_cmd_suffix configured")
        return False

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def build_aggregated_cmd(target_project, start_cmd_suffix):
    """Build the aggregated start command from decomposed fields.

    Returns the command string to send to the tmux session, or None if
    required fields are missing.

    Format: cd {target_project} {suffix}
    The closing quote and Enter are added by run_cmd_in_session.
    Suffix should NOT include ' Enter — only the command itself.
    """
    if not start_cmd_suffix:
        return None
    if not target_project:
        return None
    return f"cd {target_project} {start_cmd_suffix}"


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

    # 2. Process each role — execute start_cmd in existing tmux session
    started = []
    skipped = []
    errors = []
    for role in roles:
        session_name = role["tmux_session"]

        if not role.get("default_runtime"):
            print(f"  {role['role_key']:15s} → '{session_name}'  (skipped — no default_runtime)")
            skipped.append(role["role_key"])
            continue

        # Verify session exists before trying to run
        if not ensure_session_exists(session_name):
            msg = f"ERROR: tmux session '{session_name}' does not exist. Run start_tmuxflow.py first."
            print(f"  {role['role_key']:15s} → '{session_name}'")
            print(f"    {msg}", file=sys.stderr)
            errors.append(role["role_key"])
            continue

        # Build command from Machine Profile
        try:
            # Fase 2B: override chain — step override > role default
            runtime = role.get("runtime_override") or role.get("default_runtime")
            provider = role.get("provider_override") or role.get("default_provider")
            model = role.get("model_override") or role.get("default_model")

            cmd_obj = build_start_command(
                runtime=runtime,
                provider=provider,
                model=model,
                role_key=role["role_key"],
                machine_profile=machine_profile,
                config_dir=role.get("config_dir"),
            )

            # Check model against provider model list (warning only)
            provider_key = role.get("default_provider")
            if provider_key and provider_key in machine_profile.get("providers", {}):
                provider_models = machine_profile["providers"][provider_key].get("models", [])
                if provider_models and role.get("default_model") not in provider_models:
                    print(f"  WARNING: model '{role.get('default_model')}' not in "
                          f"Machine Profile provider '{provider_key}' model list")

            cmd_str = render_tmux_shell_string(cmd_obj)
            # cwd: Prompt Compiler's target_project (project_root) takes precedence.
            # Machine Profile's paths.project_root is the fallback.
            cwd = project_root
            mp_paths = machine_profile.get("paths", {})
            cwd = mp_paths.get("project_root", project_root)
            cmd_str = f"cd {cwd} && {cmd_str}"
            print(f"  {role['role_key']:15s} → '{session_name}'  (machine_profile) ...")

            ok = run_cmd_in_session(
                session_name,
                cmd_str,
                bridge_dir,
                project_root,
                start_cmd_suffix=None,
                target_project=project_root,
            )

        except ValueError as e:
            print(f"  {role['role_key']:15s} → '{session_name}'")
            print(f"  ERROR building Machine Profile command: {e}")
            errors.append(role["role_key"])
            continue

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
