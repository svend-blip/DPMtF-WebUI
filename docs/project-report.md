# DPMtF-WebUI — Projektrapport: Fra Claude Code-assisteret til lokalt selvkørende

**Dato:** 2026-06-12
**Forfatter:** Claude Code (read-only analyse på tværs af tre projekter)
**Projekter analyseret:**
- `/home/svend/DPMtF-WebUI` — father-projekt, governance-motor
- `/home/svend/ai-pc-resource-webui-v2` — reference-implementation (PAUSED)
- `/home/svend/ai-pc-resource-webui-v3` — aktiv migration, 14 faser gennemført

---

## 1. Resumé af nuværende tilstand

### DPMtF-WebUI (father-projektet)

En **governance-first orchestration engine** til lokal AI-drevet projektudvikling. FastAPI + SQLite + vanilla JS. Kører på port 9130. Har gennemført faser 1A-1X (24 faser) og er midt i fase 2A-2K (11 faser, heraf 4 completed: 2A-2D, resten planned).

**Styrker:**
- 19 governance-templates i `docs/governance-templates/` — det fælles udgangspunkt for alle nye projekter
- `initialize_target_project_governance.py` — kopierer templates til nye projekter med `--dry-run` og `--overwrite` sikkerhed
- Database-drevet layout (layout_slots, layout_panels), i18n (ui_labels, ui_label_translations), endpoint-registry, fase-tracking
- Prompt-run templates i `docs/prompt-runs/templates/`
- 4 arkitektur-beslutninger dokumenteret (ADR-6000001 til ADR-6000004)

**Kritiske huller til den fremtidige vision:**
- **Fase 2H (Hitrate Scoring):** Ikke implementeret — databasen har ingen tabeller til at tracke prompt-succesrater
- **Fase 2I (Implementation Pattern Manager):** Ikke implementeret — ingen mekanisme til at genbruge succesfulde implementeringsmønstre
- **Fase 2J (Prompt Template Manager):** Ikke implementeret — templates ligger som statiske Markdown-filer, ikke database-drevne
- **Fase 2K (Local Prompt Compiler):** Ikke implementeret — ingen automatisk generering af prompts fra database-data
- **17_PERMISSION_MODE_POLICY.md** findes kun i v3 — mangler i master-templates
- **Governance-templates er forældede** i forhold til v3's forbedrede versioner (11 af 19 filer er blevet forbedret gennem praktisk brug i v3)

### ai-pc-resource-webui-v2 (reference)

En **produktionsklar operator-konsol** til Svends AI PC. FastAPI + vanilla JS, ingen database, 20 action-scripts (start/stop/prepare), 6 pipelines med action-mapping. Kører på port 9121. Udvikling er PAUSED — fungerer som funktionel reference for v3.

**Læringspunkter til DPMtF-WebUI:**
- Action-script mønstret (set -euo pipefail, idempotens, port-baseret PID-opløsning) er gennemprøvet
- Hardcoded `_ACTION_MAP` i app.py er en sikkerhedsmekanisme der bør generaliseres til database-drevne actions
- Server-side modelopløsning (stop_ollama_model.sh får modelnavn fra backend, ikke frontend) er et sikkerhedsprincip

### ai-pc-resource-webui-v3 (aktiv migration)

En **database-drevet, i18n-komplet, read-only WebUI** under aktiv udvikling. 17 database-tabeller, 24 labels med 48 oversættelser (da-DK + en-US), 6 GET-endpoints, 2 frontend-paneler (System Resources + Pipeline Status). 14 faser gennemført (3C-1 til 3C-14). Kører på port 9123.

**Læringspunkter til DPMtF-WebUI:**
- **Prompt-strukturen udviklet i 3C-14** er en betydelig forbedring: semantiske beskrivelser (ingen linjenumre), dedikerede nøgle-tjek, konkrete valideringskommandoer, "stop before commit"
- **Fase-historikken** (3C-1 → 3C-14) viser at små, afgrænsede faser på 10-15 minutter er den mest effektive arbejdsform
- **Governance-forbedringerne** i v3's docs/dpmtf/ bør tilbageføres til master-templates
- **17_PERMISSION_MODE_POLICY.md** er kritisk infrastruktur — definerer Auto-mode grænser og stop-and-ask regler

---

## 2. Optimeringsanbefalinger: Governance-templates

Følgende forbedringer bør tilbageføres fra v3's `docs/dpmtf/` til DPMtF-WebUI's `docs/governance-templates/`:

