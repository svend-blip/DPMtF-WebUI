#!/usr/bin/env python3
"""
Role teardown script — unload model via Model Allocator.
Reads role configuration from the database (bridge_roles table).
No tmux kill-session calls — sessions are persistent in no-kill mode.
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
        description="BridgeV002 role teardown — unload model via Model Allocator"
    )
    parser.add_argument("--role", required=True)
    parser.add_argument("--force", action="store_true")
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

    print(f"Tearing down role '{args.role}'...")

    # Resolve model via allocator
    model_source, model_alias = get_effective_model_source(
        args.role, step_key=args.step_key, flow_key=args.flow_key
    )

    if model_source == "model_allocator" and model_alias:
        print(f"  Stopping allocator model '{model_alias}'...")
        try:
            result = subprocess.run(
                [_model_allocator_path(), "stop", "--alias", model_alias],
                capture_output=True, text=True, timeout=45,
            )
            if result.returncode == 0:
                print(f"  Model stopped via allocator")
            else:
                print(f"  Model may already be unloaded: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"  WARNING: allocator stop timed out")
        except Exception as e:
            print(f"  WARNING: allocator stop failed: {e}")
    elif role_config.get("model_type") == "ollama" and role_config.get("ollama_model"):
        # Legacy fallback (should not exist after Phase 2)
        print(f"  WARNING: role '{args.role}' not on allocator — using legacy ollama stop")
        subprocess.run(["ollama", "stop", role_config["ollama_model"]],
                       capture_output=True, text=True)
    else:
        print(f"  No model to unload for role '{args.role}'")

    print(f"  Role '{args.role}' torn down")


if __name__ == "__main__":
    main()
