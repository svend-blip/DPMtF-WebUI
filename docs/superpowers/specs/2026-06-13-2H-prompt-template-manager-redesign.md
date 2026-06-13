# 2H: Prompt Template Manager — Redesign Spec

**Dato:** 2026-06-13
**Fase:** 2H (oprindeligt "Prompt Template Manager")
**Status:** Redesign — baseret på Excel-dataanalyse af 8 prompt-runs
**Input-data:** `/home/svend/Hentet/claude_ollama_prompt_history.xlsx`
**Governance:** `superpowers.md` + `alignmentstructure.md`

---

## Redesign-begrundelse

Eksisterende `prompt_templates` tabel og 4 seed-templates blev oprettet i fase 2H's
initiale implementering. Analyse af 8 faktiske prompt-runs fra Excel-filen afslører
6 kritiske mismatch mellem design og virkelighed:

| # | Fund | Konsekvens |
|---|------|------------|
| 1 | **62% af prompts er rekonstruerede** (5/8) — kun 1/8 er verbatim | Templates skal auto-captures ved generering, ikke rekonstrueres post-hoc |
| 2 | **100% af runs bruger lokal model** (8/8) — 0 cloud runs | `suitable_for` default skal være `local`, ikke `both` |
| 3 | **DPMtF-WebUI prompts har 0.65 SR vs v2's 1.0** | Templates skal have complexity tier der matcher opgavens sværhedsgrad |
| 4 | **37.5% af runs har ukendt outcome** (3/8) | Outcome-felter skal være obligatoriske ved run-registrering |
| 5 | **Prompt-længde varierer 4.6x** (205-941 tegn) | Templates skal understøtte variable-length slots og valgfrie sektioner |
| 6 | **Kun 2 model-tags brugt på 8 runs** — model-diversitet i praksis er lav | Hitrate skal trackes per (template, model) kombination, ikke kun per template |

---

## Database-ændringer

### 1. `prompt_templates` — 6 nye kolonner (ALTER TABLE ADD COLUMN)

| Kolonne | Type | Beskrivelse |
|---|---|---|
| `complexity_tier` | INTEGER DEFAULT 2 | 1=simple (1-2 filer, mekanisk), 2=medium (multi-fil, endpoints), 3=complex (arkitektur, schema-ændringer) |
| `capture_source` | TEXT DEFAULT 'designed' | `designed` = hånd-designet template, `verbatim` = auto-captured fra eksakt prompt, `reconstructed` = genskabt fra git/resultat |
| `local_success_rate` | REAL DEFAULT 0.0 | Rolling success rate for lokale model-kørsler |
| `cloud_success_rate` | REAL DEFAULT 0.0 | Rolling success rate for cloud model-kørsler |
| `total_local_runs` | INTEGER DEFAULT 0 | Antal kørsler med lokal model |
| `total_cloud_runs` | INTEGER DEFAULT 0 | Antal kørsler med cloud model |

Alle via `ALTER TABLE ADD COLUMN` med try/except for idempotens.

### 2. `prompt_templates.structure_json` — udvidet sektions-format

Nuværende format:
```json
{
  "sections": [
    {"name": "context", "label": "...", "type": "fixed", "value": "..."}
  ]
}
```

Nyt format — tilføjer `required` og `min_length`/`max_length`:
```json
{
  "sections": [
    {
      "name": "context",
      "label": "You are working in:",
      "type": "fixed",
      "value": "{project_path}",
      "required": true
    },
    {
      "name": "goal",
      "label": "Goal:",
      "type": "param",
      "param_key": "goal",
      "required": true,
      "min_length": 20,
      "max_length": 500
    },
    {
      "name": "notes",
      "label": "Additional notes:",
      "type": "param",
      "param_key": "notes",
      "required": false,
      "max_length": 300
    }
  ]
}
```

**Nye sektions-attributter:**
- `required`: true/false — valgfrie sektioner udelades ved kompilering hvis parameterværdi er tom
- `min_length`: minimum tegn for parameterværdi (validering ved template-save)
- `max_length`: maximum tegn for parameterværdi (trunkering ved kompilering)

### 3. `prompt_runs` — 5 nye kolonner (ALTER TABLE ADD COLUMN)

