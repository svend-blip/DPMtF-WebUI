# Scope

## Purpose

This governance document defines what is included and excluded in the current phase or task. It acts as the boundary for the role-based prompt loop — all roles must operate within these limits unless scope is explicitly changed through the documented process.

## When to Use

- **Project initializer**: Fill in scope before starting a new phase.
- **Analyst step**: First file reviewed to understand boundaries.
- **Validator step**: Changes are checked against this document to detect scope violations.
- **After `/clear`**: Read to reconstruct what is and isn't allowed in the current session.

## Required Inputs

| Input | Description |
|-------|-------------|
| Phase key and title | E.g., `3A — Governance Foundation`. |
| Feature list | What features or tasks belong in this phase. |
| Exclusions | What is explicitly not part of this phase. |
| Constraints | Technical, operational, or process constraints. |
| Success criteria | Measurable conditions that define completion. |

## Required Outputs

- Completed scope document with filled-in sections.
- Measurable success criteria (at least one per in-scope item).
- Constraint list aligned with project governance rules.

## Default Constraints (DPMtF WebUI)

Unless explicitly overridden, the following constraints apply:

- No new dependencies unless explicitly approved by Human Approval Gate.
- No database schema changes unless the phase explicitly allows it.
- No frontend visual acceptance without human or screenshot review when visual change is involved.
- Prefer hiding over deleting (CSS class or conditional guard).
- One logical change per commit.
- Match existing code style — do not broad-refactor unrelated code.

## In Scope

- [Feature or task 1]
- [Feature or task 2]

## Out of Scope

- [Explicitly excluded item 1]
- [Explicitly excluded item 2]

## Constraints

- [Constraint 1, e.g., "No new npm dependencies."]
- [Constraint 2, e.g., "Must run offline."]

## Success Criteria

- [Criterion 1, measurable.]
- [Criterion 2, measurable.]

## Scope Change Process

If scope must change during a session:

1. Document the proposed change and reason in `DECISIONS.md`.
2. Obtain Human Approval Gate sign-off if the change adds work or removes constraints.
3. Update this document with the new scope boundary.
4. Log the change date and decision reference in the Scope Change Log below.

## Scope Change Log

| Date | Change | Reason | Decision Reference |
|------|--------|--------|-------------------|
| [YYYY-MM-DD] | [What changed] | [Why] | [Decision N] |

---
