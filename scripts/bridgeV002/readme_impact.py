#!/usr/bin/env python3
"""Deterministic README Impact deliverable contract.

Governance: docs/governance-templates-v2/31_README_STANDARD.md

Validates that an implementation deliverable carries exactly one
``## README Impact`` block satisfying the contract:

  impact: no   ->  a non-empty Reason
  impact: yes  ->  Affected sections (at least one), ``README updated: yes``,
                   and README-validator evidence showing PASS

This module answers "did the Implementer explicitly evaluate README impact,
and prove the README update?". Whether the resulting README satisfies the
mechanical standard is `scripts/validate_readme.py`'s separate job — the two
stay distinct even when one gate invokes both.

Activation is per flow-step via ``bridge_flow_steps.requires_readme_impact``
(migration 086), mirroring the pre-dispatch gate wiring pattern: steps that
have not opted in are untouched, and historical deliverables are never
retroactively invalidated.

Stdlib-only. CLI:

    python3 scripts/bridgeV002/readme_impact.py <deliverable.md> [--readme <README.md>] [--json]

Exit 0 valid, 1 invalid, 2 usage/IO error. Error codes are stable; gates and
tests assert codes, not messages.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

HEADING = "README Impact"

# The minimal templates, embedded so a refusal can teach the fix directly.
TEMPLATE_NO = """## README Impact

README impact: no

Reason: <why no README-relevant surface changed>"""

TEMPLATE_YES = """## README Impact

README impact: yes

Affected sections:
- <canonical section>

README updated: yes

