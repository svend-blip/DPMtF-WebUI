#!/usr/bin/env python3
"""Deterministic README validator for the DPMtF README standard.

Governance: docs/governance-templates-v2/31_README_STANDARD.md

Mechanically enforces the interpretation-free parts of the README contract:
exactly one H1; the mandatory operational sections; the three Installation
subsections; canonical core ordering; no duplicated mandatory headings; no
secret-like material. Advisory findings (missing Overview/Architecture,
legacy alias headings, personal absolute paths) are warnings and never fail
the run.

Deliberately stdlib-only with no DPMtF imports, so the same file is callable
by LightWorkers and against foreign repositories:

    python3 scripts/validate_readme.py <path>/README.md
    python3 scripts/validate_readme.py --json <path>/README.md

Exit codes: 0 pass (warnings allowed), 1 fail, 2 usage/IO error.
Error codes are stable; gates and tests assert codes, not messages.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Canonical operational core, in required order.
CORE_ORDER = ["Requirements", "Installation", "Configuration", "Running", "Testing"]

# Advisory sections: recommended, warning when absent.
ADVISORY_H2 = ["Overview", "Architecture"]

# Required H3 subsections under Installation.
INSTALL_SUBSECTIONS = ["Install manually", "Install using an Agent", "Verify installation"]

# All headings whose duplication is an error (canonical repository-level sections).
MANDATORY_H2 = CORE_ORDER + ADVISORY_H2

# Legacy alias -> canonical. Warn only when the canonical heading is absent.
ALIASES = {
    "Setup": "Installation",
    "Prerequisites": "Requirements",
    "Dependencies": "Requirements",
    "Host Requirements": "Requirements",
    "Tests": "Testing",
    "Running the Test Suite": "Testing",
}

# JSON "sections" keys per the governance contract.
SECTION_KEYS = {
    "overview": ("h2", "Overview"),
    "architecture": ("h2", "Architecture"),
    "requirements": ("h2", "Requirements"),
    "installation": ("h2", "Installation"),
    "install_manually": ("h3", "Install manually"),
    "agent_installation": ("h3", "Install using an Agent"),
    "installation_verification": ("h3", "Verify installation"),
    "configuration": ("h2", "Configuration"),
    "running": ("h2", "Running"),
    "testing": ("h2", "Testing"),
}

PERSONAL_PATH_RE = re.compile(r"/home/[A-Za-z0-9_][A-Za-z0-9_-]*/")

# Conservative secret detection. Values beginning with <, $, { or quoting a
# clearly symbolic word are placeholders, not secrets. Bare variable NAMES
# (ANTHROPIC_API_KEY) never match: an assignment with a long literal does.
SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b[A-Z0-9_]*(API_KEY|APIKEY|TOKEN|SECRET|PASSWORD|PASSWD)\b\s*[=:]\s*"
    r"['\"]?(?P<val>[A-Za-z0-9_\-./+]{16,})"
)
BEARER_RE = re.compile(r"\bBearer\s+(?P<val>[A-Za-z0-9_\-.]{20,})")
KEYLIKE_RE = re.compile(r"\b(?P<val>sk-[A-Za-z0-9]{20,})\b")
PLACEHOLDER_HINTS = ("example", "placeholder", "your", "changeme", "redacted", "xxxx")


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(h in lowered for h in PLACEHOLDER_HINTS)


def parse_headings(text: str):
    """Return [(level, title, line_no)] for headings outside fenced code blocks."""
    headings = []
    fence = None
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        m = re.match(r"^(```+|~~~+)", stripped)
        if m:
            marker = m.group(1)[0] * 3
            if fence is None:
                fence = marker
            elif stripped.startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue
        hm = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", raw)
        if hm:
            headings.append((len(hm.group(1)), hm.group(2).strip(), i))
    return headings


def validate(text: str) -> dict:
    errors = []
    warnings = []

    def err(code, message):
        errors.append({"code": code, "message": message})

    def warn(code, message):
        warnings.append({"code": code, "message": message})

    headings = parse_headings(text)
    h1 = [h for h in headings if h[0] == 1]
    h2 = [h for h in headings if h[0] == 2]

    # --- H1 ---
    if not h1:
        err("README_H1_MISSING", "No H1 project heading found.")
    elif len(h1) > 1:
        lines = ", ".join(str(h[2]) for h in h1)
        err("README_H1_MULTIPLE", f"Multiple H1 headings (lines {lines}); exactly one is required.")

    # --- Mandatory core H2 sections ---
    h2_titles = [t for _, t, _ in h2]
    for name in CORE_ORDER:
        if name not in h2_titles:
            err(f"README_{name.upper()}_MISSING", f"Mandatory section '## {name}' is missing.")

    for name in ADVISORY_H2:
        if name not in h2_titles:
            warn(f"README_{name.upper()}_MISSING", f"Recommended section '## {name}' is missing.")

    # --- Duplicate mandatory headings ---
    for name in MANDATORY_H2:
        occurrences = [ln for lvl, t, ln in h2 if t == name]
        if len(occurrences) > 1:
            lines = ", ".join(str(ln) for ln in occurrences)
            err("README_DUPLICATE_HEADING", f"Mandatory heading '## {name}' appears more than once (lines {lines}).")

    # --- Core ordering ---
    positions = [(name, h2_titles.index(name)) for name in CORE_ORDER if name in h2_titles]
    for (prev_name, prev_idx), (cur_name, cur_idx) in zip(positions, positions[1:]):
        if cur_idx < prev_idx:
            err(
                "README_SECTION_ORDER",
                f"'## {cur_name}' appears before '## {prev_name}'; required order is "
                + " -> ".join(CORE_ORDER) + ".",
            )

    # --- Installation subsections (H3s between '## Installation' and the next H2) ---
    found_subsections = set()
    if "Installation" in h2_titles:
        install_line = next(ln for lvl, t, ln in h2 if t == "Installation")
        following_h2 = [ln for lvl, t, ln in h2 if ln > install_line]
        end_line = min(following_h2) if following_h2 else float("inf")
        for lvl, title, ln in headings:
            if lvl == 3 and install_line < ln < end_line:
                found_subsections.add(title)
        codes = {
            "Install manually": "README_INSTALL_MANUAL_MISSING",
            "Install using an Agent": "README_AGENT_INSTALL_MISSING",
            "Verify installation": "README_INSTALL_VERIFY_MISSING",
        }
        for sub in INSTALL_SUBSECTIONS:
            if sub not in found_subsections:
                err(codes[sub], f"Installation is missing '### {sub}'.")

    # --- Legacy aliases (warn only when the canonical section is absent) ---
    for alias, canonical in ALIASES.items():
        if alias in h2_titles and canonical not in h2_titles:
            warn(
                "README_ALIAS_HEADING",
                f"'## {alias}' looks like a legacy alias; the canonical heading is '## {canonical}'.",
            )

    # --- Personal absolute paths ---
    path_hits = sorted(set(PERSONAL_PATH_RE.findall(text)))
    if path_hits:
        warn(
            "README_PERSONAL_PATH",
            "Personal absolute path(s) present: " + ", ".join(path_hits)
            + " — acceptable only when clearly marked as examples.",
        )

    # --- Secret-like material ---
    for regex in (SECRET_ASSIGN_RE, BEARER_RE, KEYLIKE_RE):
        for m in regex.finditer(text):
            value = m.group("val")
            if _is_placeholder(value):
                continue
            err(
                "README_SECRET_MATERIAL",
                f"Secret-like literal detected: '{value[:8]}…' — reference the variable name, never a value.",
            )

    sections = {}
    for key, (kind, title) in SECTION_KEYS.items():
        if kind == "h2":
            sections[key] = title in h2_titles
        else:
            sections[key] = title in found_subsections

    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "sections": sections,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate a README against the DPMtF README standard.")
    parser.add_argument("readme", help="Path to the README.md to validate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        with open(args.readme, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {args.readme}: {exc}", file=sys.stderr)
        return 2

    result = validate(text)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['status'].upper()}  {args.readme}")
        for e in result["errors"]:
            print(f"  ERROR    {e['code']}  {e['message']}")
        for w in result["warnings"]:
            print(f"  WARNING  {w['code']}  {w['message']}")
        print(
            f"  {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)"
        )

    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
