#!/usr/bin/env python3
"""
BridgeV002 dispatcher — universal script for ALL role-to-role transitions.
Reads config dynamically from bridge_lib. No hardcoded roles, sessions, or paths.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent)
)
sys.path.insert(0, str(Path(__file__).parent))

from bridge_lib import (
    load_bridge_config,
    load_role_config,
    load_flow_config,
    get_next_id,
    ensure_subdir,
    resolve_placeholders,
)


def _bridge_dir():
    """Return the configured bridge directory."""
    return os.environ.get(
        "DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge")
    )


def kill_session(session_name):
    """Kill a tmux session. Non-destructive — silently succeeds if not exists."""
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True, text=True,
    )
    return True


def start_session(session_name, start_cmd):
    """Start a new detached tmux session with the given command."""
    result = subprocess.Popen(
        ["bash", "-c", (
            f"tmux kill-session -t '{session_name}' 2>/dev/null; "
            f"sleep 0.3; "
            f"tmux new-session -d -s {session_name} '{start_cmd}'"
        )],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result


def wait_session_ready(session_name, timeout=5):
    """Poll until tmux session is actually running. Returns True if ready."""
    for _ in range(timeout * 10):
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
        time.sleep(0.1)
    return False


def get_pane_command(session_name):
    """Detect which tool runs in the session's active pane.

    Returns lowercase string: 'opencode', 'claude', or 'unknown'.
    Used to adapt injection method per tool type.
    """
    result = subprocess.run(
        ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_current_command}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return "unknown"
    cmd = result.stdout.strip().lower()
    if "opencode" in cmd:
        return "opencode"
    elif "node" in cmd or "claude" in cmd:
        return "claude"
    return "unknown"


def inject_via_send_keys(session_name, text):
    """Send text + Enter via tmux send-keys. Used for Claude Code sessions."""
    # Write text to temp file then use send-keys with load-buffer for multiline
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="bridge-inject-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp], check=True)
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"], check=True
        )
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def inject_via_paste_buffer(session_name, text):
    """Write to temp file, load-buffer, paste-buffer. Used for OpenCode sessions."""
    fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="bridge-prompt-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp_path], check=True)
        subprocess.run(["tmux", "paste-buffer", "-t", session_name], check=True)
        time.sleep(0.5)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def inject_prompt(session_name, text):
    """Detect tool type and route to correct injection method.

    For OpenCode sessions, prepends soft-clear preamble before actual prompt.
    For Claude Code sessions, uses send-keys directly.
    """
    tool = get_pane_command(session_name)
    if tool == "opencode":
        soft_clear = (
            "Start a new logical task now. "
            "Ignore earlier conversation context unless this prompt explicitly references it. "
            "Do not continue previous plans, assumptions, file edits, or task state. "
            "Treat this message as the authoritative task."
        )
        combined = f"{soft_clear}\n\n{text}"
        inject_via_paste_buffer(session_name, combined)
    else:
        inject_via_send_keys(session_name, text)


def unload_ollama_model(model_name):
    """Stop an Ollama model to free VRAM and clear context.

    Returns True on success or if model was already unloaded, False otherwise.
    """
    if not model_name:
        return False

    result = subprocess.run(
        ["ollama", "stop", model_name],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True
    else:
        return True


def reload_ollama_model(model_name):
    """Reload an Ollama model with fresh context via direct load.

    Returns True on success, False on error.
    """
    if not model_name:
        return False

    result = subprocess.run(
        ["ollama", "pull", model_name],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True
    else:
        return False


def execute_script(script_path):
    """Execute a pre/post dispatch script if configured in flow step INI."""
    if not script_path:
        return True
    if not os.path.exists(script_path):
        return True
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Script failed: {result.stderr[:200]}")
        return False
    return True


def update_symlink(bridge_dir, subdir, target):
    """Update current.md symlink for timeline navigation."""
    link_path = os.path.join(bridge_dir, subdir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(target, link_path)


def log(direction, handoff_id, status, message, source="manual"):
    """Append to trace.log with UTC timestamp."""
    bridge_dir = _bridge_dir()
    trace_log = os.path.join(bridge_dir, "trace.log")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"{ts} | {direction} | {handoff_id} | {status} | {source} | {message}\n"
    os.makedirs(bridge_dir, exist_ok=True)
    with open(trace_log, "a", encoding="utf-8") as f:
        f.write(entry)


def run_flow_step(step_config, bridge_dir, handoff_id):
    """Execute a single flow step (defined in INI).

    Golden rule sequential dispatch sequence:
      1. Kill target tmux session
      2. Unload Ollama model if applicable
      3. Wait 1 second
      4. Start fresh target session with start_cmd from INI
      5. Wait for session to be ready
      6. Reload Ollama model if applicable
      7. Wait for model to be ready (3 seconds)
      8. Inject prompt (tool-aware: paste-buffer for OpenCode, send-keys for Claude)
    """
    from_role_name = step_config.get("from_role", "")
    to_role_name = step_config.get("to_role", "")

    to_role = load_role_config(to_role_name)

    print(f"\nDispatch: {from_role_name} -> {to_role_name}")

    tmux_session = to_role["tmux_session"]
    start_cmd = to_role.get("start_cmd", "")
    model_type = to_role.get("model_type", "")
    ollama_model = to_role.get("ollama_model", "")

    kill_session(tmux_session)

    if model_type == "ollama" and ollama_model:
        unload_ollama_model(ollama_model)

    time.sleep(1)

    if start_cmd:
        start_session(tmux_session, start_cmd)

    if not wait_session_ready(tmux_session):
        error_msg = step_config.get("error_msg", f"Target session did not start")
        print(f"  ERROR: {error_msg}")
        log(
            f"{from_role_name}->{to_role_name}",
            handoff_id,
            "failed",
            error_msg,
        )
        return False

    if model_type == "ollama" and ollama_model:
        reload_ollama_model(ollama_model)
        time.sleep(3)

    pre_script = step_config.get("pre_dispatch_script", "")
    if pre_script:
        resolved = resolve_placeholders(pre_script, bridge_dir=bridge_dir)
        if not execute_script(resolved):
            print(f"  Pre-dispatch script failed — aborting")
            return False

    deliverable_dir = step_config.get("deliverable_dir", "")
    deliverable_pattern = step_config.get("deliverable_pattern", "")
    deliverable_file = deliverable_pattern.replace("{ID}", handoff_id)

    full_deliverable_path = os.path.join(bridge_dir, deliverable_dir, deliverable_file)
    ensure_subdir(bridge_dir, deliverable_dir)

    inject_prompt(tmux_session, f"Read and execute {full_deliverable_path}")
    time.sleep(0.5)

    post_script = step_config.get("post_dispatch_script", "")
    if post_script:
        resolved = resolve_placeholders(post_script, bridge_dir=bridge_dir)
        execute_script(resolved)

    update_symlink(bridge_dir, deliverable_dir, deliverable_file)

    log(
        f"{from_role_name}->{to_role_name}",
        handoff_id,
        "dispatched",
        f"Delivered {deliverable_file} to {tmux_session}",
    )

    return True


def manual_dispatch(from_role_name, to_role_name, handoff_id, deliverable_path, bridge_dir):
    """Perform a direct role-to-role dispatch using INI role configs.

    Same golden rule sequence as run_flow_step.
    """
    from_role = load_role_config(from_role_name)
    to_role = load_role_config(to_role_name)

    tmux_session = to_role["tmux_session"]
    start_cmd = to_role.get("start_cmd", "")
    model_type = to_role.get("model_type", "")
    ollama_model = to_role.get("ollama_model", "")

    print(f"\nManual Dispatch: {from_role_name} -> {to_role_name}")

    kill_session(tmux_session)

    if model_type == "ollama" and ollama_model:
        unload_ollama_model(ollama_model)

    time.sleep(1)

    if start_cmd:
        start_session(tmux_session, start_cmd)

    if not wait_session_ready(tmux_session):
        error_msg = to_role.get("deliver_error_msg", f"Failed to deliver to {to_role_name}")
        print(f"  ERROR: {error_msg}")
        log(
            f"{from_role_name}->{to_role_name}",
            handoff_id,
            "failed",
            error_msg,
        )
        sys.exit(1)

    if model_type == "ollama" and ollama_model:
        reload_ollama_model(ollama_model)
        time.sleep(3)

    time.sleep(0.5)

    inject_prompt(tmux_session, f"Read and execute {deliverable_path}")

    log(
        f"{from_role_name}->{to_role_name}",
        handoff_id,
        "dispatched",
        f"Delivered to {tmux_session} via manual dispatch",
    )

    print(f"  Delivered to {to_role_name} — session '{tmux_session}'")


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 dispatcher — universal role transition"
    )
    parser.add_argument("--from-role", required=True, help="Source role name (matches INI [role:NAME])")
    parser.add_argument("--to-role", required=True, help="Target role name (matches INI [role:NAME])")
    parser.add_argument("--id", default=None, help="Handoff ID (auto-generated if omitted)")
    parser.add_argument("--flow", default=None, help="Flow name for step lookup (e.g. heavy, simplified)")
    parser.add_argument("--step", default=None, help="Specific step name in flow")
    parser.add_argument("--deliverable", default=None, help="Existing deliverable file path to dispatch")

    args = parser.parse_args()

    bridge_config = load_bridge_config()
    bridge_dir = _bridge_dir()

    handoff_id = args.id or f"{get_next_id(bridge_dir):03d}"

    if args.flow:
        flow_config = load_flow_config(args.flow)
        step_name = None
        step_key = None

        if args.step:
            step_key = f"step:{args.step}"
        else:
            if "flow" in flow_config:
                steps_str = flow_config["flow"].get("steps", "")
                steps_list = [s.strip() for s in steps_str.split(",")]
                if steps_list:
                    step_name = steps_list[0]
                    step_key = f"step:{step_name}"

        if step_key and step_key in flow_config:
            step_config = dict(flow_config[step_key])
            step_config["id"] = handoff_id
            run_flow_step(step_config, bridge_dir, handoff_id)
        else:
            print(f"Error: Step not found in flow '{args.flow}'")
            sys.exit(1)

    elif args.deliverable:
        manual_dispatch(args.from_role, args.to_role, handoff_id, args.deliverable, bridge_dir)
    else:
        print("Error: Provide either --flow or --deliverable")
        sys.exit(1)


if __name__ == "__main__":
    main()
