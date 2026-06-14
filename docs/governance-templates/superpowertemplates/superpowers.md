# Superpowers Governance

> **Hovedindgang for Superpowers-sessioner.** Når brugeren refererer til `superpowers.md`,
> loads denne fil og aktiverer alle aggregerede regler, model decision tree, og
> krydsreferencer til søster-filer.

---

## 1. Projekt-hierarki

| Projekt | Port | Rolle |
|---|---|---|
| **DPMtF-WebUI** | 9130 | **Father project** — governance engine, holder ALLE governance templates |
| **ENO** (Evaluate Next Optimization) | 9131 | Første søn-projekt under alignment |
| **ai-pc-resource-webui-v3** | 9123 | Reference-projekt til test af DPMtF prompt compiler |
| **claude-bridge** | — | Tmux bridge infrastruktur: `bridge.py` med symmetrisk send/complete. 3 tmux sessioner: `claude_architect` (cloud, deepseek-v4-pro), `claude_implementer` (lokal, qwen36-27b-q4km), `claude_review` (cloud, deepseek-v4-flash). |

DPMtF-WebUI's `docs/governance-templates/` er den **autoritative kilde** til alle
governance-regler. Andre projekter får kopier via `scripts/initialize_target_project_governance.py`.

### Father-Child Governance Sync (obligatorisk)

Dette er den **formelle protokol** for hvordan governance-filer vedligeholdes på tværs af
Father og Child projects. Protokollen sikrer at hvert projekt har korrekte governance-filer
der afspejler projektets egen identitet, samtidig med at strukturelle regler forbliver synkroniseret.

#### Fil-klassifikation

| Klassifikation | Filer | Synkronisering | Beskrivelse |
|---|---|---|---|
| **Strukturelle templates** | 01_ROLES, 03_FILE_ACCESS_POLICY, 04_ARCHITECTURE, 05_CODING_STANDARD, 06_VALIDATION, 07_RESTART, 08_TESTPLAN, 09_DECISIONS, 13_VALIDATION_REPORT, 14_OFFLINE_MODE, 15_GIT_POLICY, 16_DATABASE_RUNTIME_STATE, 17_PERMISSION_MODE_POLICY | **Synkroniseret med Father** — opdateres via `initialize_target_project_governance.py` | Regler der gælder ens for alle projekter. Father's version er master. |
| **Projekt-specifikke** | 00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README | **Uafhængige** — hvert Child projekt vedligeholder sin egen version | Indeholder projektets navn, port, repository, fase, historik, og status. SKAL afspejle det enkelte projekts identitet. |

#### Audit-regler

1. **Ved hver superpowers-session:** Tjek at alle Child projects' projekt-specifikke filer afspejler deres egen identitet. Trigger: bruger refererer til `superpowers.md`.
2. **Audit-checkliste per Child project:**
   - `00_PROJECT.md`: Projektnavn, port, repository, formål — matcher projektets faktiske identitet?
   - `02_SCOPE.md`: Fase — matcher projektets faktiske nuværende fase?
   - `10_CHANGELOG.md`: Indeholder projektets egen git-historik — ikke Father's?
   - `11_NEXT_CONTEXT.md`: Afspejler projektets egen status og næste skridt — ikke Father's?
   - `12_IMPLEMENTATION_REPORT.md`: Afspejler projektets seneste implementering — ikke Father's?
   - `README.md`: Er projekt-specifik — ikke en generisk template-index?
3. **Ved discrepancy:** Trigger GATE-GOVERNANCE-SYNC (se [[gates]]).
4. **Strukturelle templates:** Tjekkes for sync-status. Hvis divergeret, trigger GATE-GOVERNANCE-SYNC for at afklare om divergensen er bevidst.

#### Opdateringsproces for projekt-specifikke filer

Når GATE-GOVERNANCE-SYNC bekræfter at et Child project's projekt-specifikke filer skal opdateres:

