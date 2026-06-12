# Scope

## Purpose

This governance document defines what is included and excluded in the current phase or task. It acts as the boundary for the role-based prompt loop — all roles must operate within these limits unless scope is explicitly changed through the documented process.

## When to Use

- **Project initializer**: Fill in scope before starting a new phase.
- **Analyst step**: First file reviewed to understand boundaries.
- **Validator step**: Changes are checked against this document to detect scope violations.
- **After `/clear`**: Read to reconstruct what is and isn't allowed in the current session.

---

## Phase

**3C-3 — Initialize governance docs into AI PC Resource WebUI v3**

## In Scope Now

- Governance initialization (copying DPMtF templates via the initializer script).
- Customizing governance Markdown files under `docs/dpmtf/` for v3-specific content.
- Future database-driven architecture planning (documented only, not implemented).
- Documentation-only work. No code implementation in this phase.

## Out of Scope Now

- Database schema creation and seed scripts.
- System Resources panel implementation.
- Authentication implementation.
- i18n implementation.
- Endpoint registry implementation.
- Copying v2 code into v3.
- Service actions implementation.
- WebUI restart or runtime testing.
- Any modification to `app.py`, `config.py`, frontend files, or scripts/actions in v3.

## Key Principle

**v3 starts clean.** AI PC Resource WebUI v3 builds the intended structure from scratch. v2 is a functional/design reference only — code from v2 is not copied into v3. Reuse v2 as inspiration for the end-state architecture, not as source material to migrate.

## Constraints

- Do NOT modify `app.py` in v3.
- Do NOT modify `config.py` in v3.
- Do NOT modify frontend files in v3 (`templates/`, `static/`).
- Do NOT modify scripts/actions in v3.
- Do NOT create database schema or modify database files.
- Do NOT modify DPMtF source files.
- Do NOT modify v2.
- Do NOT restart any WebUI or run uvicorn.
- Do NOT commit until explicitly instructed.
- Only Markdown files under `docs/dpmtf/` may be created or modified.

## Success Criteria

- All 18 DPMtF governance templates copied to `docs/dpmtf/`.
- v3-specific customization applied to the required documents (00_PROJECT, 02_SCOPE, 04_ARCHITECTURE, 07_RESTART, 11_NEXT_CONTEXT, 15_GIT_POLICY, 16_DATABASE_RUNTIME_STATE, README).
- No files outside `docs/dpmtf/` are modified in v3.
- No DPMtF source files are modified.
- No v2 files are modified.
- Markdown fence check passes on all edited files.
- No commit is made during this phase.

## Scope Change Process

If scope must change during a session:

1. Document the proposed change and reason in `09_DECISIONS.md`.
2. Obtain Human Approval Gate sign-off if the change adds work or removes constraints.
3. Update this document with the new scope boundary.
4. Log the change date and decision reference in the Scope Change Log below.

## Scope Change Log

| Date | Change | Reason | Decision Reference |
|------|--------|--------|-------------------|
| 2026-06-11 | Initial scope for phase 3C-3 | Governance initialization phase | — |

---