| Kolonne | Type | Beskrivelse |
|---|---|---|
| `template_key` | TEXT | FK til `prompt_templates.template_key`. NULL = ikke template-baseret. |
| `execution_status` | TEXT NOT NULL DEFAULT 'unknown' | `completed`, `failed`, `unknown`, `sent` (sendt men ikke afsluttet) |
| `first_try_success` | INTEGER | 0=nej, 1=ja, NULL=ukendt. Obligatorisk ved status='completed'. |
| `manual_corrections` | INTEGER DEFAULT 0 | Antal korrigerende prompts/manuelle rettelser. |
| `validation_passed` | INTEGER | 0=nej, 1=ja, NULL=ukendt. Obligatorisk ved status='completed'. |

Alle via `ALTER TABLE ADD COLUMN` med try/except.

### 4. `template_model_hitrates` — ny tabel (CREATE TABLE IF NOT EXISTS)

```sql
CREATE TABLE IF NOT EXISTS template_model_hitrates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_key TEXT NOT NULL,
    model_used TEXT NOT NULL,
    total_runs INTEGER NOT NULL DEFAULT 0,
    successful_runs INTEGER NOT NULL DEFAULT 0,
    rolling_success_rate REAL NOT NULL DEFAULT 0.0,
    avg_duration_seconds INTEGER,
    last_run_timestamp TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_key, model_used)
)
```

**Formål:** Track hvilke model+template kombinationer der historisk giver bedst resultater.
Dette muliggør data-drevet model-valg — ikke kun baseret på `suitable_for` flag.

---

## API-ændringer

### POST /api/prompt-templates — udvidet

**Nye body-felter:**
```json
{
  "template_key": "tpl_create_add_local",
  "template_name": "Create/Add — Local Model",
  "description": "For create/add operations with local Ollama model. 1-3 files, no schema changes.",
  "structure_json": "{...}",
  "constraints_json": "{...}",
  "suitable_for": "local",
  "complexity_tier": 1,
  "capture_source": "verbatim",
  "avg_token_count_input": 300,
  "avg_token_count_output": 600
}
```

**Validering ved POST/PUT:**
- `template_key`: unik, slug-format (små bogstaver, underscores, bindestreger)
- `suitable_for`: skal være `local`, `cloud`, eller `both`
- `complexity_tier`: skal være 1, 2, eller 3
- `capture_source`: skal være `designed`, `verbatim`, eller `reconstructed`
- `structure_json`: valid JSON, mindst én sektion, alle `required: true` sektioner skal have `param_key` eller `value`

### GET /api/prompt-templates — udvidet filtrering

Nye query params:
- `?suitable_for=local` — filtrer på model-kompatibilitet
- `?complexity_tier=1` — filtrer på kompleksitetsniveau
- `?capture_source=verbatim` — filtrer på capture-kilde
- `?is_active=1` — kun aktive templates

Response inkluderer nu `local_success_rate`, `cloud_success_rate`, `total_local_runs`, `total_cloud_runs`.

### GET /api/prompt-templates/{template_key}/hitrate — NY

Returnerer per-model hitrate for en template:

```json
{
  "template_key": "tpl_implementation_small",
  "model_hitrates": [
    {
      "model_used": "qwen3.6-35b-128k",
      "total_runs": 5,
      "successful_runs": 5,
      "rolling_success_rate": 1.0,
      "avg_duration_seconds": 180
    },
    {
      "model_used": "qwen36-27b-q4km",
      "total_runs": 2,
      "successful_runs": 1,
      "rolling_success_rate": 0.5,
      "avg_duration_seconds": 320
    }
  ]
}
```

### POST /api/prompt-runs — skærpede krav

**Nye obligatoriske felter når `execution_status` = `completed`:**
- `first_try_success`: skal være 0 eller 1 (ikke NULL)
- `validation_passed`: skal være 0 eller 1 (ikke NULL)
- `manual_corrections`: skal være ≥ 0

**Nye valgfrie felter:**
- `template_key`: link til template (udløser opdatering af `template_model_hitrates`)
- `execution_status`: `completed`, `failed`, `unknown`, `sent`

**Backend-logik ved POST:**
1. Hvis `template_key` er angivet:
   a. Opdater `prompt_templates.total_local_runs` eller `total_cloud_runs`
   b. Opdater `prompt_templates.local_success_rate` eller `cloud_success_rate`
   c. UPSERT `template_model_hitrates` for (template_key, model_used) kombinationen
2. Hvis `execution_status` = `completed` og `first_try_success`/`validation_passed` er NULL → **400 Bad Request**
3. Opdater `prompt_hitrates` for phase_key (eksisterende logik)

### GET /api/prompt-runs — udvidet filtrering

