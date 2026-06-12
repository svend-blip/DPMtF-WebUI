# Changelog

## Purpose

This governance document records all notable changes to the target project in chronological order. It is append-only — never edit existing entries. The changelog provides a human-readable history of what changed, when, and in what direction.

## When to Use

- **Release Operator**: Append an entry after committing verified changes.
- **After `/clear`**: Read to understand recent project evolution.
- **Any role**: Reference to check if something was already changed in a previous phase.

## Required Inputs

| Input | Description |
|-------|-------------|
| Change description | What was changed, added, fixed, removed, or temporarily hidden. |
| Date | When the change was committed (YYYY-MM-DD). |
| Phase key | E.g., `3A`, `2D-D`. |

## Required Outputs

- New entry appended at the bottom of this file.
- Entry follows the format defined below.

---

## Format

```markdown
### [YYYY-MM-DD] — [Phase key]: [Brief description]
- Changed: [What was modified and why.]
- Added: [What was introduced.]
- Fixed: [What was repaired.]
- Removed: [What was deleted with scope authorization and approval.]
- Hidden (temporary): [What was hidden for migration purposes only — cleanup phase noted.]
```

## Rules

1. **Append only** — never edit or delete existing entries.
2. Use the "Removed" category for code, panels, or features that were explicitly deleted per phase scope with Human Approval Gate approval and validation.
3. Use the "Hidden (temporary)" category only for migration work in existing projects where cleanup is documented and a planned removal phase is specified. New projects should not use this category — implement cleanly.
4. Include the phase key in each entry header to trace changes back to phases.
5. Keep descriptions brief but specific enough that a future session understands what changed without reading git diff.
6. Do not log trivial formatting fixes or whitespace-only changes.

## Entries

### [2026-06-12] — 2E: Governance-template opgradering fra v3-læringer
- Opgraderet: 10 governance-templates fra ai-pc-resource-webui-v3's forbedrede versioner (00_PROJECT, 02_SCOPE, 04_ARCHITECTURE, 05_CODING_STANDARD, 07_RESTART, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, 15_GIT_POLICY, 16_DATABASE_RUNTIME_STATE).
- Tilføjet: 06_VALIDATION.md og 17_PERMISSION_MODE_POLICY.md var allerede identiske — ingen ændring nødvendig.
- Opdateret: `scripts/init_db.py` — fase-tracking restruktureret efter projektrapportens 6-blok roadmap. 2D markeret completed. 2E (Governance-template opgradering) tilføjet som completed. Nye faser 2F-2O for prompt-infrastruktur, automatisering, og lokal model integration.
- Ændret: 01_ROLES, 03_FILE_ACCESS_POLICY, 08_TESTPLAN, 09_DECISIONS, 13_VALIDATION_REPORT, 14_OFFLINE_MODE forblev uændrede (identiske mellem master og v3).
- Skrevet: `docs/project-report.md` — tværgående analyse af DPMtF-WebUI, ai-pc-resource-webui-v2, og ai-pc-resource-webui-v3 med anbefalinger til governance, automatisering, og transition til lokal model.

---
