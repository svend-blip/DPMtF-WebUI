# 13 — VALIDATION

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the validation rules that the Review role MUST enforce on every
implementation result before it reaches the Human Approval Gate. These rules
prevent scope violations, ensure code quality, and protect the project from
uncontrolled modifications.

## When to Use

- **Review:** Primary reference for every validation pass.
- **Implementor:** Run self-validation checks before signaling completion.
- **Architect:** Understand what Review will check when designing prompts.

---

## Pre-Commit Checks (Mandatory)

Every change set MUST pass ALL of the following before being considered valid:

| # | Check | Command / Method | Pass Criteria |
|---|---|-------|----------------|---------------|
| 1 | Backend syntax | `python3 -m py_compile app.py` | Exit code 0, no errors. |
| 2 | Frontend syntax | `node --check static/js/*.js` | Exit code 0 for each modified file. |
| 3 | Shell syntax | `bash -n <file>` | Exit code 0. |
| 4 | Diff scope review | `git diff --stat` | Changes within phase scope. No broad refactor. |
| 5 | Dependency check | `git diff requirements.txt` | No new dependencies unless explicitly approved. |
| 6 | Schema change check | Review diff for `ALTER TABLE`, `CREATE TABLE` | No schema changes unless phase explicitly allows them. |
| 7 | innerHTML check | `grep -RIn "innerHTML" static templates --exclude-dir=__pycache__ \|\| echo "no_innerHTML"` | Result MUST be `no_innerHTML` or an approved exception with security justification. |
| 8 | i18n check | `grep -RIn '"[A-Z][a-z]' static/js/` | Only `lbl()` fallbacks and CSS classes. No bare user-visible English strings. |
| 9 | Frontend Impact | Verify Frontend Impact section present per [[30_FRONTEND_GOVERNANCE]] | Missing = fail. Panel registration, subgroup mapping, i18n labels verified. |

## Functional Validation

- Each modified endpoint returns the expected response shape (status code, body structure).
- UI panels render without layout breakage.
- Database queries return correct data for the affected feature area.
- Hidden elements (via `dpmtf-hidden` class) remain accessible via backend API.

## Regression Checks

- Previously completed phases still function after changes.
- No new console errors in the browser.
- Backend health endpoint (`/api/health`) returns `{"status": "healthy"}`.
- Panel groups collapse/expand correctly after changes.

## Prohibited Changes (Auto-Fail)

A change set automatically fails validation if it contains:

1. **Broad refactor** — rewriting files outside scope to improve style or reorganize.
2. **New dependencies** — adding packages without Human approval.
3. **Database schema changes** — `ALTER TABLE`, new tables without phase authorization.
4. **Unapproved visual changes** — visual changes without screenshot + Human approval.
5. **Unscoped deletion** — deleting user-visible features without phase authorization.
6. **Hardcoded operational targets** — ports, paths, model names not from configuration.
7. **Direct frontend binding to ui_labels** — MUST use `data-slot` + 4-layer traversal.
8. **Hardcoded English frontend text** — MUST use `lbl()`.

## Visual Change Rules

When a change affects visual appearance:

1. Implementor takes a full-page screenshot of the affected area.
2. Screenshot saved as `screenshot-v<N>.png` in the project root.
3. Human reviews screenshot and approves or rejects.
4. No visual change is committed without screenshot + Human approval.

## Sign-Off Criteria

- ALL pre-commit checks pass.
- At least one manual verification of the affected feature area completed.
- If any check fails: document in [[29_VALIDATION_REPORT]], return to Implementor.

---