Nye query params:
- `?template_key=tpl_implementation_small` — filtrer på template
- `?execution_status=unknown` — find runs der mangler outcome
- `?first_try_success=0` — find fejlede runs til analyse

---

## Seed Data — opdaterede templates

Eksisterende 4 templates opdateres med nye felter. 2 nye templates tilføjes baseret på Excel-mønstre.

### Opdatering af eksisterende templates

```sql
-- tpl_implementation_small: complexity_tier 1, local-first
UPDATE prompt_templates SET
  complexity_tier = 1,
  capture_source = 'designed',
  suitable_for = 'local',
  local_success_rate = 0.0,
  cloud_success_rate = 0.0,
  total_local_runs = 0,
  total_cloud_runs = 0
WHERE template_key = 'tpl_implementation_small';

-- tpl_implementation_medium: complexity_tier 2, local-first
UPDATE prompt_templates SET
  complexity_tier = 2,
  capture_source = 'designed',
  suitable_for = 'local',
  local_success_rate = 0.0,
  cloud_success_rate = 0.0,
  total_local_runs = 0,
  total_cloud_runs = 0
WHERE template_key = 'tpl_implementation_medium';

-- tpl_validation: complexity_tier 1, local (allerede local)
UPDATE prompt_templates SET
  complexity_tier = 1,
  capture_source = 'designed',
  local_success_rate = 0.0,
  cloud_success_rate = 0.0,
  total_local_runs = 0,
  total_cloud_runs = 0
WHERE template_key = 'tpl_validation';

-- tpl_brainstorm: complexity_tier 3, cloud (forbliver cloud — kræver stærk reasoning)
UPDATE prompt_templates SET
  complexity_tier = 3,
  capture_source = 'designed',
  local_success_rate = 0.0,
  cloud_success_rate = 0.0,
  total_local_runs = 0,
  total_cloud_runs = 0
WHERE template_key = 'tpl_brainstorm';
```

### Nye templates baseret på Excel-data

**Template 5: `tpl_create_add_local`** — baseret på 6/8 Create/Add runs (SR 0.83 gennemsnit)

```sql
INSERT OR IGNORE INTO prompt_templates
  (template_key, template_name, description, structure_json,
   constraints_json, suitable_for, complexity_tier, capture_source,
   avg_token_count_input, avg_token_count_output, is_active)
VALUES
  ('tpl_create_add_local',
   'Create/Add — Local Model',
   'For create/add operations with local Ollama model. 1-3 files, no schema changes. Based on 6 prompt runs averaging 83% success rate.',
   '{"sections":[
     {"name":"context","label":"You are working in:","type":"fixed","value":"{project_path}","required":true},
     {"name":"phase","label":"Start phase","type":"param","param_key":"phase_id","required":true},
     {"name":"goal","label":"Goal:","type":"param","param_key":"goal","required":true,"min_length":20,"max_length":300},
     {"name":"rules","label":"Rules:","type":"list","param_key":"constraints","required":true},
     {"name":"implementation","label":"Implementation target:","type":"param","param_key":"implementation","required":true,"max_length":200},
     {"name":"allowed_files","label":"Allowed files:","type":"list","param_key":"allowed_files","required":true},
     {"name":"validate","label":"Validate:","type":"list","param_key":"validation_commands","required":true},
     {"name":"notes","label":"Additional notes:","type":"param","param_key":"notes","required":false,"max_length":300},
     {"name":"stop","label":"Do not commit.","type":"fixed","value":"","required":true}
   ]}',
   '{"default_constraints":["no-schema-migration","no-innerHTML","no-service-control","no-new-dependencies"]}',
   'local', 1, 'verbatim',
   300, 600, 1);
```

**Template 6: `tpl_update_edit_local`** — baseret på 2/8 Update/Edit runs

