#!/usr/bin/env python3
"""
Role setup script — warm up the model for a role session via Model Allocator.
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

from bridge_lib import load_role_from_db, get_effective_model_source

import config


def _model_allocator_path():
    return os.path.join(
        config.get_project_path("model-allocator"), "scripts", "model-allocator"
    )


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 role setup — warm model via Model Allocator"
    )
    parser.add_argument("--role", required=True)
    parser.add_argument("--flow-key", default=None)
    parser.add_argument("--step-key", default=None)
    parser.add_argument("--from-role", default=None)
    parser.add_argument("--to-role", default=None)
    parser.add_argument("--deliverable-dir", default=None)
    parser.add_argument("--deliverable-pattern", default=None)
    parser.add_argument("--deliverable-file", default=None)
    parser.add_argument("--handoff-id", default=None)
    parser.add_argument("--bridge-dir", default=None)
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

    print(f"Setting up role '{args.role}'...")
    print(f"  Session: {tmux_session}")

    # Resolve model via allocator
    model_source, model_alias = get_effective_model_source(
        args.role, step_key=args.step_key, flow_key=args.flow_key
    )

    if model_source == "model_allocator" and model_alias:
        print(f"  Warming allocator model '{model_alias}'...")
        try:
            result = subprocess.run(
                [_model_allocator_path(), "start", "--alias", model_alias],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0:
                print(f"  Model warmed via allocator")
            else:
                print(f"  WARNING: allocator start returned {result.returncode}: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"  WARNING: allocator start timed out")
        except Exception as e:
            print(f"  WARNING: allocator start failed: {e}")
    elif role_config.get("default_model_source") == "model_allocator" and role_config.get("default_model_alias"):
        # Already handled above — this branch is kept for clarity
        pass
    else:
        print(f"  No model to warm for role '{args.role}'")

    print(f"  Role '{args.role}' ready — session '{tmux_session}'")


if __name__ == "__main__":
    main()
