# Next Context / Handoff

## Purpose

This governance document is the primary handoff artifact between sessions. The Handoff Writer role updates it before every `/clear`. After `/clear`, the new session reads this file first to reconstruct project state, current phase progress, and what needs to happen next. This file, combined with the governance documents in `docs/governance-templates/`, is the authoritative source of context — not chat memory.

## When to Use

- **Handoff Writer step**: Always update before `/clear`.
- **After `/clear`**: Read immediately to reconstruct state.
- **Between role transitions**: Update to record the transition and next role.

## Required Inputs

| Input | Description |
|-------|-------------|
| Current phase and progress | From `00_PROJECT.md` and implementation reports. |
| Completed work in this session | What was done, what was changed. |
| Remaining work | What still needs to be done. |
| Open questions | Unresolved items that need attention. |
| File change list | What files were modified and why. |

## Required Outputs

- Updated `NEXT_CONTEXT.md` with current state.
- Clear indication of the next role or action required.
- List of changed files with descriptions.

---

## `/clear` Reconstruction Rules

1. **Use `/clear` between role transitions.** After `/clear`, chat memory is unavailable.
2. **Governance documents are the source of truth.** Do not rely on chat history as the only record of decisions or state.
3. **Reconstruction order after `/clear`:**
 - Read `NEXT_CONTEXT.md` (this file) — identify current role and remaining work.
 - Read `00_PROJECT.md` — confirm project identity.
 - Read `01_ROLES.md` — understand the role flow and position.
 - Read `02_SCOPE.md` — confirm phase boundaries.
 - Read previous role's output (analysis, design, prompts, or implementation report).
4. **If information is missing from governance documents, ask for clarification.** Do not assume.

## Current State

[Where are we in the project? What phase is active? Which role is next?]

## Completed in This Session

- [Item 1 — what was done and which files were affected.]
- [Item 2 — what was done and which files were affected.]

## Remaining Work

- [Item 1 — what still needs to be done, assigned to which role.]
- [Item 2 — what still needs to be done, assigned to which role.]

## Important Notes for Next Session

- [Context note 1, e.g., "Phase 3A is in progress."]
- [Context note 2, e.g., "Hidden panels are marked with CSS class `dpmtf-hidden-phase-3A`."]

## Open Questions

- [Question 1 — what needs clarification or a decision.]

## Files Changed

| File | What Changed |
|------|-------------|
| [File 1] | [Description of change.] |
| [File 2] | [Description of change.] |

---
