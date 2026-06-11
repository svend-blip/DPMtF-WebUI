# Implementation Report

## Purpose

This governance document captures what was implemented in a specific prompt-run session: which items were completed, which files were changed, what deviated from the plan, and what verification results were obtained. It serves as the permanent record for this session's work and is referenced by the Validator role and future sessions after `/clear`.

## When to Use

- **Implementer step**: Complete this report at the end of an implementation session.
- **Before handing off to Validator**: Attach this report so the Validator knows what was changed and where.
- **After `/clear`**: Read to reconstruct what was done in a previous session without chat history.

## Required Inputs

| Input | Description |
|-------|-------------|
| Phase key and title | From `00_PROJECT.md`. |
| Implementation plan | From Prompt Engineer's generated prompts. |
| Changed files | The actual files modified during this session. |
| Verification results | Syntax check outputs, health endpoint status, visual tests. |

## Required Outputs

- Completed implementation report with filled-in sections.
- Status for each planned item (Done / In Progress / Blocked).
- Known issues documented.
- Next steps identified for the following session or role.

---

## Phase

[Phase key and title, e.g., `3A — Governance Foundation`]

## Prompt-Run ID

[PRUN-XXXXXX, if applicable. Reference the prompt-run from `docs/prompt-runs/`.]

## What Was Implemented

| Item | File(s) | Status | Notes |
|------|---------|--------|-------|
| [Item 1] | [file path] | Done / In Progress / Blocked | [Context if relevant.] |
| [Item 2] | [file path] | Done / In Progress / Blocked | [Context if relevant.] |

## Deviations from Plan

- [Any deviation from the original plan, with reason and Human Approval Gate reference if applicable.]

## Verification Results

| Check | Method | Result | Notes |
|-------|--------|--------|-------|
| Syntax check (Python) | `python3 -m py_compile app.py` | Pass / Fail | |
| Syntax check (JavaScript) | `node --check static/js/*.js` | Pass / Fail | Only if JS was modified. |
| Shell script syntax | `bash -n <file>` | Pass / Fail | Only if shell scripts were modified. |
| Page loads without errors | Browser test | Pass / Fail | Console checked for errors. |
| Backend health endpoint | `curl http://localhost:9130/api/health` | Pass / Fail | |

## Known Issues

- [Issue 1 — description, severity, and impact. If any.]

## Next Steps

- [Next action item 1, assigned to which role.]
- [Next action item 2, assigned to which role.]

---
