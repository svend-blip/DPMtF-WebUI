# Next Context / Handoff

## Purpose

This governance document is the primary handoff artifact between sessions. The Handoff Writer role updates it before every `/clear`. After `/clear`, the new session reads this file first to reconstruct project state, current phase progress, and what needs to happen next. This file, combined with the governance documents in `docs/governance-templates/`, is the authoritative source of context — not chat memory.

---

## `/clear` Reconstruction Rules

1. **Use `/clear` between role transitions.** After `/clear`, chat memory is unavailable.
2. **Governance documents are the source of truth.** Do not rely on chat history as the only record of decisions or state.
3. **Reconstruction order after `/clear`:**
   - Read `11_NEXT_CONTEXT.md` (this file) — identify current role and remaining work.
   - Read `00_PROJECT.md` — confirm project identity.
   - Read `01_ROLES.md` — understand the role flow and position.
   - Read `02_SCOPE.md` — confirm phase boundaries.
   - Read previous role's output (analysis, design, prompts, or implementation report).
4. **If information is missing from governance documents, ask for clarification.** Do not assume.

## Required Inputs

| Input | Description |
|-------|-------------|
| Phase-start git baseline | From `git log --oneline -8` at session start — actual HEAD as baseline. |
| Current phase and progress | From `00_PROJECT.md` and implementation reports. |
| Completed work in this session | What was done, what was changed. |
| Remaining work | What still needs to be done. |
| Open questions | Unresolved items that need attention. |
| File change list | What files were modified and why. |

## Required Outputs

- Updated `NEXT_CONTEXT.md` with current state.
- Clear indication of the next role or action required.
- List of changed files with descriptions.

---

## Phase-Start Git Baseline

| Check | Result |
|-------|--------|
| Branch | `master` |
| Latest commit (HEAD) | `bd671f5` (2E: Upgrade governance templates from v3 learnings) — actual HEAD as baseline |
| Uncommitted changes | Phase 2F changes (see Current State below) |
| Remote | `origin → https://github.com/svend-blip/DPMtF-WebUI.git` |

**Rule:** Always verify with live git commands. Do not assume commit/push state from previous NEXT_CONTEXT text. If git state conflicts with this file, stop and ask Svend. See [[15_GIT_POLICY]] for full rules.

## Current State

- **Project**: DPMtF WebUI — governance-first orchestration engine
- **Current phase**: Phase 2F — Hitrate Scoring (uncommitted)
- **Latest committed baseline before this phase**: bd671f5 (2E: Upgrade governance templates from v3 learnings)
- **Blok 1-3 (1A-2E) er completed og committed.** Blok 4 (2F) er implementeret men uncommitted. Blok 5-6 (2G-2O) er planned.

### Phase Progress

| Phase | Status | Description |
|-------|--------|-------------|
| **Blok 1: Core infrastructure (1A-1X)** | **24 faser — alle completed** | Skeleton, panel import, classification, app profiles, prompt sequences, layout schema, i18n, endpoint registry, bootstrap dataset, ADR |
| **Blok 2: Migration prep (2A-2D)** | **4 faser — alle completed** | AI PC WebUI migration target, reusable panel selection, project skeleton, v2 panel requirements |
| **2E** | **Completed — committed (bd671f5)** | **Governance-template opgradering: 10 templates upgraded fra v3-læringer. Fase-tracking restruktureret med nyt 6-blok roadmap (2F-2O). Projektrapport skrevet.** |
| **2F** | **In progress (uncommitted)** | **Hitrate Scoring: prompt_runs + prompt_hitrates tabeller, GET/POST /api/prompt-runs, GET /api/prompt-hirates, frontend hitrate-panel med farvekodede success rates. Seedet med 2E run.** |
| **2G** | **Next** | **Implementation Pattern Manager: Capture successful implementation patterns fra completed faser.** |
| **2H** | Planned | Prompt Template Manager |
| **2I** | Planned | Local Prompt Compiler |
| **2J** | Planned | Validation Automation |
| **2K** | Planned | Git Sync Management |
| **2L** | Planned | Platform Adapter Framework |
| **2M** | Planned | Local Claude Code Session Manager |
| **2N** | Planned | Prompt→Implementer→Validator loop |
| **2O** | Planned | Parallel-kørsel test (cloud vs lokal) |

## Completed in This Session

- **Phase 2F — Hitrate Scoring**: Implementeret komplet hitrate-infrastruktur.
  - Database: `prompt_runs` og `prompt_hitrates` tabeller med seed data (PRUN-2E-0001).
  - API: `GET /api/prompt-runs` (med filtre), `POST /api/prompt-runs` (med atomisk hitrate-opdatering), `GET /api/prompt-hirates`.
  - Frontend: Hitrate-panel med farvekodede success rates (grøn ≥80%, orange ≥50%, rød <50%) og expandable recent runs tabel.
  - Ingen innerHTML i ny kode — bruger `createElement`/`textContent`/`replaceChildren`.
  - 3 nye endpoint_registry entries, 2 nye bootstrap_dataset entries.

## Remaining Work

