# Decision Log

## Purpose

This governance document records all significant decisions made during the project. It is append-only — never edit existing entries. Every decision captures context, alternatives considered, rationale, and consequences so that future sessions (especially after `/clear`) understand why something was done, not just what was done.

## When to Use

- **Any role**: Record a decision when a non-obvious choice is made that affects the project's direction, architecture, or governance.
- **After `/clear`**: Read to reconstruct past decisions without asking "why did we do it this way?".
- **Human Approval Gate**: Reference before approving scope changes or architectural deviations.

## Required Inputs

| Input | Description |
|-------|-------------|
| Decision context | What situation or problem led to this decision. |
| Options considered | The alternatives evaluated. |
| Chosen option | What was selected and why. |

## Required Outputs

- New entry appended at the bottom of this file.
- Entry follows the format defined below.
- If the decision changes scope, `02_SCOPE.md` is updated accordingly.

---

## Format

Each decision follows this structure:

```markdown
### Decision [number]: [Short title]
**Date:** YYYY-MM-DD
**Role:** [Analyst / Solution Architect / Prompt Engineer / Implementer / Validator / Human Approval Gate]
**Context:** [What situation led to this decision?]
**Options Considered:** [List of options, brief description of each.]
**Decision:** [What was chosen and why. Include trade-offs acknowledged.]
**Consequences:** [Impact on timeline, scope, architecture, or future work.]
```

## Rules

1. **Append only** — never edit, renumber, or delete existing decisions.
2. Number sequentially: Decision 1, Decision 2, etc.
3. Include the role that made the decision.
4. If a decision is later reversed, add a new decision explaining the reversal (do not edit the original).
5. Reference related governance documents in the context or consequences fields using `[[filename]]` notation.

## Decisions

### Decision 1: Hide-over-delete is a temporary migration tactic only

**Date:** 2026-06-11
**Role:** Human Approval Gate
**Context:** During the DPMtF WebUI transition, old frontend panels were temporarily hidden (CSS class) rather than deleted to preserve code while new features were built quickly. This was documented in the governance templates as a general rule ("hide over delete") which risked becoming a default policy for all future projects including AI PC Resource WebUI v3.
**Options Considered:**
1. Keep "hide over delete" as a general forward-looking policy — simple but leads to accumulated technical debt in new projects.
2. Limit hiding to migration work only; allow explicit scoped deletion; require clean implementation for new projects.
3. Remove hiding entirely — too strict; prevents pragmatic migration transitions in existing projects.
**Decision:** Option 2. Temporary hiding is allowed for existing-project migration when cleanup is explicitly postponed and documented with a planned removal phase. Deletion is valid when scope authorizes it, references are checked, validation passes, and Human Approval Gate approves. New projects must implement cleanly — no irrelevant hidden panels or code by default.
**Consequences:** Governance templates in [[05_CODING_STANDARD]], [[06_VALIDATION]], [[10_CHANGELOG]], and [[15_GIT_POLICY]] were corrected to reflect this policy. AI PC Resource WebUI v3 will not inherit the temporary hiding approach from DPMtF's migration.

---

---
