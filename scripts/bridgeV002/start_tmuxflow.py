#!/usr/bin/env python3
"""start_tmuxflow.py — Inspect required sessions and preload models for a BridgeV002 flow.

BridgeV002 no-kill policy: This script does NOT create tmux sessions.
Session creation is handled exclusively by the start-tmux endpoint (H118).

Usage:
    python3 scripts/bridgeV002/start_tmuxflow.py <flow_key>

Example:
    python3 scripts/bridgeV002/start_tmuxflow.py strict_review
"""

import argparse
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def get_active_flow_roles(db_path, flow_key):
    """Fetch all unique FROM-ROLE tmux sessions and ollama models for a flow."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    roles = set()
    models = set()
    rows = conn.execute(
        "SELECT DISTINCT r.tmux_session, r.ollama_model, r.model_type "
        "FROM bridge_flow_steps s "
        "JOIN bridge_roles r ON s.from_role = r.role_key "
        "WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1",
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


def preload_ollama_models(models):
    """Pull all Ollama models for a flow (load from registry)."""
    loaded = []
    for model in sorted(models):
        print(f"  Pulling Ollama model '{model}'...")
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            loaded.append(model)
            print(f"    Model '{model}' ready")
        else:
            msg = result.stdout.strip() or result.stderr.strip()
            print(f"    WARNING: Failed to pull '{model}': {msg}")
    return loaded


def main():
    parser = argparse.ArgumentParser(
        description="Check required sessions and preload models for a BridgeV002 flow (no tmux create)."
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
    required_sessions, required_models = get_active_flow_roles(db_path, args.flow_key)
    if not required_sessions:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # 2. Report sessions (inspection only — no create)
    print(f"Required tmux sessions for flow '{args.flow_key}':")
    for s in sorted(required_sessions):
        print(f"  - {s} (ensure session is running via /api/bridge-v2/start-tmux)")

    # 3. Preload Ollama models
    if required_models:
        print(f"\nRequired Ollama models:")
        for m in sorted(required_models):
            print(f"  - {m}")

        loaded = preload_ollama_models(required_models)
        print(f"\nDone: {len(loaded)} model(s) preloaded. "
              f"Sessions must be started manually via start-tmux endpoint.")
    else:
        print("\nDone: No Ollama models required.")


if __name__ == "__main__":
    main()
