# 29 — VALIDATION REPORT

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Template for recording validation results and verdict (pass/fail). Completed
by the Review role after every validation pass.

## When to Use

- **Review:** Fill in after validating implementation results.
- **Human:** Read before approving commit.
- **After `/clear`:** Reference to understand last validation outcome.

---

## Report Template

### Session Information

| Field | Value |
|-------|-------|
| **Date** | {YYYY-MM-DD} |
| **Phase** | {PHASE_KEY} — {PHASE_TITLE} |
| **Handoff ID** | {ID} |
| **Reviewer** | claude_review |

### Pre-Commit Checks

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Backend syntax (`py_compile`) | {✅ Pass / ❌ Fail} | {Errors if any} |
| 2 | Frontend syntax (`node --check`) | {✅ Pass / ❌ Fail} | {Errors if any} |
| 3 | Shell syntax (`bash -n`) | {✅ Pass / ❌ Fail} | {Errors if any} |
| 4 | Diff scope review | {✅ Pass / ❌ Fail} | {Scope violations if any} |
| 5 | Dependency check | {✅ Pass / ❌ Fail} | {New deps if any} |
| 6 | Schema change check | {✅ Pass / ❌ Fail} | {Schema changes if any} |
| 7 | innerHTML check | {✅ Pass / ❌ Fail} | {Violations if any} |
| 8 | i18n check | {✅ Pass / ❌ Fail} | {Hardcoded strings if any} |

### Functional Validation

| Check | Result | Details |
|-------|--------|---------|
| Health endpoint | {✅ / ❌} | {Response} |
| UI rendering | {✅ / ❌} | {Issues if any} |
| Data correctness | {✅ / ❌} | {Issues if any} |

### Regression Checks

| Check | Result |
|-------|--------|
| Previous phases functional | {✅ / ❌} |
| No new console errors | {✅ / ❌} |
| Panel groups correct | {✅ / ❌} |

### Overall Verdict

| Verdict | {✅ PASS / ❌ FAIL} |
|---------|---------------------|
| **Action** | {Proceed to Human approval / Return to Implementor} |

### Findings

{List specific findings with file paths and line numbers if any checks failed.}

### Notes

{Observations, recommendations, or context for Human review.}

---