1. **Læs** Child project's git-historik (`git log --oneline --all`) for at forstå projektets faktiske udvikling.
2. **Opdatér** `00_PROJECT.md` — projektnavn, port, repository, formål, nuværende commit, related projects.
3. **Opdatér** `02_SCOPE.md` — nuværende fase, in/out of scope, constraints, success criteria.
4. **Opdatér** `10_CHANGELOG.md` — erstat Father's historik med Child's egen git-historik, organiseret i faser.
5. **Opdatér** `11_NEXT_CONTEXT.md` — erstat Father's handoff med Child's egen status, fase-progress, remaining work.
6. **Opdatér** `12_IMPLEMENTATION_REPORT.md` — erstat med Child's seneste implementering.
7. **Opdatér** `README.md` — gør projekt-specifik med governance sync noter.
8. **Bevar** strukturelle templates (01, 03-09, 13-17) uændrede — de forbliver synkroniseret med Father.
9. **Dokumentér** opdateringen i Child's `10_CHANGELOG.md` og `11_NEXT_CONTEXT.md`.
10. **Opdatér** `alignmentstructure.md`'s alignment-status sektion hvis relevant.

---

## 2. Aggregerede regelsæt

Komprimeret fra de 19 governance templates. Ved detaljeret opslag, se den enkelte template.

### Proces-regler

- **Rolle-flow:** Analyst → Solution Architect → Prompt Engineer → Implementer → Validator → Human Approval Gate → Release Operator → Handoff Writer
- **`/clear` mellem hver rolle-overgang** — governance docs er source of truth, ikke chat memory
- **ROLELOCAL:** Samme pipeline kan køre på lokal Ollama model. Local git er source of truth. Ingen eksterne API kald uden eksplicit autorisation.
- **Human Approval Gate triggers:** Visuelle frontend ændringer, database schema ændringer, nye dependencies, fjernelse af bruger-synlig funktionalitet, scope ændringer.

### Scope-regler

- Scope-ændringer kræver: dokumenter i `09_DECISIONS.md` → Human Approval Gate → opdater `02_SCOPE.md` → log i Scope Change Log
- v3 bygges rent fra bunden — v2 er kun reference, IKKE kilde til kode
- Nye projekter implementerer rent — "hide-over-delete" er kun tilladt ved migration i eksisterende projekter
- **Panelgrupper er fixed:** Daily, Journals, Reports, Periodic, Setup. Ændringer kræver ny design-specifikation og Human Approval Gate.

### Kode-standard (kritiske regler)

- **INGEN `innerHTML` til dynamisk indhold** — auto-fail i validation. Brug `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`
- **ALLE brugervendte frontend-tekster SKAL bruge `lbl(key, fallback)`** — auto-fail i validation. Ingen hardcodede engelske strenge i DOM-konstruktion. Hver label skal have `ui_labels` + `ui_label_translations` (da-DK + en-US) seed-data. Dette er fast rutine, ikke valgfrit.
- **4-lags i18n arkitektur er obligatorisk:** `ui_text_slots` (slot_key = unik position-ID) → `ui_text_slot_labels` (slot→label mapping) → `ui_labels` (semantisk label med default_text) → `ui_label_translations` (locale-specific tekst). API'et SKAL traversere alle 4 lag og returnere `{slot_key: text}`. Flere slots KAN mappe til samme label. Frontend `data-slot` attributter og `lbl()` kald bruger `slot_key` som nøgle.
- **Ingen gæt på operationelle targets** — porte, paths, model-navne skal være eksplicitte argumenter, ikke hardcodede
- **Ingen nye dependencies** uden Human Approval Gate
- **Stop efter 2 fejlede patching forsøg** — eskaler, gæt ikke videre
- **En logisk ændring per commit** — ikke blandede concerns
- **Targeted edits only** — ingen broad refactor uden for scope
- **Python:** `py_compile` før commit, PEP 8, parameterized SQL queries
- **Shell:** `bash -n` før commit, `set -euo pipefail`, ingen heredocs til kodefiler
- **CSS:** Class-based selectors, temporary hiding med `dpmtf-hidden-phase-X` klasse
- **Markdown:** ATX headings, tabeller konsistente, append-only til CHANGELOG og DECISIONS