Verification:
- `python3 scripts/validate_readme.py README.md --json`
- PASS"""


def _strip_fences(text: str) -> str:
    """Blank out fenced code blocks so example blocks never count."""
    out = []
    fence = None
    for raw in text.splitlines():
        stripped = raw.strip()
        m = re.match(r"^(```+|~~~+)", stripped)
        if m:
            marker = m.group(1)[0] * 3
            if fence is None:
                fence = marker
            elif stripped.startswith(fence):
                fence = None
            out.append("")
            continue
        out.append("" if fence is not None else raw)
    return "\n".join(out)


def _find_blocks(text: str):
    """Return the bodies of every top-level '## README Impact' section."""
    lines = _strip_fences(text).splitlines()
    starts = [
        i for i, line in enumerate(lines)
        if re.match(r"^##\s+" + re.escape(HEADING) + r"\s*$", line)
    ]
    blocks = []
    for start in starts:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if re.match(r"^##?\s+\S", lines[j]) and not lines[j].startswith("###"):
                end = j
                break
        blocks.append("\n".join(lines[start + 1 : end]))
    return blocks


def parse_readme_impact(text: str) -> dict:
    """Normalize the block into the machine-readable contract structure."""
    parsed = {
        "declared": False,
        "impact": None,
        "reason": None,
        "affected_sections": [],
        "readme_updated": None,
        "validation": {"command": None, "status": None},
        "block_count": 0,
    }
    blocks = _find_blocks(text)
    parsed["block_count"] = len(blocks)
    if len(blocks) != 1:
        return parsed
    body = blocks[0]

    m = re.search(r"(?im)^\s*README impact:\s*(\S+)\s*$", body)
    if m:
        parsed["declared"] = True
        parsed["impact"] = m.group(1).strip().lower()

    m = re.search(r"(?im)^\s*Reason:\s*(.+)$", body)
    if m and m.group(1).strip():
        parsed["reason"] = m.group(1).strip()

    m = re.search(r"(?im)^\s*Affected sections:\s*$", body)
    if m:
        tail = body[m.end():]
        for line in tail.splitlines():
            item = re.match(r"^\s*[-*]\s+(.+)$", line)
            if item:
                parsed["affected_sections"].append(item.group(1).strip())
            elif line.strip() and not item:
                break

    m = re.search(r"(?im)^\s*README updated:\s*(\S+)\s*$", body)
    if m:
        parsed["readme_updated"] = m.group(1).strip().lower() == "yes"

    m = re.search(r"(?im)^\s*Verification:\s*$", body)
    if m:
        tail = body[m.end():]
        cmd = re.search(r"validate_readme\.py[^\n`]*", tail)
        if cmd:
            parsed["validation"]["command"] = cmd.group(0).strip()
        if re.search(r"(?m)\bFAIL\b", tail):
            parsed["validation"]["status"] = "fail"
        elif re.search(r"(?m)\bPASS\b|\"status\":\s*\"pass\"", tail):
            parsed["validation"]["status"] = "pass"

    return parsed


def validate_readme_impact(text: str, readme_path: str | None = None) -> dict:
    """Validate the contract. Returns {'valid', 'errors', 'parsed'}."""
    errors = []

    def err(code, message):
        errors.append({"code": code, "message": message})

    parsed = parse_readme_impact(text)

    if parsed["block_count"] == 0:
        err(
            "README_IMPACT_BLOCK_MISSING",
            "Deliverable has no '## README Impact' section. Minimal form:\n"
            + TEMPLATE_NO,
        )
        return {"valid": False, "errors": errors, "parsed": parsed}
    if parsed["block_count"] > 1:
        err(
            "README_IMPACT_BLOCK_DUPLICATE",
            f"{parsed['block_count']} '## README Impact' sections found; exactly one is required.",
        )
        return {"valid": False, "errors": errors, "parsed": parsed}

    if not parsed["declared"]:
        err(
            "README_IMPACT_VALUE_MISSING",
            "The block carries no 'README impact: yes|no' declaration.",
        )
        return {"valid": False, "errors": errors, "parsed": parsed}

    if parsed["impact"] not in ("yes", "no"):
        err(
            "README_IMPACT_VALUE_INVALID",
            f"'README impact: {parsed['impact']}' — the only accepted values are 'yes' and 'no'.",
        )
        return {"valid": False, "errors": errors, "parsed": parsed}

    if parsed["impact"] == "no":
        if not parsed["reason"]:
            err(
                "README_IMPACT_NO_REASON_MISSING",
                "'README impact: no' requires a non-empty 'Reason:'. Minimal form:\n"
                + TEMPLATE_NO,
            )
    else:
        if not parsed["affected_sections"]:
            err(
                "README_IMPACT_AFFECTED_SECTIONS_MISSING",
                "'README impact: yes' requires 'Affected sections:' with at least one item. Minimal form:\n"
                + TEMPLATE_YES,
            )
        if parsed["readme_updated"] is None:
            err(
                "README_IMPACT_UPDATE_CONFIRMATION_MISSING",
                "'README impact: yes' requires 'README updated: yes'.",
            )
        elif parsed["readme_updated"] is False:
            err(
                "README_IMPACT_README_NOT_UPDATED",
                "'README impact: yes' combined with 'README updated: no' is a contradiction — update the README in the same Run.",
            )
        if parsed["validation"]["command"] is None or parsed["validation"]["status"] is None:
            err(
                "README_IMPACT_VALIDATION_EVIDENCE_MISSING",
                "'README impact: yes' requires Verification evidence: the validate_readme.py command and its PASS result.",
            )
        elif parsed["validation"]["status"] == "fail":
            err(
                "README_VALIDATION_FAILED",
                "The README validator evidence reports FAIL; a failed validator blocks advancement and cannot be waved through.",
            )

        # Live re-check when the gate hands us the README path: evidence says
        # PASS, the tree must agree.
        if readme_path and not any(e["code"] == "README_VALIDATION_FAILED" for e in errors):
            live = _run_readme_validator(readme_path)
            if live is not None and live.get("status") == "fail":
                codes = ", ".join(e["code"] for e in live.get("errors", []))
                err(
                    "README_VALIDATION_FAILED",
                    f"Live run of validate_readme.py against {readme_path} reports FAIL ({codes}).",
                )

    return {"valid": not errors, "errors": errors, "parsed": parsed}


def _run_readme_validator(readme_path: str):
    """Invoke scripts/validate_readme.py in-process. None if unavailable."""
    import importlib.util
    import os

    candidate = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validate_readme.py",
    )
    if not os.path.exists(candidate) or not os.path.exists(readme_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("validate_readme", candidate)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(readme_path, "r", encoding="utf-8") as fh:
            return mod.validate(fh.read())
    except Exception:
        return None


def step_requires_readme_impact(flow_key, from_role, to_role, db_path=None):
    """Read the per-step activation flag (migration 086). Missing column or
    row means not activated — older databases keep their behaviour."""
    import sqlite3

    if db_path is None:
        try:
            import config

            db_path = config.get_db_path()
        except Exception:
            return False
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT requires_readme_impact FROM bridge_flow_steps "
            "WHERE flow_key = ? AND from_role = ? AND to_role = ?",
            (flow_key, from_role, to_role),
        ).fetchone()
        conn.close()
        return bool(row and row[0])
    except sqlite3.OperationalError:
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a deliverable's README Impact block."
    )
    parser.add_argument("deliverable", help="Path to the deliverable .md file")
    parser.add_argument("--readme", help="Optional README.md to re-validate live")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        with open(args.deliverable, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {args.deliverable}: {exc}", file=sys.stderr)
        return 2

    result = validate_readme_impact(text, readme_path=args.readme)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "VALID" if result["valid"] else "INVALID"
        print(f"{status}  {args.deliverable}")
        for e in result["errors"]:
            first_line = e["message"].splitlines()[0]
            print(f"  ERROR  {e['code']}  {first_line}")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
