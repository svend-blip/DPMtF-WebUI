# Design: Superpowers Governance Framework

**Dato:** 2026-06-13
**Projekt:** DPMtF-WebUI (port 9130) — Father project
**Status:** Godkendt

---

## Formål

Oprette et meta-governance framework i `docs/governance-templates/superpowertemplates/`
der styrer hvordan Superpowers (deepseek-v4-pro:cloud) og lokale Ollama modeller
bruges på tværs af DPMtF-afledte projekter.

Frameworket aggregerer regler fra de 19 governance templates og tilføjer:
- Model-valg decision tree (cloud vs lokal, dyr vs billig)
- Feature-alignment på tværs af projekter (DPMtF-WebUI, ENO, v3)
- Gate-spørgsmål før kritiske operationer
- Regler for lokal Ollama model-brug

---

## Fil-struktur

```
docs/governance-templates/
└── superpowertemplates/          ← NY mappe
    ├── superpowers.md            ← Hovedindgang — aggregerede regler + model decision tree
    ├── alignmentstructure.md     ← Feature-alignment på tværs af projekter
    ├── gates.md                  ← Gate-spørgsmål før kritiske operationer
    └── localmodel.md             ← Regler for lokal Ollama model-brug
```

---

## Projekt-hierarki

| Projekt | Port | Rolle |
|---|---|---|
| **DPMtF-WebUI** | 9130 | Father project — governance engine, holder ALLE governance templates |
| **ENO** (Evaluate Next Optimization) | 9131 | Første søn-projekt under alignment |
| **ai-pc-resource-webui-v3** | 9123 | Reference-projekt til test af DPMtF prompt compiler |

---

## `superpowers.md` — Hovedindgang

### Sektion 1: Aggregerede regelsæt

Komprimerede regler fra de 19 governance templates, struktureret efter domæne:

**Proces-regler (fra `01_ROLES.md`, `07_RESTART.md`):**
- Rolle-flow: Analyst → Solution Architect → Prompt Engineer → Implementer → Validator → Human Approval Gate → Release Operator → Handoff Writer
- `/clear` mellem hver rolle-overgang
- ROLELOCAL: Samme pipeline kan køre på lokal Ollama model

**Scope-regler (fra `02_SCOPE.md`):**
- Scope-ændringer kræver Human Approval Gate + dokumentation i `09_DECISIONS.md`
- v3 bygges rent fra bunden — v2 er kun reference

**Kode-standard (fra `05_CODING_STANDARD.md`):**
- INGEN `innerHTML` til dynamisk indhold — auto-fail i validation
- Brug `createElement()` / `textContent` / `appendChild()`
- Ingen gæt på operationelle targets (porte, paths, model-navne)
- Ingen nye dependencies uden approval
- Stop efter 2 fejlede patching forsøg

**Validering (fra `06_VALIDATION.md`):**
- 7 pre-commit checks: backend syntax, frontend syntax, shell syntax, diff scope, dependencies, schema changes, innerHTML check
- 7 auto-fail ændringer: broad refactor, nye dependencies, schema changes, unapproved visual changes, unscoped deletion, hardcoded targets, direct frontend binding

**Git-policy (fra `15_GIT_POLICY.md`):**
- Local git er source of truth — GitHub push er optional sync
- 4 baseline checks ved fase-start: `git status --short`, `git log --oneline -8`, `git branch --show-current`, `git remote -v`
- En logisk ændring per commit
- `Co-Authored-By: Claude <noreply@anthropic.com>`

**Permission mode (fra `17_PERMISSION_MODE_POLICY.md`):**
- 5 fase-modes: prompt_generation, implementation, validation, commit_release, service_control
- commit_release og service_control kræver ALTID human approval
- 7 stop-and-ask regler

**Offline/local LLM (fra `14_OFFLINE_MODE.md`):**
- Local git er source of truth
- Lokal LLM (Ollama) til agent-driven prompt execution
- Prompt generation og execution med local models kræver IKKE internet
- Ollama service control kræver ALTID human approval

### Sektion 2: Model Selection Decision Tree