### 2.1 Høj prioritet — kritiske huller

| Master-template | v3-forbedring | Handling |
|---|---|---|
| **Mangler helt** | `17_PERMISSION_MODE_POLICY.md` | **Kopiér fra v3 til master.** Definerer Auto-mode, fase-modes, 6 eksplicitte policy-items, 7 stop-and-ask regler. Uden denne kan Auto-mode ikke styres sikkert. |
| `11_NEXT_CONTEXT.md` | Fase-progress-tabel, per-fase filændringstabeller, label-counts, fase-start git-baseline | **Erstat master med v3-versionen.** v3's NEXT_CONTEXT er langt rigere og mere maskin-læsbar. |
| `12_IMPLEMENTATION_REPORT.md` | Permission Mode Compliance sektion, frontend innerHTML check, stop-before-commit | **Tilføj disse sektioner til master.** De er afgørende for Auto-mode governance. |
| `15_GIT_POLICY.md` | Fase-start git-baseline checks (4 obligatoriske kommandoer), baseline-regler | **Erstat master med v3-versionen.** v3's GIT_POLICY er mere operationel. |

### 2.2 Mellem prioritet — forbedringer fra praktisk brug

| Master-template | v3-forbedring | Handling |
|---|---|---|
| `00_PROJECT.md` | Runtime-kommando, kendte porte, related projects tabel | **Tilføj runtime-kommando og port-tabel som standardfelter.** |
| `02_SCOPE.md` | Default constraints (DPMtF WebUI), scope change log | **Tilføj default constraints og change log.** |
| `04_ARCHITECTURE.md` | i18n fire-lags arkitektur detaljeret, komponent-tabel | v3's version er mere komplet. **Flet forbedringer ind.** |
| `05_CODING_STANDARD.md` | "No fixed line numbers in prompts"-regel, innerHTML-regler uddybet | **Tilføj disse regler.** De er lært gennem hård erfaring. |
| `07_RESTART.md` | `/clear` reconstruction rules, common failure modes | v3's version er mere operationel. **Flet ind.** |
| `10_CHANGELOG.md` | Eksempel-entries (tom i master) | **OK som den er** — entries kommer med brug. |
| `16_DATABASE_RUNTIME_STATE.md` | v3 har 17 tabeller dokumenteret; master har 15 | **Opdater master med v3's tabel-dokumentation som reference-arkitektur.** |
| `README.md` (index) | v3 har en docs/dpmtf/README.md | **Tilføj til master.** Giver overblik over alle templates. |

### 2.3 Lav prioritet — kan vente

| Fil | Status |
|---|---|
| `01_ROLES.md` | Identisk i master og v3. **OK.** Bør opdateres med "combined prompt"-rolle når DPMtF-WebUI kan generere prompts. |
| `03_FILE_ACCESS_POLICY.md` | Identisk. **OK.** |
| `06_VALIDATION.md` | Identisk. **OK.** Bør have "slot/key existence check" tilføjet (lært fra 3C-14). |
| `08_TESTPLAN.md` | Identisk. **OK.** |
| `09_DECISIONS.md` | Identisk. **OK.** |
| `13_VALIDATION_REPORT.md` | Identisk. **OK.** |
| `14_OFFLINE_MODE.md` | Identisk. **OK.** |

---

## 3. Vejen til minimal menneskelig involvering

### 3.1 Nuværende flaskehalse

Dagens workflow kræver menneskelig indgriben ved:

1. **Hver fase-start:** Svend skal paste et prompt (som jeg har genereret)
2. **Human Approval Gate:** Ved visuelle ændringer, schema-ændringer, nye dependencies
3. **Commit/push:** Altid manuel godkendelse
4. **Service control:** Start/stop af servere kræver manuel godkendelse
5. **Mellem faser:** `/clear` og kontekst-rekonstruktion

### 3.2 Reduktionsstrategi

**Fase 1: Prompt-generering fra database (DPMtF-WebUI faser 2H-2K)**

