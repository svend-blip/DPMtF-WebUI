#!/usr/bin/env python3
"""
Role setup script — restart a session with fresh context.
Reads role configuration dynamically via bridge_lib. No hardcoded paths or model names.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent)
)
sys.path.insert(0, str(Path(__file__).parent))

from bridge_lib import load_role_config


def wait_session_ready(session_name, timeout=5):
    """Wait until tmux session is actually running."""
    for _ in range(timeout * 10):
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
        time.sleep(0.1)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 role setup — start a role session with fresh context"
    )
    parser.add_argument("--role", required=True, help="Role name matching [role:NAME] in config")
    args = parser.parse_args()

    role_config = load_role_config(args.role)
    tmux_session = role_config["tmux_session"]
    start_cmd = role_config.get("start_cmd", "")
    model_type = role_config.get("model_type", "")
    ollama_model = role_config.get("ollama_model", "")

    print(f"Setting up role '{args.role}'...")
    print(f"  Session: {tmux_session}")
    if model_type:
        print(f"  Model type: {model_type}")
    if ollama_model:
        print(f"  Ollama model: {ollama_model}")

    subprocess.run(
        ["tmux", "kill-session", "-t", tmux_session],
        capture_output=True,
    )

    if model_type == "ollama" and ollama_model:
        print(f"  Unloading '{ollama_model}' for clean state...")
        subprocess.run(
            ["ollama", "stop", ollama_model],
            capture_output=True,
        )

    if not start_cmd:
        print(f"  WARNING: No start_cmd defined for role '{args.role}'")
        return False

    print(f"  Starting session '{tmux_session}'...")
    subprocess.Popen(
        ["bash", "-c", (
            f"tmux kill-session -t '{tmux_session}' 2>/dev/null; "
            f"sleep 0.3; "
            f"tmux new-session -d -s {tmux_session} '{start_cmd}'"
        )],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ready = wait_session_ready(tmux_session)
    if not ready:
        print(f"  WARNING: Session '{tmux_session}' did not become ready in time")
        return False

    if model_type == "ollama" and ollama_model:
        print(f"  Reloading '{ollama_model}' fresh...")
        result = subprocess.run(
            ["ollama", "pull", ollama_model],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  WARNING: Model reload returned non-zero")

    print(f"  Role '{args.role}' started — session '{tmux_session}' ready")


if __name__ == "__main__":
    main()