### Validering (pre-commit checks)

1. Backend syntax: `python3 -m py_compile app.py`
2. Frontend syntax: `node --check static/js/*.js`
3. Shell syntax: `bash -n <file>`
4. Diff scope review: `git diff --stat`
5. Dependency check: ingen nye i `requirements.txt`
6. Schema change check: ingen `ALTER TABLE`/`CREATE TABLE` uden fase-godkendelse
7. **Frontend innerHTML check:** `grep -RIn "innerHTML"` — skal være `no_innerHTML`
8. **Frontend i18n check:** `grep -RIn '"[A-Z][a-z]' static/js/` — kun `lbl()` fallbacks og CSS klasser, ingen bare bruger-synlige engelske strenge

**8 auto-fail ændringer:** Broad refactor, nye dependencies, schema changes, unapproved visual changes, unscoped deletion, hardcoded operational targets, direct frontend binding til reusable labels, hardcodede engelske frontend-tekster uden `lbl()`.

### Git-policy

- **Local git er source of truth** — GitHub push er optional sync
- **4 baseline checks ved fase-start:**
  1. `git status --short`
  2. `git log --oneline -8`
  3. `git branch --show-current`
  4. `git remote -v`
- **Commit:** `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Forbudt:** Amend published commits, rebase shared history, force-push til master, commit forbidden paths
- **Offline:** Commit lokalt, mark push som pending, sync når online

### Permission mode

- **5 fase-modes:** `prompt_generation`, `implementation`, `validation`, `commit_release`, `service_control`
- **commit_release og service_control** kræver ALTID human approval
- **7 stop-and-ask regler:** Commit/push, destructive commands, service control (inkl. Ollama), credential/auth changes, broad filesystem operations, unclear scope, exceeding policy boundaries

### Offline / Local LLM

- Local git er source of truth — GitHub push er optional sync
- Lokal LLM (Ollama) til agent-driven prompt execution
- Prompt generation og execution med local models kræver IKKE internet
- Ollama service control (start/stop/restart) kræver ALTID human approval
- Model downloads er one-time setup — kræver internet første gang

---

## 3. Model Selection Decision Tree

```
START: Bruger giver en opgave
│
├─ Er opgaven mekanisk/triviel?
│   Kendetegn: 1-2 filer, veldefineret spec, ingen design-beslutninger
│   └─ BRUG: deepseek-v4-flash:cloud (billigere tokens)
│
├─ Er opgaven kompleks? (complexity_tier ≥ 3)
│   Kendetegn: multi-fil integration, arkitektur/design, debugging, schema-ændringer
│   └─ BRUG: deepseek-v4-pro:cloud
│
├─ Har en prompt template historisk bedre performance med en bestemt model?
│   └─ BRUG: modellen med højest rolling_success_rate for denne template
│      (tjek /api/prompt-templates/{key}/hitrate)
│
├─ Er opgaven medium-høj kompleksitet eller lavere? (complexity_tier ≤ 3)
│   Kendetegn: ≤5 filer, veldefineret mønster, dokumentation, mekanisk migration
│   └─ BRUG: Lokal Ollama model (qwen36-27b-q4km:latest)
│      Evidens (2O, 2026-06-14): 9/9 first-try success på tværs af
│      lav (1 fil), medium (1-3 filer), og medium-høj (5 filer) opgaver.
│      Cost: 0 EUR/run vs ~0.02 EUR/run for cloud.
│      Begrænsning: ~55s thinking overhead — langsommere end cloud
│      til produktion, men sufficient til validering og mekaniske opgaver.
│
├─ Er miljøet offline?
│   └─ BRUG: Lokal Ollama model → se [[localmodel]]
│
└─ HVER GANG et større emne skifter:
   1. Spørg dig selv: "Kan en billigere model løse denne opgave?"
   2. Hvis ja → foreslå model-skift til brugeren (GATE-MODEL)
      Eksempel: "Denne opgave er mekanisk. Jeg foreslår deepseek-v4-flash:cloud
      i stedet for deepseek-v4-pro:cloud. Skift?"
   3. Opdater denne decision tree hvis nye modeller tilføjes
