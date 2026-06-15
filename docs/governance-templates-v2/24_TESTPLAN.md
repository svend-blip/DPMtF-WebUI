# 24 — TESTPLAN

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines test cases, manual verification steps, and pass/fail criteria for the
current phase. Used by Review during validation and by Implementor for
self-testing.

## When to Use

- **Architect:** Include test criteria in implementation prompts.
- **Implementor:** Run self-tests before signaling completion.
- **Review:** Execute all test cases during validation.

---

## Test Cases

{Define test cases for the current phase. Each test case should have:}

### Test Case {N}: {Name}

| Field | Value |
|-------|-------|
| **ID** | TC-{PHASE}-{NNN} |
| **Description** | {What is being tested} |
| **Preconditions** | {What must be true before the test} |
| **Steps** | {Step-by-step instructions} |
| **Expected Result** | {What should happen} |
| **Actual Result** | {Filled in by Review} |
| **Pass/Fail** | {Filled in by Review} |

---

## Automated Checks

These checks run automatically during validation (see [[13_VALIDATION]]):

| # | Check | Command |
|---|-------|---------|
| 1 | Backend syntax | `python3 -m py_compile app.py` |
| 2 | Frontend syntax | `node --check static/js/*.js` |
| 3 | Shell syntax | `bash -n <file>` |
| 4 | Diff scope | `git diff --stat` |
| 5 | Dependencies | `git diff requirements.txt` |
| 6 | Schema changes | Review diff for DDL |
| 7 | innerHTML | `grep -RIn "innerHTML" static templates` |
| 8 | i18n | `grep -RIn '"[A-Z][a-z]' static/js/` |

## Manual Verification

{List manual verification steps specific to the current phase:}

1. **Health endpoint:** `curl http://localhost:{PORT}/api/health` → `{"status": "healthy"}`
2. **UI rendering:** Open browser, navigate to `http://localhost:{PORT}`, verify {specific panels/pages}.
3. **{Additional manual checks}**

## Regression Checks

- All previously completed phases still function.
- No new console errors in the browser.
- Panel groups collapse/expand correctly.
- Language dropdown switches all UI text correctly.

## Sign-Off

| Criterion | Required | Verified By |
|-----------|----------|-------------|
| All automated checks pass | Yes | Review |
| All test cases pass | Yes | Review |
| Manual verification complete | Yes | Review |
| Screenshot captured (if visual change) | Conditional | Implementor |
| Human approval (if visual change) | Conditional | Human |

---
