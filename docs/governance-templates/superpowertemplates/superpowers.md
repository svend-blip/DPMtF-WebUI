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

DPMtF-WebUI's `docs/governance-templates/` er den **autoritative kilde** til alle
governance-regler. Andre projekter får kopier via `scripts/initialize_target_project_governance.py`.

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

### Kode-standard (kritiske regler)

- **INGEN `innerHTML` til dynamisk indhold** — auto-fail i validation. Brug `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`
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

**7 auto-fail ændringer:** Broad refactor, nye dependencies, schema changes, unapproved visual changes, unscoped deletion, hardcoded operational targets, direct frontend binding til reusable labels.

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
├─ Er opgaven kompleks?
│   Kendetegn: multi-fil integration, arkitektur/design, debugging
│   └─ BRUG: deepseek-v4-pro:cloud (nuværende standard)
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
| **deepseek-v4-pro:cloud** | Cloud (standard) | Komplekse opgaver, arkitektur, multi-fil |
| **deepseek-v4-flash:cloud** | Cloud (billig) | Mekaniske opgaver, 1-2 filer |
| **qwen36-27b-q4km:latest** | Lokal (Ollama) | Offline, ROLELOCAL, prompt compiler |

---

## 4. Søster-filer

Disse filer ligger i samme mappe og loads efter behov:

| Fil | Indhold | Loades når |
|---|---|---|
| [[alignmentstructure]] | Feature-alignment på tværs af projekter | Feature implementeres eller udrulles |
| [[gates]] | Gate-spørgsmål før kritiske operationer | GATE-trigger rammes |
| [[localmodel]] | Regler for lokal Ollama model-brug | Lokal model overvejes |

---

## 5. Workflow: Når brugeren refererer til superpowers.md

```
1. LOAD superpowers.md (denne fil)
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
   ├─ Følg aggregerede regler
   └─ Dokumenter afvigelser

6. OPDATER .md filer
   ├─ superpowers.md: nye regler, model-ændringer
   ├─ alignmentstructure.md: nye features i matrix
   ├─ gates.md: nye gates hvis nødvendigt
   └─ localmodel.md: nye model-regler
```

---

## 6. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — initiale aggregerede regler, model decision tree, projekt-hierarki |