```sql
INSERT OR IGNORE INTO prompt_templates
  (template_key, template_name, description, structure_json,
   constraints_json, suitable_for, complexity_tier, capture_source,
   avg_token_count_input, avg_token_count_output, is_active)
VALUES
  ('tpl_update_edit_local',
   'Update/Edit — Local Model',
   'For update/edit operations with local Ollama model. Read-only context, targeted edits. Based on 2 prompt runs (v3 phases 3C-6, 3C-14).',
   '{"sections":[
     {"name":"context","label":"You are working in:","type":"fixed","value":"{project_path}","required":true},
     {"name":"phase","label":"Start phase","type":"param","param_key":"phase_id","required":true},
     {"name":"baseline","label":"First run phase-start git baseline checks:","type":"list","param_key":"baseline_commands","required":true},
     {"name":"goal","label":"Goal:","type":"param","param_key":"goal","required":true,"min_length":30,"max_length":500},
     {"name":"rules","label":"Rules:","type":"list","param_key":"constraints","required":true},
     {"name":"implementation","label":"Implementation target:","type":"param","param_key":"implementation","required":true,"max_length":300},
     {"name":"allowed_files","label":"Allowed files:","type":"list","param_key":"allowed_files","required":true},
     {"name":"validate","label":"Validate:","type":"list","param_key":"validation_commands","required":true},
     {"name":"docs","label":"Update docs/dpmtf/10_CHANGELOG.md, 11_NEXT_CONTEXT.md, 12_IMPLEMENTATION_REPORT.md","type":"fixed","value":"","required":false},
     {"name":"stop","label":"Stop before commit and report.","type":"fixed","value":"","required":true}
   ]}',
   '{"default_constraints":["read-only","no-schema-migration","no-innerHTML","no-POST/PUT/DELETE","no-service-control"]}',
   'local', 2, 'verbatim',
   500, 1000, 1);
```

### Backfill PRUN-2E-0001 med nye obligatoriske felter

```sql
UPDATE prompt_runs SET
  execution_status = 'completed',
  first_try_success = 1,
  manual_corrections = 0,
  validation_passed = 1,
  template_key = 'tpl_implementation_medium'
WHERE run_id = 'PRUN-2E-0001';
```

### Seed template_model_hitrates for PRUN-2E-0001

```sql
INSERT OR IGNORE INTO template_model_hitrates
  (template_key, model_used, total_runs, successful_runs,
   rolling_success_rate, avg_duration_seconds)
VALUES
  ('tpl_implementation_medium', 'claude-fable-5', 1, 1, 1.0, 240);
```

### Endpoint registry — nye endpoints

```
ENDP-4000022: GET /api/prompt-templates/{template_key}/hitrate
```

### Bootstrap dataset registry — ny tabel

```
BDS-5000016: template_model_hitrates
```

---

## Frontend-ændringer

### Template Manager panel (nyt eller udvidet)

Viser alle templates i en tabel:

| Kolonne | Source |
|---|---|
| Template Key | `template_key` (klikbar — åbner detail-visning) |
| Name | `template_name` |
| Complexity | `complexity_tier` som badge: 🟢 Tier 1, 🟡 Tier 2, 🔴 Tier 3 |
| Suitable For | `suitable_for` som badge: blå=`local`, lilla=`cloud`, grå=`both` |
| Capture | `capture_source` som badge: grøn=`verbatim`, gul=`designed`, orange=`reconstructed` |
| Local SR | `local_success_rate` som procent (grøn ≥80%, orange ≥50%, rød <50%) |
| Cloud SR | `cloud_success_rate` som procent (samme farvekodning) |
| Active | `is_active` toggle |

**Detail-visning:** Klik på template_key åbner:
- Template-struktur med sektioner (navn, type, required, min/max length)
- Default constraints
- Per-model hitrate (fra `GET /api/prompt-templates/{key}/hitrate`)
- Seneste 10 runs med denne template (fra `GET /api/prompt-runs?template_key=...`)

### Prompt Runs tabel — udvidede kolonner

Tre nye kolonner i "Recent Prompt Runs":

| Kolonne | Indhold |
|---|---|
| Status | `execution_status` badge: grøn=`completed`, rød=`failed`, grå=`unknown`, blå=`sent` |
| First-Try | `first_try_success`: ✅=1, ❌=0, ◻=NULL |
| Corrections | `manual_corrections` tal (kun vises hvis >0, orange badge) |

### JavaScript (static/js/dpmtf-app.js)

- `loadTemplates()` — fetcher `/api/prompt-templates`, renderer template-tabel med filtre
- `showTemplateDetail(templateKey)` — fetcher `/api/prompt-templates/{key}` + `/api/prompt-templates/{key}/hitrate`, viser detail-panel
- `loadPromptRuns()` — extended med 3 nye kolonner + template_key filter
- `formatRate(rate)` — helper: formaterer 0.86 som "86%" med farvekodning
- `complexityBadge(tier)` — helper: returnerer 🟢/🟡/🔴 badge
- Alle nye DOM-manipulationer bruger `createElement`/`textContent`/`replaceChildren`

### CSS (static/css/dpmtf-theme.css)

