#!/usr/bin/env python3
"""Pre-dispatch import script: import pending JSON files into trade-ui database.

Runs before the next role in the chain is activated. Ensures that upstream
role outputs are available in the trade-ui database for downstream roles
that query the database (portfolio01_trade, score01_trade, learn01_trade).

Derives the trade-ui project root from --deliverable-dir (parent of inbox/).
Always returns success — import failures must not block the flow chain.
"""

import argparse
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pre-dispatch: import pending JSON into trade-ui database"
    )
    parser.add_argument("--deliverable-dir", required=True,
                        help="Deliverable directory (e.g. {PROJECT_ROOT}/inbox/pending)")
    parser.add_argument("--handoff-id", default="",
                        help="Handoff ID (for logging)")
    parser.add_argument("--step-key", default="",
                        help="Step key (for logging)")
    # Accept but ignore other dispatch params
    parser.add_argument("--flow-key", default="")
    parser.add_argument("--from-role", default="")
    parser.add_argument("--to-role", default="")
    parser.add_argument("--deliverable-pattern", default="")
    parser.add_argument("--deliverable-file", default="")
    parser.add_argument("--bridge-dir", default="")
    parser.add_argument("--prompt-template", default="")
    return parser.parse_known_args()[0]


def derive_project_root(deliverable_dir):
    """Derive trade-ui project root from deliverable_dir.

    deliverable_dir is e.g. {PROJECT_ROOT}/inbox/pending
    The inbox/ directory is a direct child of the project root.
    Returns the project root path, or None if it cannot be derived.
    """
    # Walk up from deliverable_dir to find the directory containing 'inbox'
    path = os.path.abspath(deliverable_dir)
    for _ in range(5):  # safety limit
        parent = os.path.dirname(path)
        if os.path.basename(path) == "inbox":
            return parent
        if parent == path:
            break
        path = parent
    return None


def run_import(project_root):
    """Run import_flow_output.py in the trade-ui project.

    Returns True if the import script ran without errors, False otherwise.
    Import validation failures (rejected files) are NOT treated as errors —
    they are expected and logged by the import script itself.
    """
    import_script = os.path.join(project_root, "scripts", "import_flow_output.py")
    if not os.path.exists(import_script):
        print(f"  WARNING: Import script not found: {import_script}")
        return False

    result = subprocess.run(
        ["python3", import_script],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    if result.returncode != 0:
        print(f"  WARNING: Import script failed (rc={result.returncode})")
        stderr_preview = result.stderr[:300] if result.stderr else "(no stderr)"
        print(f"  Stderr: {stderr_preview}")
        return False

    # Print the import summary (JSON on stdout from import_flow_output.py)
    if result.stdout:
        # Only print first 500 chars to keep logs readable
        stdout_preview = result.stdout[:500]
        print(f"  Import result: {stdout_preview}")
        if len(result.stdout) > 500:
            print(f"  ... (truncated, {len(result.stdout)} total chars)")

    return True


def main():
    args = parse_args()

    print(f"\n[Pre-Dispatch Import] Handoff #{args.handoff_id} (step: {args.step_key})")

    # Step 1: Derive trade-ui project root from deliverable_dir
    project_root = derive_project_root(args.deliverable_dir)
    if not project_root:
        print(f"  WARNING: Could not derive project root from '{args.deliverable_dir}'")
        print(f"  [Pre-Dispatch Import] Skipped — no project root")
        return 0

    print(f"  Project root: {project_root}")

    # Step 2: Run import_flow_output.py
    success = run_import(project_root)
    if not success:
        # Non-fatal — import failures must not block the chain
        print(f"  [Pre-Dispatch Import] Complete with warnings")
    else:
        print(f"  [Pre-Dispatch Import] Complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
