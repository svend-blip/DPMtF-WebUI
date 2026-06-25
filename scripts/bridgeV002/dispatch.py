#!/usr/bin/env python3
"""
BridgeV002 dispatcher — universal script for ALL role-to-role transitions.
Reads config dynamically from bridge_lib. No hardcoded roles, sessions, or paths.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent.parent)
)
sys.path.insert(0, str(Path(__file__).parent))

from bridge_lib import (
    load_role_from_db,
    load_flow_from_db,
    resolve_convention_from_db,
    resolve_content_template_from_db,
    validate_deliverable_against_schema,
    get_next_id_for_flow,
    ensure_subdir,
    resolve_placeholders,
    list_scripts_from_db,
)

# ── Constants ──────────────────────────────────────────────
_STARTUP_FILE = "docs/StartUpNextSession.md"


def _bridge_dir():
    """Return the configured bridge directory."""
    return os.environ.get(
        "DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge")
    )


def _db_path():
    """Return the absolute database path, resolving relative paths against PROJECT_ROOT."""
    import config as _cfg
    p = _cfg.get_db_path()
    if not os.path.isabs(p):
        p = os.path.join(PROJECT_ROOT, p)
    return p


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


def inject_via_send_keys(session_name, text, enter_command="default"):
    """Send text + submit key via tmux send-keys.

    Supports per-role enter_command:
      - 'default': Enter in same command (Claude Code, standard)
      - 'c-m': Two-step — text first, then separate C-m (Freebuff)
      - 'c-j': Two-step with C-j (Ctrl+J / line feed)
      - 'c-d': Two-step with C-d (Ctrl+D / EOF)
    """
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="bridge-inject-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp], check=True)

        # Submit based on enter_command
        if enter_command == "c-m":
            # Two-step: paste text first, then separate C-m (Freebuff)
            subprocess.run(
                ["tmux", "paste-buffer", "-t", session_name], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-m"], check=True
            )
        elif enter_command == "c-j":
            subprocess.run(
                ["tmux", "paste-buffer", "-t", session_name], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-j"], check=True
            )
        elif enter_command == "c-d":
            subprocess.run(
                ["tmux", "paste-buffer", "-t", session_name], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-d"], check=True
            )
        else:  # "default" — paste text then Enter (Claude Code, standard)
            subprocess.run(
                ["tmux", "paste-buffer", "-t", session_name], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Enter"], check=True
            )
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def inject_via_paste_buffer(session_name, text, enter_command="default"):
    """Write to temp file, load-buffer, paste-buffer, send submit key. Used for OpenCode sessions.

    Supports per-role enter_command (same values as inject_via_send_keys).
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="bridge-prompt-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp_path], check=True)
        subprocess.run(["tmux", "paste-buffer", "-t", session_name], check=True)
        time.sleep(0.3)

        # Submit based on enter_command
        if enter_command == "c-m":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-m"], check=True
            )
        elif enter_command == "c-j":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-j"], check=True
            )
        elif enter_command == "c-d":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-d"], check=True
            )
        else:  # "default" — original behavior
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Enter"], check=True
            )
        time.sleep(0.3)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def inject_prompt(session_name, text, enter_command="default"):
    """Detect tool type and route to correct injection method.

    For OpenCode sessions, prepends soft-clear preamble before actual prompt.
    For Claude Code sessions, uses send-keys directly.

    enter_command controls how the submit key is sent:
      - 'default': Enter (standard for Claude Code / OpenCode)
      - 'c-m': Two-step C-m (Freebuff)
      - 'c-j': Two-step C-j
      - 'c-d': Two-step C-d
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
        inject_via_paste_buffer(session_name, combined, enter_command)
    else:
        inject_via_send_keys(session_name, text, enter_command)


def unload_ollama_model(model_name):
    """Stop an Ollama model to free VRAM and clear context.

    Returns True on success or if model was already unloaded.
    Returns False on actual failure (model name invalid, ollama not running, etc.).
    """
    if not model_name:
        return True  # nothing to unload — not an error

    result = subprocess.run(
        ["ollama", "stop", model_name],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  Stopped Ollama model '{model_name}'")
        return True

    # Check for 'already unloaded' — not a failure
    stderr_lower = (result.stderr or "").lower()
    if "not loaded" in stderr_lower or "not found" in stderr_lower:
        print(f"  Model '{model_name}' not currently loaded — VRAM already free")
        return True

    # Actual failure
    print(f"  WARNING: Failed to stop '{model_name}': {result.stderr.strip()}")
    return False


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


def _update_cycle_state(handoff_id, flow_key, active_role, title=None,
                        design_notes=None, verification_checklist=None):
    """Update docs/bridgeV002/current-cycle.json after a successful dispatch.

    Called by every signal function to keep the Architect's cold-start state
    current. The JSON file is the single source of truth for cycle state —
    StartUpNextSession.md holds only durable reference information.
    """
    project_root = os.environ.get(
        "DPMTF_PROJECT_ROOT",
        str(Path(__file__).resolve().parent.parent)
    )
    cycle_file = os.path.join(project_root, "docs", "bridgeV002", "current-cycle.json")

    # Read existing state (preserve fields not being updated)
    current = {}
    if os.path.exists(cycle_file):
        try:
            with open(cycle_file, "r", encoding="utf-8") as f:
                current = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Update fields
    current["last_handoff"] = handoff_id
    current["flow"] = flow_key
    current["active_role"] = active_role
    if title is not None:
        current["title"] = title
    if design_notes is not None:
        current["design_notes"] = design_notes
    if verification_checklist is not None:
        current["verification_checklist"] = verification_checklist
    current["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write atomically via temp file
    os.makedirs(os.path.dirname(cycle_file), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="cycle-",
                               dir=os.path.dirname(cycle_file))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        os.replace(tmp, cycle_file)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)


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


def resolve_script_key(script_key, bridge_dir=None):
    """Resolve a script key (from bridge_flow_steps) to an absolute file path.

    Looks up the script key in bridge_scripts table, resolves placeholders
    in the stored path, and returns the absolute path.

    Args:
        script_key: Script key string (e.g. 'post-dispatch-common')
        bridge_dir: Optional bridge directory for placeholder resolution

    Returns:
        Absolute path to the script file, or None if not found.
    """
    if not script_key:
        return None

    scripts = list_scripts_from_db(db_path=_db_path())
    script_path = None
    for s in scripts:
        if s.get("script_key") == script_key:
            script_path = s.get("path", "")
            break

    if not script_path:
        print(f"  WARNING: Script key '{script_key}' not found in bridge_scripts")
        return None

    # Resolve placeholders in the stored path
    resolved = resolve_placeholders(script_path, bridge_dir=bridge_dir)
    return resolved


def execute_script_with_params(script_path, payload):
    """Execute a pre/post dispatch script with flow-context parameters.

    Args:
        script_path: Absolute path to the Python script to execute.
        payload: dict with flow context (flow_key, step_key, from_role, etc.)

    Returns:
        True on success, False on failure.
    """
    if not script_path:
        return True
    if not os.path.exists(script_path):
        print(f"  WARNING: Script not found: {script_path}")
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
        flow_data = load_flow_from_db(flow_key, db_path=_db_path())
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

    # Extract rule_key for validation and content template resolution (Step 6-7)
    rule_key = target_step.get("rule_key")

    # Step 3: Load to_role from DB
    try:
        to_role = load_role_from_db(payload["to_role"],
                                    db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{payload['to_role']}' from database: {e}")
        return False

    print(f"\nDispatch: {payload['from_role']} -> {payload['to_role']}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    tmux_session = to_role["tmux_session"]
    role_type = to_role.get("role_type", "agent")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        full_deliverable_path = os.path.join(bridge_dir,
                                             payload["deliverable_dir"],
                                             payload["deliverable_file"])
        print(f"  INFO: Delivering to human recipient — {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "dispatched_to_human",
            f"Deliverable written to {full_deliverable_path} for human review",
        )
        return True

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
        resolved_path = resolve_script_key(pre_script, bridge_dir=bridge_dir)
        if resolved_path:
            print(f"  Running pre-dispatch script: {resolved_path}")
            if not execute_script_with_params(resolved_path, payload):
                print(f"  Pre-dispatch script failed -- aborting")
                return False

    # Validate deliverable if step requires validation and rule_key is set
    step_validation_required = target_step.get("validation_required", 0)
    if step_validation_required and rule_key:
        vresult = validate_deliverable_against_schema(full_deliverable_path, rule_key,
                                                      db_path=_db_path())
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
        ctemplate = resolve_content_template_from_db(rule_key, db_path=_db_path())
        if ctemplate:
            prompt_text = ctemplate.replace("{handoff_id}", payload["handoff_id"])
            prompt_text = prompt_text.replace("{source_role}", payload["from_role"])
            prompt_text = prompt_text.replace("{next_role}", payload["to_role"])
            prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
            prompt_text = prompt_text.replace("{flow_key}", payload["flow_key"])
        else:
            prompt_text = f"Read and execute {full_deliverable_path}"
    else:
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{handoff_id}", payload["handoff_id"])
        prompt_text = prompt_text.replace("{flow_key}", payload["flow_key"])

    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role.get("enter_command", "default"))
    time.sleep(0.5)

    # Post-dispatch: offload predecessor's model to free VRAM
    from_role = load_role_from_db(payload["from_role"],
                                  db_path=_db_path())
    if from_role.get("model_type") == "ollama" and from_role.get("ollama_model"):
        unload_ollama_model(from_role["ollama_model"])

    post_script = target_step.get("post_dispatch_script")
    if post_script:
        resolved_path = resolve_script_key(post_script, bridge_dir=bridge_dir)
        if resolved_path:
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


def signal_complete(flow_key, step_key, from_role_key, handoff_id, bridge_dir=None):
    """Signal that a role has completed its deliverable for a flow step.

    Replaces legacy bridge.py complete <ID>. DB-driven: loads the completed
    step, resolves callback convention, builds prompt from content_template,
    injects into next role's tmux session, and optionally chains to next step.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load flow + steps from DB
      2. Find current step (by step_key or by matching from_role)
      3. Build payload from step + convention
      4. Load to_role from DB -> get tmux_session
      5. Check session_alive(to_role) -- fail if not running
      6. Verify deliverable file exists (written by completing role)
      7. Resolve content_template placeholders ({handoff_id}, {source_role}, ...)
      8. Inject callback prompt into to_role's tmux session
      9. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
      10. Update symlink in deliverable_dir
      11. Log completion event to trace.log
      12. If auto_complete_enabled: chain to next step via run_flow_step_db()
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load flow + steps from DB
    try:
        flow_data = load_flow_from_db(flow_key, db_path=_db_path())
    except ValueError as e:
        print(f"Error loading flow '{flow_key}' from database: {e}")
        return False

    steps = flow_data["steps"]
    auto_complete_enabled = flow_data["flow"].get("auto_complete_enabled", 0)

    # Step 2: Find current step (by step_key or by matching from_role)
    current_step = None
    if step_key:
        for s in steps:
            if s.get("step_key") == step_key:
                current_step = s
                break
    elif from_role_key:
        for s in steps:
            if s.get("from_role") == from_role_key:
                current_step = s
                break

    if not current_step:
        lookup = step_key if step_key else from_role_key
        print(f"Error: Step not found for '{lookup}' in flow '{flow_key}'")
        return False

    # Step 3: Build payload from step + convention
    payload = build_step_payload(current_step, flow_key, handoff_id, bridge_dir)

    # Step 4: Load to_role from DB
    try:
        to_role = load_role_from_db(payload["to_role"],
                                    db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{payload['to_role']}' from database: {e}")
        return False

    rule_key = current_step.get("rule_key")

    print(f"\nSignal Complete: {payload['from_role']} -> {payload['to_role']}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    tmux_session = to_role["tmux_session"]
    role_type = to_role.get("role_type", "agent")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        full_deliverable_path = os.path.join(bridge_dir,
                                             payload["deliverable_dir"],
                                             payload["deliverable_file"])
        print(f"  INFO: Completion delivered to human recipient — {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_to_human",
            f"Completion deliverable at {full_deliverable_path} for human review",
        )
        return True

    # Step 5: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 6: Verify deliverable file exists (written by completing role)
    full_deliverable_path = os.path.join(bridge_dir,
                                         payload["deliverable_dir"],
                                         payload["deliverable_file"])
    if not os.path.exists(full_deliverable_path):
        print(f"  ERROR: Deliverable missing: {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_failed",
            f"Deliverable missing: {full_deliverable_path}",
        )
        return False

    # Ensure deliverable subdirectory exists (for symlink)
    ensure_subdir(bridge_dir, payload["deliverable_dir"])

    # Step 7: Build callback prompt from convention content_template
    step_validation_required = current_step.get("validation_required", 0)
    if step_validation_required and rule_key:
        vresult = validate_deliverable_against_schema(
            full_deliverable_path, rule_key,
            db_path=_db_path(),
        )
        if not vresult["valid"]:
            print(f"  ERROR: Deliverable validation failed, missing sections: {vresult['missing']}")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "signal_complete_failed",
                f"Validation failed: missing {', '.join(vresult['missing'])}",
            )
            return False

    # Compose prompt: use content_template with placeholder replacement
    ctemplate = resolve_content_template_from_db(
        rule_key, db_path=_db_path()
    ) if rule_key else ""

    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", payload["handoff_id"])
        prompt_text = prompt_text.replace("{source_role}", payload["from_role"])
        prompt_text = prompt_text.replace("{next_role}", payload["to_role"])
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", payload["flow_key"])
        prompt_text += f"\n\n## Current Deliverable\nRead your input from: {full_deliverable_path}"
    else:
        prompt_text = (
            f"Your previous role '{payload['from_role']}' has completed handoff "
            f"#{payload['handoff_id']}.\n"
            f"Read and proceed with: {full_deliverable_path}"
        )

    # Prepend governance file reference for target role
    gov_file = to_role.get("governance_file")
    project_root_sc = os.path.dirname(_db_path())
    if gov_file:
        gov_path = os.path.join(project_root_sc, "docs", "governance-templates-v2", gov_file)
        prompt_text = (
            f"Your role is defined in {gov_path}. Read it now before proceeding.\n\n"
            f"{prompt_text}"
        )

    # Step 8: Inject callback prompt into to_role's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role.get("enter_command", "default"))
    time.sleep(0.5)

    # Step 9: Post-dispatch - stop from_role's Ollama model (VRAM cleanup)
    try:
        from_role_data = load_role_from_db(payload["from_role"],
                                           db_path=_db_path())
        if from_role_data.get("model_type") == "ollama" and from_role_data.get("ollama_model"):
            unload_ollama_model(from_role_data["ollama_model"])
    except ValueError:
        pass  # from_role not in DB - not an ollama role, skip

    # Step 10: Update symlink
    deliverable_dir = payload["deliverable_dir"]
    if os.path.isabs(deliverable_dir):
        # For absolute paths, update symlink in the deepest subdirectory
        link_dir = deliverable_dir
    else:
        link_dir = os.path.join(bridge_dir, deliverable_dir)

    link_path = os.path.join(link_dir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(payload["deliverable_file"], link_path)

    # Step 11: Log completion event
    log(
        f"{payload['from_role']}->{payload['to_role']}",
        handoff_id,
        "signal_complete",
        f"Callback dispatched to {tmux_session} (DB-driven)",
    )

    print(f"  Callback injected into '{tmux_session}'")
    print(f"  Symlink updated in {link_dir}")
    print(f"  Logged signal_complete for handoff #{handoff_id}")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, payload["to_role"])

    # Step 12: Auto-chain to next step if enabled
    if auto_complete_enabled:
        current_sort = current_step.get("sort_order", 0)
        next_step = None
        for s in steps:
            if s.get("sort_order", 0) == current_sort + 1:
                next_step = s
                break
        if next_step:
            print(f"\n  Auto-chain enabled - dispatching next step: {next_step['step_key']}")
            # Generate new ID for next step
            next_id = f"{get_next_id_for_flow(flow_key, db_path=_db_path()):03d}"
            run_flow_step_db(flow_key, next_step["step_key"], next_id, bridge_dir)

    return True


def signal_escalation(flow_key, from_role_key, to_role_key, handoff_id, bridge_dir=None):
    """Signal that a review role has escalated a question to architect.

    Replaces legacy cmd_ask_architect(). DB-driven: resolves both roles,
    builds escalation prompt from convention content_template, injects into
    architect's tmux session, and cleans up VRAM.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load from_role + to_role from DB
      2. Check target session is alive
      3. Verify escalation question file exists (written by review)
      4. Resolve escalation convention content_template
      5. Build prompt with placeholder replacement
      6. Inject prompt into architect's tmux session
      7. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
      8. Update symlink in escalation directory
      9. Log escalation event to trace.log
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load both roles from DB
    try:
        from_role_data = load_role_from_db(from_role_key,
                                           db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{from_role_key}' from database: {e}")
        return False

    try:
        to_role_data = load_role_from_db(to_role_key,
                                         db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{to_role_key}' from database: {e}")
        return False

    tmux_session = to_role_data["tmux_session"]
    role_type = to_role_data.get("role_type", "agent")

    print(f"\nSignal Escalation: {from_role_key} -> {to_role_key}")
    print(f"  Flow: {flow_key}")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        esc_dir = os.path.join(bridge_dir, "escalations")
        question_file = f"{handoff_id}-{from_role_key}-question.md"
        full_question_path = os.path.join(esc_dir, question_file)
        print(f"  INFO: Escalation delivered to human recipient — {full_question_path}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "escalation_to_human",
            f"Escalation question at {full_question_path} for human review",
        )
        return True

    # Step 2: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "escalation_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 3: Verify escalation question file exists (written by review)
    # The question file lives in the bridge dir under an escalation subdirectory
    esc_dir = os.path.join(bridge_dir, "escalations")
    question_file = f"{handoff_id}-{from_role_key}-question.md"
    full_question_path = os.path.join(esc_dir, question_file)

    if not os.path.exists(full_question_path):
        print(f"  ERROR: Escalation question file missing: {full_question_path}")
        print(f"  Review must write its question before signaling escalation")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "escalation_failed",
            f"Question file missing: {full_question_path}",
        )
        return False

    # Ensure escalation subdirectory exists (for symlink)
    os.makedirs(esc_dir, exist_ok=True)

    # Step 4: Resolve escalation convention content_template
    ctemplate = resolve_content_template_from_db(
        "escalation", db_path=_db_path()
    ) or ""

    # Step 5: Build prompt with placeholder replacement
    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", handoff_id)
        prompt_text = prompt_text.replace("{source_role}", from_role_key)
        prompt_text = prompt_text.replace("{next_role}", to_role_key)
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", flow_key)
        # Inject the actual question file path so architect knows what to read
        prompt_text += f"\n\n## Escalation Question File\nRead the escalation question from: {full_question_path}"
    else:
        prompt_text = (
            f"The role '{from_role_key}' has escalated a question for handoff "
            f"#{handoff_id}.\n"
            f"Please review and respond. Read the question from: {full_question_path}"
        )

    # Prepend governance file reference for target role
    gov_file = to_role_data.get("governance_file")
    if gov_file:
        gov_path_e = os.path.join(os.path.dirname(_db_path()),
                                  "docs", "governance-templates-v2", gov_file)
        prompt_text = (
            f"Your role is defined in {gov_path_e}. Read it now before proceeding.\n\n"
            f"{prompt_text}"
        )

    # Step 6: Inject prompt into architect's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
    time.sleep(0.5)

    # Step 7: Post-dispatch — stop from_role's Ollama model (VRAM cleanup)
    try:
        if from_role_data.get("model_type") == "ollama" and from_role_data.get("ollama_model"):
            unload_ollama_model(from_role_data["ollama_model"])
    except Exception:
        pass  # Not an ollama role or model already stopped

    # Step 8: Update symlink in escalation directory
    link_path = os.path.join(esc_dir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(question_file, link_path)

    # Step 9: Log escalation event
    log(
        f"{from_role_key}->{to_role_key}",
        handoff_id,
        "escalation_asked",
        f"Escalation dispatched to {tmux_session} (DB-driven)",
    )

    print(f"  Escalation prompt injected into '{tmux_session}'")
    print(f"  Symlink updated in {esc_dir}")
    print(f"  Logged escalation_asked for handoff #{handoff_id}")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, to_role_key)

    return True


def signal_answer(flow_key, from_role_key, to_role_key, handoff_id, bridge_dir=None):
    """Signal that architect has answered an escalation question.

    Replaces legacy cmd_answer_review(). Sends response back to the review
    role that originated the escalation. No auto-chain — review continues work.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load from_role + to_role from DB
      2. Check target session is alive
      3. Build prompt from escalation convention content_template
      4. Inject prompt into review's tmux session
      5. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
      6. Update symlink in answer directory
      7. Log answer event to trace.log
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load both roles from DB
    try:
        from_role_data = load_role_from_db(from_role_key,
                                           db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{from_role_key}' from database: {e}")
        return False

    try:
        to_role_data = load_role_from_db(to_role_key,
                                         db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{to_role_key}' from database: {e}")
        return False

    tmux_session = to_role_data["tmux_session"]
    role_type = to_role_data.get("role_type", "agent")

    print(f"\nSignal Answer: {from_role_key} -> {to_role_key}")
    print(f"  Flow: {flow_key}")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        ans_dir = os.path.join(bridge_dir, "escalations")
        response_file = f"{handoff_id}-{from_role_key}-response.md"
        full_response_path = os.path.join(ans_dir, response_file)
        print(f"  INFO: Answer delivered to human recipient — {full_response_path}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "answer_to_human",
            f"Escalation response at {full_response_path} for human review",
        )
        return True

    # Step 2: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "answer_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 3: Build prompt from escalation convention content_template
    # (same convention as signal_escalation — architect answer uses same structure)
    ctemplate = resolve_content_template_from_db(
        "escalation", db_path=_db_path()
    ) or ""

    # Check for optional architect response file
    ans_dir = os.path.join(bridge_dir, "escalations")
    response_file = f"{handoff_id}-{from_role_key}-response.md"
    full_response_path = os.path.join(ans_dir, response_file)

    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", handoff_id)
        prompt_text = prompt_text.replace("{source_role}", from_role_key)
        prompt_text = prompt_text.replace("{next_role}", to_role_key)
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", flow_key)
    else:
        prompt_text = (
            f"The role '{from_role_key}' has provided an escalation response "
            f"for handoff #{handoff_id}.\n"
            f"Please review the architect's decision and proceed."
        )

    # If architect wrote a response file, include it in the prompt
    if os.path.exists(full_response_path):
        prompt_text += f"\n\n## Architect Response File\nRead the architect's response from: {full_response_path}"
    else:
        prompt_text += f"\n\n## Note\nNo separate response file found. The architect may have provided inline guidance."

    # Step 4: Inject prompt into review's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
    time.sleep(0.5)

    # Step 5: Post-dispatch — stop from_role's Ollama model (VRAM cleanup)
    try:
        if from_role_data.get("model_type") == "ollama" and from_role_data.get("ollama_model"):
            unload_ollama_model(from_role_data["ollama_model"])
    except Exception:
        pass  # Not an ollama role or model already stopped

    # Step 6: Update symlink in answer directory
    link_path = os.path.join(ans_dir, "current_answer.md")
    if os.path.exists(full_response_path):
        try:
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.unlink(link_path)
        except FileNotFoundError:
            pass
        os.symlink(response_file, link_path)

    # Step 7: Log answer event
    log(
        f"{from_role_key}->{to_role_key}",
        handoff_id,
        "escalation_answered",
        f"Answer dispatched to {tmux_session} (DB-driven)",
    )

    print(f"  Answer prompt injected into '{tmux_session}'")
    print(f"  Logged escalation_answered for handoff #{handoff_id}")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, to_role_key)

    return True


def signal_send(flow_key, from_role_key, to_role_key, handoff_id, bridge_dir=None):
    """Signal initial handoff dispatch from review to target role.

    Replaces legacy cmd_send(). DB-driven: resolves both roles,
    validates handoff file exists with required XML sections, performs
    model stop+reload for clean context, and injects dispatch prompt
    into the target role's tmux session.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load from_role + to_role from DB
      2. Check target session is alive
      3. Verify handoff file exists with required XML sections
      4. Stop target role's Ollama model (clear VRAM + context)
      5. Reload target role's Ollama model (fresh context)
      6. Resolve handoff convention content_template
      7. Build prompt with placeholder replacement
      8. Inject prompt into target role's tmux session
      9. Update symlink in handoff directory
      10. Log dispatch event to trace.log
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load both roles from DB
    try:
        from_role_data = load_role_from_db(from_role_key,
                                           db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{from_role_key}' from database: {e}")
        return False

    try:
        to_role_data = load_role_from_db(to_role_key,
                                         db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{to_role_key}' from database: {e}")
        return False

    tmux_session = to_role_data["tmux_session"]

    # Step 1.5: Load flow and find matching step from DB
    try:
        flow_data = load_flow_from_db(flow_key, db_path=_db_path())
    except ValueError as e:
        print(f"Error loading flow '{flow_key}' from database: {e}")
        return False

    steps = flow_data["steps"]
    target_step = None
    for s in steps:
        if s.get("from_role") == from_role_key and s.get("to_role") == to_role_key:
            target_step = s
            break

    if not target_step:
        print(f"Error: No step matching {from_role_key}->{to_role_key} in flow '{flow_key}'")
        return False

    # Build payload from step + convention (resolves deliverable_dir, pattern, rule_key)
    payload = build_step_payload(target_step, flow_key, handoff_id, bridge_dir)
    rule_key = target_step.get("rule_key")

    print(f"\nSignal Send: {from_role_key} -> {to_role_key}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    role_type = to_role_data.get("role_type", "agent")
    if role_type == "human":
        deliverable_dir = payload.get("deliverable_dir", "")
        handoff_path = os.path.join(bridge_dir, deliverable_dir, payload["deliverable_file"])
        print(f"  INFO: Handoff delivered to human recipient — {handoff_path}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_to_human",
            f"Handoff file at {handoff_path} for human review",
        )
        return True

    # Step 2: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 3: Verify handoff file exists with required XML sections
    deliverable_dir = payload.get("deliverable_dir", "")
    handoff_path = os.path.join(bridge_dir, deliverable_dir, payload["deliverable_file"])

    if not os.path.exists(handoff_path):
        print(f"  ERROR: Handoff file missing: {handoff_path}")
        print(f"  Prompt Compiler must write handoff file before signaling send")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_failed",
            f"Handoff file missing: {handoff_path}",
        )
        return False

    # Validate required XML sections in handoff content (matches legacy cmd_send)
    with open(handoff_path, "r", encoding="utf-8") as f:
        content = f.read()
    required_sections = ["<role>", "<task>", "<constraint>"]
    missing = [s for s in required_sections if s not in content]
    if missing:
        print(f"  ERROR: Handoff file missing required XML sections: "
              f"{', '.join(missing)}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_failed",
            f"Missing XML sections: {', '.join(missing)}",
        )
        return False

    handoff_abs = os.path.abspath(handoff_path)
    handoff_file = payload["deliverable_file"]

    # Ensure deliverable subdirectory exists (for symlink)
    ensure_subdir(bridge_dir, deliverable_dir)

    # Step 4: Stop target role's Ollama model — clear VRAM and context
    if to_role_data.get("model_type") == "ollama" and to_role_data.get("ollama_model"):
        unload_ollama_model(to_role_data["ollama_model"])

    # Step 5: Prepend governance file reference if target role has one
    gov_file = to_role_data.get("governance_file")
    project_root = os.path.dirname(_db_path())
    if gov_file:
        gov_path = os.path.join(project_root, "docs", "governance-templates-v2", gov_file)
        print(f"  Governance: {gov_file}")

    # Step 6: Resolve convention content_template from step's rule_key
    ctemplate = resolve_content_template_from_db(
        rule_key, db_path=_db_path()
    ) if rule_key else ""

    # Step 7: Build prompt with placeholder replacement
    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", handoff_id)
        prompt_text = prompt_text.replace("{source_role}", from_role_key)
        prompt_text = prompt_text.replace("{next_role}", to_role_key)
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", flow_key)
        # Append explicit dispatch instruction with absolute path
        prompt_text += (
            f"\n\n## Dispatch Instruction\n"
            f"Read and execute {handoff_abs}"
        )
    else:
        prompt_text = (
            f"The role '{from_role_key}' has dispatched handoff "
            f"#{handoff_id} to you.\n"
            f"Read and execute {handoff_abs}"
        )

    # Prepend governance file reference for target role
    if gov_file:
        prompt_text = (
            f"Your role is defined in {gov_path}. Read it now before proceeding.\n\n"
            f"{prompt_text}"
        )

    # Step 8: Inject prompt into target role's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
    time.sleep(0.5)

    print(f"  Handoff dispatch prompt injected into '{tmux_session}'")

    # Step 9: Update symlink in deliverable directory
    link_path = os.path.join(bridge_dir, deliverable_dir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(handoff_file, link_path)

    # Step 10: Log dispatch event to trace.log
    log(
        f"{from_role_key}->{to_role_key}",
        handoff_id,
        "dispatched",
        f"Handoff {handoff_file} dispatched to {tmux_session}",
    )

    print(f"  Logged dispatched for handoff #{handoff_id}")
    print(f"✅ Handoff {handoff_id} sent to {tmux_session}")
    print(f"   File: {handoff_path}")
    print(f"   Waiting for work from target role...")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, to_role_key)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 dispatcher — universal role transition"
    )
    parser.add_argument("--from-role", default=None, help="Source role key (matches bridge_roles.role_key)")
    parser.add_argument("--to-role", default=None, help="Target role key (matches bridge_roles.role_key)")
    parser.add_argument("--id", default=None, help="Handoff ID (auto-generated if omitted)")
    parser.add_argument("--db-flow", default=None,
                        help="DB flow_key for database-driven dispatch (required)")
    parser.add_argument("--step-key", default=None,
                        help="DB step_key within the flow (for --signal-complete)")
    parser.add_argument("--signal-send", action="store_true",
                        help="Signal initial handoff dispatch from review to target role")
    parser.add_argument("--signal-complete", action="store_true",
                        help="Signal role completion — dispatch callback to next role")
    parser.add_argument("--signal-escalation", action="store_true",
                        help="Signal review escalation to architect")
    parser.add_argument("--signal-answer", action="store_true",
                        help="Signal architect answer back to review")

    args = parser.parse_args()

    bridge_dir = _bridge_dir()

    if not args.db_flow:
        print("Error: --db-flow is required for all BridgeV002 dispatch operations")
        print("  Legacy INI-based dispatch has been removed.")
        sys.exit(1)

    # Determine handoff ID: explicit --id overrides; DB auto-incremented counter.
    if args.id:
        handoff_id = args.id
    else:
        handoff_id = f"{get_next_id_for_flow(args.db_flow, db_path=_db_path()):03d}"

    if args.signal_send:
        # Signal-send path: initial handoff dispatch from review to target role
        if not args.to_role:
            print("Error: --to-role is required for --signal-send")
            sys.exit(1)
        signal_send(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    if args.signal_escalation:
        # Signal-escalation path: review escalates question to architect
        if not args.to_role:
            print("Error: --to-role is required for --signal-escalation")
            sys.exit(1)
        signal_escalation(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    if args.signal_answer:
        # Signal-answer path: architect responds back to review
        if not args.to_role:
            print("Error: --to-role is required for --signal-answer")
            sys.exit(1)
        signal_answer(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    if args.signal_complete:
        # Signal-complete path: role has finished its deliverable, dispatch to next role
        signal_complete(
            args.db_flow,
            args.step_key,
            args.from_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    # No signal flag but db-flow provided — run full flow step via DB dispatch
    run_flow_step_db(args.db_flow, args.step_key, handoff_id, bridge_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
