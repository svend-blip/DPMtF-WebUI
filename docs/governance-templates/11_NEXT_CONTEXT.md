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
| Latest commit (HEAD) | `fc98229` (2O complete — 3 parallel comparisons, model decision tree updated) |
| Uncommitted changes | Ingen — clean working tree (kun untracked test artifacts) |
| Remote | `origin → https://github.com/svend-blip/DPMtF-WebUI.git` |

**Rule:** Always verify with live git commands. Do not assume commit/push state from previous NEXT_CONTEXT text. If git state conflicts with this file, stop and ask Svend. See [[15_GIT_POLICY]] for full rules.

## Current State

- **Project**: DPMtF WebUI — governance-first orchestration engine
- **Current phase**: **Blok 6 (2H-2O) KOMPLET** — næste roadmap skal defineres
- **Latest committed baseline**: fc98229 (2O complete)
- **Alle faser 1A-2O er completed og committed.** DPMtF-WebUI governance-infrastruktur er fuldt bygget og empirisk valideret.

### Phase Progress

| Phase | Status | Description |
|-------|--------|-------------|
| **Blok 1: Core infrastructure (1A-1X)** | **24 faser — alle completed** | Skeleton, panel import, classification, app profiles, prompt sequences, layout schema, i18n, endpoint registry, bootstrap dataset, ADR |
| **Blok 2: Migration prep (2A-2D)** | **4 faser — alle completed** | AI PC WebUI migration target, reusable panel selection, project skeleton, v2 panel requirements |
| **2E** | **Completed — committed (bd671f5)** | **Governance-template opgradering** |
| **2F** | **Completed — committed (b28fac5)** | **Hitrate Scoring: prompt_runs + prompt_hitrates, API, frontend** |
| **2F-bis** | **Completed — committed (26f5c81)** | **Frontend i18n + Dark Theme: 46 labels, skeleton HTML, 0 dynamic innerHTML, dark dashboard** |
| **2G** | **Completed — committed (0a173fa→ed48ad7)** | **Implementation Pattern Manager: implementation_patterns tabel, pattern-matching, frontend pattern-tabel, model metadata** |
| **2H** | **Completed — committed (91f1147→c093cd6)** | **Prompt Template Manager: database-drevne templates, 4 baseline + 2 nye, parametriserbare** |
| **2H Redesign** | **Completed — committed (552f432)** | **Data-drevet redesign: 6 templates, complexity tiers, capture sources, per-model hitrate, obligatoriske outcome-felter** |
| **2H-bis** | **Completed — committed (7c8e000)** | **Fuld i18n-understøttelse af alle frontend-tekster — lbl() på alle brugervendte strenge** |
| **2I** | **Completed — committed (5d389b8→fdea70e)** | **Local Prompt Compiler: POST /api/prompt-templates/{key}/compile, frontend compile-form** |
| **2J** | **Completed — committed (5b4a44b→1a9d6ba)** | **Validation Automation: 7 baseline regler, POST /api/validate, frontend validation panel** |
| **2K** | **Completed — committed (7d78926→85498f1)** | **Git Sync Management: git_sync_status + git_operations tabeller, API, frontend panel** |
| **2L** | **Completed — committed (7cbc34e→a951d20)** | **Platform Adapter Framework: PlatformAdapter ABC, LinuxPlatformAdapter, GET /api/platform** |
| **2M** | **Completed — committed (9bf352f→379b169)** | **Local Claude Code Session Manager: claude_sessions tabel, API, frontend session panel** |
| **2N** | **Completed — committed (700a513→cb074f5)** | **Prompt→Implementer→Validator loop: workflow_runs tabel, POST /api/workflow/start, status flow** |
| **2O** | **Completed — committed (fc98229)** | **Parallel-kørsel test: 3 runs (README reuse, footer new, CHANGELOG new). Model decision tree opdateret med empirisk data. 9/9 first-try for lokal model.** |

## Completed Since Last Handoff (2G → nu)

