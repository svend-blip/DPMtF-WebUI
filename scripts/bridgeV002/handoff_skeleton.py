#!/usr/bin/env python3
"""Handoff skeleton generator — writes a broker-valid handoff file.

Usage:
    python3 handoff_skeleton.py --flow <flow-key> --id <N> --to <role>

Writes {artifact_root}/handoffs/{N}-handoff.md with the XML envelope sections
the broker's validator requires (<role>, <task>, <constraint>, <deliverable>),
plus scope fence, standing constraints and Signal Completion pre-filled from
the run's GOAL.

The generated file must pass bridge_lib.validate_deliverable_against_schema
with rule_key='handoff' unchanged.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# config.py lives at the project root, not in scripts/bridgeV002/
_PROJECT_ROOT = str(_HERE.parent.parent)
for _p in (str(_HERE), _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import bridge_lib  # noqa: E402


def _read_goal_section(goal_path: Path, section_num: int) -> str:
    """Extract a numbered section from GOAL.md."""
    if not goal_path.exists():
        return ""
    text = goal_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    capture = False
    result: list[str] = []
    prefix = f"## {section_num}."
    alt_prefix = f"## §{section_num}"
    for line in lines:
        if line.startswith(prefix) or line.startswith(alt_prefix):
            capture = True
            result.append(line)
            continue
        if capture:
            if line.startswith("## ") and not line.startswith(prefix) and not line.startswith(alt_prefix):
                break
            result.append(line)
    return "\n".join(result).strip()


def _find_active_run_goal(artifact_root: str) -> Path | None:
    """Find the GOAL.md for the currently active (open) run."""
    bridge_dir = config.get_bridge_dir()
    runs_dir = Path(bridge_dir) / artifact_root / "runs"
    if not runs_dir.is_dir():
        return None
    # Find newest run without END-REPORT that has GOAL.md
    candidates = sorted(
        [p for p in runs_dir.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    for run_path in candidates:
        if (run_path / "END-REPORT.md").exists():
            continue
        goal = run_path / "GOAL.md"
        if goal.exists():
            return goal
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate handoff skeleton")
    parser.add_argument("--flow", required=True, help="Flow key")
    parser.add_argument("--id", required=True, type=int, help="Handoff ID")
    parser.add_argument("--to", required=True, dest="to_role", help="Target role key")
    args = parser.parse_args(argv)

    flow_key: str = args.flow
    handoff_id: int = args.id
    to_role: str = args.to_role

    artifact_root = bridge_lib.get_effective_artifact_root(flow_key)
    bridge_dir = config.get_bridge_dir()

    # Output path
    handoffs_dir = Path(bridge_dir) / artifact_root / "handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    out_path = handoffs_dir / f"{handoff_id}-handoff.md"

    # Read GOAL for fence and standing constraints
    goal_path = _find_active_run_goal(artifact_root)
    fence_section = _read_goal_section(goal_path, 4) if goal_path else ""
    standing_constraints = _read_goal_section(goal_path, 2) if goal_path else ""

    # Extract just the fence paths line from §4
    fence_paths = ""
    if fence_section:
        for line in fence_section.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                fence_paths = stripped
                break

    content = f"""# Handoff {handoff_id}

<role>
{to_role}
</role>

<task>
<!-- DECOMPOSER: fill this section with the implementation task -->
TODO: describe the implementation task here.
</task>

<constraint>
Fence: {fence_paths or '(see GOAL §4)'}

{standing_constraints or 'See GOAL §2 for standing constraints.'}

Never commit, stage or push. Do NOT run the full DPMtF suite — that is the
reviewer's closing measure.
</constraint>

<deliverable>
Write your result to: {{bridge_dir}}/{artifact_root}/results/{handoff_id}-result.md
</deliverable>

## Scope Fence

{fence_section or 'See GOAL §4.'}

## Signal Completion

After writing your deliverable, signal exactly once:

```
python3 scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role {to_role} --to-role 1000-reviewer --id {handoff_id} --action signal-send
```
"""

    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path}")

    # Self-validate
    validation = bridge_lib.validate_deliverable_against_schema(str(out_path), "handoff")
    if not validation["valid"]:
        print(f"WARNING: envelope validation failed: missing {validation['missing']}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Envelope validation: PASS")


if __name__ == "__main__":
    main()
