#!/usr/bin/env python3
"""
Role teardown script — gracefully stop a role session and clean up.
Reads role configuration dynamically via bridge_lib. Unloads Ollama model to free VRAM.
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

from bridge_lib import load_role_config


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 role teardown — stop a role session and clean up context"
    )
    parser.add_argument("--role", required=True, help="Role name matching [role:NAME] in config")
    parser.add_argument("--force", action="store_true", help="Skip confirmation for programmatic use")
    args = parser.parse_args()

    role_config = load_role_config(args.role)
    tmux_session = role_config["tmux_session"]
    model_type = role_config.get("model_type", "")
    ollama_model = role_config.get("ollama_model", "")

    print(f"Tearing down role '{args.role}'...")
    print(f"  Killing session '{tmux_session}'...")
    result = subprocess.run(
        ["tmux", "kill-session", "-t", tmux_session],
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if hasattr(result, "stderr") else ""
        print(f"  Session already gone or error: {stderr}")

    if model_type == "ollama" and ollama_model:
        print(f"  Unloading Ollama model '{ollama_model}' to free VRAM...")
        unload_result = subprocess.run(
            ["ollama", "stop", ollama_model],
            capture_output=True, text=True,
        )
        if unload_result.returncode == 0:
            print(f"  VRAM freed — model unloaded")
        else:
            unload_stdout = unload_result.stdout.strip() if unload_result.stdout else ""
            unload_stderr = unload_result.stderr.strip() if unload_result.stderr else ""
            if unload_stdout or unload_stderr:
                msg = unload_stdout or unload_stderr
                print(f"  Model stop returned non-zero: {msg}")
            else:
                print(f"  Model already unloaded")

    print(f"  Role '{args.role}' torn down")


if __name__ == "__main__":
    main()