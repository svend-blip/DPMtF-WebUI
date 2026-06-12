# Changelog

## Purpose

This governance document records all notable changes to the target project in chronological order. It is append-only — never edit existing entries. The changelog provides a human-readable history of what changed, when, and in what direction.

## When to Use

- **Release Operator**: Append an entry after committing verified changes.
- **After `/clear`**: Read to understand recent project evolution.
- **Any role**: Reference to check if something was already changed in a previous phase.

## Required Inputs

| Input | Description |
|-------|-------------|
| Change description | What was changed, added, fixed, removed, or temporarily hidden. |
| Date | When the change was committed (YYYY-MM-DD). |
| Phase key | E.g., `3A`, `2D-D`. |

## Required Outputs

- New entry appended at the bottom of this file.
- Entry follows the format defined below.

---

## Format

```markdown
### [YYYY-MM-DD] — [Phase key]: [Brief description]
- Changed: [What was modified and why.]
- Added: [What was introduced.]
- Fixed: [What was repaired.]
- Removed: [What was deleted with scope authorization and approval.]
- Hidden (temporary): [What was hidden for migration purposes only — cleanup phase noted.]
```

## Rules

1. **Append only** — never edit or delete existing entries.
2. Use the "Removed" category for code, panels, or features that were explicitly deleted per phase scope with Human Approval Gate approval and validation.
3. Use the "Hidden (temporary)" category only for migration work in existing projects where cleanup is documented and a planned removal phase is specified. New projects should not use this category — implement cleanly.
4. Include the phase key in each entry header to trace changes back to phases.
5. Keep descriptions brief but specific enough that a future session understands what changed without reading git diff.
6. Do not log trivial formatting fixes or whitespace-only changes.

## Entries

### [2026-06-12] — 2E: Governance-template opgradering fra v3-læringer
- Opgraderet: 10 governance-templates fra ai-pc-resource-webui-v3's forbedrede versioner (00_PROJECT, 02_SCOPE, 04_ARCHITECTURE, 05_CODING_STANDARD, 07_RESTART, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, 15_GIT_POLICY, 16_DATABASE_RUNTIME_STATE).
- Tilføjet: 06_VALIDATION.md og 17_PERMISSION_MODE_POLICY.md var allerede identiske — ingen ændring nødvendig.
- Opdateret: `scripts/init_db.py` — fase-tracking restruktureret efter projektrapportens 6-blok roadmap. 2D markeret completed. 2E (Governance-template opgradering) tilføjet som completed. Nye faser 2F-2O for prompt-infrastruktur, automatisering, og lokal model integration.
- Ændret: 01_ROLES, 03_FILE_ACCESS_POLICY, 08_TESTPLAN, 09_DECISIONS, 13_VALIDATION_REPORT, 14_OFFLINE_MODE forblev uændrede (identiske mellem master og v3).
- Skrevet: `docs/project-report.md` — tværgående analyse af DPMtF-WebUI, ai-pc-resource-webui-v2, og ai-pc-resource-webui-v3 med anbefalinger til governance, automatisering, og transition til lokal model.

### [2026-06-12] — 2F: Hitrate Scoring
- Added: `prompt_runs` tabel — individuelle prompt-kørsler med run_id, phase_key, target_project, success, duration_seconds, error_summary, model_used, timestamp.
- Added: `prompt_hitrates` tabel — aggregerede success rates grupperet efter phase_key med rolling_success_rate, total_runs, successful_runs.
- Added: `GET /api/prompt-runs` — list prompt runs med valgfri filtre (phase_key, target_project, success, limit/offset).
- Added: `POST /api/prompt-runs` — record en ny prompt-kørsel og opdatér hitrate-aggregatet atomisk via INSERT + ON CONFLICT UPDATE.
- Added: `GET /api/prompt-hirates` — aggregerede hitrate-statistikker sorteret efter success rate (værst først).
- Added: Frontend hitrate-panel i `templates/index.html` med farvekodede success rates (grøn ≥80%, orange ≥50%, rød <50%) og expandable "Recent Prompt Runs" tabel.
- Added: `loadHitrates()` og `loadPromptRuns()` funktioner i `static/js/dpmtf-app.js` — bruger `createElement`/`textContent`/`replaceChildren` (ingen innerHTML).
- Added: CSS styles for `.hitrate-section`, `.hitrate-good`, `.hitrate-ok`, `.hitrate-low` i `static/css/dpmtf-theme.css`.
- Seeded: 2E run som første prompt_runs record (PRUN-2E-0001) og tilhørende hitrate-aggregat.
- Registered: 3 nye endpoints i endpoint_registry (ENDP-4000013 til ENDP-4000015) og 2 bootstrap datasets (BDS-5000012, BDS-5000013).
- No schema migrations — nye tabeller via CREATE TABLE IF NOT EXISTS.

