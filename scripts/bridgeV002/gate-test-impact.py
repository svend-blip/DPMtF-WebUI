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
        --mode block \\
        --run-dir /home/svend/flows/1000/runs/010 \\
        --requested-scope full
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
from scripts.testing.planner import PlanError, plan_tests, _scope_max  # noqa: E402
from scripts.testing.policy import PolicyError, load_policy  # noqa: E402
from scripts.testing.runner import RunnerError, run_plan  # noqa: E402

# ---------------------------------------------------------------------------
# Engine chain
# ---------------------------------------------------------------------------


def _compose_narrowing(target_repo, changes, baseline, policy):
    """Build (symbols, closure, note) for symbol/file narrowing.

    Returns ``(None, None, reason)`` whenever narrowing cannot be trusted:
    no Python changes, an empty policy, or any analysis failure. The
    planner treats ``None`` as "component ladder only".
    """
    py_changes = [p for p in changes if p.endswith(".py")]
    if not py_changes:
        return None, None, "not attempted: no Python files changed"
    if policy.is_empty:
        return None, None, "not attempted: empty policy"
    try:
        from scripts.testing.git_changes import changed_ranges
        from scripts.testing.symbol_analysis import changed_symbols
        from scripts.testing.dependency_graph import build_graph, reverse_closure, node_id
        ranges = changed_ranges(target_repo, baseline=baseline)
        symbols = {}
        for path in changes:
            if path.endswith(".py"):
                found = changed_symbols(target_repo, path, ranges.get(path, []))
                symbols[path] = set(found) if isinstance(found, (list, set, tuple)) else found
            else:
                symbols[path] = set()
        graph = build_graph(target_repo)
        seeds = [
            node_id(path, sym)
            for path, syms in symbols.items()
            if isinstance(syms, set)
            for sym in syms
        ]
        closure = reverse_closure(graph, seeds)
        return symbols, closure, f"symbols for {len(py_changes)} Python file(s); closure safe={closure.is_safe}"
    except Exception as exc:  # noqa: BLE001 — degrade, never block the dispatch
        return None, None, f"unavailable: {type(exc).__name__}: {exc}"

