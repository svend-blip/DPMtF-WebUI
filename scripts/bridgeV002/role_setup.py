#!/usr/bin/env python3
"""
Role setup script — preload an Ollama model for a role session.
Reads role configuration from the database (bridge_roles table).
No hardcoded paths or model names.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent)
)
sys.path.insert(0, str(Path(__file__).parent))

from bridge_lib import load_role_from_db


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 role setup — start a role session with fresh context"
    )
    parser.add_argument("--role", required=True, help="Role key (matches bridge_roles.role_key)")
    parser.add_argument("--flow-key", default=None,
                        help="Flow key (e.g. 'heavy', 'simplified')")
    parser.add_argument("--step-key", default=None,
                        help="Step key within the flow")
    parser.add_argument("--from-role", default=None,
                        help="Source role name")
    parser.add_argument("--to-role", default=None,
                        help="Target role name (overrides --role if given)")
    parser.add_argument("--deliverable-dir", default=None,
                        help="Deliverable directory relative to bridge_dir")
    parser.add_argument("--deliverable-pattern", default=None,
                        help="Deliverable filename pattern with {ID} placeholder")
    parser.add_argument("--deliverable-file", default=None,
                        help="Resolved deliverable filename")
    parser.add_argument("--handoff-id", default=None,
                        help="Handoff ID")
    parser.add_argument("--bridge-dir", default=None,
                        help="Bridge directory path")
    args = parser.parse_args()

    if args.flow_key:
        print(f"  Flow: {args.flow_key}")
    if args.step_key:
        print(f"  Step: {args.step_key}")
    if args.from_role:
        print(f"  From: {args.from_role}")
    if args.handoff_id:
        print(f"  Handoff ID: {args.handoff_id}")

    role_config = load_role_from_db(args.role)
    tmux_session = role_config["tmux_session"]
    model_type = role_config.get("model_type", "")
    ollama_model = role_config.get("ollama_model", "")

    print(f"Setting up role '{args.role}'...")
    print(f"  Session: {tmux_session}")
    if model_type:
        print(f"  Model type: {model_type}")
    if ollama_model:
        print(f"  Ollama model: {ollama_model}")

    if model_type == "ollama" and ollama_model:
        print(f"  Reloading '{ollama_model}' fresh via pull...")
        result = subprocess.run(
            ["ollama", "pull", ollama_model],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  WARNING: Model reload returned non-zero")

    print(f"  Role '{args.role}' started — session '{tmux_session}' ready")


if __name__ == "__main__":
    main()