```
START: Bruger giver en opgave
│
├─ Er opgaven mekanisk/triviel?
│   Kendetegn: 1-2 filer, veldefineret spec, ingen design-beslutninger
│   └─ BRUG: deepseek-v4-flash:cloud (billigere tokens)
│
├─ Er opgaven kompleks?
│   Kendetegn: multi-fil integration, arkitektur/design, debugging
│   └─ BRUG: deepseek-v4-pro:cloud (nuværende standard)
│
├─ Er miljøet offline?
│   └─ BRUG: Lokal Ollama model (se localmodel.md)
│
└─ HVER GANG et større emne skifter:
   1. Spørg dig selv: "Kan en billigere model løse denne opgave?"
   2. Hvis ja → foreslå model-skift til brugeren
      Eksempel: "Denne opgave er mekanisk. Jeg foreslår deepseek-v4-flash:cloud i stedet for deepseek-v4-pro:cloud. Skift?"
   3. Opdater decision tree i superpowers.md hvis nye modeller tilføjes
```

### Sektion 3: Referencer til søster-filer

```
[[alignmentstructure]]  — Feature-alignment på tværs af projekter
[[gates]]                — Gate-spørgsmål før kritiske operationer
[[localmodel]]           — Regler for lokal Ollama model-brug
```

### Sektion 4: Nuværende model

- **Aktiv model:** deepseek-v4-pro:cloud
- **Billigere alternativ:** deepseek-v4-flash:cloud
- **Lokalt alternativ:** Ollama (qwen36-27b-q4km:latest på cuda0-rtx5090)

---

## `alignmentstructure.md` — Feature-alignment

### Sektion 1: Alignment Matrix

Tabel der tracker hvilke features gælder for hvilke projekter:

| Feature | DPMtF-WebUI (9130) | ENO (9131) | ai-pc-resource-webui-v3 (9123) | Dato |
|---|---|---|---|---|
| Sprog-tabel + dropdown | ✅ | ✅ | ✅ | 2026-06-12 |
| (Fremtidige features tilføjes her) | | | | |

### Sektion 2: Feature Rollout Regler

1. **Når en feature implementeres i DPMtF-WebUI:**
   - Spørg: "Er dette kun en DPMtF-WebUI feature, eller skal den også udrulles til ENO og/eller v3?"
   - Hvis brugeren ikke har specificeret → spørg brugeren
   - Opdater alignment matrix med svaret

2. **Når en feature skal udrulles til flere projekter:**
   - Start med DPMtF-WebUI (father project)
   - Udrul til ENO (første søn-projekt)
   - For v3: stil GATE-V3 først (se gates.md)

3. **Når en feature kun er DPMtF-WebUI:**
   - Dokumenter i alignment matrix med "✅ DPMtF only"

### Sektion 3: Projekt-registre

| Projekt | Port | Repo | Governance |
|---|---|---|---|
| DPMtF-WebUI | 9130 | `/home/svend/DPMtF-WebUI` | Master templates i `docs/governance-templates/` |
| ENO | 9131 | `/home/svend/ENO` | Kopi i `docs/dpmtf/` |
| ai-pc-resource-webui-v3 | 9123 | `/home/svend/ai-pc-resource-webui-v3` | Kopi i `docs/dpmtf/` |

---

## `gates.md` — Gate-spørgsmål

### Sektion 1: Definerede Gates

**GATE-V3:**
```
Spørgsmål: "ai-pc-resource-webui-v3 is our current reference project
for testing the DPMtF prompt compiler. Are you sure you want to modify it?"

Trigger: Når brugeren beder om ændringer i ai-pc-resource-webui-v3
         og ændringen ikke er en governance-template synkronisering.

Konsekvens: Hvis brugeren siger ja → fortsæt.
            Hvis brugeren siger nej → stop, afklar hvad der skal ske i stedet.
```

**GATE-SCOPE:**
```
Spørgsmål: "This change exceeds the current phase scope defined in
02_SCOPE.md. Should we update the scope first?"

Trigger: Når en ændring falder uden for nuværende fase-scope.

Konsekvens: Hvis brugeren siger ja → opdater 02_SCOPE.md + 09_DECISIONS.md først.
            Hvis brugeren siger nej → stop ændringen.
```

**GATE-MODEL:**
```
Spørgsmål: "This task could be done by a cheaper model.
Proposed: [model]. Switch?"

Trigger: Når en opgave vurderes som mekanisk/triviel
         og deepseek-v4-flash:cloud kan løse den.

Konsekvens: Hvis brugeren siger ja → skift model for denne opgave.
            Hvis brugeren siger nej → fortsæt med nuværende model.
```