- **Phase 2H — Prompt Template Manager**: Første version med 4 baseline templates, database-drevne, parametriserbare. Commits: 91f1147, 33db344, e221ba4, c093cd6.
- **Phase 2H Redesign**: Data-drevet redesign baseret på Excel-analyse af 8 prompt-runs. 6 kritiske fund adresseret. 6 templates med complexity tiers, capture sources, per-model hitrate tracking, obligatoriske outcome-felter. Commit: 552f432.
- **Phase 2H-bis — Fuld i18n**: Alle brugervendte frontend-tekster bruger nu `lbl()`. ui_labels + ui_label_translations seed-data for alle nye labels. Commit: 7c8e000.
- **Phase 2I — Local Prompt Compiler**: POST /api/prompt-templates/{key}/compile med parameter-substitution. Frontend compile-form i template detail view. Commits: 5d389b8, 06d8dd5, fdea70e.
- **Phase 2J — Validation Automation**: 7 baseline valideringsregler fra 06_VALIDATION.md. POST /api/validate med sikkerhedsfilter. Frontend validation panel med farvekodet verdict. Commits: 5b4a44b, 80a1034, 9493961, 1a9d6ba.
- **Phase 2K — Git Sync Management**: git_sync_status + git_operations tabeller. GET /api/git/status med live git enrichment. Frontend git panel. Commits: 7d78926, 342c309, 85498f1.
- **Phase 2L — Platform Adapter Framework**: PlatformAdapter ABC + LinuxPlatformAdapter (nvidia-smi, df, ss, ps, fuser). GET /api/platform. Commits: 7cbc34e, a951d20.
- **Phase 2M — Local Claude Code Session Manager**: claude_sessions tabel. GET/POST/PUT /api/sessions. Frontend session panel med Active/No active badge. Commits: 9bf352f, 379b169.
- **Phase 2N — Prompt→Implementer→Validator loop**: workflow_runs tabel. POST /api/workflow/start (kompilerer internt). PUT status flow (compiled→implementing→validating→done/failed). Commits: 700a513, cb074f5.
- **Panel Groups**: user_panel_groups tabel, collapse/expand JS+CSS, panel-group containers, i18n labels. Commits: 7647d07→e8d7128.
- **Superpowers Governance Framework**: superpowers.md, alignmentstructure.md, gates.md, localmodel.md oprettet og itereret. Commits: 10d5655, d7f320d.
- **4-lags i18n Arkitektur Alignment**: DPMtF-WebUI's get_ui_labels_for_domain() omskrevet til fuld 4-lags traversering (slot→slot_label→label→translation), samme flow som ENO. 108 slots, 108 mappings, 108 labels, 216 translations. Commit: 303f7a9.

## Remaining Work

- **Definér næste roadmap:** Blok 6 (2H-2O) er komplet. Næste blok skal defineres — mulige retninger:
  - 2O-b: Comparison panel i DPMtF-WebUI (designet, ikke implementeret)
  - ENO-6 Fase 2: Alignment-dashboard i ENO
  - Prompt-optimering til lokal model (reducér thinking overhead)
  - Automatisk model-routing baseret på 2O baseline data
- **Prompt #5 og #6 er skrevet men kun kørt som cloud** — kan genbruges til fremtidige lokal-model tests.

## Important Notes for Next Session

- **Alle faser 2H-2N er committed.** Kun 2O mangler i Blok 6. Dette er en milepæl — governance-infrastrukturen er næsten komplet.
- **alignmentstructure.md er nu synkroniseret** med faktisk git-status (2I-2N markeret ✅). Var tidligere stale (viste ⏳).
- **Superpowers governance framework** (`docs/governance-templates/superpowertemplates/`) er den autoritative kilde til tværprojekt-regler, model selection, og alignment. Loades ved reference til `superpowers.md`.
- **4-lags i18n er nu obligatorisk** på tværs af alle projekter. Både DPMtF-WebUI og ENO bruger samme flow: `ui_text_slots` → `ui_text_slot_labels` → `ui_labels` → `ui_label_translations`, API returnerer `{slot_key: text}`.
- **ENO's governance-filer er stale** — 00_PROJECT.md siger stadig "AI PC Resource WebUI v3", 02_SCOPE.md viser fase 3C-3, 10_CHANGELOG.md og 11_NEXT_CONTEXT.md er DPMtF-WebUI kopier. Dette skal adresseres via GATE-GOVERNANCE-SYNC.
- **Projektrapporten** (`docs/project-report.md`) er den autoritative reference for den videre retning. Læs den før næste fase planlægges.
- DPMtF-WebUI bruger `docs/governance-templates/` som sine egne governance-docs — der er ingen separat `docs/dpmtf/` mappe. Templates tjener dobbelt funktion: master-kopier til initialisering af nye projekter OG aktiv governance for DPMtF-WebUI selv.

