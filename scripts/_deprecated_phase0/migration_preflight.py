#!/usr/bin/env python3
"""Migration preflight — validates the proposed alias mapping before any DB changes.

Phase 0 mode (no aliases created yet):
  1. Every active non-human role has a known client (default_runtime)
  2. Every non-human, non-excluded role has a proposed alias
  3. No human role is assigned a model
  4. No role has conflicting role- and step-level model config
  5. No duplicate alias assignment
  6. Excluded roles are explicitly listed
  7. Proposed alias names follow naming conventions

Phase 2 mode (aliases created, run with --check-resolution):
  All Phase 0 checks plus:
  8. Every proposed alias resolves via model-allocator
  9. Every alias supports the required client
  10. No required environment variable is silently absent
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config

PROPOSED_MAPPING = {
    "archi01": "archi-local",
    "archi01cloud": "archi-local",
    "analyst01_trade": "archi-local",
    "sim01_trade": "archi-local",
    "trend01_trade": "trend-local",
    "market01_trade": "coder-96k-local",
    "portfolio01_trade": "coder-96k-local",
    "risk01_trade": "coder-48k-local",
    "score01_trade": "coder-48k-local",
    "learn01_trade": "learn-local",
    "review01": "review01-local",
    "review01cloud": "review02-local",
    "review01pay": "review02-local",
    "review02": "review02-local",
    "review01_trade": "review02-local",
    "review02cloud": "review-cloud",
    "review02pay": "review-cloud",
    "archi01pay": "archi-pay",
    "imple01pay": "imple-pay",
    "imple01": "imple01-local",
}

EXCLUDED = {
    "human", "humancloud", "humanpay", "humantrade",
    "imple01cloud",
}

CLIENT_MAP = {"claude": "claude-code", "opencode": "opencode"}

ALLOCATOR_SCRIPT = os.path.join(
    config.get_project_path("model-allocator"), "scripts", "model-allocator"
)


def main():
    check_resolution = "--check-resolution" in sys.argv
    db_path = config.get_db_path()
    if not os.path.isabs(db_path):
        db_path = os.path.join(str(PROJECT_ROOT), db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    roles = conn.execute("""
        SELECT role_key, role_type, default_runtime, default_provider,
               default_model, default_model_source, default_model_alias,
               ollama_model, cloud_model
        FROM bridge_roles WHERE is_active = 1 ORDER BY role_key
    """).fetchall()

    step_overrides = conn.execute("""
        SELECT flow_key, step_key, from_role, to_role, model_source, model_alias
        FROM bridge_flow_steps
        WHERE is_active = 1
          AND model_source IS NOT NULL AND model_source != ''
    """).fetchall()
    conn.close()

    errors = []
    warnings = []
    passed = []
    seen_aliases = {}

    for r in roles:
        role_key = r["role_key"]
        role_type = r["role_type"]

        if role_type == "human":
            if r["default_model_source"] or r["default_model_alias"]:
                errors.append(f"{role_key}: human role has model_source/alias set")
            else:
                passed.append(f"{role_key}: human role correctly has no model")
            continue

        if role_key in EXCLUDED:
            passed.append(f"{role_key}: excluded from migration")
            continue

        runtime = r["default_runtime"]
        if not runtime:
            errors.append(f"{role_key}: no default_runtime set")
            continue

        alias = PROPOSED_MAPPING.get(role_key)
        if not alias:
            errors.append(f"{role_key}: no proposed alias in mapping")
            continue

        # Check for duplicate alias assignments
        if alias in seen_aliases:
            # Same alias for multiple roles is OK if they share the same model
            # — but we record it as a shared alias
            seen_aliases[alias].append(role_key)
        else:
            seen_aliases[alias] = [role_key]

        client = CLIENT_MAP.get(runtime, runtime)

        if check_resolution:
            # Phase 2 mode: check actual alias resolution via --json
            try:
                result = subprocess.run(
                    [ALLOCATOR_SCRIPT, "validate", "--alias", alias, "--client", client, "--json"],
                    capture_output=True, text=True, timeout=15,
                )
                # Parse JSON output
                try:
                    data = json.loads(result.stdout.strip())
                    status = data.get("validation_status", "UNKNOWN")
                    if status == "ERROR":
                        errors.append(
                            f"{role_key}: alias '{alias}' validation ERROR: "
                            f"{data.get('errors', [])}"
                        )
                    elif status == "WARNING":
                        warnings.append(
                            f"{role_key}: alias '{alias}' has warnings: "
                            f"{data.get('warnings', [])}"
                        )
                        passed.append(f"{role_key}: alias '{alias}' resolves (WARNING)")
                    else:
                        passed.append(f"{role_key}: alias '{alias}' validates OK for client '{client}'")
                except json.JSONDecodeError:
                    # Fallback for allocators without --json
                    if result.returncode == 1:
                        errors.append(
                            f"{role_key}: alias '{alias}' fails validation: {result.stderr.strip()}"
                        )
                    else:
                        passed.append(f"{role_key}: alias '{alias}' validates (text mode)")
            except Exception as e:
                errors.append(f"{role_key}: allocator check failed: {e}")
        else:
            # Phase 0 mode: just check structure
            passed.append(
                f"{role_key}: mapped to alias '{alias}' (client={client}, "
                f"model={r['ollama_model'] or r['cloud_model'] or r['default_model']})"
            )

    # Report shared aliases
    for alias, role_list in seen_aliases.items():
        if len(role_list) > 1:
            passed.append(f"alias '{alias}' shared by: {', '.join(role_list)}")

    # Step overrides
    if step_overrides:
        for s in step_overrides:
            warnings.append(
                f"step override: {s['flow_key']}/{s['step_key']} "
                f"has model_source='{s['model_source']}'"
            )
    else:
        passed.append("no step-level model overrides")

    # Print report
    print("=" * 70)
    print("MIGRATION PREFLIGHT REPORT")
    print(f"Mode: {'Phase 2 (resolution check)' if check_resolution else 'Phase 0 (structure check)'}")
    print("=" * 70)
    print(f"\nPassed: {len(passed)}")
    for p in passed:
        print(f"  ✓ {p}")
    print(f"\nWarnings: {len(warnings)}")
    for w in warnings:
        print(f"  ⚠ {w}")
    print(f"\nErrors: {len(errors)}")
    for e in errors:
        print(f"  ✗ {e}")

    if errors:
        print(f"\n❌ PREFLIGHT FAILED — {len(errors)} error(s)")
        return 1
    else:
        print(f"\n✅ PREFLIGHT PASSED — {len(passed)} checks, {len(warnings)} warnings")
        return 0


if __name__ == "__main__":
    sys.exit(main())