**GATE-FEATURE-ROLLOUT:**
```
Spørgsmål: "Should this feature also be implemented in ENO?"

Trigger: Når en feature implementeres i DPMtF-WebUI
         og brugeren ikke har specificeret om den skal udrulles.

Konsekvens: Hvis brugeren siger ja → tilføj til alignment matrix,
            implementer i ENO efter DPMtF-WebUI.
            Hvis brugeren siger nej → marker som DPMtF-WebUI only.
```

### Sektion 2: Gate-regler

- Alle gates skal stilles PRÆCIST som defineret — ikke parafraseret
- Brugerens svar dokumenteres i alignmentstructure.md eller 09_DECISIONS.md
- Nye gates kan tilføjes efter behov — opdater denne fil

---

## `localmodel.md` — Lokale model-regler

### Sektion 1: Hvornår lokal model

**Brug lokal Ollama model når:**
1. Miljøet er offline (ingen internetforbindelse)
2. Opgaven er ROLELOCAL — hele rolle-pipelinen kører på lokal LLM
3. Prompt compilation via DPMtF prompt compiler med `suitable_for: local`
4. Brugeren eksplicit beder om lokal model

**Brug cloud model når:**
1. Opgaven kræver kompleks arkitektur/design reasoning
2. Multi-fil integration med mange afhængigheder
3. Internet er tilgængeligt OG opgaven kræver stærkere reasoning
4. Prompt template har `suitable_for: cloud` eller `suitable_for: both`

### Sektion 2: Prompt Compiler Flow

```
1. Vælg prompt template fra DPMtF-WebUI
2. Kald POST /api/prompt-templates/{key}/compile med parametre
3. Tjek suitable_for flag:
   ├─ local  → send kompileret prompt til Ollama
   ├─ cloud  → brug cloud model (deepseek-v4-pro:cloud)
   └─ both   → vælg baseret på decision tree i superpowers.md
4. Eksekver prompt mod valgte model
5. Dokumenter resultat i prompt-runs
```

### Sektion 3: Model-konfiguration

- **Nuværende lokale model:** qwen36-27b-q4km:latest (på cuda0-rtx5090)
- **Model-navne:** Skal være eksplicitte argumenter, ikke hardcodede (fra `05_CODING_STANDARD.md`)
- **Ollama service control:** Start/stop/restart kræver ALTID human approval (fra `17_PERMISSION_MODE_POLICY.md`)
- **Model downloads:** One-time setup, kræver internet første gang (fra `14_OFFLINE_MODE.md`)

### Sektion 4: Opdateringsregler

- Når brugeren refererer til `superpowers.md`, opdateres `localmodel.md` med eventuelle nye regler
- Nye lokale modeller tilføjes her når de tages i brug
- `suitable_for` flag på prompt templates opdateres når nye modeller evalueres

---

## Workflow: Når brugeren refererer til superpowers.md

```
1. LOAD superpowers.md
   ├─ Aggregerede regler aktiveres
   ├─ Model decision tree konsulteres
   └─ Nuværende model identificeres

2. TJEK alignmentstructure.md
   ├─ Hvilke projekter berøres af opgaven?
   ├─ Er feature-rollout specificeret?
   └─ Hvis ikke → stil GATE-FEATURE-ROLLOUT

3. TJEK gates.md
   ├─ Trigger GATE-V3 hvis v3 berøres
   ├─ Trigger GATE-SCOPE hvis scope overskrides
   └─ Trigger GATE-MODEL hvis billigere model kan bruges

4. TJEK localmodel.md
   ├─ Er opgaven egnet til lokal model?
   └─ Brug prompt compiler flow hvis relevant

5. UDFØR opgave
   ├─ Følg aggregerede regler fra superpowers.md
   └─ Dokumenter afvigelser

6. OPDATER .md filer
   ├─ superpowers.md: nye regler, model-ændringer
   ├─ alignmentstructure.md: nye features i matrix
   ├─ gates.md: nye gates hvis nødvendigt
   └─ localmodel.md: nye model-regler
```

---

## Næste prompt fra brugeren

Når brugeren næste gang refererer til `superpowers.md`, skal følgende ske:

1. Start alignment mellem DPMtF-WebUI og ENO:
   - Sammenlign governance templates (DPMtF-WebUI master vs ENO kopi)
   - Synkroniser eventuelle forskelle
   - Opdater alignmentstructure.md med alignment-status
2. Opdater alle 4 .md filer med eventuelle nye regler
