#!/usr/bin/env python3
"""Post-dispatch script: Architect -> Implementer transition.

Executed after the handoff from architect to implementer is complete.
Validates deliverable file exists on disk and stops architect's Ollama model
to free VRAM for the next role.

All configuration comes from DPMtF-WebUI's config.py (read at runtime):
  - bridge_dir   = config.get_bridge_base_path()   [from dpmtf.ini [bridge] base_path]
  - db_path      = config.get_db_path()             [from dpmtf.ini [database] db_path]

Script modtager kun parametre fra DB via CLI:
  --handoff-id        Handoff ID (e.g., "113")
  --step-key          Step key (e.g., "architect_to_implementer")
  --deliverable-dir   Deliverable subdirectory (from bridge_flow_steps.deliverable_dir)
  --deliverable-pattern  Deliverable filename pattern with {ID} placeholder (from bridge_flow_steps.deliverable_pattern, e.g. "{ID}-handoff.md")
  --from-role         From role key (from bridge_flow_steps.from_role)
  --error-msg         Error message for failure case (from bridge_flow_steps.error_msg)

NOTE: Script knows nothing about the bridge directory as a hardcoded path or repo.
      Bridge directory resolves via config.get_bridge_base_path() -- the configurable
      value from dpmtf.ini [bridge] base_path. Where that path points is a setup detail,
      not a hardcoded dependency on any particular bridge repository.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone


def parse_args():
    parser = argparse.ArgumentParser(
        description="Post-dispatch: validate deliverable + stop architect model"
    )
    parser.add_argument("--handoff-id", required=True, help="Handoff ID")
    parser.add_argument("--step-key", required=True, help="Step key")
    parser.add_argument("--deliverable-dir", required=True, help="Deliverable subdirectory (from DB bridge_flow_steps.deliverable_dir)")
    parser.add_argument("--deliverable-pattern", required=True, help="Deliverable filename pattern with {ID} placeholder (from DB bridge_flow_steps.deliverable_pattern). Script resolves {ID} at runtime.")
    parser.add_argument("--from-role", required=True, help="From role key (from DB bridge_flow_steps.from_role)")
    parser.add_argument("--error-msg", default="", help="Error message template for failure case (from DB bridge_flow_steps.error_msg)")
    return parser.parse_args()


def resolve_deliverable_file(deliverable_pattern, handoff_id):
    """Replace {ID} placeholder in pattern with actual handoff ID.

    This function is the ONLY place where {ID} resolution happens -- making it
    configurable via database without changing script code.

    Examples:
        "{ID}-handoff.md" + "113" -> "113-handoff.md"
        "{ID}-frommetoyou.md" + "113" -> "113-frommetoyou.md"

    Returns a string; never modifies the original pattern.
    """
    return deliverable_pattern.replace("{ID}", str(handoff_id))


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
    Uses parameterized SQL -- never f-strings or concatenation in SQL.
    """
    if not db_path or not os.path.exists(db_path):
        print("  WARNING: Database file not found, skipping Ollama lookup")
        return None

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT ollama_model FROM bridge_roles WHERE role_key = ?",
            (from_role_key,)
        ).fetchone()
        if not row:
            conn.close()
            return None

        model = row[0]
        conn.close()
        return model if model else None
    except sqlite3.OperationalError as e:
        print(f"  WARNING: Database lookup failed ({e})")
        return None


def stop_ollama_model(model_name):
    """Stop an Ollama model to free VRAM. Returns True on success.

    Handles the case where the model is already unloaded -- this is idempotent,
    not a failure condition. Already-unloaded models return non-zero from 'ollama stop'
    with stderr containing "not loaded" or "not found".
    """
    if not model_name:
        print("  No Ollama model configured for this role -- skipping stop.")
        return True

    result = subprocess.run(
        ["ollama", "stop", model_name],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  Stopped Ollama model '{model_name}'")
        return True

    # Check for 'already unloaded' -- not a failure
    stderr_lower = (result.stderr or "").lower()
    if "not loaded" in stderr_lower or "not found" in stderr_lower:
        print(f"  Model '{model_name}' not currently loaded -- VRAM already free")
        return True

    # Actual failure
    print(f"  WARNING: Failed to stop '{model_name}': {result.stderr.strip()}")
    return False


def main():
    args = parse_args()

    # Import DPMtF-WebUI config at runtime -- never hardcoded paths
    import config as dpmtf_config
    bridge_dir = dpmtf_config.get_bridge_base_path()
    db_path = dpmtf_config.get_db_path()

    print(f"\n[Post-Dispatch archi01-imple01] Handoff #{args.handoff_id}")

    # Step 1: Resolve deliverable filename by replacing {ID} placeholder
    resolved_filename = resolve_deliverable_file(args.deliverable_pattern, args.handoff_id)

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

    # Step 5: Stop the Ollama model (absolute last action -- no stdout after this)
    success = stop_ollama_model(ollama_model)
    if not success:
        print("  WARNING: Post-dispatch completed with ollama stop failure")
        sys.exit(1)

    # Step 6: Final status output (last printed line before exit)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  [Post-Dispatch archi01-imple01] Complete -- {ts}Z\n")


if __name__ == "__main__":
    main()