## Open Questions

- Hvordan skal 2O designes? Skal det være en interaktiv test-runner i frontend, eller en batch-sammenligning der kører på tværs af alle templates?
- Hvilke metrics er vigtigst for model selection: success rate, duration, cost, eller output quality?
- ENO's næste funktionelle fase — hvad er ENO's eget roadmap ud over alignment med DPMtF-WebUI?
- Om 10_CHANGELOG.md og README.md i governance-templates skal forblive generiske (template-versioner) eller også opdateres med DPMtF-WebUI-specifikt indhold. Nuværende praksis: de forbliver generiske; projektspecifikke versioner lever i target-projektets `docs/dpmtf/`.

## Files Changed (Governance Update 2026-06-13)

| File | What Changed |
|------|-------------|
| `docs/governance-templates/superpowertemplates/alignmentstructure.md` | Alignment matrix: 2I-2N rettet fra ⏳ til ✅ med commit-referencer. Alignment-status opdateret. |
| `docs/governance-templates/11_NEXT_CONTEXT.md` | Denne fil — komplet omskrivning fra 2G til nuværende status (2O next). |
| `docs/governance-templates/02_SCOPE.md` | Fase opdateret fra 3C-3 til 2O med korrekt scope. |

---

## Files Changed (Phase 2H + 2H Redesign + 2H-bis)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | CREATE TABLE prompt_templates (4 baseline). ALTER TABLE prompt_templates (+6 kolonner: complexity_tier, capture_source, local/cloud_success_rate, total_local/cloud_runs). ALTER TABLE prompt_runs (+5 kolonner: template_key, execution_status, first_try_success, manual_corrections, validation_passed). CREATE TABLE template_model_hitrates. Seed: 4→6 templates, PRUN-2E-0001 backfill, template_model_hitrates. |
| `app.py` | GET/POST/PUT /api/prompt-templates (nye felter + filtre). GET /api/prompt-templates/{key}/hitrate. POST /api/prompt-runs (obligatoriske outcome-felter + template_key + template_model_hitrates UPSERT). GET /api/prompt-runs (nye filtre). |
| `templates/index.html` | Template Manager panel, compile-form, udvidede runs-tabel kolonner. |
| `static/js/dpmtf-app.js` | Template Manager: 9 kolonner, complexity/capture/success-rate badges, per-model hitrate tabel, compile-form. Prompt Runs: 13 kolonner, Status/1st-Try/Corr badges. Hjælpere: complexityBadge(), formatRate(), rateClass(). |
| `static/css/dpmtf-theme.css` | 12 nye klasser: complexity-tier-1/2/3, capture-verbatim/designed/reconstructed, status-completed/failed/unknown/sent, template-detail-panel. |
| `docs/governance-templates/superpowertemplates/superpowers.md` | Model decision tree: per-template hitrate opslag, complexity_tier ≥ 3 → cloud. Workflow: template-valg + run-registrering. |
| `docs/governance-templates/superpowertemplates/localmodel.md` | suitable_for default → local. Prompt compiler flow opdateret. |
| `docs/governance-templates/superpowertemplates/alignmentstructure.md` | 2H ✅, 2H Redesign ✅. |
| `docs/governance-templates/10_CHANGELOG.md` | 2H, 2H Redesign, 2H-bis entries. |

## Files Changed (Phase 2I — Local Prompt Compiler)

