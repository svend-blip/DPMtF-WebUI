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

**MACHINE_PROFILE_FASE2A — Machine Profile: Role Runtime Config**

## In Scope Now

- `bridge_flows.use_machine_profile` kolonne (idempotent)
- `bridge_roles.default_runtime`, `default_provider`, `default_model` kolonner (idempotent)
- `scripts/bridgeV002/command_builder.py` — `build_start_command()` + 5 builders + renderer
- `start_coding.py` ændring — vælg mellem legacy og Machine Profile kommando
- Frontend: `use_machine_profile` checkbox på flow, `default_runtime/provider/model` på rolle
- Backend API: flow/role endpoints accepterer nye felter
- i18n labels for nye UI-elementer

## Out of Scope Now

- Fjernelse af `start_cmd_suffix`
- Massemigrering af alle flows
- `command_templates` i Machine Profile
- `runtime_commands` database-tabel
- Flow-role overrides (Fase 2B)
- Ændring af tmux/prompt/flow execution ud over valg af startkommando

## Key Principle

Flow bestemmer OM Machine Profile bruges. Rolle bestemmer HVAD der skal køres. Machine Profile bestemmer HVORDAN. Builder oversætter. `start_cmd_suffix` bevares som legacy fallback.

## Constraints

- Do NOT remove `start_cmd_suffix`.
- Do NOT massemigrere flows.
- Do NOT modify tmux injection or role start/stop logic beyond command source selection.
- Do NOT modify deliverable_dir resolution.
- Do NOT introduce new dependencies without Human Approval Gate.
- Do NOT commit until explicitly instructed by Human.
- All frontend text MUST use `lbl(key, fallback)` — no hardcoded English strings.
- No `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`.
- Python: `py_compile` before signaling completion, PEP 8, parameterized SQL queries.
- Shell: `bash -n` before signaling completion, `set -euo pipefail`.

## Success Criteria

- `use_machine_profile` default = 0 for alle eksisterende flows
- Flow med `use_machine_profile=0` bruger `start_cmd_suffix` uændret
- Flow med `use_machine_profile=1` bruger `build_start_command()`
- Samme rolle i to flows påvirkes ikke globalt
- Manglende Machine Profile ved `use_machine_profile=1` → stop med fejl, ingen fallback
- Alle 5 builder-mønstre producerer korrekte kommandoer
- Ingen cloud secrets i command object eller shell-string

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
