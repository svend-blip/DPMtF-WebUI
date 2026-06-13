# Local Model Rules

> **Regler for hvornår og hvordan lokale Ollama modeller bruges.**
> Loades når lokal model overvejes til en opgave.
> Refereret fra [[superpowers]].

---

## 1. Hvornår lokal model

### Brug lokal Ollama model når:

1. **Miljøet er offline** — ingen internetforbindelse tilgængelig
2. **ROLELOCAL** — hele rolle-pipelinen kører på lokal LLM (fra `01_ROLES.md`)
3. **Prompt compiler output** — DPMtF prompt compiler returnerer `suitable_for: local`
4. **Brugeren eksplicit beder om det** — "brug lokal model til dette"

### Brug cloud model når:

1. **Kompleks arkitektur/design** — kræver stærk reasoning på tværs af mange filer
2. **Multi-fil integration** — mange afhængigheder der skal koordineres
3. **Internet er tilgængeligt OG opgaven kræver det** — ikke tving cloud hvis lokal kan klare det
4. **Prompt template har `suitable_for: cloud` eller `suitable_for: both`** — men bemærk: default er nu `local` (ændret 2026-06-13 baseret på data der viser 100% lokal model-brug)

### Afgørelses-flow

```
START: Opgave modtaget
│
├─ Er internet tilgængeligt?
│   ├─ NEJ → BRUG: Lokal Ollama model
│   └─ JA  → fortsæt
│
├─ Kræver opgaven kompleks reasoning?
│   ├─ JA  → BRUG: Cloud model (deepseek-v4-pro:cloud)
│   └─ NEJ → fortsæt
│
├─ Er der en prompt template med suitable_for?
│   ├─ local → BRUG: Lokal Ollama model
│   ├─ cloud → BRUG: Cloud model
│   └─ both  → BRUG: Cloud (default), lokal hvis offline
│
└─ Standard: BRUG cloud model, men overvej lokal hvis opgaven er simpel
```

---

## 2. Prompt Compiler Flow

Når DPMtF-WebUI's prompt compiler bruges til at generere prompts til lokal model:

```
1. VÆLG prompt template fra DPMtF-WebUI
   - Gennemse tilgængelige templates via /api/prompt-templates
   - Filtrer på complexity_tier, suitable_for, capture_source
   - Tjek per-model hitrate via /api/prompt-templates/{key}/hitrate
   - Vælg baseret på opgavetype, complexity tier, og historisk model-performance

2. KOMPILER prompt
   - Kald POST /api/prompt-templates/{key}/compile
   - Send parametre som JSON body
   - Modtag kompileret prompt + suitable_for flag

3. TJEK suitable_for
   ├─ local  → send kompileret prompt til Ollama
   ├─ cloud  → brug cloud model (deepseek-v4-pro:cloud)
   └─ both   → vælg baseret på afgørelses-flow ovenfor

4. EKSEKVER prompt mod valgte model
   - Cloud: brug Claude API / Superpowers
   - Lokal: send til Ollama via API eller CLI

5. DOKUMENTER resultat
   - Gem prompt-run i DPMtF-WebUI's database via POST /api/prompt-runs
   - Obligatoriske felter: execution_status, first_try_success, validation_passed
   - Angiv template_key for at opdatere template- og model-hitrates
   - Registrer success/failure, model brugt, tokens, duration, corrections
```

---

## 3. Model-konfiguration

### Nuværende lokale modeller

| Model | GPU | Brug |
|---|---|---|
| **qwen36-27b-q4km:latest** | cuda0-rtx5090 | Primær lokal model — 27B parametre, Q4KM kvantisering |

### Vigtige regler

- **Model-navne skal være eksplicitte argumenter** — ikke hardcodede i scripts (fra `05_CODING_STANDARD.md`)
- **Ollama service control kræver ALTID human approval** — start/stop/restart af Ollama må IKKE gøres automatisk (fra `17_PERMISSION_MODE_POLICY.md`)
- **Tmux bridge protokol:** Cloud→lokal kommunikation via tmux session `review_claude`. Se [[bridge-protocol]] for fuld workflow, kommando-reference, og handoff fil-format.
- **Model downloads er one-time setup** — kræver internet første gang, derefter offline-brug (fra `14_OFFLINE_MODE.md`)
- **Model state per GPU** — spores i `ollama_card_state` tabellen i v3's database (planlagt, ikke implementeret endnu)

### Tilføjelse af nye lokale modeller

Når en ny lokal model tages i brug:

1. Download modellen via Ollama (kræver internet, human approval)
2. Test modellen med enkle prompts
3. Opdater denne fil med model-info
4. Opdater `suitable_for` flag på relevante prompt templates
5. Dokumenter i DPMtF-WebUI's `10_CHANGELOG.md`

---

## 4. ROLELOCAL — Rolle-pipeline på lokal model

Når hele rolle-pipelinen kører på lokal model (fra `01_ROLES.md`):