```

### Nuværende modeller

| Model | Type | Brug |
|---|---|---|
| **deepseek-v4-pro:cloud** | Cloud (standard) | Komplekse opgaver (tier ≥4), arkitektur, multi-fil integration, design-beslutninger |
| **deepseek-v4-flash:cloud** | Cloud (billig) | Mekaniske opgaver, 1-2 filer, trivielle ændringer |
| **qwen36-27b-q4km:latest** | Lokal (Ollama) | Offline, ROLELOCAL, prompt compiler. **2O evidens (9/9 first-try):** sufficient til opgaver ≤ medium-høj (≤5 filer). 0 EUR cost. ~55s thinking overhead. |

---

## 4. Søster-filer

Disse filer ligger i samme mappe og loads efter behov:

| Fil | Indhold | Loades når |
|---|---|---|
| [[alignmentstructure]] | Feature-alignment på tværs af projekter | Feature implementeres eller udrulles |
| [[gates]] | Gate-spørgsmål før kritiske operationer | GATE-trigger rammes |
| [[localmodel]] | Regler for lokal Ollama model-brug | Lokal model overvejes |
| [[bridge-protocol]] | Tmux bridge: cloud→lokal kommunikation | Cloud model skal sende instruktioner til lokal model |

---

## 5. Workflow: Når brugeren refererer til superpowers.md

```
1. LOAD superpowers.md (denne fil)
   ├─ Aggregerede regler aktiveres
   ├─ Model decision tree konsulteres
   └─ Nuværende model identificeres

