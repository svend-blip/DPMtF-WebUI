# 11 — SCOPE

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines what is included and excluded in the current phase or task. Acts as
the boundary for the entire role loop — all roles MUST operate within these
limits unless scope is explicitly changed through the documented process.

## When to Use

- **Human:** Define and approve scope at phase start.
- **Architect:** Analyze requirements against scope boundaries.
- **Review:** Check all changes against scope — detect scope creep.
- **After `/clear`:** Reconstruct what is and is not allowed.

---

## Phase

**{PHASE_KEY} — {PHASE_TITLE}**

## In Scope Now

- {Bullet list of what is included in this phase.}
- {Be specific — reference files, components, features.}

## Out of Scope Now

- {Bullet list of what is explicitly excluded.}
- {Changes to other projects.}
- {New external dependencies without Human approval.}
- {Database schema changes without prior approval.}
- {Changes to {specific files or components}.}

## Key Principle

{1-2 sentences describing the guiding principle for this phase.}

## Constraints

- Do NOT modify {other projects}.
- Do NOT introduce new dependencies without Human Approval Gate.
- Do NOT modify database schema without prior approval.
- Do NOT commit until explicitly instructed by Human.
- All frontend text MUST use `lbl(key, fallback)` — no hardcoded English strings.
- No `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`.
- Python: `py_compile` before signaling completion, PEP 8, parameterized SQL queries.
- Shell: `bash -n` before signaling completion, `set -euo pipefail`.

## Success Criteria

- {Measurable, verifiable criteria for phase completion.}
- {Each criterion should be testable by Review.}

## Scope Change Process

If scope must change during a session:

1. Document the proposed change and reason in [[25_DECISIONS]].
2. Architect or Review escalates to Human via GATE-SCOPE (see [[20_GATES]]).
3. Human approves and updates this document with the new scope boundary.
4. Log the change date and decision reference below.

## Scope Change Log

| Date | Change | Reason | Decision Reference |
|------|--------|--------|-------------------|
| {DATE} | Initial scope for {PHASE} | Phase initiation | — |

---