Når DPMtF-WebUI har:
- **Hitrate Scoring (2H):** Database-tracker succes/failure per prompt. Tabeller: `prompt_runs` (run_id, prompt_template_id, phase_key, success, duration, error_log), `prompt_hitrates` (template_id, rolling_success_rate, total_runs, last_updated).
- **Implementation Pattern Manager (2I):** Gemte mønstre fra succesfulde faser. Hver gang en fase som 3C-14 lykkes, gemmes mønstret (hvilke filer blev ændret, hvilke valideringskommandoer blev brugt, hvilke constraints gjaldt).
- **Prompt Template Manager (2J):** Database-drevne templates med variable felter. Erstat de statiske Markdown-templates med database-rækker der kan parametriseres.
- **Local Prompt Compiler (2K):** Samler et prompt fra: (a) et valgt template, (b) hitrate-data der viser hvilke parametre der historisk virker, (c) det aktuelle projekts governance-filer.

**Fase 2: Auto-mode udvidelse**

Når prompt-generering er database-drevet:
- Prompt Engineer rollen kan køre uden Claude Code (mig) — DPMtF-WebUI's Local Prompt Compiler genererer promptet
- Implementer rollen kører i en separat Claude Code session med lokal model
- Validator rollen kører automatisk (alle checks er script-baserede)
- Human Approval Gate reduceres til kun: første gang en ny action-type køres, schema-ændringer, dependency-ændringer

**Fase 3: Lokal model overtager**

- Claude Code session med lokal Ollama-model (qwen36-27b eller tilsvarende) kører Implementer og Validator rollerne
- Min rolle (Claude Code cloud) reduceres til: arkitektur-design, kompleks fejlfinding, governance-vedligeholdelse
- DPMtF-WebUI's prompt-compiler genererer prompts baseret på hitrate-data — den ved hvilke prompt-mønstre der historisk giver succes

### 3.3 Målbillede

```
DPMtF-WebUI (port 9130)
├── Prompt Compiler: vælger template → parametriserer fra governance → genererer prompt
├── Hitrate Database: tracker succes/failure → vægter templates
├── Action Engine: eksekverer prompts via lokal Claude Code session
└── Governance Engine: vedligeholder templates, faser, beslutninger

Lokal Claude Code session (Ollama model)
├── Læser prompt fra DPMtF-WebUI
├── Implementerer i target-projekt
├── Validerer automatisk
└── Rapporterer tilbage til DPMtF-WebUI (hitrate-data)

Svends rolle:
├── Definerer nye faser (hvad skal bygges næste gang?)
├── Godkender schema-ændringer og nye dependencies
├── Committer/pusher (eller delegerer når tillid er opbygget)
└── Reviewer visuelle ændringer
```

---

## 4. Platform-uafhængighed (Windows/Linux)

### 4.1 Nuværende status

ADR-6000003 ("linux_first_platform_adapter_design") fastslår princippet: Linux-først, men undgå hardcoding af platform-specifik adfærd.

### 4.2 Konkrete anbefalinger

| Område | Linux (nu) | Windows (fremtid) |
|---|---|---|
| **Shell scripts** | Bash scripts i `scripts/actions/` | PowerShell scripts eller Python-baserede actions |
| **Sti-separatorer** | `/` hardcodet i config_json | Brug `os.path.join` / `pathlib` i backend |
| **Process detection** | `ss`, `pgrep`, `/proc` | `netstat`, `tasklist`, WMI |
| **GPU queries** | `nvidia-smi` | `nvidia-smi` (findes på Windows) eller DXGI |
| **Port killing** | `fuser -k` | `netstat -ano` + `taskkill` |
| **Database** | SQLite (platform-uafhængig) | SQLite (ingen ændring nødvendig) |
| **Python runtime** | `/home/svend/.local/bin/uvicorn` | `python -m uvicorn` eller venv |

**Anbefalet arkitektur:**
- Backend abstraherer platform-specifikke operationer bag en `PlatformAdapter` klasse
- `config.py` eller `defaults.json` definerer platform-specifikke kommandoer
- Service actions i databasen får et `platform` felt så Windows/Linux actions kan sameksistere
- Seed-scripts er allerede platform-uafhængige (Python + SQLite)

---

## 5. Transition fra Claude Code (cloud) til lokal model

### 5.1 Hvad Claude Code (cloud) gør i dag

- Læser governance-filer og forstår kontekst
- Designer implementeringsplaner
- Genererer prompts med præcise constraints og valideringskommandoer
- Validerer ændringer (syntax checks, diff scope, innerHTML, etc.)
- Skriver governance-opdateringer (CHANGELOG, NEXT_CONTEXT, IMPLEMENTATION_REPORT)

### 5.2 Hvad der kan flyttes til lokal model

