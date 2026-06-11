# Validation

## Purpose

This governance document defines the validation rules that the Validator role must enforce on every set of changes before they reach Human Approval Gate or Release Operator. These rules prevent scope violations, ensure code quality, and protect the project from uncontrolled modifications.

## When to Use

- **Validator step**: Primary reference for all validation checks.
- **Before commit**: Every change set must pass these checks.
- **After `/clear`**: Second-pass review uses this document as the checklist.

## Required Inputs

| Input | Description |
|-------|-------------|
| Changed files | The diff produced by the Implementer (`git diff`). |
| Phase scope | Defined in `02_SCOPE.md`. |
| Coding standard | Defined in `05_CODING_STANDARD.md`. |

## Required Outputs

- Validation report (see template: `13_VALIDATION_REPORT.md`).
- Pass/fail verdict for each check.
- If any check fails: specific findings with file paths and line numbers.

---

## Pre-Commit Checks (Mandatory)

Every change set must pass all of the following before being considered valid:

| # | Check | Command / Method | Pass Criteria |
|---|-------|-----------------|---------------|
| 1 | Backend syntax check | `python3 -m py_compile app.py` | Exit code 0, no errors. |
| 2 | Frontend syntax check (if JS changed) | `node --check static/js/*.js` | Exit code 0 for each modified file. |
| 3 | Shell script syntax (if shell changed) | `bash -n <file>` | Exit code 0. |
| 4 | Diff scope review | `git diff --stat` | Changes are within phase scope. No broad refactor. |
| 5 | Dependency check | `git diff requirements.txt` (or equivalent) | No new dependencies added unless explicitly approved. |
| 6 | Schema change check | Review diff for `ALTER TABLE`, `CREATE TABLE`, or migration scripts | No schema changes unless the phase explicitly allows them. |
| 7 | Frontend innerHTML check | `grep -RIn "innerHTML" static templates --exclude-dir=__pycache__ || echo "no_innerHTML"` | Result must be `no_innerHTML` or an approved exception. If `innerHTML` is found, Claude must either remove it or report an approved exception with security justification. |

## Functional Validation

- Each modified endpoint returns the expected response shape (status code, body structure).
- UI panels render without layout breakage in the browser.
- Database queries return correct data for the affected feature area.
- If panels are temporarily hidden during migration, they remain accessible via backend API even if invisible in the frontend. For new projects or explicitly scoped deletion, verify removed functionality is replaced or no longer needed.

## Regression Checks

- Previously completed phases still function after the changes.
- No new console errors appear in the browser.
- If panels are temporarily hidden during migration, the hidden CSS class must be reversible. For explicitly scoped deletion, verify no remaining references exist and the application functions without the removed code.
- Backend health endpoint (`/api/health`) returns `{"status": "healthy"}` or equivalent.

## Prohibited Changes (Auto-Fail)

A change set automatically fails validation if it contains any of the following:

1. **Broad refactor** — rewriting files outside the defined scope to improve style, reorganize code, or apply modern patterns. Only targeted edits within scope are allowed.
2. **New dependencies** — adding packages, libraries, or runtime requirements without Human Approval Gate approval.
3. **Database schema changes** — `ALTER TABLE`, new tables, column removals unless the current phase explicitly authorizes them.
4. **Unapproved frontend visual changes** — if a change affects visual appearance and no screenshot review has been performed by a human.
5. **Unscoped deletion of functionality** — deleting user-visible features without explicit phase scope authorization, reference verification, validation pass, Human Approval Gate approval, and CHANGELOG documentation is prohibited. For migration work in existing projects, temporary hiding is allowed if cleanup is documented; for new projects, implement cleanly without obsolete code.
6. **Hardcoded operational targets** — ports, paths, model names must come from explicit arguments or configuration, not be guessed.
7. **Direct frontend binding to reusable labels** — when the UI Text Slot layer is in use, frontend code must reference stable text slot IDs/keys, not `ui_labels` directly. The four-layer architecture (slots → bindings → labels → translations) must be respected. See [[04_ARCHITECTURE]] for details.

## Visual Change Rules

When a change affects the visual appearance of the frontend:

1. Implementer takes a full-page screenshot of the affected area after changes.
2. Screenshot is saved as `screenshot-v<N>.png` in the project root or `docs/prompt-runs/<run-id>/`.
3. Human Approval Gate reviews the screenshot and approves or rejects the visual result.
4. No visual change is committed without screenshot + human approval.

## Sign-Off Criteria

All pre-commit checks pass AND at least one manual verification of the affected feature area is completed. If any check fails, the Validator must document the failure in the validation report and return changes to the Implementer.

---