def engine_chain(
    target_repo: str,
    flow_key: str,
    handoff_id: str,
    bridge_dir: str = "",
    run_dir: str | None = None,        # NEW — run directory for baseline resolution
    requested_scope: str | None = None, # NEW — "full" triggers explicit regression gate
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

    # --- Lifecycle-aware baseline resolution ---
    resolved_baseline = None
    baseline_resolution = None
    lifecycle_point = "work_unit"
    baseline_tree_state = None

    if run_dir is not None:
        # Read baseline from RUN-LEDGER
        baseline_sha = read_run_ledger_baseline(run_dir)
        tree_cleanliness = read_run_ledger_tree_cleanliness(run_dir)

        if baseline_sha is None:
            # Baseline not recorded -> escalate to full regression
            baseline_resolution = "unresolved"
            resolved_baseline = None
        else:
            # Verify the baseline resolves
            try:
                from scripts.testing.git_changes import resolve_baseline as resolve_baseline_sha
                resolved = resolve_baseline_sha(target_repo, baseline_sha)
                resolved_baseline = resolved
                baseline_resolution = "resolved"
            except ValueError:
                # Baseline SHA no longer in repository -> escalate to full regression
                resolved_baseline = None
                baseline_resolution = "unresolved"

        # Dirty-tree condition: escalate scope
        if tree_cleanliness == "dirty" or tree_cleanliness is None:
            requested_scope = _scope_max(requested_scope or "component", "broad")

        baseline_tree_state = tree_cleanliness
        lifecycle_point = "run_baseline"

    # Explicit full-regression gate
    if requested_scope == "full" and run_dir is not None:
        lifecycle_point = "explicit_gate"

    # Step 2: Read changed files (baseline=resolved_baseline or None)
    try:
        changes = changed_files(target_repo, baseline=resolved_baseline)
    except subprocess.CalledProcessError as exc:
        result["error"] = f"Change detection failed: {exc}"
        return result

    # Step 3: Plan tests — with symbol/closure narrowing when the change is
    # Python and the analysis succeeds. Every failure degrades to the
    # component ladder; the reason is recorded, never hidden.
    symbols, closure, narrowing_note = _compose_narrowing(target_repo, changes, resolved_baseline, policy)
    result["narrowing"] = narrowing_note
    try:
        plan = plan_tests(
            target_repo, policy, changes, requested_scope=requested_scope,
            symbols=symbols, closure=closure,
        )
    except PlanError as exc:
        result["error"] = f"Planning failed: {exc}"
        return result

    # Step 4: Run plan (runner.run_plan already calls build_evidence internally)
    # When the policy is empty and the plan is exhaustive, skip the test run
    # to avoid running the full suite indefinitely (no policy = no gates).
    if policy.is_empty and getattr(plan, "is_exhaustive", False):
        # No policy at the target: nothing was measured. This is SKIPPED,
        # not PASS — until 2026-09-02 it was recorded as PASS and 150
        # evidence files in a row said green without running a test.
        status = "SKIPPED"
        print(
            f"test-impact: no .dpmtf/test-policy.json in {target_repo} — "
            f"no tests selected or run (SKIPPED, not a pass)"
        )
        evidence = build_evidence(
            repo_root=target_repo,
            plan=plan,
            test_command=["skip-empty-policy"],
            status="SKIPPED",
            duration_seconds=0.0,
            lifecycle_point=lifecycle_point,
            baseline_tree_state=baseline_tree_state,
            baseline_resolution=baseline_resolution,
        )
    else:
        try:
            evidence = run_plan(target_repo, plan, policy, timeout=120)
            status = evidence.get("status", "ERROR")
            # Post-process: add lifecycle fields to evidence from run_plan
            evidence["lifecycle_point"] = lifecycle_point
            evidence["baseline_tree_state"] = baseline_tree_state
            evidence["baseline_resolution"] = baseline_resolution
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
    result["status"] = status
    result["evidence"] = evidence
    result["success"] = status in ("PASS", "SKIPPED")
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
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Path to the run directory (e.g. /home/svend/flows/1000/runs/010). "
             "When provided, the gate resolves the Run baseline from RUN-LEDGER.md.",
    )
    parser.add_argument(
        "--requested-scope",
        default=None,
        choices=["symbol", "file", "component", "broad", "full"],
        help="Request a minimum scope level. 'full' triggers the explicit full-regression gate.",
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
    result = engine_chain(
        project_path, flow_key, handoff_id, bridge_dir,
        run_dir=args.run_dir,
        requested_scope=args.requested_scope,
    )

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


# ---------------------------------------------------------------------------
# RUN-LEDGER baseline reader (gate-only; engine stays flow-blind)
# ---------------------------------------------------------------------------


def read_run_ledger_baseline(run_dir: str) -> str | None:
    """Read the baseline commit from a run's RUN-LEDGER.md.

    Looks for a line matching:
        - baseline: `<sha>` in <path> (working tree: ... at promotion)

    Returns the 40-char SHA as str, or None if not found.

    Parameters
    ----------
    run_dir:
        Path to the run directory (e.g. /home/svend/flows/1000/runs/010).

    Returns
    -------
    str | None
        The baseline commit SHA, or None if the entry is not found.
    """
    ledger_path = os.path.join(run_dir, "RUN-LEDGER.md")
    try:
        with open(ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- baseline:"):
                    # Extract the SHA between backticks
                    start = line.find("`")
                    end = line.find("`", start + 1)
                    if start != -1 and end != -1:
                        sha = line[start + 1:end]
                        return sha
    except (OSError, FileNotFoundError):
        pass
    return None


def read_run_ledger_tree_cleanliness(run_dir: str) -> str | None:
    """Read whether the tree was clean at promotion from a run's RUN-LEDGER.md.

    Looks for a line matching:
        working tree: 6 uncommitted path(s) at promotion
        working tree: clean at <sha>
        working tree: clean

    Returns:
        "clean" if tree was clean
        "dirty" if uncommitted paths were present
        None if the information is not stated in the ledger

    Parameters
    ----------
    run_dir:
        Path to the run directory.

    Returns
    -------
    str | None
    """
    ledger_path = os.path.join(run_dir, "RUN-LEDGER.md")
    try:
        with open(ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "working tree:" in line or "working tree :" in line:
                    # Check for uncommitted paths (dirty)
                    if "uncommitted" in line:
                        return "dirty"
                    # Check for clean
                    if "clean" in line:
                        return "clean"
    except (OSError, FileNotFoundError):
        pass
    return None


if __name__ == "__main__":
    main()
