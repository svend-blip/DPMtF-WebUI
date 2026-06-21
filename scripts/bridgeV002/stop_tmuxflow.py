#!/usr/bin/env python3
"""stop_tmuxflow.py — Inspect and unload Ollama models for a BridgeV002 flow.

BridgeV002 no-kill policy: This script does NOT kill tmux sessions.
Session management is handled exclusively by the start-tmux endpoint (H118).

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

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def get_active_flow_roles(db_path, flow_key):
    """Fetch all unique FROM-ROLE tmux sessions for active steps in a flow.

    Returns two sets: (session_names, ollama_models).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    roles = set()
    models = set()
    rows = conn.execute(
        """
        SELECT DISTINCT r.tmux_session, r.ollama_model, r.model_type
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
        model = row["ollama_model"]
        if model and row["model_type"] == "ollama":
            models.add(model)

    conn.close()
    return roles, models


def unload_ollama_models(models):
    """Unload all Ollama models for a flow.

    This is the ONLY lifecycle operation permitted in BridgeV002.
    Session management belongs to start-tmux endpoint (H118).
    """
    unloaded = []
    for model in sorted(models):
        print(f"  Unloading Ollama model '{model}'...")
        result = subprocess.run(
            ["ollama", "stop", model],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            unloaded.append(model)
            print(f"    Model '{model}' unloaded")
        else:
            msg = result.stdout.strip() or result.stderr.strip()
            print(f"    WARNING: Failed to unload '{model}': {msg}")
    return unloaded


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and manage Ollama models for a BridgeV002 flow (no tmux kill)."
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
    sessions_to_stop, ollama_models = get_active_flow_roles(db_path, args.flow_key)
    if not sessions_to_stop:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. Report sessions (inspection only — no kill)
    print(f"Sessions in flow '{args.flow_key}':")
    for s in sorted(sessions_to_stop):
        print(f"  - {s} (managed by /api/bridge-v2/start-tmux)")

    # 3. Unload Ollama models only
    if ollama_models:
        unloaded = unload_ollama_models(ollama_models)
        print(f"\nDone: {len(unloaded)} model(s) unloaded (no tmux kill).")
    else:
        print("\nNo Ollama models to unload.")


if __name__ == "__main__":
    main()
