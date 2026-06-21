#!/usr/bin/env python3
"""
BridgeV002 dispatcher — universal script for ALL role-to-role transitions.
Reads config dynamically from bridge_lib. No hardcoded roles, sessions, or paths.
"""
import argparse
import os
import sqlite3
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
    load_role_from_db,
    load_flow_from_db,
    resolve_convention_from_db,
    resolve_content_template_from_db,
    validate_deliverable_against_schema,
    get_next_id,
    ensure_subdir,
    resolve_placeholders,
)

# ── Constants ──────────────────────────────────────────────
_STARTUP_FILE = "docs/StartUpNextSession.md"


def _bridge_dir():
    """Return the configured bridge directory."""
    return os.environ.get(
        "DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge")
    )


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


def build_step_payload(step, flow_key, handoff_id, bridge_dir):
    """Build a structured payload dict from a step row, convention rule, and context.

    The payload is the single source of truth passed to all dispatch scripts via CLI.

    Args:
        step: dict from bridge_flow_steps row
        flow_key: the flow key (e.g. 'heavy', 'simplified')
        handoff_id: string handoff ID (e.g. '106')
        bridge_dir: path to the bridge directory

    Returns:
        dict with keys: flow_key, step_key, from_role, to_role,
                       deliverable_dir, deliverable_pattern,
                       deliverable_file, error_msg, prompt_template,
                       handoff_id, bridge_dir
    """
    payload = {
        "flow_key": flow_key,
        "step_key": step.get("step_key", ""),
        "from_role": step.get("from_role", ""),
        "to_role": step.get("to_role", ""),
        "handoff_id": handoff_id,
        "bridge_dir": bridge_dir,
    }

    # deliverable_dir: use step value, fall back to convention template
    rule_key = step.get("rule_key")
    if step.get("deliverable_dir"):
        payload["deliverable_dir"] = step["deliverable_dir"]
    elif rule_key:
        try:
            convention = resolve_convention_from_db(rule_key)
            payload["deliverable_dir"] = convention.get("dir_template", "")
        except (ValueError, sqlite3.OperationalError):
            payload["deliverable_dir"] = ""
    else:
        payload["deliverable_dir"] = ""

    # deliverable_pattern: use step value, fall back to convention template
    if step.get("deliverable_pattern"):
        payload["deliverable_pattern"] = step["deliverable_pattern"]
    elif rule_key:
        try:
            convention = resolve_convention_from_db(rule_key)
            payload["deliverable_pattern"] = convention.get("pattern_template", "")
        except (ValueError, sqlite3.OperationalError):
            payload["deliverable_pattern"] = ""
    else:
        payload["deliverable_pattern"] = ""

    # deliverable_file: pattern with {ID} replaced by handoff_id
    pattern = payload.get("deliverable_pattern", "")
    payload["deliverable_file"] = pattern.replace("{ID}", handoff_id)

    # error_msg: use step value, fall back to convention template
    if step.get("error_msg"):
        payload["error_msg"] = step["error_msg"]
    elif rule_key:
        try:
            convention = resolve_convention_from_db(rule_key)
            tmpl = convention.get("error_template", "")
            payload["error_msg"] = tmpl.format(
                step_type=step.get("step_key", ""),
                to_role=payload["to_role"],
            )
        except (ValueError, sqlite3.OperationalError):
            payload["error_msg"] = f"Failed to deliver to {payload['to_role']}."
    else:
        payload["error_msg"] = f"Failed to deliver to {payload['to_role']}."

    # prompt_template: convention-provided template for enriched injection (Phase 2)
    if rule_key:
        try:
            convention = resolve_convention_from_db(rule_key)
            payload["prompt_template"] = convention.get("prompt_template", "")
        except (ValueError, sqlite3.OperationalError):
            payload["prompt_template"] = ""
    else:
        payload["prompt_template"] = ""

    return payload