| Opgave | Cloud (mig) i dag | Lokal model i morgen | Forudsætning |
|---|---|---|---|
| **Prompt-generering** | Jeg skriver promptet manuelt | DPMtF-WebUI's Local Prompt Compiler | Fase 2J+2K implementeret |
| **Implementering** | Jeg kører i Auto-mode | Lokal Claude Code session med Ollama | Promptet er præcist nok |
| **Validering** | Jeg kører checks | Automatiske scripts (samme checks) | Allerede script-baserede |
| **Governance-opdatering** | Jeg skriver CHANGELOG mv. | Lokal model følger template | Templates er database-drevne |
| **Fejlfinding** | Jeg analyserer fejl | Lokal model + hitrate-data foreslår fixes | Hitrate-database findes |
| **Arkitektur-design** | Jeg designer | Forbliver cloud (kompleks kontekst) | - |

### 5.3 Transition-strategi

1. **Byg DPMtF-WebUI's hitrate-infrastruktur først** (fase 2H-2K). Uden hitrate-data kan den lokale model ikke vælge effektive prompt-mønstre.
2. **Kør parallelle sessioner:** En cloud-session (mig) og en lokal session kører samme prompt. Sammenlign resultater. Brug dette som hitrate-ground-truth.
3. **Graduel overgang:** Start med at den lokale model kun kører Implementer-rollen. Cloud forbliver Architect + Validator. Udvid lokal ansvar efterhånden som hitrate-data akkumuleres.
4. **Internet-uafhængighed:** Når DPMtF-WebUI kan generere prompts og den lokale model kan implementere, er systemet fuldt offline-kapabelt. GitHub push forbliver optional sync.

---

## 6. Transition af validation og git-hub push til DPMtF-WebUI

### 6.1 Validation i dag

Jeg kører 7+ pre-commit checks manuelt i hver fase:
- `python3 -m py_compile`, `node --check`, `bash -n`
- `git diff --stat`, `grep -RIn "innerHTML"`, `grep -RIn "@app\.\(post\|put\|delete\)"`
- Dedikerede nøgle-tjek (f.eks. `slot_pipeline_required_list` must NOT appear)

### 6.2 Validation som DPMtF-WebUI feature

DPMtF-WebUI bør have:
- En **`validation_rules`** tabel i databasen: `rule_key`, `command`, `expected_output`, `severity` (error/warning), `applies_to` (python/js/shell/all)
- En **`validation_runs`** tabel: `run_id`, `phase_key`, `timestamp`, `overall_verdict`, `triggered_by`
- En **`validation_results`** tabel: `run_id`, `rule_key`, `passed`, `actual_output`, `notes`
- Et `/api/validate` endpoint der kører alle relevante rules mod det aktuelle projekt og returnerer en struktureret rapport
- Dette gør validation **fuldt automatiseret** — ingen menneskelig indgriben nødvendig

### 6.3 Git-hub push som DPMtF-WebUI feature

- En **`git_sync_status`** tabel: `project_key`, `unpushed_commits`, `last_push_timestamp`, `last_push_success`
- En **`git_operations`** tabel: `operation_id`, `project_key`, `operation_type` (commit/push), `timestamp`, `success`, `error_log`
- `/api/git/status` endpoint: returnerer sync-status for et projekt
- `/api/git/push` endpoint: pusher hvis online, markerer som pending hvis offline
- Commit forbliver manuel (Human Approval Gate) indtil tillid er opbygget

---

## 7. Anbefalet implementations-rækkefølge for DPMtF-WebUI

### Blok 1: Governance-template opgradering (1-2 sessioner)

1. Kopiér `17_PERMISSION_MODE_POLICY.md` fra v3 til master-templates
2. Opgradér `11_NEXT_CONTEXT.md`, `12_IMPLEMENTATION_REPORT.md`, `15_GIT_POLICY.md` fra v3's forbedrede versioner
3. Tilføj `README.md` (index) til master-templates
4. Opdatér `05_CODING_STANDARD.md` med "no fixed line numbers" og innerHTML-regler
5. Tilføj "slot/key existence check" til `06_VALIDATION.md`

### Blok 2: Prompt-infrastruktur (3-5 sessioner)

6. **Fase 2H — Hitrate Scoring:** Design og implementer `prompt_runs` + `prompt_hitrates` tabeller, seed-script, API-endpoints
7. **Fase 2I — Implementation Pattern Manager:** Design og implementer `implementation_patterns` tabel, capture-mekanisme fra succesfulde faser
8. **Fase 2J — Prompt Template Manager:** Migrér statiske templates til database-drevne, parametriserbare templates
9. **Fase 2K — Local Prompt Compiler:** Byg prompt-samler der kombinerer template + hitrate-data + governance-kontekst

