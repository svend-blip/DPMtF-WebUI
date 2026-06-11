# Validation Report

## Purpose

This governance document records the results of the Validator role's checks for a specific phase or prompt-run. Every check is documented with method, result, and notes so that future sessions (after `/clear`) can verify what was tested and whether it passed. This report must be complete before Human Approval Gate is requested.

## When to Use

- **Validator step**: Complete this report after running all validation checks defined in `06_VALIDATION.md`.
- **Before Human Approval Gate**: Attach this report as evidence of validation completeness.
- **After `/clear`**: Read to understand what was validated and whether any issues remain.

## Required Inputs

| Input | Description |
|-------|-------------|
| Validation rules | Defined in `06_VALIDATION.md`. |
| Implementation report | From `12_IMPLEMENTATION_REPORT.md`. |
| Changed files | The diff produced by the Implementer (`git diff`). |

## Required Outputs

- Completed validation report with pass/fail for every check.
- Summary verdict: overall pass, fail with blockers, or conditional pass.
- Recommendations if something needs follow-up before commit.

---

## Phase

[Phase key and title, e.g., `3A — Governance Foundation`]

## Prompt-Run ID

[PRUN-XXXXXX, if applicable.]

## Validation Checklist

| Check | Method | Result | Notes |
|-------|--------|--------|-------|
| Backend syntax | `python3 -m py_compile app.py` | Pass / Fail | |
| Frontend syntax | `node --check static/js/*.js` | Pass / Fail | Only if JS was modified. |
| Shell script syntax | `bash -n <file>` | Pass / Fail | Only if shell was modified. |
| Page loads | Browser test — no console errors | Pass / Fail | |
| API health | `GET /api/health` | Pass / Fail | |
| Diff scope check | `git diff --stat` — within scope? | Pass / Fail | Reference `02_SCOPE.md`. |
| No new dependencies | Check requirements files in diff | Pass / Fail | |
| No schema changes | Check for ALTER/CREATE TABLE in diff | Pass / Fail | Unless phase allows it. |
| Visual change approved | Screenshot review by human | Pass / Fail / N/A | Required when visual appearance changes. |
| Migration hiding correct (if applicable) | Verify hidden panels use named class, are reversible, and cleanup is documented | Pass / Fail / N/A | N/A for new projects or clean implementation phases. |
| Scoped deletion verified (if applicable) | Verify removed code has no dangling references, validation passes, approval obtained | Pass / Fail / N/A | N/A if nothing was deleted in this phase. |
| No broad refactor | Review diff for unrelated rewrites | Pass / Fail | |

## Scope Compliance

| Check | Result |
|-------|--------|
| All changes within `02_SCOPE.md` boundaries? | Yes / No — [details if No.] |
| Coding standard followed (per `05_CODING_STANDARD.md`)? | Yes / No — [details if No.] |
| File access policy respected (per `03_FILE_ACCESS_POLICY.md`)? | Yes / No — [details if No.] |

## Summary

[Overall assessment: all passed, issues found and severity, or fail with blockers. Be specific about what blocks sign-off if applicable.]

## Recommendations

- [Action item 1 if something needs follow-up before commit.]
- [Action item 2 if a known issue should be tracked for later.]

## Verdict

| Verdict | Meaning |
|---------|---------|
| **PASS** | All checks passed. Ready for Human Approval Gate or Release Operator. |
| **PASS WITH NOTES** | Non-blocking issues found; document but do not block commit. |
| **FAIL — REQUIRES FIX** | Blocking issues found. Return changes to Implementer with specific findings. |

**Verdict:** [PASS / PASS WITH NOTES / FAIL]

---