def step_to_cli_args(payload):
    """Convert a payload dict to a list of CLI arguments for subprocess invocation.

    Returns list like ['--flow-key', 'heavy', '--step-key', 'architect_to_implementer', ...]
    """
    args = []
    key_map = {
        "flow_key": "--flow-key",
        "step_key": "--step-key",
        "from_role": "--from-role",
        "to_role": "--to-role",
        "deliverable_dir": "--deliverable-dir",
        "deliverable_pattern": "--deliverable-pattern",
        "deliverable_file": "--deliverable-file",
        "handoff_id": "--handoff-id",
        "bridge_dir": "--bridge-dir",
        "prompt_template": "--prompt-template",
    }
    for pk, flag in key_map.items():
        val = payload.get(pk)
        if val is not None:
            args.append(flag)
            args.append(str(val))
    return args


def execute_script_with_params(script_path, payload):
    """Execute a pre/post dispatch script with flow-context parameters.

    Args:
        script_path: Path to the Python script to execute.
        payload: dict with flow context (flow_key, step_key, from_role, etc.)

    Returns:
        True on success, False on failure.
    """
    if not script_path:
        return True
    if not os.path.exists(script_path):
        return True

    cli_args = step_to_cli_args(payload)
    cmd = ["python3", script_path] + cli_args

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Script {script_path} failed (rc={result.returncode})")
        stderr_preview = result.stderr[:300] if result.stderr else "(no stderr)"
        print(f"  Stderr: {stderr_preview}")
        return False
    stdout_truncated = result.stdout[:500] if result.stdout else ""
    if stdout_truncated:
        print(f"  Script output: {stdout_truncated.rstrip()}")
    return True