2. KØR Father-Child governance audit (OBLIGATORISK — se Sektion 1)
   ├─ Tjek ALLE Child projects' projekt-specifikke filer (00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README)
   ├─ Audit-spørgsmål per Child:
   │  • 00_PROJECT.md: Afspejler projektets faktiske navn, port, repository?
   │  • 02_SCOPE.md: Afspejler projektets faktiske nuværende fase?
   │  • 10_CHANGELOG.md: Indeholder projektets egen git-historik (ikke Father's)?
   │  • 11_NEXT_CONTEXT.md: Afspejler projektets egen status (ikke Father's)?
   │  • 12_IMPLEMENTATION_REPORT.md: Afspejler projektets seneste implementering?
   │  • README.md: Er projekt-specifik?
   ├─ Ved discrepancy → trigger GATE-GOVERNANCE-SYNC (se [[gates]])
   └─ Dokumentér fund i alignmentstructure.md's alignment-status sektion

3. TJEK alignmentstructure.md
   ├─ Hvilke projekter berøres af opgaven?
   ├─ Er feature-rollout specificeret?
   └─ Hvis ikke → stil GATE-FEATURE-ROLLOUT

4. TJEK gates.md
   ├─ Trigger GATE-V3 hvis v3 berøres
   ├─ Trigger GATE-SCOPE hvis scope overskrides
   ├─ Trigger GATE-MODEL hvis billigere model kan bruges
   └─ Trigger GATE-GOVERNANCE-SYNC hvis step 2 fandt discrepancies

5. TJEK localmodel.md
   ├─ Er opgaven egnet til lokal model?
   └─ Brug prompt compiler flow hvis relevant

6. VÆLG prompt template (hvis relevant)
   ├─ Query /api/prompt-templates med complexity_tier og suitable_for filtre
   ├─ Tjek per-model hitrate via /api/prompt-templates/{key}/hitrate
   └─ Vælg template med bedst historisk performance for opgavetypen

7. TJEK bridge-infrastruktur (hvis lokal model involveres)
   ├─ Verificer at tmux sessioner kører (claude_architect, claude_implementer, claude_review)
   ├─ Hvis lokal model skal udføre opgaven → brug [[bridge-protocol]]: bridge.py send/complete
   ├─ cloud→lokal: skriv handoff.md → bridge.py send {ID}
   ├─ lokal→cloud: bridge.py complete {ID} → læs resultat → review
   └─ Alle bridge-handlinger logges i claude-bridge/trace.log (append-only)

8. UDFØR opgave
   ├─ Følg aggregerede regler
   ├─ Brug bridge-protokol hvis lokal model eksekverer
   └─ Dokumenter afvigelser

9. REGISTRER prompt-run
   ├─ POST /api/prompt-runs med obligatoriske outcome-felter
   ├─ Angiv template_key for at opdatere hitrate-statistik
   └─ Dette muliggør data-drevet template-forbedring over tid

10. OPDATER .md filer
   ├─ superpowers.md: nye regler, model-ændringer, governance sync protokol ændringer
   ├─ alignmentstructure.md: nye features i matrix, governance doc-status
   ├─ gates.md: nye gates hvis nødvendigt
   ├─ localmodel.md: nye model-regler
   ├─ bridge-protocol.md: nye kommandoer, fejlscenarier, eller workflow-ændringer
   └─ Child projects' projekt-specifikke filer: hvis GATE-GOVERNANCE-SYNC godkendte opdatering
```

---

## 6. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — initiale aggregerede regler, model decision tree, projekt-hierarki |
| 2026-06-13 | Opdateret — model decision tree: tilføjet per-template hitrate opslag, complexity_tier ≥ 3 threshold for cloud. Workflow: tilføjet template-valg (trin 5) og prompt-run registrering (trin 7). Baseret på 2H redesign og Excel-dataanalyse. |
| 2026-06-13 | Tilføjet obligatorisk i18n-regel — alle brugervendte frontend-tekster SKAL bruge `lbl()` med `ui_labels` + `ui_label_translations` seed-data. Validering udvidet fra 7 til 8 pre-commit checks (nyt check #8: frontend i18n). Auto-fail ændringer udvidet fra 7 til 8. |
| 2026-06-13 | Tilføjet 4-lags i18n arkitektur som obligatorisk standard — `ui_text_slots` → `ui_text_slot_labels` → `ui_labels` → `ui_label_translations`. API SKAL traversere alle 4 lag og returnere `{slot_key: text}`. Alignment med ENO gennemført (DPMtF-WebUI's API rettet til samme flow som ENO). Dokumenteret i 05_CODING_STANDARD.md. |
| 2026-06-13 | Tilføjet **Father-Child Governance Sync protokol** (Sektion 1) — formelle regler for fil-klassifikation (strukturelle vs projekt-specifikke), audit-checkliste per Child project, opdateringsproces for projekt-specifikke filer. Workflow (Sektion 5) opdateret: nyt step 2 (Governance audit) med audit-spørgsmål og GATE-GOVERNANCE-SYNC trigger. Step 9 udvidet med Child project fil-opdatering. Baseret på ENO governance documentation update (ENO-5). |
| 2026-06-14 | **2O baseline data integreret i Model Selection Decision Tree:** Tilføjet lokal model branch — "Er opgaven medium-høj eller lavere? → BRUG Lokal Ollama model". Evidens: 9/9 first-try success (ENO-6: 4 prompts + bridge tests: 2 + 2O: 3 valideringer). Model-tabel opdateret med 2O data. Cost-sammenligning: cloud ~0.02 EUR/run vs lokal 0 EUR. Lokal model begrænsning: ~55s thinking overhead. |
| 2026-06-14 | **Bridge infrastruktur integreret:** claude-bridge tilføjet i projekt-hierarki. Workflow udvidet med step 7 (bridge-infrastruktur check). Søster-fil bridge-protocol.md opdateret til v2 (symmetrisk Python bridge.py). Bridge valideret med 2 tests, trace.log aktiv. |
