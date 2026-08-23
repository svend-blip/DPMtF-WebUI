"""Governance templates must not instruct a role using one machine's paths.

A role reads its governance file FROM DISK, so nothing interpolates a
placeholder written inside it — see `build_target_project_block` in
scripts/bridgeV002/dispatch.py. A literal `/home/svend/...` in these files
therefore reaches the role as an instruction to work in a directory that does
not exist on any other machine.

Some occurrences are the point, though. The coding standard teaches the rule
by naming the thing it forbids; reviewers run `grep '"/home/svend'` as the
check; 200_HARDENING_V2.md archives a prompt written on 2026-06-15 and
editing it would falsify the record. Those are enumerated below, exactly, so
that adding a real hardcoded path fails even in a file that already contains
an allowed one.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE = ROOT / "docs" / "governance-templates-v2"
# Cold-start procedures instruct a session the same way governance instructs a
# role, so they are held to the same rule.
SKILLS = ROOT / ".claude" / "skills"

NEEDLE = "/home/svend"

# The rule cannot be stated without naming what it forbids. Any line that
# spells the placeholder form, or runs the reviewer's grep, is teaching.
RULE_MARKERS = ("/home/svend/...", "/home/svend or user-specific")
GREP_MARKERS = ("grep -n", "grep -rn", "grep -RIn")

# Everything else that may legitimately name a real path, matched on the
# exact stripped line so a new path in the same file still fails.
ALLOWED_LINES = {
    # An archived prompt. The words are a historical record, not instructions.
    "200_HARDENING_V2.md": {
        "/home/svend/DPMtF-WebUI/docs/governance-templates",
        "/home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates",
        "/home/svend/DPMtF-WebUI/docs/governance-templates-v2",
    },
    # The migration guide's before/after table — the whole lesson is that the
    # left column becomes the right one on your machine.
    "300_SETUPINSTRUCTION.md": {
        "| `project_root` | `/home/svend/DPMtF-WebUI` | `/home/alice/DPMtF-WebUI` |",
        "| `DPMTF_BRIDGE_DIR` | `/home/svend/flows` | `/home/alice/flows` |",
        "# Must print your actual paths, not /home/svend/...",
    },
    # A getter table showing the shape of each return value, plus the
    # auto-fail example the correct one is contrasted against.
    "16_FILE_ACCESS.md": {
        "| Project root | `config.get_project_root()` | `/home/svend/DPMtF-WebUI` |",
        "| Bridge directory | `config.get_bridge_dir()` | `/home/svend/flows` (configured via `DPMTF_BRIDGE_DIR`) |",
        "| Governance docs | `config.get_governance_dir_abs()` | `/home/svend/DPMtF-WebUI/docs/governance-templates-v2` |",
        "<project>/home/svend/DPMtF-WebUI</project>",
        "- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md",
    },
    # The WRONG example under "Example (WRONG — auto-fail)".
    "12_CODING_STANDARD.md": {
        'handoff_path = f"/home/svend/flows/strict_review/handoffs/{hid}-handoff.md"',
    },
    # What handoff 006 actually said. The 461_LLAMA_SG_SUPERVISOR.md
    # file is RETIRED by Run 017 D3 (git rm); the entry is removed from
    # ALLOWED_LINES so test_allowlist_has_no_stale_entries stays clean.
    # The worked example of a testgoals block, showing run 008's real
    # criterion. That run's TG2 existed precisely to stop a blanket
    # search-and-replace from destroying .env.example's "# Example:" lines,
    # and the criterion cannot be written without naming the string it counts.
    "LLAMASG/SKILL.md": {
        "run: grep -c '^# Example: /home/svend' .env.example",
    },
}


def _is_allowed(rel_name, line):
    stripped = line.strip()
    if any(m in line for m in RULE_MARKERS):
        return True
    if any(m in line for m in GREP_MARKERS) and NEEDLE in line:
        return True
    return stripped in ALLOWED_LINES.get(rel_name, ())


class GovernancePaths(unittest.TestCase):

    def test_no_unjustified_absolute_home_paths(self):
        offenders = []
        for base in (GOVERNANCE, SKILLS):
            for path in sorted(base.rglob("*.md")):
                rel = str(path.relative_to(base))
                for n, line in enumerate(
                        path.read_text(encoding="utf-8").splitlines(), 1):
                    if NEEDLE in line and not _is_allowed(rel, line):
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{n}: {line.strip()}")

        self.assertEqual(offenders, [], "\n\nGovernance files name a specific "
                         "machine's paths. Use a config getter, "
                         "$DPMTF_BRIDGE_DIR, or prose naming the checkout — or "
                         "add the line to ALLOWED_LINES with a reason:\n\n"
                         + "\n".join(offenders) + "\n")

    def test_allowlist_has_no_stale_entries(self):
        """A justified line that gets edited should force re-justification."""
        stale = []
        for rel_name, lines in ALLOWED_LINES.items():
            # Entries are keyed relative to whichever root holds the file, so
            # a skill entry and a governance entry look the same here.
            for base in (GOVERNANCE, SKILLS):
                path = base / rel_name
                if path.exists():
                    break
            if not path.exists():
                stale.append(f"{rel_name} (file is gone)")
                continue
            present = {ln.strip()
                       for ln in path.read_text(encoding="utf-8").splitlines()}
            for line in lines:
                if line not in present:
                    stale.append(f"{rel_name}: {line}")

        self.assertEqual(stale, [], "\n\nALLOWED_LINES entries no longer match "
                         "the file. If the line was fixed, drop the entry:\n\n"
                         + "\n".join(stale) + "\n")


if __name__ == "__main__":
    unittest.main()
