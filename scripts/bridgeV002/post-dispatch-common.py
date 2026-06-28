#!/usr/bin/env python3
"""Generic post-dispatch script: validate deliverable + stop from_role's Ollama model.

Convention-agnostic — works identically for handoff, callback, and verdict conventions.
All configuration comes from DPMtF-WebUI's config.py (read at runtime):
  - bridge_dir   = config.get_bridge_base_path()   [from dpmtf.ini [bridge] base_path]
  - db_path      = config.get_db_path()             [from dpmtf.ini [database] db_path]

Script modtager kun parametre fra DB via CLI:
  --handoff-id        Handoff ID (e.g., "113")
  --step-key          Step key (e.g., "implementer_to_review_heavy1")
  --deliverable-dir   Deliverable subdirectory (from bridge_flow_steps.deliverable_dir)
  --deliverable-pattern  Deliverable filename pattern with {ID} placeholder (from bridge_flow_steps.deliverable_pattern, e.g. "{ID}-callback.md")
  --from-role         From role key (from bridge_flow_steps.from_role)
  --error-msg         Error message for failure case (from bridge_flow_steps.error_msg)

NOTE: Scriptet kender intet til bridge-stien som hardcoded path eller repo.
      Bridge directory resolves via config.get_bridge_base_path() — den konfigurerbare
      værdi fra dpmtf.ini [bridge] base_path. Alle post-dispatch steps bruger dette
      samme script; forskellen er udelukkende i database-værdierne (from_role, pattern, dir).
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generic post-dispatch: validate deliverable + stop from_role model"
    )
    parser.add_argument("--handoff-id", required=True, help="Handoff ID")
    parser.add_argument("--step-key", required=True, help="Step key")
    parser.add_argument("--deliverable-dir", required=True, help="Deliverable subdirectory (from DB bridge_flow_steps.deliverable_dir)")
    parser.add_argument("--deliverable-pattern", required=True, help="Deliverable filename pattern with {ID} placeholder (from DB bridge_flow_steps.deliverable_pattern). Script resolves {ID} at runtime.")
    parser.add_argument("--from-role", required=True, help="From role key (from DB bridge_flow_steps.from_role)")
    parser.add_argument("--error-msg", default="", help="Error message template for failure case (from DB bridge_flow_steps.error_msg)")
    return parser.parse_known_args()[0]


def resolve_deliverable_file(deliverable_pattern, handoff_id, from_role=None):
    """Replace {ID} and {role_key} placeholders in pattern.

    {ID} is replaced with the handoff ID.
    {role_key} is replaced with the from_role (the role that wrote the file).

    Examples:
        "{ID}-handoff.md" + "113" → "113-handoff.md"
        "{ID}_{role_key}.json" + "012" + "trend01_trade" → "012_trend01_trade.json"

    Returns a string; never modifies the original pattern.
    """
    result = deliverable_pattern.replace("{ID}", str(handoff_id))
    if from_role:
        result = result.replace("{role_key}", from_role)
    return result


def get_deliverable_path(bridge_dir, deliverable_dir, resolved_filename):
    """Construct full deliverable path from bridge base directory components."""
    return os.path.join(bridge_dir, deliverable_dir, resolved_filename)


def validate_deliverable(full_path):
    """Check if deliverable file exists on disk and print status."""
    if os.path.exists(full_path):
        size = os.path.getsize(full_path)
        print(f"  Deliverable OK: {full_path} ({size} bytes)")
        return True
    else:
        return False


def get_ollama_model_from_db(from_role_key, db_path):
    """Look up the Ollama model for a given role from bridge_roles table.

    Returns the ollama_model string or None if not found/not configured.
    Uses parameterized SQL — never f-strings or concatenation in SQL-sp queries.
    """
    if not db_path or not os.path.exists(db_path):
        print("  WARNING: Database file not found, skipping Ollama lookup")
        return None

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        row = conn.execute(
            "SELECT ollama_model FROM bridge_roles WHERE role_key = ?",
            (from_role_key,)
        ).fetchone()
        conn.close()
        return row["ollama_model"] if row and row["ollama_model"] else None
    except sqlite3.OperationalError as e:
        print(f"  WARNING: Database lookup failed ({e})")
        return None


def stop_ollama_model(model_name):
    """Stop an Ollama model to free VRAM. Returns True on success.

    Handles the case where the model is already unloaded — this is idempotent,
    not a failure condition. Already-unloaded models return non-zero from 'ollama stop'
    with stderr containing "not loaded" or "not found".
    """
    if not model_name:
        print("  No Ollama model configured for this role — skipping stop.")
        return True

    result = subprocess.run(
        ["ollama", "stop", model_name],
        capture_output=True, text=True
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


def main():
    args = parse_args()

    # Ensure project root is on sys.path for config import
    import sys as _sys
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(os.path.dirname(_script_dir))
    if _project_root not in _sys.path:
        _sys.path.insert(0, _project_root)

    # Import DPMtF-WebUI config at runtime — never hardcoded paths
    import config as dpmtf_config
    bridge_dir = dpmtf_config.get_bridge_base_path()
    db_path = dpmtf_config.get_db_path()

    print(f"\n[Post-Dispatch Common] Handoff #{args.handoff_id} (step: {args.step_key})")

    # Step 1: Resolve deliverable filename by replacing {ID} and {role_key} placeholders
    resolved_filename = resolve_deliverable_file(args.deliverable_pattern, args.handoff_id, args.from_role)

    # Step 2: Construct full deliverable path from config + DB values
    full_deliverable_path = get_deliverable_path(bridge_dir, args.deliverable_dir, resolved_filename)

    # Step 3: Validate deliverable file exists on disk
    if not validate_deliverable(full_deliverable_path):
        print(f"  ERROR: {args.error_msg}")
        sys.exit(1)

    # Step 4: Look up Ollama model for from_role in database
    ollama_model = get_ollama_model_from_db(args.from_role, db_path)
    if ollama_model:
        print(f"  From role '{args.from_role}' has Ollama model: {ollama_model}")

    # Step 5: Stop the Ollama model (absolute last action — no stdout after this)
    success = stop_ollama_model(ollama_model)
    if not success:
        print("  WARNING: Post-dispatch completed with ollama stop failure")
        sys.exit(1)

    # Step 6: Final status output (last printed line before exit)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  [Post-Dispatch Common] Complete — {ts}Z\n")


if __name__ == "__main__":
    main()
