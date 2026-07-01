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

**GOVERNANCE_FRONTEND — Frontend Governance + Machine Profile afsluttet**

## In Scope Now

- `30_FRONTEND_GOVERNANCE.md` — fælles frontend-governance
- Frontend Impact som obligatorisk output-afsnit i designs og implementeringer
- Review/verdict fejler ved manglende Frontend Impact
- Opdatering af eksisterende governance templates med Frontend Impact referencer
- Machine Profile: legacy-kode fjernet, døde frontend-felter fjernet

## Out of Scope Now

- MCP server til frontend-kontekst (fremtidig fase)
- Nye panel groups (kun eksisterende: Daily, Journals, Reports, Periodic, Setup)

## Key Principle

Frontend Impact må aldrig udelades. Alle UI-ændringer skal følge panel-registreringsreglerne i `30_FRONTEND_GOVERNANCE.md`. "No frontend impact" skal begrundes.

## Constraints

- Do NOT introduce new dependencies without Human Approval Gate.
- Do NOT commit until explicitly instructed by Human.
- All frontend text MUST use `lbl(key, fallback)` — no hardcoded English strings.
- No `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`.
- Python: `py_compile` before signaling completion, PEP 8, parameterized SQL queries.
- Shell: `bash -n` before signaling completion, `set -euo pipefail`.
- New panels MUST be registered in `panel_subgroups` + `panel_subgroup_mappings`.

## Success Criteria

- `30_FRONTEND_GOVERNANCE.md` oprettet og committet
- Alle relevante governance templates opdateret med Frontend Impact referencer
- Review/verdict fejler ved manglende Frontend Impact

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
