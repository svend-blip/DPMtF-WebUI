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
| Latest commit (HEAD) | `d6259b1` (2G: Add pattern table + extended runs) — actual HEAD as baseline |
| Uncommitted changes | Phase 2G documentation (see Current State below) |
| Remote | `origin → https://github.com/svend-blip/DPMtF-WebUI.git` |

**Rule:** Always verify with live git commands. Do not assume commit/push state from previous NEXT_CONTEXT text. If git state conflicts with this file, stop and ask Svend. See [[15_GIT_POLICY]] for full rules.

## Current State

- **Project**: DPMtF WebUI — governance-first orchestration engine
- **Current phase**: Phase 2G — Implementation Pattern Manager (uncommitted docs)
- **Latest committed baseline before this phase**: 26f5c81 (2F-bis: Documentation update)
- **Blok 1-5 (1A-2G) er completed og committed.** Blok 6 (2H-2O) er planned.

### Phase Progress

| Phase | Status | Description |
|-------|--------|-------------|
| **Blok 1: Core infrastructure (1A-1X)** | **24 faser — alle completed** | Skeleton, panel import, classification, app profiles, prompt sequences, layout schema, i18n, endpoint registry, bootstrap dataset, ADR |
| **Blok 2: Migration prep (2A-2D)** | **4 faser — alle completed** | AI PC WebUI migration target, reusable panel selection, project skeleton, v2 panel requirements |
| **2E** | **Completed — committed (bd671f5)** | **Governance-template opgradering** |
| **2F** | **Completed — committed (b28fac5)** | **Hitrate Scoring: prompt_runs + prompt_hitrates, API, frontend** |
| **2F-bis** | **Completed — committed (26f5c81)** | **Frontend i18n + Dark Theme: 46 labels, skeleton HTML, 0 dynamic innerHTML, dark dashboard** |
| **2G** | **Completed — committed** | **Implementation Pattern Manager: implementation_patterns tabel, pattern-matching i POST /api/prompt-runs, GET /api/implementation-patterns, frontend pattern-tabel med expandable runs, model metadata (type/tokens/cost)** |
| **2H** | **Completed — redesign implemented (uncommitted)** | **Prompt Template Manager: Redesign baseret på Excel-dataanalyse. 6 templates, complexity tiers, capture sources, per-model hitrate tracking, obligatoriske outcome-felter.** |
| **2I** | **Next** | Local Prompt Compiler |
| **2J** | Planned | Validation Automation |
| **2K** | Planned | Git Sync Management |
| **2L** | Planned | Platform Adapter Framework |
| **2M** | Planned | Local Claude Code Session Manager |
| **2N** | Planned | Prompt→Implementer→Validator loop |
| **2O** | Planned | Parallel-kørsel test (cloud vs lokal) |

## Completed in This Session

- **Phase 2H Redesign — Prompt Template Manager**: Fuld redesign og implementering baseret på Excel-dataanalyse.
  - **Analyse:** 8 prompt-runs fra `claude_ollama_prompt_history.xlsx` evalueret. 6 kritiske fund: 62% rekonstruerede prompts, 100% lokal model-brug, DPMtF-WebUI SR 0.65 vs v2's 1.0, 37.5% ukendte outcomes, 4.6x længde-variation, kun 2 model-tags.
  - **Database:** ALTER TABLE prompt_templates (+6 kolonner), ALTER TABLE prompt_runs (+5 kolonner), CREATE TABLE template_model_hitrates.
  - **Seed:** 4 templates opdateret, 2 nye tilføjet (tpl_create_add_local, tpl_update_edit_local), PRUN-2E-0001 backfill'et, template_model_hitrates seedet.
  - **API:** GET /api/prompt-templates (nye filtre), POST /api/prompt-templates (validering), PUT (nye felter), GET /api/prompt-templates/{key}/hitrate (nyt), POST /api/prompt-runs (obligatoriske outcome-felter + template_model_hitrates UPSERT), GET /api/prompt-runs (nye filtre).
  - **Frontend:** Template Manager: 9 kolonner med complexity/capture/success-rate badges. Template detail: per-model hitrate tabel. Prompt Runs: 13 kolonner med Status/1st-Try/Corr badges.
  - **CSS:** 12 nye klasser for complexity tiers, capture sources, execution statuses.
  - **Governance:** alignmentstructure.md (2H ✅), localmodel.md (suitable_for default → local), superpowers.md (decision tree + workflow opdateret), CHANGELOG, NEXT_CONTEXT, IMPLEMENTATION_REPORT.
  - **Registreringer:** ENDP-4000022, BDS-5000016. BDS-5000015 count: 4→6. Phase tracking: 2G→completed, 2H→completed.

## Remaining Work

- Commit/push alle 2H ændringer.
- Phase 2I (Local Prompt Compiler): Byg prompt-samler fra templates + hitrate-data + governance-kontekst.
- Phase 2J (Validation Automation): Automatiser pre-commit checks som DPMtF-WebUI feature.

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

## Files Changed (Phase 2F-bis)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | Added ui_text_slots and ui_text_slot_labels tables. 46 new ui_labels, 104 new ui_label_translations, 46 ui_text_slots, 46 ui_text_slot_labels bindings. |
| `templates/index.html` | Reduced from 348 to 46 line skeleton. 8 data-slot attributes. All panel HTML removed — JS renders all content. |
| `static/js/dpmtf-app.js` | Rewritten from 1813 to 840 lines. 9 sections. 54 lbl() i18n calls. 1 static innerHTML. 39 dynamic innerHTML replaced with safe DOM APIs. |
| `static/css/dpmtf-theme.css` | Complete dark dashboard theme rewrite. #0d1117 background, #21262d cards. .dpmtf- prefix convention. |
| `docs/governance-templates/10_CHANGELOG.md` | Added 2F-bis entry. |
| `docs/governance-templates/11_NEXT_CONTEXT.md` | This file — updated for 2F-bis handoff. |

---

## Files Changed (Phase 2G)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | ALTER TABLE prompt_runs: 7 new columns. CREATE TABLE implementation_patterns. Backfill PRUN-2E-0001. Seed PAT-0001. Register 2 endpoints + 1 bootstrap dataset. Phase tracking: 2F/2F-bis completed, 2G next. |
| `app.py` | Extended POST /api/prompt-runs: 7 new optional fields, model_type derivation, pattern-matching logic. Added _next_pattern_id(), _update_pattern_hitrate(). Added GET /api/implementation-patterns + GET /api/implementation-patterns/{pattern_id}/runs. |
| `static/js/dpmtf-app.js` | Added pattern table to loadHitrates() with clickable rows. Added loadPatternRuns() for expandable detail. Extended runs table with Model Type, Tokens, Cost columns. Added truncate(), formatTokens() helpers. |
| `docs/governance-templates/10_CHANGELOG.md` | Added 2G entry. |
| `docs/governance-templates/11_NEXT_CONTEXT.md` | This file — updated for 2G handoff. |

---