### Blok 3: Automatisering (2-3 sessioner)

10. **Validation Automation:** `validation_rules` + `validation_runs` + `validation_results` tabeller, `/api/validate` endpoint
11. **Git Sync Management:** `git_sync_status` + `git_operations` tabeller, `/api/git/status` + `/api/git/push` endpoints
12. **Platform Adapter Framework:** `PlatformAdapter` base class, Linux implementation, Windows stub

### Blok 4: Lokal model integration (2-3 sessioner)

13. **Local Claude Code Session Manager:** Start/stop/monitor lokal Claude Code session via Ollama
14. **Prompt → Implementering → Validering loop:** DPMtF-WebUI genererer prompt → lokal session implementerer → automatisk validering → hitrate opdateres
15. **Parallel-kørsel test:** Samme prompt køres i cloud (mig) og lokal model — resultater sammenlignes

---

## 8. Øvrige overvejelser for den perfekte lokale model

### 8.1 Model-valg

- **Nuværende:** `qwen36-27b-q4km:latest` på CUDA0-RTX5090 (defineret i `ollama_model_defaults`)
- **Overvejelser:** 27B parametre kvantiseret til 4-bit er en god balance mellem kapacitet og VRAM-forbrug på et 5090 (32 GB). Til prompt-generering og implementering af små faser er dette tilstrækkeligt.
- **Hitrate-tracking bør inkludere model-version:** Samme prompt kan give forskellige resultater med forskellige modeller. Dette er værdifuld data.

### 8.2 Prompt-struktur til lokale modeller

Lokale modeller har kortere kontekstvinduer og mindre "forståelse" end cloud-modeller. Prompts skal være:
- **Mere eksplicitte:** Ingen implicitte antagelser om hvad modellen "bør vide"
- **Mere strukturerede:** Flere sektioner, klarere afgrænsning
- **Mindre kontekst-tunge:** Færre governance-filer at læse, mere præcise henvisninger
- **Selvvaliderende:** Promptet inkluderer sine egne valideringskommandoer (som 3C-14 mønstret)

### 8.3 Kontinuerlig læring

- **Hitrate-data skal vægte templates:** Templates der historisk giver >80% success rate promoveres; templates der giver <50% success rate demoveres eller markeres til revision
- **Prompt-diffing:** Når et prompt fejler, skal DPMtF-WebUI kunne analysere *hvad* der gik galt (syntax error? scope violation? missing file?) og foreslå template-justeringer
- **Cross-project learning:** Hitrate-data fra ai-pc-resource-webui-v3 bør informere templates til fremtidige projekter

### 8.4 Sikkerhed ved lokal autonomi

- **Første gang en action-type køres:** Kræv Human Approval Gate (mønsteret fra 17_PERMISSION_MODE_POLICY)
- **Schema-ændringer:** Altid Human Approval Gate, uanset hitrate
- **Commit/push:** Start med Human Approval Gate; automatiser når hitrate for commit-validation >95% over 20+ runs
- **Service control (start/stop):** Start med Human Approval Gate; automatiser for idempotente scripts med verificeret sikkerhedsprofil

---

## 9. Konklusion

DPMtF-WebUI har et solidt fundament: governance-templates, database-drevet arkitektur, og en gennemprøvet prompt-loop gennem 14 faser i v3. De kritiske huller er:

1. **Governance-templates skal opgraderes** med læring fra v3 (11 filer er forbedret, 1 fil mangler helt)
2. **Hitrate-infrastruktur skal bygges** (fase 2H-2K) — dette er forudsætningen for al automation
3. **Validation og git-sync skal automatiseres** som DPMtF-WebUI features
4. **Platform-abstraktion skal designeres** nu, implementeres gradvist

Med disse fire blokke på plads kan DPMtF-WebUI transitionere fra at være afhængig af Claude Code (cloud) til at køre selvkørende med lokal model — og dermed opfylde visionen om minimal menneskelig involvering, internet-uafhængighed, og database-drevne, hitrate-optimerede prompts til nye WebUI-projekter.

---

*Denne rapport er skrevet som read-only analyse. Ingen filer er ændret i nogen af de tre projekter.*