| File | What Changed |
|------|-------------|
| `app.py` | POST /api/prompt-templates/{key}/compile — parameter-substitution, {placeholders} → værdier, list-generering. |
| `static/js/dpmtf-app.js` | Compile-form i template detail view: project path, phase ID, goal, constraints, allowed files, validation commands. Kompileret prompt visning med copy-knap. |
| `docs/governance-templates/10_CHANGELOG.md` | 2I entry. |

## Files Changed (Phase 2J — Validation Automation)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | CREATE TABLE validation_rules (7 baseline regler), validation_runs, validation_results. Seed: 7 regler + registreringer. |
| `app.py` | POST /api/validate — kører regler mod projekt, sikkerhedsfilter, struktureret rapport. GET /api/validation-runs, GET /api/validation-rules. |
| `static/js/dpmtf-app.js` | Validation panel i System Setup: regler tabel, "Run Validation" knap, farvekodet verdict + per-regel resultater. |
| `docs/governance-templates/10_CHANGELOG.md` | 2J entry. |

## Files Changed (Phase 2K — Git Sync Management)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | CREATE TABLE git_sync_status, git_operations. Seed + registreringer. |
| `app.py` | GET /api/git/status (live git enrichment), POST /api/git/operations (registrerer kun), GET /api/git/operations. |
| `static/js/dpmtf-app.js` | Git panel i System Setup: branch, unpushed commits, last commit per projekt. |
| `docs/governance-templates/10_CHANGELOG.md` | 2K entry. |

## Files Changed (Phase 2L — Platform Adapter Framework)

| File | What Changed |
|------|-------------|
| `platform_adapter.py` | NY FIL: PlatformAdapter ABC + LinuxPlatformAdapter (nvidia-smi, df, ss, ps, fuser) + WindowsPlatformAdapter stub. |
| `app.py` | GET /api/platform — OS, Python version, GPU count/details, home disk usage. |
| `static/js/dpmtf-app.js` | Platform info panel i System Setup drawer. |
| `docs/governance-templates/10_CHANGELOG.md` | 2L entry. |

## Files Changed (Phase 2M — Local Claude Code Session Manager)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | CREATE TABLE claude_sessions. Seed + registreringer. |
| `app.py` | GET /api/sessions, GET /api/sessions/current, POST /api/sessions, PUT /api/sessions/{id}. |
| `static/js/dpmtf-app.js` | Session panel i System Setup: Active/No active badge, model, project, started tid. |
| `docs/governance-templates/10_CHANGELOG.md` | 2M entry. |

## Files Changed (Phase 2N — Prompt→Implementer→Validator loop)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | CREATE TABLE workflow_runs. Seed + registreringer. |
| `app.py` | POST /api/workflow/start (kompilerer internt via _compile_prompt_internal()), PUT /api/workflow/{id}/status, GET /api/workflow/runs. |
| `static/js/dpmtf-app.js` | Workflow panel i System Setup: runs med status badges (grøn=done, rød=failed, orange=implementing, blå=compiled). |
| `docs/governance-templates/10_CHANGELOG.md` | 2N entry. |

## Files Changed (Panel Groups + Superpowers + 4-lags Alignment)

| File | What Changed |
|------|-------------|
| `scripts/init_db.py` | CREATE TABLE user_panel_groups. |
| `app.py` | GET/POST /api/user-panel-groups. get_ui_labels_for_domain() omskrevet til fuld 4-lags traversering. |
| `templates/index.html` | Panel-group containers (daily, journals, reports, periodic, setup). |
| `static/js/dpmtf-app.js` | Panel-group collapse/expand logic. |
| `static/css/dpmtf-theme.css` | Panel-group collapse/expand styles. |
| `docs/governance-templates/superpowertemplates/` | NY MAPPE: superpowers.md, alignmentstructure.md, gates.md, localmodel.md. |
| `docs/governance-templates/05_CODING_STANDARD.md` | 4-lags i18n arkitektur dokumenteret som obligatorisk standard. |
| `docs/governance-templates/10_CHANGELOG.md` | Panel groups, superpowers, 4-lags alignment entries. |

---
