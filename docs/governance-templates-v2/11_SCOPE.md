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

**MACHINE_PROFILE_FASE1 — Machine Profile: Portabelt Setup-lag**

## In Scope Now

- `profiles/` mappe
- `profiles/.gitkeep`
- `profiles/machine.local.example.json`
- `profiles/machine.ai-pc.example.json`
- `.gitignore` opdatering for lokale Machine Profiles
- `config.get_machine_profile()`
- `config.get_machine_profile_path()`
- `config.get_machine_profile_metadata()`
- `GET /api/system/machine-profile`
- `GET /api/system/healthcheck`
- `GET /api/system/healthcheck/{section}`
- Read-only System Setup panel i frontend
- i18n labels for nye System Setup UI-elementer

## Out of Scope Now

- Ændring af `bridge_roles` schema
- Ændring af `bridge_flow_steps` schema
- Ændring af `bridge_roles.start_cmd_suffix`
- Automatisk kommando-bygning fra Machine Profile
- `use_machine_profile` på flows
- Migration af eksisterende roller
- Migration af deliverable_dir
- Start/stop af roller via Machine Profile
- Redigering af Machine Profile fra UI

## Key Principle

Machine Profile er et read-only opslagslag. Det må ikke ændre eksisterende runtime-adfærd. Alle flows, roller og scripts skal køre uændret videre — med eller uden Machine Profile.

## Constraints

- Do NOT modify `bridge_roles` schema or data.
- Do NOT modify `bridge_flow_steps` schema or data.
- Do NOT modify `start_cmd_suffix` logic.
- Do NOT modify tmux injection or role start/stop logic.
- Do NOT modify deliverable_dir resolution.
- Do NOT introduce new dependencies without Human Approval Gate.
- Do NOT commit until explicitly instructed by Human.
- All frontend text MUST use `lbl(key, fallback)` — no hardcoded English strings.
- No `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`.
- Python: `py_compile` before signaling completion, PEP 8, parameterized SQL queries.
- Shell: `bash -n` before signaling completion, `set -euo pipefail`.

## Success Criteria

- App starter uden `profiles/` mappe
- App starter uden Machine Profile fil
- Invalid JSON i Machine Profile crasher ikke appen
- `GET /api/system/machine-profile` returnerer `exists=false` hvis fil mangler
- `GET /api/system/healthcheck` returnerer warning hvis fil mangler
- Path check markerer eksisterende sti som `pass`
- Path check markerer manglende required path som `fail`/`error`
- Binary check virker både for absolut sti og PATH binary
- Secrets check returnerer kun `found`/`missing` — aldrig secret value
- Ukendt healthcheck section returnerer `400`

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