### [2026-06-12] — 2F-bis: Frontend i18n + Dark Theme Refactoring
- Changed: `templates/index.html` — reduceret fra 348 til 46 linjers skeleton med 8 data-slot attributter. Al panel-HTML fjernet — JS renderer nu alt indhold.
- Changed: `static/js/dpmtf-app.js` — omskrevet fra 1813 linjers monolit med 39 innerHTML til 840 linjer organiseret i 9 sektioner. 1 statisk innerHTML (drawer close button &times;). 54 lbl() i18n opslag. Al tekst via labelMap med da-DK/en-US fallbacks.
- Changed: `static/css/dpmtf-theme.css` — komplet omskrivning til mørkt dashboard-tema (#0d1117 baggrund, #21262d cards). .dpmtf- prefix konvention. Farvepalet matcher ai-pc-resource-webui-v3.
- Added: ui_text_slots og ui_text_slot_labels tabeller (fire-lags i18n lag 1-2). 46 nye ui_labels (LBL-1000007 til LBL-1000052). 104 nye ui_label_translations (52 en-US + 52 da-DK). 46 ui_text_slot_labels bindings. 46 ui_text_slots entries.
- Preserved: Alle eksisterende API-endpoints og backend-funktionalitet (app.py uændret). System Setup drawer med 6 i18n-kompatible sektioner. Prompt Sequence Planner og New Project Planning funktionalitet.
- No schema migrations — nye tabeller via CREATE TABLE IF NOT EXISTS. No backend changes.

### [2026-06-12] — 2G: Implementation Pattern Manager
- Added: `implementation_patterns` tabel — grupperer prompt_runs efter file_signature + constraint_set med egen hitrate (rolling_success_rate, best_model, avg_duration_seconds, avg_idle_seconds). UNIQUE(file_signature, constraint_set).
- Changed: `prompt_runs` — 7 nye kolonner via ALTER TABLE (model_type, idle_seconds, token_count_input/output, token_cost_eur/dkk, pattern_id FK).
- Changed: `POST /api/prompt-runs` — accepterer 7 nye valgfri felter. Auto-deriver model_type fra model_used (:cloud suffix → cloud). Pattern-matching: hvis file_signature + constraint_set angives, findes eller oprettes implementation_pattern, pattern-hitrate opdateres, pattern_id sættes på run.
- Added: `GET /api/implementation-patterns` — list patterns sorteret efter success rate (værst først). Valgfrit ?constraint_set filter.
- Added: `GET /api/implementation-patterns/{pattern_id}/runs` — alle runs for et givet pattern.
- Added: Frontend pattern-tabel i hitrate-panelet med farvekodede success rates, klikbare rækker der viser pattern-specifikke runs. Recent runs tabel udvidet med Model Type (local/cloud badge), Tokens (in/out), Cost (EUR/DKK) kolonner.
- Added: `_next_pattern_id()`, `_update_pattern_hitrate()`, `truncate()`, `formatTokens()` hjælpefunktioner.
- Seeded: PRUN-2E-0001 backfillet med model_type=cloud, pattern_id=PAT-0001. PAT-0001 oprettet som første pattern.
- Registered: 2 nye endpoints (ENDP-4000016/17) + 1 bootstrap dataset (BDS-5000014).
- No schema migrations — ALTER TABLE med try/except for idempotens, CREATE TABLE IF NOT EXISTS.

---

### [2026-06-12] — 2H: Prompt Template Manager
- Added: `prompt_templates` tabel — database-drevne, parametriserbare prompt templates med structure_json (sektioner med fixed/param/list typer), constraints_json, suitable_for (local/cloud/both), token estimates.
- Added: `GET /api/prompt-templates` — list alle aktive templates.
- Added: `POST /api/prompt-templates` — opret nyt template med structure_json og constraints_json.
- Added: `GET /api/prompt-templates/{key}` — hent enkelt template med parsed structure, constraints, og rendered preview.
- Added: `PUT /api/prompt-templates/{key}` — opdatér template felter selektivt.
- Added: Frontend template manager panel — tabel med template_key, navn, suitable_for badge (farvekodet), token estimates, klikbare rækker med detalje-visning og preview.
- Seeded: 4 baseline templates (tpl_implementation_small, tpl_implementation_medium, tpl_validation, tpl_brainstorm) fra eksisterende prompt-run mønstre.
- Registered: 4 endpoints (ENDP-4000018-21) + 1 bootstrap dataset (BDS-5000015).
- suitable_for feltet muliggør ENO model-valg logik (local/cloud/both).
- No schema migrations — CREATE TABLE IF NOT EXISTS.


### [2026-06-12] — 2I: Local Prompt Compiler
- Added: `POST /api/prompt-templates/{key}/compile` — kompilerer et prompt fra en template med parametre. Erstatter {placeholders} i fixed-sektioner, indsætter param-værdier, genererer list-punkter.
- Added: Frontend compile-form i template detail view — felter for project path, phase ID, goal, constraints, allowed files, validation commands. Viser kompileret prompt med copy-knap.
- Returns: template_key, template_name, suitable_for, prompt text, params_used.
- Muliggør ENO's prompt-generering til lokal/cloud model eksekvering.


### [2026-06-12] — 2J: Validation Automation
- Added: `validation_rules` tabel — 7 baseline regler fra 06_VALIDATION.md (syntax, scope, dependencies, schema, innerHTML checks).
- Added: `validation_runs` tabel — kørselshistorik med overall_verdict, rules_total/passed/failed.
- Added: `validation_results` tabel — per-regel resultater med passed, actual_output, notes.
- Added: `POST /api/validate` — kører valideringsregler mod et projekt, returnerer struktureret rapport med verdict. Sikkerhedsfilter blokerer destruktive kommandoer.
- Added: `GET /api/validation-runs` — seneste valideringskørsler.
- Added: `GET /api/validation-rules` — alle aktive regler.
- Added: Frontend validation panel i System Setup drawer — viser regler, "Run Validation" knap, farvekodet verdict + per-regel resultat tabel.
- Registered: ENDP-4000022 + 3 bootstrap datasets (BDS-5000016-18).
- Phase tracking: 2H/2I→completed, 2J→next.
- No schema migrations — CREATE TABLE IF NOT EXISTS.


### [2026-06-12] — 2K: Git Sync Management
- Added: `git_sync_status` tabel — tracker projekters git status (branch, unpushed_commits, last_push).
- Added: `git_operations` tabel — historik over git operationer (commit/push) med success, error_log, operator.
- Added: `GET /api/git/status` — read-only status med live git enrichment (unpushed commits, last commit, branch fra faktisk git).
- Added: `POST /api/git/operations` — registrerer eksterne git operationer (udfører IKKE git — commit/push forbliver manuelle).
- Added: `GET /api/git/operations` — seneste git operationer.
- Added: Frontend git panel i System Setup drawer — viser branch, unpushed commits, last commit per projekt.
- Registered: 3 endpoints (ENDP-4000023-25) + 2 bootstrap datasets (BDS-5000019-20).
- Phase tracking: 2J→completed, 2K→next.
- No schema migrations — CREATE TABLE IF NOT EXISTS.


### [2026-06-12] — 2L: Platform Adapter Framework
- Added: `platform_adapter.py` — PlatformAdapter ABC med abstrakte metoder for GPU, disk, port, processer.
- Added: `LinuxPlatformAdapter` — fuld implementation via nvidia-smi, df, ss, ps, fuser.
- Added: `WindowsPlatformAdapter` — stub for fremtidig Windows-understøttelse.
- Added: `GET /api/platform` — returnerer OS, Python version, GPU count/details, home disk usage.
- Added: Platform info panel i System Setup drawer.
- Phase tracking: 2K→completed, 2L→next.
- ADR-6000003 compliance: Linux-first, platform-abstraheret.


### [2026-06-12] — 2M: Local Claude Code Session Manager
- Added: `claude_sessions` tabel — tracker Claude Code sessioner med model_used, project_context, status (active/idle/stopped), started_at, ended_at, last_activity.
- Added: `GET /api/sessions` — list seneste sessioner.
- Added: `GET /api/sessions/current` — check om en session er aktiv nu.
- Added: `POST /api/sessions` — registrer ny session (startes manuelt af Svend).
- Added: `PUT /api/sessions/{id}` — opdatér status, aktivitet, noter.
- Added: Frontend session panel i System Setup drawer — viser Active/No active badge med model, project, started tid.
- Registered: 4 endpoints (ENDP-4000026-29) + 1 bootstrap dataset (BDS-5000021).
- Phase tracking: 2L→completed, 2M→next.
- No schema migrations — CREATE TABLE IF NOT EXISTS.


### [2026-06-12] — 2N: Prompt→Implementer→Validator loop
- Added: `workflow_runs` tabel — tracker faser gennem P→I→V loopet (prompt_compiled → implementing → validating → done/failed).
- Added: `POST /api/workflow/start` — kompilerer prompt internt, opretter workflow run, returnerer prompt + next step.
- Added: `PUT /api/workflow/{id}/status` — opdatér status gennem loopet.
- Added: `GET /api/workflow/runs` — list seneste runs med farvekodede status badges.
- Added: `_compile_prompt_internal()` — kompilerer prompt direkte fra database uden HTTP-kald til sig selv.
- Added: Frontend workflow panel i System Setup drawer — viser runs med status badges (grøn=done, rød=failed, orange=implementing, blå=compiled).
- Registered: 3 endpoints (ENDP-4000030-32) + 1 bootstrap dataset (BDS-5000022).
- Phase tracking: 2M→completed, 2N→next.
- No schema migrations — CREATE TABLE IF NOT EXISTS.

