#!/usr/bin/env python3
"""Deterministic pre-dispatch gate — test-impact analysis.

Calls the deterministic engine chain (policy -> changes -> plan -> run ->
evidence) and fails closed in block mode.

This is a composable gate — it works identically for any flow topology
(no PLOOP/ELOOP branching). The engine serves both identically.

Usage:
    python3 gate-test-impact.py \\
        --flow-key 1000-02-ELOOP \\
        --step-key implementer-reviewer \\
        --from-role 1000-implementer \\
        --to-role 1000-reviewer \\
        --deliverable-dir /home/svend/flows/1000/results \\
        --deliverable-pattern *-result.md \\
        --deliverable-file /home/svend/flows/1000/results/32-result.md \\
        --handoff-id 32 \\
        --bridge-dir /home/svend/flows \\
        --prompt-template default \\
        --mode block
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT",
    str(Path(__file__).resolve().parent.parent.parent),
)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_lib  # noqa: E402
from scripts.testing.evidence import build_evidence, write_evidence  # noqa: E402
from scripts.testing.git_changes import changed_files  # noqa: E402
from scripts.testing.planner import PlanError, plan_tests  # noqa: E402
from scripts.testing.policy import PolicyError, load_policy  # noqa: E402
from scripts.testing.runner import RunnerError, run_plan  # noqa: E402

# ---------------------------------------------------------------------------
# Engine chain
# ---------------------------------------------------------------------------


def engine_chain(
    target_repo: str,
    flow_key: str,
    handoff_id: str,
    bridge_dir: str = "",
) -> dict:
    """Run the full deterministic engine chain.

    Returns a dict with keys:
        success: bool
        status: str  -- "PASS", "FAIL", or "ERROR"
        evidence: dict | None
        error: str | None
        evidence_path: str | None
    """
    result = {
        "success": False,
        "status": "ERROR",
        "evidence": None,
        "error": None,
        "evidence_path": None,
    }

    # Step 1: Load policy
    try:
        policy = load_policy(target_repo)
    except (PolicyError, OSError) as exc:
        result["error"] = f"Policy load failed: {exc}"
        return result

    # Step 2: Read changed files (baseline=None = working tree vs HEAD/index)
    try:
        changes = changed_files(target_repo, baseline=None)
    except subprocess.CalledProcessError as exc:
        result["error"] = f"Change detection failed: {exc}"
        return result

    # Step 3: Plan tests
    try:
        plan = plan_tests(target_repo, policy, changes)
    except PlanError as exc:
        result["error"] = f"Planning failed: {exc}"
        return result

    # Step 4: Run plan (runner.run_plan already calls build_evidence internally)
    try:
        evidence = run_plan(target_repo, plan, policy)
    except (RunnerError, OSError) as exc:
        result["error"] = f"Execution failed: {exc}"
        return result

    # Step 5: Write evidence under bridge_dir / artifact_root (NOT cwd or target tree)
    try:
        artifact_root = bridge_lib.get_effective_artifact_root(flow_key)
        evidence_dir = os.path.join(
            bridge_dir, artifact_root, "artifacts", "test-impact", flow_key
        )
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(
            evidence_dir, f"handoff-{handoff_id}-impact.md"
        )
        write_evidence(evidence, evidence_path)
        result["evidence_path"] = evidence_path
    except OSError as exc:
        result["error"] = f"Evidence write failed: {exc}"
        return result

    # Determine pass/fail from evidence status
    status = evidence.get("status", "ERROR")
    result["status"] = status
    result["evidence"] = evidence
    result["success"] = status == "PASS"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic pre-dispatch gate — runs test-impact analysis "
            "and fails closed in block mode."
        )
    )
    parser.add_argument(
        "--flow-key",
        required=True,
        help="The flow key (e.g. 1000-02-ELOOP).",
    )
    parser.add_argument(
        "--step-key",
        required=True,
        help="The step key (e.g. implementer-reviewer).",
    )
    parser.add_argument(
        "--from-role",
        required=True,
        help="The source role key.",
    )
    parser.add_argument(
        "--to-role",
        required=True,
        help="The destination role key.",
    )
    parser.add_argument(
        "--deliverable-dir",
        required=True,
        help="Directory containing deliverables.",
    )
    parser.add_argument(
        "--deliverable-pattern",
        required=True,
        help="Glob pattern for deliverable files.",
    )
    parser.add_argument(
        "--deliverable-file",
        required=True,
        help="Path to the specific deliverable file.",
    )
    parser.add_argument(
        "--handoff-id",
        required=True,
        help="The handoff ID.",
    )
    parser.add_argument(
        "--bridge-dir",
        required=True,
        help="The bridge directory base path.",
    )
    parser.add_argument(
        "--prompt-template",
        required=True,
        help="The prompt template identifier.",
    )
    parser.add_argument(
        "--mode",
        choices=["block", "warn"],
        # Default warn, not block: the pre-dispatch wiring (085) invokes this
        # gate through step_to_cli_args, which passes only the ten standard
        # fields and CANNOT pass --mode. GOAL 006 D2's rollout contract is
        # "runs in WARN mode; the step configuration does not switch to
        # block" — with a block default, the wiring silently ran block and a
        # gate failure aborted delivery with no trace event. Measured live on
        # run 017 handoff 43, 2026-08-28. Block mode remains available to any
        # caller that passes --mode block explicitly.
        default="warn",
        help="Gate mode: 'block' exits 1 on failure, 'warn' always exits 0. "
             "Default: warn.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    """Entry point."""
    args = parse_args()

    flow_key = args.flow_key
    handoff_id = args.handoff_id
    mode = args.mode
    bridge_dir = args.bridge_dir

    # Resolve target project
    try:
        target_project = bridge_lib.get_flow_target_project(flow_key)
    except Exception as exc:
        print(f"ERROR: Failed to resolve target project: {exc}", file=sys.stderr)
        sys.exit(1)

    # Resolve target repo path
    project_path = os.path.join(bridge_dir, target_project)
    if not os.path.isdir(project_path):
        print(f"ERROR: Project path not found: {project_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Gate starting for flow={flow_key}, handoff={handoff_id}")
    print(f"Target project: {target_project}")
    print(f"Target repo: {project_path}")
    print(f"Mode: {mode}")

    # Run the engine chain
    result = engine_chain(project_path, flow_key, handoff_id, bridge_dir)

    # Report results
    print(f"Result: status={result['status']}, success={result['success']}")
    if result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
    if result["evidence_path"]:
        print(f"Evidence written to: {result['evidence_path']}")

    # Fail closed in block mode
    if mode == "block" and not result["success"]:
        print(f"Gate FAILED (mode=block): {result['status']}", file=sys.stderr)
        sys.exit(1)

    if mode == "block":
        print("Gate PASSED (mode=block)")

    # In warn mode, always exit 0
    print("Gate complete.")


if __name__ == "__main__":
    main()