def session_alive(session_name):
    """Check if tmux session exists and is running. Instant yes/no, no wait."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    return result.returncode == 0


def run_flow_step_db(flow_key, step_key, handoff_id, bridge_dir=None):
    """Execute a single flow step using database-backed configuration.

    Replaces INI-based run_flow_step(). All role config, step data, and
    convention templates are loaded from the database at runtime.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load flow + step from DB
      2. Build payload from step + convention
      3. Load to_role from DB
      4. Check session_alive(target) -- instant yes/no, no wait
      5. Verify deliverable file exists -- fail fast if missing
      6. Ensure deliverable subdirectory exists
      7. Inject prompt (tool-aware: paste-buffer for OpenCode, send-keys for Claude)
      8. Post-dispatch: offload predecessor's Ollama model to free VRAM
      9. Update symlink + log dispatch event
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load flow + step from DB
    try:
        flow_data = load_flow_from_db(flow_key, db_path=dpmtf_config.get_db_path())
    except ValueError as e:
        print(f"Error loading flow '{flow_key}' from database: {e}")
        return False

    steps = flow_data["steps"]
    target_step = None
    if step_key:
        for s in steps:
            if s.get("step_key") == step_key:
                target_step = s
                break
    else:
        target_step = steps[0] if steps else None

    if not target_step:
        step_err = (f"Step '{step_key}' not found in flow '{flow_key}'"
                     if step_key else f"No active steps in flow '{flow_key}'")
        print(f"Error: {step_err}")
        return False

    # Step 2: Build payload from step + convention
    payload = build_step_payload(target_step, flow_key, handoff_id, bridge_dir)

    # Step 3: Load to_role from DB
    try:
        to_role = load_role_from_db(payload["to_role"],
                                    db_path=dpmtf_config.get_db_path())
    except ValueError as e:
        print(f"Error loading role '{payload['to_role']}' from database: {e}")
        return False

    print(f"\nDispatch: {payload['from_role']} -> {payload['to_role']}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    tmux_session = to_role["tmux_session"]
    from_ollama_model = ""
    model_type = to_role.get("model_type", "")
    ollama_model = to_role.get("ollama_model", "")

    # Step 4: Check session is alive (persistent session, not started)
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 5: Verify deliverable file exists (fail fast)
    full_deliverable_path = os.path.join(bridge_dir,
                                         payload["deliverable_dir"],
                                         payload["deliverable_file"])
    if not os.path.exists(full_deliverable_path):
        print(f"  ERROR: Deliverable missing: {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "failed",
            f"Deliverable missing: {full_deliverable_path}",
        )
        return False

    # Step 6
    ensure_subdir(bridge_dir, payload["deliverable_dir"])

    pre_script = target_step.get("pre_dispatch_script")
    if pre_script:
        resolved_path = resolve_placeholders(pre_script, bridge_dir=bridge_dir)
        print(f"  Running pre-dispatch script: {resolved_path}")
        if not execute_script_with_params(resolved_path, payload):
            print(f"  Pre-dispatch script failed -- aborting")
            return False

    # Validate deliverable if step requires validation and rule_key is set
    step_validation_required = target_step.get("validation_required", 0)
    if step_validation_required and rule_key:
        vresult = validate_deliverable_against_schema(full_deliverable_path, rule_key,
                                                      db_path=dpmtf_config.get_db_path())
        if not vresult["valid"]:
            print(f"  ERROR: Deliverable validation failed, missing sections: {vresult['missing']}")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "failed",
                f"Validation failed: missing {', '.join(vresult['missing'])}",
            )
            return False

    # Compose final injection text: use convention prompt_template or content_template from DB
    prompt_text = payload.get("prompt_template", "")
    if not prompt_text:
        ctemplate = resolve_content_template_from_db(rule_key, db_path=dpmtf_config.get_db_path())
        if ctemplate:
            prompt_text = ctemplate.replace("{handoff_id}", payload["handoff_id"])
            prompt_text = prompt_text.replace("{source_role}", payload["from_role"])
            prompt_text = prompt_text.replace("{next_role}", payload["to_role"])
            prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        else:
            prompt_text = f"Read and execute {full_deliverable_path}"
    else:
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{handoff_id}", payload["handoff_id"])

    inject_prompt(tmux_session, prompt_text)
    time.sleep(0.5)

    # Post-dispatch: offload predecessor's model to free VRAM
    from_role = load_role_from_db(payload["from_role"],
                                  db_path=dpmtf_config.get_db_path())
    if from_role.get("model_type") == "ollama" and from_role.get("ollama_model"):
        unload_ollama_model(from_role["ollama_model"])

    post_script = target_step.get("post_dispatch_script")
    if post_script:
        resolved_path = resolve_placeholders(post_script, bridge_dir=bridge_dir)
        print(f"  Running post-dispatch script: {resolved_path}")
        execute_script_with_params(resolved_path, payload)

    update_symlink(bridge_dir, deliverable_dir, payload["deliverable_file"])

    log(
        f"{payload['from_role']}->{payload['to_role']}",
        handoff_id,
        "dispatched",
        f"Delivered {payload['deliverable_file']} to {tmux_session} (DB-driven)",
    )

    return True


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

    if model_type == "ollama" and ollama_model:
        unload_ollama_model(ollama_model)

    if not session_alive(tmux_session):
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
    model_type = to_role.get("model_type", "")
    ollama_model = to_role.get("ollama_model", "")

    print(f"\nManual Dispatch: {from_role_name} -> {to_role_name}")

    if model_type == "ollama" and ollama_model:
        unload_ollama_model(ollama_model)

    if not session_alive(tmux_session):
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
    parser.add_argument("--from-role", default=None, help="Source role name (matches INI [role:NAME])")
    parser.add_argument("--to-role", default=None, help="Target role name (matches INI [role:NAME])")
    parser.add_argument("--id", default=None, help="Handoff ID (auto-generated if omitted)")
    parser.add_argument("--flow", default=None, help="Flow name for step lookup (e.g. heavy, simplified)")
    parser.add_argument("--step", default=None, help="Specific step name in flow")
    parser.add_argument("--deliverable", default=None, help="Existing deliverable file path to dispatch")
    parser.add_argument("--db-flow", default=None,
                        help="DB flow_key for database-driven dispatch")
    parser.add_argument("--db-step", default=None,
                        help="DB step_key within the flow (optional)")

    args = parser.parse_args()

    bridge_config = load_bridge_config()
    bridge_dir = _bridge_dir()

    handoff_id = args.id or f"{get_next_id(bridge_dir):03d}"

    if args.db_flow:
        run_flow_step_db(args.db_flow, args.db_step, handoff_id, bridge_dir)
        sys.exit(0)

    if not (args.from_role and args.to_role):
        print("Error: --from-role and --to-role are required for INI-based dispatch")
        sys.exit(1)

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
