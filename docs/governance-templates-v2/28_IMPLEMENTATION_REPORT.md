# 28 — IMPLEMENTATION REPORT

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Template for documenting what was implemented in a session. Completed by the
Implementor as part of the result file, and summarized by the Review role
in this document for the project record.

## When to Use

- **Implementor:** Fill in as part of `implementertoreview/{ID}-result.md`.
- **Review:** Consolidate into this file after validation passes.
- **After `/clear`:** Reference to understand what was last implemented.

---

## Report Template

### Session Information

| Field | Value |
|-------|-------|
| **Date** | {YYYY-MM-DD} |
| **Phase** | {PHASE_KEY} — {PHASE_TITLE} |
| **Handoff ID** | {ID} |
| **Implementor** | claude_implementer |
| **Reviewer** | claude_review |

### Git Baseline

| Check | Value |
|-------|-------|
| **Baseline commit (before)** | {hash} |
| **Branch** | {branch} |

### Changes Made

| File | Change Type | Description |
|------|-------------|-------------|
| {path} | {added | modified | deleted} | {What and why} |

### Validation Results

| # | Check | Result |
|---|-------|--------|
| 1 | Backend syntax | {pass/fail} |
| 2 | Frontend syntax | {pass/fail} |
| 3 | Shell syntax | {pass/fail} |
| 4 | Diff scope review | {pass/fail} |
| 5 | Dependency check | {pass/fail} |
| 6 | Schema change check | {pass/fail} |
| 7 | innerHTML check | {pass/fail} |
| 8 | i18n check | {pass/fail} |

### Human Approval

| Field | Value |
|-------|-------|
| **Visual changes?** | {yes/no} |
| **Screenshot?** | {yes/no} |
| **Human approved?** | {yes/no — date} |
| **Committed?** | {yes/no — commit hash} |
| **Pushed?** | {yes/no} |

### Notes

{Observations, challenges, recommendations for future work.}

---
