#!/usr/bin/env python3
"""Import flow outputs and refresh portfolio01 session before dispatch.

Called as a pre_dispatch_script on the sim01->portfolio01 step.  Two jobs:

1. Kill + recreate the portfolio01_trade tmux session so it starts with
   fresh context (the session is never cycled by stop_tmuxflow/start_tmuxflow
   because portfolio01 only appears as a to_role, never a from_role).

2. Call trade-ui's POST /api/periodic/import-now endpoint and wait for the
   response so portfolio01 always sees imported data in the database.

Usage:
  python3 scripts/bridgeV002/import-flow-output.py --handoff-id 053 --from-role sim01_trade
  (dispatch.py also passes --flow-key, --step-key, --to-role, etc.)
"""

import os
import sys
import time
import sqlite3
import argparse
import subprocess

import requests


TRADE_UI_URL = "http://localhost:9140/api/periodic/import-now"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

# ── portfolio01 session management ──────────────────────

def _get_db_path():
    """Resolve the Father database path (same project root as this script)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    return os.path.join(project_root, "databases", "dpmtf.db")


def _get_role_config(role_key):
    """Read role config from bridge_roles.  Returns dict or None."""
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM bridge_roles WHERE role_key = ? AND is_active = 1",
        (role_key,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _build_start_command(role):
    """Build the CLI start command for a role via Model Allocator."""
    model_source = role.get("default_model_source") or ""
    model_alias = role.get("default_model_alias") or ""

    if model_source != "model_allocator" or not model_alias:
        return None

    # Determine client from enter_command (Freebuff uses c-m)
    enter_cmd = role.get("enter_command", "default")
    if enter_cmd == "c-m":
        allocator_client = "freebuff"
    else:
        allocator_client = "opencode"

    import config as _cfg
    allocator_path = os.path.join(
        _cfg.get_project_path("model-allocator"), "scripts", "model-allocator"
    )
    # Use allocator run to get the shell command, then return it
    try:
        result = subprocess.run(
            [allocator_path, "run",
             "--role", role["role_key"],
             "--client", allocator_client],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            shell_str = result.stdout.strip()
            cwd = _cfg.get_project_root()
            return f"cd {cwd} && {shell_str}"
    except Exception:
        pass
    return None


def _restart_session(session_name, role_key):
    """Kill and recreate a tmux session with a fresh coding frontend."""
    # Kill existing session (ignore errors)
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )

    # Create new detached session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name],
        check=True, capture_output=True,
    )
    print(f"  Restarted tmux session: {session_name}")

    # Build and send start command
    role = _get_role_config(role_key)
    if not role:
        print(f"  WARNING: role '{role_key}' not found in bridge_roles — "
              f"session created but no start command sent")
        return

    cmd = _build_start_command(role)
    if not cmd:
        print(f"  WARNING: no start command for role '{role_key}' "
              f"(model_source={role.get('default_model_source')}) — session is idle")
        return

    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, cmd, "Enter"],
        check=True, capture_output=True,
    )
    print(f"  Start command sent to {session_name} "
          f"(alias={role.get('default_model_alias')})")


# ── Import ──────────────────────────────────────────────

def _try_import():
    """Call the trade-ui import endpoint.  Returns (ok, data) tuple."""
    r = requests.post(TRADE_UI_URL, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data.get("ok", False), data


def _verify_handoff_imported(summary, handoff_id):
    """Check that at least one file for this handoff was imported."""
    files = summary.get("files", [])
    handoff_files = [f for f in files
                     if str(handoff_id) in str(f.get("file", ""))]
    if not handoff_files:
        return True, 0
    rejected = [f for f in handoff_files
                if f.get("status") == "rejected"]
    return len(rejected) == 0, len(rejected)


def main():
    parser = argparse.ArgumentParser(
        description="Import flow outputs and refresh portfolio01 session"
    )
    parser.add_argument("--handoff-id", required=True,
                        help="Flow run ID (e.g. 053)")
    parser.add_argument("--from-role", required=True,
                        help="Role that completed (e.g. sim01_trade)")
    # Accepted but not used directly — passed by dispatch.py step_to_cli_args()
    parser.add_argument("--flow-key", default=None, help="Flow key")
    parser.add_argument("--step-key", default=None, help="Step key")
    parser.add_argument("--to-role", default=None, help="Target role")
    parser.add_argument("--deliverable-dir", default=None,
                        help="Deliverable directory")
    parser.add_argument("--deliverable-pattern", default=None,
                        help="Deliverable filename pattern")
    parser.add_argument("--deliverable-file", default=None,
                        help="Deliverable filename")
    parser.add_argument("--bridge-dir", default=None,
                        help="Bridge directory")
    parser.add_argument("--prompt-template", default=None,
                        help="Prompt template key")
    args = parser.parse_args()

    # ── 1. Restart portfolio01 session (fresh context) ──
    to_role = args.to_role or "portfolio01_trade"
    _restart_session(to_role, to_role)

    # ── 2. Import ───────────────────────────────────────
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ok, data = _try_import()
            if ok:
                break
            last_error = f"import returned ok=false: {data}"
        except requests.exceptions.ConnectionError:
            last_error = f"cannot reach trade-ui at {TRADE_UI_URL}"
        except requests.exceptions.Timeout:
            last_error = "import request timed out after 60s"
        except Exception as exc:
            last_error = f"import request failed: {exc}"

        if attempt < MAX_RETRIES:
            print(f"  Import attempt {attempt}/{MAX_RETRIES} failed: "
                  f"{last_error} — retrying in {RETRY_DELAY}s")
            time.sleep(RETRY_DELAY)

    if last_error is not None:
        print(f"ERROR: Import failed after {MAX_RETRIES} attempts: "
              f"{last_error}", file=sys.stderr)
        return 1

    # ── 3. Report ───────────────────────────────────────
    summary = data.get("summary", {})
    imported = summary.get("imported", 0)
    rejected = summary.get("rejected", 0)
    skipped = summary.get("skipped", 0)

    print(f"Import OK: {imported} imported, {rejected} rejected, "
          f"{skipped} skipped (handoff {args.handoff_id}, "
          f"from {args.from_role})")

    verified, rejected_count = _verify_handoff_imported(summary,
                                                        args.handoff_id)
    if rejected_count > 0:
        handoff_files = [f for f in summary.get("files", [])
                         if str(args.handoff_id) in str(f.get("file", ""))]
        for rf in handoff_files:
            if rf.get("status") == "rejected":
                print(f"  REJECTED: {rf.get('file','?')} — "
                      f"{rf.get('error','?')}")

    if not verified:
        print(f"ERROR: {rejected_count} file(s) for handoff "
              f"{args.handoff_id} were rejected", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