- Commit/push efter validering for phase 2F.
- Phase 2G (Implementation Pattern Manager): Design `implementation_patterns` tabel, capture-mekanisme fra succesfulde faser.
- Phase 2H (Prompt Template Manager): Migrér statiske templates til database-drevne.
- Phase 2I (Local Prompt Compiler): Byg prompt-samler fra templates + hitrate-data + governance-kontekst.

## Important Notes for Next Session

- **Governance-templates er nu synkroniseret med v3's forbedringer.** 10 af 19 templates er opgraderet. 6 var allerede identiske (01_ROLES, 03_FILE_ACCESS_POLICY, 06_VALIDATION, 08_TESTPLAN, 09_DECISIONS, 13_VALIDATION_REPORT, 14_OFFLINE_MODE). 17_PERMISSION_MODE_POLICY var allerede til stede og identisk.
- **10_CHANGELOG.md og README.md forbliver templatespecifikke** — master-versionen er generisk, v3-versionen er projekt-specifik. Dette er korrekt.
- **Det nye 6-blok roadmap** (2E-2O) erstatter det gamle 2E-2K. De gamle faser (Wire endpoints, Validate replacement, Prompt Run Review) er absorberet i den nye struktur.
- **Projektrapporten** (`docs/project-report.md`) er den autoritative reference for den videre retning. Læs den før næste fase planlægges.
- DPMtF-WebUI bruger `docs/governance-templates/` som sine egne governance-docs — der er ingen separat `docs/dpmtf/` mappe. Templates tjener dobbelt funktion: master-kopier til initialisering af nye projekter OG aktiv governance for DPMtF-WebUI selv.

## Open Questions

- Om 10_CHANGELOG.md og README.md i governance-templates skal forblive generiske (template-versioner) eller også opdateres med DPMtF-WebUI-specifikt indhold. Nuværende praksis: de forbliver generiske; projektspecifikke versioner lever i target-projektets `docs/dpmtf/`.

## Files Changed (Phase 2E)

| File | What Changed |
|------|-------------|
| `docs/governance-templates/00_PROJECT.md` | Opgraderet fra v3: runtime-kommando, port-tabel, related projects struktur. |
| `docs/governance-templates/02_SCOPE.md` | Opgraderet fra v3: default constraints, scope change log. |
| `docs/governance-templates/04_ARCHITECTURE.md` | Opgraderet fra v3: komplet i18n fire-lags arkitektur, komponent-tabel. |
| `docs/governance-templates/05_CODING_STANDARD.md` | Opgraderet fra v3: "no fixed line numbers", innerHTML-regler uddybet. |
| `docs/governance-templates/07_RESTART.md` | Opgraderet fra v3: /clear reconstruction rules, common failure modes. |
| `docs/governance-templates/11_NEXT_CONTEXT.md` | Opgraderet fra v3: fase-progress-tabel, per-fase filændringstabeller, fase-start git-baseline. Indhold tilpasset DPMtF-WebUI. |
| `docs/governance-templates/12_IMPLEMENTATION_REPORT.md` | Opgraderet fra v3: Permission Mode Compliance sektion, innerHTML check. |
| `docs/governance-templates/15_GIT_POLICY.md` | Opgraderet fra v3: fase-start git-baseline checks (4 obligatoriske kommandoer), baseline-regler. |
| `docs/governance-templates/16_DATABASE_RUNTIME_STATE.md` | Opgraderet fra v3: 17-tabel dokumentation, schema change policy. |
| `docs/governance-templates/10_CHANGELOG.md` | Tilføjet 2E entry. |
| `scripts/init_db.py` | Fase-tracking restruktureret: 2D→completed, nyt 2E-2O roadmap med 6 blokke. |
| `docs/project-report.md` | Ny fil: tværgående analyse af DPMtF-WebUI, v2, v3 med anbefalinger. |

## Files Changed (Phase 2F)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | Tilføjet `prompt_runs` og `prompt_hitrates` tabeller (CREATE TABLE IF NOT EXISTS). Seedet PRUN-2E-0001 som første run + hitrate-aggregat. Registreret 3 nye endpoints og 2 bootstrap datasets. |
| `app.py` | Tilføjet 3 endpoints: `GET /api/prompt-runs` (med phase_key/target_project/success filtre + limit/offset), `POST /api/prompt-runs` (record run + atomisk hitrate-opdatering via ON CONFLICT UPDATE), `GET /api/prompt-hirates` (aggregeret statistik sorteret værst først). |
| `templates/index.html` | Tilføjet hitrate-panel sektion med farvekodet success rate tabel og expandable "Recent Prompt Runs" detalje-visning. |
| `static/js/dpmtf-app.js` | Tilføjet `loadHitrates()`, `loadPromptRuns()`, `td()` helper. Bruger `createElement`/`textContent`/`replaceChildren` — ingen innerHTML. Initialiseret ved page load. |
| `static/css/dpmtf-theme.css` | Tilføjet `.hitrate-section`, `.hitrate-good` (grøn), `.hitrate-ok` (orange), `.hitrate-low` (rød) styles. |
| `docs/governance-templates/10_CHANGELOG.md` | Tilføjet 2F entry. |
| `docs/governance-templates/11_NEXT_CONTEXT.md` | Denne fil — opdateret for 2F handoff. |

---