```
Analyst (lokal) → Solution Architect (lokal) → Prompt Engineer (lokal)
→ Implementer (lokal) → Validator (lokal)
→ Human Approval Gate → Release Operator (lokal) → Handoff Writer (lokal)
```

**Regler for ROLELOCAL:**
- Samme rolle-flow som cloud — bare med lokal LLM
- Local git er source of truth — ingen GitHub push krævet
- Ingen eksterne API kald uden eksplicit autorisation
- `/clear` mellem hver rolle-overgang — governance docs genindlæses
- Prompt templates med `suitable_for: local` eller `suitable_for: both` bruges
- **Father-Child governance audit gælder også ved lokal model-brug** — Child projects' projekt-specifikke filer skal stadig afspejle deres egen identitet. Følg audit-processen i superpowers.md Sektion 1. Lokal model fritager IKKE fra governance sync ansvar.

---

## 5. Best practices for lokal model prompts (fra ENO-6 erfaring)

Baseret på 3 prompts med first-try success (medium-lav → medium → medium-høj):

1. **Brug XML-lignende sektioner** — `<role>`, `<project>`, `<governance>`, `<task>`, `<scope>`, `<validation>`, `<constraint>`. Den lokale model responderer præcist på struktureret kontekst.
2. **Referér eksplicitte governance-filer** — angiv fulde stier og specifikke sektioner (f.eks. "superpowers.md Sektion 1"). Den lokale model læser og anvender dem korrekt.
3. **Giv konkrete nøgleregler** — ikke generelle "følg governance". Uddrag de 2-4 mest relevante regler og list dem i `<governance>`.
4. **Definér scope med fulde fil-stier** — både tilladte og forbudte filer. Den lokale model overholder scope præcist.
5. **Inkludér selv-validerings-checks** — konkrete verificerings-trin i `<validation>`. Den lokale model kører dem og rapporterer resultater.
6. **ALTID "COMMIT IKKE"** — dette er den kritiske sikkerheds-mekanisme. Giver mulighed for cloud-review før commit.
7. **Start småt, eskaler gradvist** — etablér baseline med simple opgaver før komplekse. Dette validerer prompt-strukturen og opbygger tillid.

---

## 6. Opdateringsregler

Denne fil opdateres når:

1. **Brugeren refererer til `superpowers.md`** — tjek om nye model-regler skal tilføjes
2. **En ny lokal model tages i brug** — tilføj til model-konfiguration
3. **Prompt compiler får nye funktioner** — opdater prompt compiler flow
4. **`suitable_for` flag ændres** på templates — opdater afgørelses-flow
5. **Nye offline-regler** tilføjes til governance templates

---

## 7. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — lokal/cloud afgørelses-flow, prompt compiler flow, model-konfiguration, ROLELOCAL |
| 2026-06-13 | Opdateret — suitable_for default ændret til `local` (100% af 8 analyserede runs bruger lokal model). Prompt compiler flow opdateret med nye API endpoints (template filtering, per-model hitrate, obligatoriske outcome-felter). |
| 2026-06-13 | Dokumenteret 4-lags i18n arkitektur som obligatorisk standard — `ui_text_slots` → `ui_text_slot_labels` → `ui_labels` → `ui_label_translations`. API skal returnere `{slot_key: text}`. Alignment med ENO gennemført. |
| 2026-06-13 | Tilføjet **Father-Child governance audit regel** til ROLELOCAL — lokal model-brug fritager IKKE fra governance sync ansvar. Child projects' projekt-specifikke filer skal stadig afspejle egen identitet. Følg audit-processen i superpowers.md Sektion 1. |
| 2026-06-13 | **ENO-6 Prompt #1 baseline:** qwen36-27b-q4km klarede medium-lav opgave (2 .md filer, dokumentation-only) med first-try success. 8/8 review-checks passeret, 0 rettelser, perfekt scope-compliance. Prompt-struktur med XML-lignende sektioner og eksplicitte governance-referencer fungerede optimalt. |
| 2026-06-13 | **ENO-6 Prompt #2:** qwen36-27b-q4km klarede medium opgave (JS ændring, 19 labelMap→lbl migrationer) med first-try success. 8/8 checks, 0 rettelser, 0 innerHTML, JS syntaks OK. lbl() helper korrekt implementeret. |
| 2026-06-13 | **ENO-6 Prompt #3:** qwen36-27b-q4km klarede medium-høj opgave (DB+API+HTML+CSS+JS, 5 filer, 6 delopgaver) med first-try success. Panel groups fuldt implementeret: migration-fil, endpoints, containers, collapse/expand, i18n labels. Forbedrede migrations-systemet (auto-discover .sql files). Kapabilitets-baseline komplet: medium-lav ✅, medium ✅, medium-høj ✅. Prompt-strukturen med XML-sektioner og eksplicitte governance-referencer er valideret som optimal til lokal model. |