- `.complexity-tier-1` — grøn venstre-border, let grøn baggrund
- `.complexity-tier-2` — gul venstre-border, let gul baggrund
- `.complexity-tier-3` — rød venstre-border, let rød baggrund
- `.capture-verbatim` — grøn badge
- `.capture-designed` — gul badge
- `.capture-reconstructed` — orange badge
- `.status-completed` — grøn badge
- `.status-failed` — rød badge
- `.status-unknown` — grå badge
- `.status-sent` — blå badge
- `.template-detail-panel` — indrykket, lettere baggrund, border-left 4px solid
- Genbrug eksisterende `.hitrate-good`, `.hitrate-ok`, `.hitrate-low`

---

## Validerings-checkliste

| # | Check | Kommando |
|---|-------|----------|
| 1 | Python syntax (app.py) | `python3 -m py_compile app.py` |
| 2 | Python syntax (init_db.py) | `python3 -m py_compile scripts/init_db.py` |
| 3 | Seed idempotent | `python3 scripts/init_db.py` (kør to gange) |
| 4 | JavaScript syntax | `node --check static/js/dpmtf-app.js` |
| 5 | Ingen ny innerHTML | `git diff -- static/js/dpmtf-app.js \| grep innerHTML` → skal være tom |
| 6 | Diff scope | `git diff --stat` — kun tilladte filer |
| 7 | ALTER TABLE safe | Verify try/except guards i init_db.py |
| 8 | Template JSON valid | `python3 -c "import json; json.loads(open('scripts/init_db.py').read())"` — strukturel check af seed data |
| 9 | Obligatoriske felter | POST /api/prompt-runs med execution_status=completed uden first_try_success → skal give 400 |
| 10 | template_model_hitrates UPSERT | POST to runs med samme (template_key, model_used) → skal UPDATE ikke INSERT |

---

## Tilladte filer

- `scripts/init_db.py`
- `app.py`
- `templates/index.html`
- `static/js/dpmtf-app.js`
- `static/css/dpmtf-theme.css`
- `docs/governance-templates/10_CHANGELOG.md`
- `docs/governance-templates/11_NEXT_CONTEXT.md`
- `docs/governance-templates/12_IMPLEMENTATION_REPORT.md`
- `docs/governance-templates/superpowertemplates/localmodel.md` (opdater `suitable_for` standard)

---

## Out of Scope (deferred to 2I+)

- Auto-capture af prompts fra Claude Code sessioner (kræver Session Manager 2M)
- Prompt compiler der automatisk parametriserer templates (2I — Local Prompt Compiler)
- Template recommendation baseret på opgavetype (kræver hitrate-data >20 runs)
- Automatic `capture_source` detection fra git-log (kræver 2K — Git Sync Management)
- Template A/B testing (parallel kørsel — 2O)

---

## Success-kriterier

1. `prompt_templates` har 6 nye kolonner og 6 seedede templates (4 opdateret + 2 nye)
2. `prompt_runs` har 5 nye kolonner med obligatoriske outcome-felter
3. `template_model_hitrates` tabel eksisterer og opdateres automatisk ved POST /api/prompt-runs
4. GET /api/prompt-templates understøtter filtrering på complexity_tier, suitable_for, capture_source
5. GET /api/prompt-templates/{template_key}/hitrate returnerer per-model statistik
6. POST /api/prompt-runs afviser completed runs uden first_try_success/validation_passed (400)
7. Frontend viser complexity tier badges, capture source badges, og per-model hitrates
8. PRUN-2E-0001 er backfill'et med alle nye obligatoriske felter
9. Alle 10 validerings-checks passerer
10. Seed script er idempotent (kan køres flere gange uden fejl)

---

## Opdatering af søster-filer

Efter implementering skal følgende governance-filer opdateres:

| Fil | Ændring |
|---|---|
| `alignmentstructure.md` | 2H status: ⏳ → ✅. Tilføj note om redesign-begrundelse |
| `localmodel.md` | Opdater "Prompt Compiler Flow" sektion 2 med nye API endpoints. Opdater `suitable_for` standard til `local` |
| `superpowers.md` | Tilføj "Template Manager" til sektion 5 workflow. Opdater model decision tree: lokal-først, cloud ved complexity_tier ≥3 |
| `10_CHANGELOG.md` | Tilføj entry for 2H redesign |
| `11_NEXT_CONTEXT.md` | Opdater fase-progress: 2H completed, 2I next |
| `12_IMPLEMENTATION_REPORT.md` | Udfyld efter implementering |
