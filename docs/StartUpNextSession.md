# Start Up Next Session — DPMtF Development Environment

> **en-US is the standard language for all governance-templates-v2 files.**
> **Review note:** When this file is referenced, verify the current state
> matches what is described here. Check that tmux sessions exist, ports are
> correct, and config values match the current PC. Update this file if the
> situation has changed.

---

## 1. Current Role

You are **Architect / Handoff Writer / Governance Controller** in the
DPMtF governance loop. Your role is defined in
`docs/governance-templates-v2/02_ARCHITECT.md`.

- **Tmux session:** `claude_architect`
- **Model:** `deepseek-v4-pro:cloud` (via Ollama)
- **Tool:** Claude Code (OpenCode config available at
  `~/.config/opencode-roles/architect/opencode.json`)

The Architect designs technical approaches, generates implementation
handoffs, makes architectural decisions for escalations, and maintains
cross-project oversight per 21_ALIGNMENT.md.

---

## 2. Required Files to Read First

Read these files in order to reconstruct full project state:

### Governance Templates (authoritative)
- `docs/governance-templates-v2/02_ARCHITECT.md` — your role definition
- `docs/governance-templates-v2/10_PROJECT.md` — project identity, port, repository
- `docs/governance-templates-v2/11_SCOPE.md` — current phase scope boundaries
- `docs/governance-templates-v2/14_ARCHITECTURE.md` — system architecture
- `docs/governance-templates-v2/99_ROLEINTERACTION.md` — role loop and escalation
- `docs/governance-templates-v2/100_BRIDGE.md` — bridge protocol

### Latest Reports/Verdicts
- `/home/svend/claude-bridge/implementertoreview/current.md` — latest callback
- `/home/svend/claude-bridge/implementertoreview/{latest}-review-verdict.md`
- `/home/svend/claude-bridge/implementertoreview/{latest}-result.md`

### Current Roadmap/Status
- `docs/StartUpNextSession.md` — this file (session startup + current state)

---

## 3. Current Workflow State

| Item | Value |
|------|-------|
| **Last handoff ID** | 104 (completed — Fase 1-3 Hardening committed, branch `hardening/bridgev002-phase1-config`) |
| **Implementer** | `claude_implementer` running **OpenCode 1.17.7** (`ollama/qwen3.6:27b-q4_K_M`) |
| **Review** | `claude_review` running **OpenCode 1.17.7** (`ollama/qwen3.6:27b-q4_K_M`) |
| **Architect** | `claude_architect` running **Claude Code** (`deepseek-v4-pro:cloud`) |
| **Bridge (prod)** | `/home/svend/claude-bridge/bridge.py` |
| **BridgeV002 (dev)** | Under udvikling i `DPMtF/docs/bridgeV002/` og `DPMtF/scripts/bridgeV002/` |

### Completed Spors

| Spor | Handoffs | What |
|------|----------|------|
| **Spor A** | 023-029 | Hardcoding cleanup — config.py foundation, all paths via getters |
| **Spor B** | 030-037 | Prompt Compiler PoC — knowledge fragments, deployment strategy |
| **Spor C** | 038-041 | Accelerated WebUI Factory — skeleton files, init script |
| **Spor D** | 043-046 | Governance Centralization — single source, legacy v1 removed |
| **Spor D-Hardening** | 047-049 | Human commit gate enforced, sequential execution hardened |
| **Spor E** | 051 | Prompt Compiler Hardening — __pycache__ exclusion, socket fix, lazy imports |
| **Spor F** | 052-061 | Prompt Compiler Integration Testing + Bridge Hardening — tool-independent bridge, auto-restart |
| **Spor C-Hardening** | 062, 067 | Skeleton corrections — innerHTML removal, config fixes, revert father governance dir |
| **Spor F5** | 064-066, 068-070, 074-075 | Bridge stabilization — .env loading, ollama reload cycle, auto-restart with detached subprocess |
| **Spor G** | 071, 073, 076-081 | Prompt Compiler Simplificering — 8-field form, dead panel removal, DPMtF cleanup |
| **Spor G-Accelerated** | 086-089 | Accelerated WebUI Factory UI integration — conditional form, create+start endpoints, 10 i18n labels |
| **Spor I** | 092-097 | BridgeV002 Database Integration — INI configs, core library, dispatch scripts, DB schema (3 tables), bridge_lib lookup functions, 5 REST API endpoints under /api/bridge-v2/ |
| **Spor J** | 098-101 | BridgeV002 UI Integration — 7 CRUD endpoints + export (app.py +295), 48 i18n labels da-DK/en-US (init_db.py +282, domain fix `4d3b1ed`), HTML panel skeleton (index.html +27), frontend JS 14 functions (dpmtf-app.js +537). Total ~1.141 lines. Commits `a2fa53b`, `4d3b1ed`. |
| **Hardening F1** | 102 | BridgeV002 Config Infrastructure — `[bridge] base_path` in dpmtf.ini, `get_bridge_base_path()` getter, bridge_lib.py path-resolve fix (eliminate hardcoded fallbacks), .gitignore update. Commit `cef2812`. |
| **Hardening F2** | 103 | BridgeV002 Script Registry — `bridge_scripts` table + CHECK constraint, 3 seed scripts (role_setup, role_teardown, dispatch), GET `/api/bridge-v2/scripts`. Commit `65e7d9f`. |
| **Hardening F3** | 104 | BridgeV002 Convention Rules — `bridge_convention_rules` table, 3 rules (handoff/callback/verdict), ALTER bridge_flow_steps + rule_key FK, map all 11 steps, GET `/api/bridge-v2/conventions`. Commit `dab0dba`. |

### Human Final Verdict

All Spors A-J approved. DPMtF-WebUI is a Prompt Compiler with 8 fields
and an integrated Accelerated WebUI Factory. When Deployment Strategy
"accelerated" is selected, the form switches to a 3-field "Create New
WebUI" flow that runs initialize_new_webui.py and starts the new server.
Bridge is tool-independent with ollama reload and auto-restart. Both
local sessions run OpenCode.

**Spor J (UI Integration):** Full-stack BridgeV002 CRUD UI delivered across 4 handoffs (H98-H101). Test-kørt af Human: alle CRUD-operationer PASS, da-DK sprog-skift fikset ved domain-migration (`bridge_setup` → `main`) i commit `4d3b1ed`.

---

## 4. Active Hard Rules

These rules are **non-negotiable** and enforced through governance files
and bridge mechanics:

| # | Rule | Source |
|---|------|--------|
| 1 | **NO parallel work** — one role active at a time. Bridge enforces with `/clear`. | 99_ROLEINTERACTION.md, 02_ARCHITECT.md |
| 2 | **STOP after handoff** — Architect stops ALL activity after `bridge.py send`. No Monitor, no Bash, no background tasks, no file writes. | 02_ARCHITECT.md §Post-Handoff Stop Rule |
| 3 | **NO split-brain exception** — batch dispatch prohibited. Pre-writing multiple handoff files prohibited. One handoff at a time. | 02_ARCHITECT.md (H3) |
| 4 | **HUMAN COMMIT GATE** — only Human may commit/push. Review prepares, Human authorizes. | 15_GIT_POLICY.md, 04_REVIEW.md (H2) |
| 5 | **Tool-independent governance** — DPMtF governance files are primary authority. OpenCode/Claude Code are runtime adapters. Governance comes from DPMtF prompts and files, not from tool permissions. | OpenCode PoC runbook §0 |
| 6 | **All inter-role communication in English (en-US)** — handoffs, bridge messages, code comments. Human may use Danish but forwarded prompts must be translated. | CLAUDE.md §2, 100_BRIDGE.md |
| 7 | **Implementer NEVER commits** — changes remain unstaged. | 03_IMPLEMENTOR.md (H2) |
| 8 | **Stop after 2 failed patching attempts** — document, escalate, do not guess. | 12_CODING_STANDARD.md |
| 9 | **Tool-independent bridge** — bridge.py auto-detects OpenCode vs Claude Code and uses correct injection method (paste-buffer for OpenCode, send-keys for Claude Code). No tool-specific code paths in governance. | bridge.py (F5a) |
| 10 | **Auto-restart after handoff** — implementer session is killed and restarted with fresh context after each `bridge.py complete`. Configured via `DPMTF_IMPLEMENTER_START_CMD` env var. Prevents context token accumulation. Uses detached subprocess (start_new_session=True) to survive own death. | bridge.py (F5b, F5e, F5f) |
| 11 | **Ollama reload before dispatch** — ollama model is stopped and restarted before each handoff dispatch to ensure fresh server-side context. Configured via DPMTF_OLLAMA_MODEL and DPMTF_OLLAMA_START_SCRIPT in .env. | bridge.py (F5c, F5d) |

---

## 5. Current Next Task

**Spor I + J complete — BridgeV002 database + UI integration operational.**

Hardening plan approved af Human — 6 faser, 17 tasks:

### Hardening Plan Oversigt

(se detaljeret plan: `docs/HardeningPlan`)

| Fase | Titel | Tasks | Status |
|------|-------|-------|--------|
| **Fase 1** | Konfiguration & Infrastructure | dpmtf.ini bridge-sektion, config.py getter, .gitignore, path-resolve | ✅ Komplet (`cef2812`) |
| **Fase 2** | Script Registry | Ny `bridge_scripts` tabel, seed data, API endpoints | ✅ Komplet (`65e7d9f`) |
| **Fase 3** | Convention Rules | Ny `bridge_convention_rules` tabel med templates for dir/pattern/error_msg | ✅ Komplet (`dab0dba`) |
| **Fase 4** | Steps CRUD (backend + frontend) | API endpoints, Flow-card "Manage Steps", form dropdowns, auto-fill fra conventions | ⏳ Ikke startet |
| **Fase 5** | Parameteriserede Script-kald | dispatch.py payload-samling, CLI invocation med argparse, example-scripts | ⏳ Ikke startet |
| **Fase 6** | Database-oprydning & Struktur | Identificér eno.db, ryd H99-backups, .gitignore databases/, backup-strategi | ⏳ Ikke startet |

#### Fase 1: Konfiguration & Infrastructure

| # | Task | Detaljer |
|---|------|----------|
| 1.1 | dpmtf.ini bridge-sektion | `[bridge]` med `base_path = /home/svend/claude-bridge` |
| 1.2 | config.py getter | `get_bridge_base_path()` → returnerer base_path fra ini med fallback til `{PROJECT_ROOT}/claude-bridge` |
| 1.3 | .gitignore opdatering | Tilføj `__pycache__/` (root) og eventuelt bridge-runtime-artefakter |
| 1.4 | bridge_lib.py path-resolve | Alle hardcoded `/home/svend/...` erstattes med `config.get_bridge_base_path()` + relative dir fra steps |

#### Fase 2: Script Registry (ny tabel)

| # | Task | Detaljer |
|---|------|----------|
| 2.1 | Schema | `bridge_scripts` tabel i `init_db.py` |
| 2.2 | Seed data | Eksempel-scripts med script_key, path, stage, params_required |
| 2.3 | API endpoints | `GET /api/bridge-v2/scripts` → dropdown-data til frontend |

#### Fase 3: Convention Rules (ny tabel)

| # | Task | Detaljer |
|---|------|----------|
| 3.1 | Schema | `bridge_convention_rules` med rule_key, step_type, dir_template, pattern_template, error_template |
| 3.2 | Seed data | "handoff", "callback", "verdict" templates |
| 3.3 | API endpoints | GET/POST/PUT/DELETE `/api/bridge-v2/conventions` |
| 3.4 | bridge_flow_steps ALTER | Erstat rå-strings med FK-reference: rule_key istedet for individuelle strings |

#### Fase 4: Steps CRUD (backend + frontend)

| # | Task | Detaljer |
|---|------|----------|
| 4.1 | API endpoints | GET/POST/PUT/DELETE `/api/bridge-v2/steps/{flow_key}` |
| 4.2 | Flow-card "Manage Steps" knap | Modal med step-tabel + inline-form |
| 4.3 | Form dropdowns | from_role, to_role (fra bridge_roles), rule_key (fra conventions), script_keys (fra scripts registry) |
| 4.4 | Auto-fill logic | Ved valg af rule_key auto-fyldes dir/pattern/error fra template |

#### Fase 5: Parameteriserede Script-kald

| # | Task | Detaljer |
|---|------|----------|
| 5.1 | dispatch.py parameter-samling | Saml flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern ved runtime |
| 5.2 | CLI invocation | Kør scripts med argparse-parametre fra payload |
| 5.3 | Eksempel-scripts | Opdater role_setup.py/role_teardown.py til at acceptere nye parametre |

#### Fase 6: Database-oprydning & Struktur

| # | Task | Detaljer |
|---|------|----------|
| 6.1 | Identificér eno.db | Hvad er den? Brug den? Kan slettes? |
| 6.2 | Ryd H99-backups | Slet .bak.h99, .bak.h99v2, .preh99.review |
| 6.3 | .gitignore databases/ | Sørg for dpmtf.db ikke er i git-history (det er runtime-state) |
| 6.4 | Backup-strategi | Definér: automatisk backup før init_db.py? Navngivningskonvention? |

### Hvad skal IKKE være hardcoded (Human krav)

| Felt | Nuværende tilstand | Måltilstand |
|------|-------------------|-------------|
| `deliverable_dir` i steps | Hardcoded strings i init_db.py seed | Beregnet fra convention_rules templates ved runtime |
| `deliverable_pattern` i steps | Hardcoded `{ID}-handoff.md` osv. | Template fra convention_rules |
| `error_msg` i steps | Hardcoded med forkerte navne/referencer | Template: "Failed to deliver {step_type} to {to_role}." |
| `pre_dispatch_script` | NULL alle steder, ingen registry | Dropdown-valg fra `bridge_scripts` tabel |
| `post_dispatch_script` | NULL alle steder, ingen registry | Dropdown-valg fra `bridge_scripts` tabel |
| `base_bridge_path` | Ingen konfiguration — implicit `/home/svend/claude-bridge/` | `[bridge] base_path` i dpmtf.ini + config.py getter |

### Nøgleprinciper (af Human)

1. **BridgeV002 er en del af DPMtF-repo** — scripts versioneres, deliverable-mapper eksterne
2. **Ingen hardcoded data** — alt konfigurerbart via frontend dropdowns og templates
3. **Scripts modtager parametre** — alle 6 params (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern) sendes til scriptet ved kald
4. **Konventioner først** — templates styres via `bridge_convention_rules`, ikke manuelt

Do NOT start hardening work without explicit Human instruction per fase.

---

## 5b. BridgeV002 — Full Stack Complete (Spor I + J)

**Status:** Spor I COMPLETE (handoffs 092-097, commits `52a621c`, `e568fff`, `4d92586`).
Spor J COMPLETE (handoffs 098-101, commits `a2fa53b`, `4d3b1ed`).
Total ~1.141 linjer tilsat kode: konfigurerbar BridgeV002 CRUD UI + backend.

### First Test Results (Human verification)

Human gennemførte manuel test af alle CRUD-operationer:
- **Roles CRUD:** PASS — create, read, update, soft-delete via UI
- **Flows CRUD:** PASS — create, read, update, soft-delete via UI
- **Export:** PASS — export roles og flows til JSON
- **Sprogskift da-DK:** Initially FEJL → fikset ved domain-migration (`bridge_setup` → `main`) i commit `4d3b1ed`. Alle 48 bridge-labels nu på "main" domain, fetches korrekt via `/api/ui-labels/main`
- **Status endpoint:** Initially FEJL (server kørte før Spor I kode) → løst ved server-genstart
- **bridge_flow_steps:** FEJL — alle felter hardcoded via seed data i `init_db.py`. Ingen frontend CRUD for steps. Identificeret som hardening-mål

### Deliverables pr. Spor

| Spor | Phase | Handoffs | commits | Leverbar |
|------|-------|----------|---------|----------|
| **I** | Foundation | 092-094 | `52a621c` | INI configs, bridge_lib.py, dispatch.py, role_setup.py, role_teardown.py |
| **I** | DB Schema | 095 | `e568fff` | 3 SQLite tables + seed data (5 roles, 3 flows, 5 heavy steps) |
| **I** | DB Functions | 096 | `e568fff` | 6 lookup functions i bridge_lib.py — alle parameterized SQL |
| **I** | REST API | 097 | `4d92586` | 5 GET endpoints under `/api/bridge-v2/` |
| **J** | Backend API | 098 | `a2fa53b` | +295 linjer app.py: 7 CRUD endpoints (POST/PUT/DELETE roles+flows) + export |
| **J** | i18n | 099-100 | `4d3b1ed` | +282 linjer init_db.py: 48 labels da-DK/en-US, domain fix |
| **J** | HTML | 100 | — | +27 linjer index.html: panel skeleton med knapper og containere |
| **J** | Frontend JS | 101 | `a2fa53b` | +537 linjer dpmtf-app.js: 14 funktioner (render, create, update, delete, export) |

### Arkitektur (as-built after Spor J)

```
DPMtF-WebUI/
├── app.py                          ← /api/bridge-v2/ endpoints (5 read + 7 CRUD = 12 total)
├── static/js/dpmtf-app.js          ← 14 BridgeV002 funktioner (~537 linjer)
├── templates/index.html            ← Bridge Setup panel med Roles/Flows sektioner
├── scripts/bridgeV002/
│   ├── bridge_lib.py               ← INI + DB lookup functions
│   ├── dispatch.py                 ← Dispatcher (currently INI-based)
│   ├── role_setup.py               ← Start session med korrekt model/tool
│   └── role_teardown.py            ← Kill session + unload model + fri VRAM
├── scripts/init_db.py              ← Schema + seed data + i18n labels
└── databases/
    └── dpmtf.db                    ← bridge_roles, bridge_flows, bridge_flow_steps
```

### Database Schema (3 tabeller)

**bridge_roles** (12 cols): `role_key`, `tmux_session`, `start_cmd`, `model_type`, `cloud_model`, `ollama_model`, `setup_script`, `teardown_script`, `deliver_error_msg`, `is_active`, `created_at`, `updated_at`

**bridge_flows** (8 cols): `flow_key`, `name`, `description`, `step_order`, `is_default`, `is_active`, `created_at`, `updated_at`

**bridge_flow_steps** (13 cols): `id`, `flow_key`, `step_key`, `from_role`, `to_role`, `deliverable_dir`, `deliverable_pattern`, `pre_dispatch_script`, `post_dispatch_script`, `error_msg`, `sort_order`, `is_active`

### Problemer Identificeret under Test — Hardening Krav

**Human krav: INGEN hardcoded data i seed data. Alt skal være konfigurerbart via frontend.**

| Felt | Nuværende | Problem | Løsning |
|------|-----------|---------|---------|
| `deliverable_dir` | Static strings ("reviewtoimplementor") | Ingen template, ingen config | Convention Rules tabel + path resolution fra dpmtf.ini |
| `deliverable_pattern` | Static strings ("{ID}-handoff.md") | Ingen template | Convention Rules tabel med templates |
| `error_msg` | Hand-written med forkerte navne | Referencer "Human" men to_role er "human" | Template: "Failed to deliver {step_type} to {to_role}." |
| `pre_dispatch_script` | NULL alle steder | Ingen script registry, ingen dropdownvalg | Script Registry tabel + dropdown i step-formular |
| `post_dispatch_script` | NULL alle steder | Ingen script registry, ingen dropdownvalg | Script Registry tabel + dropdown i step-formular |
| `base_bridge_path` | Ingen konfiguration | Implicit `/home/svend/claude-bridge/` | `[bridge] base_path` i dpmtf.ini + config.py getter |

### Database-oprydning (identificeret under test)

```
databases/
├── dpmtf.db            ← Aktiv database (648K)
├── dpmtf.db.bak.h99    ← H99 backup 1, ikke længere relevant (596K)
├── dpmtf.db.bak.h99v2  ← H99 backup 2, ikke længere relevant (648K)
├── dpmtf.db.preh99.review ← Pre-review backup, ikke længere relevant (644K)
└── eno.db              ← Ukendt formål — behov for Human-klarifikation
```

### Udviklingsstrategi (uden ændring)

BridgeV002 udvikles og testes via den nuværende bridge. Same workflow:
Architect → Review → Implementer → Human godkendelse.

---

## 6. Stop Condition

Stop ALL activity and wait for Human (Svend) after:

- Dispatching a handoff via `bridge.py send {ID}`
- Completing an escalation response via `bridge.py answer-review {ID}`
- Hitting an ambiguity that requires Human decision (scope, architecture, gates)
- Human explicitly says "stop" or "wait"
- Encountering a governance violation (report to Human, do not continue)

**Do NOT:**
- Start new work without explicit Human instruction
- Poll for results with Monitor or Bash after dispatch
- Pre-write handoff files for future tasks
- Continue working after signaling completion

---

## 7. Tmux Session Setup

### 7.1 Check existing sessions

```bash
tmux list-sessions
# Shorthand:
tmux ls
```

Expected output (all three must exist):
```
claude_architect: 1 windows (created ...)
claude_implementer: 1 windows (created ...)
claude_review: 1 windows (created ...)
```

### 7.2 Create missing sessions

If any session is missing, create it detached:

```bash
# Create all three (detached — no UI yet)
tmux new-session -d -s claude_implementer
tmux new-session -d -s claude_review
tmux new-session -d -s claude_architect
```

Verify with `tmux ls` that all three now exist.

### 7.3 Session purpose

| Session | Role | Tool/Model | Purpose |
|---------|------|------------|---------|
| `claude_implementer` | Implementor (03) | **OpenCode** (`ollama/qwen3.6:27b-q4_K_M`) | Code execution — receives handoffs, writes code |
| `claude_review` | Review (04) | OpenCode 1.17.7 (`ollama/qwen3.6:27b-q4_K_M`) | Validation & dispatch — reviews diffs, prepares commits for Human |
| `claude_architect` | Architect (02) | Claude Code (`deepseek-v4-pro:cloud`) | Design & escalation — designs handoffs |

---

## 8. Bridge Communication Workflow

### 8.1 The 3-Layer Loop

```
claude_architect (design)
    │  writes handoff to reviewtoimplementor/{ID}-handoff.md
    │  signals: bridge.py send {ID}
    ▼
claude_review (dispatch)
    │  validates prompt structure
    │  dispatches: bridge.py send {ID}
    ▼
claude_implementer (execute)
    │  reads handoff, executes task
    │  writes result to implementertoreview/{ID}-result.md
    │  signals: bridge.py complete {ID}
    ▼
claude_review (validate)
    │  reviews diff, runs validation
    │  PREPARES commit for Human approval (does NOT commit/push directly)
    │  escalates to architect if needed: bridge.py ask-architect {ID}
    ▼
claude_architect (escalation target)
    │  answers architectural questions
    │  signals: bridge.py answer-review {ID}
```

### 8.2 Bridge commands

```bash
# ALWAYS set this first:
export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge

# Send handoff from review to implementer:
python3 /home/svend/claude-bridge/bridge.py send {ID}

# Signal completion from implementer to review:
python3 /home/svend/claude-bridge/bridge.py complete {ID}

# Escalate from review to architect:
python3 /home/svend/claude-bridge/bridge.py ask-architect {ID}

# Answer from architect to review:
python3 /home/svend/claude-bridge/bridge.py answer-review {ID}

# Get next available handoff ID:
python3 /home/svend/claude-bridge/bridge.py next-id
```

### 8.3 Bridge directory structure

```
/home/svend/claude-bridge/
├── bridge.py                          # The bridge script
├── trace.log                          # Append-only audit trail
├── .gitignore                         # Ignores current.md, trace.log
├── reviewtoimplementor/               # Handoff files (Architect → Implementer)
│   └── {ID}-handoff.md
├── implementertoreview/               # Results + callbacks (Implementer → Review)
│   ├── {ID}-result.md                 # Implementation result
│   ├── {ID}-notification.md           # Completion notification
│   ├── {ID}-callback.md               # Auto-generated review instruction
│   └── {ID}-review-verdict.md         # Review verdict
├── reviewtoarchitect/                 # Escalation handoffs (Review → Architect)
│   └── {ID}-handoff.md
└── architecttoreview/                 # Escalation responses (Architect → Review)
    └── {ID}-response.md
```

### 8.4 Bridge rules

1. **Sequential only** — one role active at a time. Bridge enforces this with `/clear`.
2. **All 4 functions send `/clear` first** — fixed in handoff 029.
3. **DPMTF_BRIDGE_DIR must be set** — otherwise bridge falls back to `~/.dpmtf/bridge/`.
4. **Bridge is a git repo** — `git log` shows change history. Remote: `github.com:svend-blip/claude-bridge`.

### 8.5 Tool-Independent Bridge (Spor F5)

Bridge.py is now tool-agnostic. It detects the running tool and adapts:

| Tool | Detection | Injection Method | /clear |
|------|-----------|-----------------|--------|
| **OpenCode** | `pane_current_command` contains "opencode" | `tmux load-buffer` + `paste-buffer` with soft-clear preamble | Not sent separately |
| **Claude Code** | `pane_current_command` contains "node" or "claude" | `tmux send-keys` + `Enter` | `/clear` sent first |

**Auto-restart:** After `bridge.py complete`, the implementer session is
automatically killed and restarted with fresh context. Configure via:
```bash
export DPMTF_IMPLEMENTER_START_CMD="<start command>"
```
Current value in `.env`:
```
DPMTF_IMPLEMENTER_START_CMD=OPENCODE_CONFIG_DIR=/home/svend/.config/opencode-roles/implementer OPENCODE_CONFIG=/home/svend/.config/opencode-roles/implementer/opencode.json /home/svend/.opencode/bin/opencode
```

**Ollama reload cycle (F5c/F5d):** Before each dispatch, the ollama model
is stopped (`ollama stop`) and reloaded via `start_ollama_model.sh`. This
ensures fresh server-side context (0 tokens). Configure via:
- DPMTF_OLLAMA_MODEL=qwen3.6:27b-q4_K_M
- DPMTF_OLLAMA_START_SCRIPT=/home/svend/ai-pc-resource-webui-v2/scripts/actions/start_ollama_model.sh

**Auto-restart (F5b/F5e/F5f):** After each `bridge.py complete`, the
implementer session is killed and restarted with fresh client-side context.
Uses a detached subprocess (`start_new_session=True`) to survive the death
of the calling process (which runs inside the session being killed).
Configure via DPMTF_IMPLEMENTER_START_CMD in .env.

---

## 9. Quick Verification After Startup

Run these checks to confirm everything is working:

```bash
# 1. Config loads correctly
cd /home/svend/DPMtF-WebUI
python3 -c "import config; print(config.get_project_root()); print(config.get_bridge_dir())"

# 2. Bridge works
export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
python3 /home/svend/claude-bridge/bridge.py next-id

# 3. Database is intact
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print('Labels:', conn.execute('SELECT COUNT(*) FROM ui_labels').fetchone()[0]); print('Fields:', conn.execute('SELECT COUNT(*) FROM prompt_compiler_fields WHERE is_active=1').fetchone()[0])"

# 4. Tmux sessions exist
tmux ls | grep -E "claude_implementer|claude_review|claude_architect"

# 5. Knowledge fragments intact
find docs/governance-templates-v2/knowledge-fragments -name "*.md" | wc -l
# Must print 10

# 6. App compiles
python3 -m py_compile app.py && echo "✅ app.py OK"
python3 -m py_compile scripts/init_db.py && echo "✅ init_db.py OK"
node --check static/js/dpmtf-app.js && echo "✅ dpmtf-app.js OK"

# 7. Accelerated WebUI Factory endpoints respond
curl -s -X POST http://localhost:9130/api/create-webui/initialize \
  -H "Content-Type: application/json" \
  -d '{"name":"","port":0,"title":""}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ /initialize OK' if d.get('detail') else '❌ FAIL')"
curl -s -X POST http://localhost:9130/api/create-webui/start \
  -H "Content-Type: application/json" \
  -d '{"project_dir":"/tmp/nonexistent","port":9132}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ /start OK' if d.get('detail') else '❌ FAIL')"

# 8. Compiler i18n labels seeded
sqlite3 databases/dpmtf.db "SELECT COUNT(*) FROM ui_text_slots WHERE slot_key LIKE 'lbl_compiler_%';" | xargs -I{} sh -c '[ {} -eq 10 ] && echo "✅ 10 compiler labels" || echo "❌ FAIL: expected 10, got {}"'

# 9. BridgeV002 database tables exist
python3 scripts/bridgeV002/bridge_lib.py | grep -q "Database-backed lookup" && echo "✅ BridgeV002 DB functions work" || echo "❌ FAIL: BridgeV002 tables missing"

# 10. BridgeV002 API endpoints respond (requires running server)
curl -s http://localhost:9130/api/bridge-v2/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ BridgeV002 status OK' if d.get('available') else '❌ FAIL')"
curl -s http://localhost:9130/api/bridge-v2/roles | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ {d[\"count\"]} BridgeV002 roles' if d.get('count', 0) >= 5 else '❌ FAIL')"
curl -s http://localhost:9130/api/bridge-v2/flows | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ {d[\"count\"]} BridgeV002 flows' if d.get('count', 0) >= 3 else '❌ FAIL')"
```

---

## 10. PC-Specific Notes

> **These values apply ONLY to this PC (svend-MS-7D75). Change them when
> moving to another machine. See 300_SETUPINSTRUCTION.md for the full guide.**

| Setting | Value | Where |
|---------|-------|-------|
| Username | svend | System |
| Home directory | /home/svend | System |
| Project root | /home/svend/DPMtF-WebUI | dpmtf.ini |
| Bridge directory | /home/svend/claude-bridge | .env + ~/.bashrc |
| Local model (implementer + review) | qwen36-27b-q4km | CLI flag |
| Cloud model (architect) | deepseek-v4-pro:cloud | CLI flag |
| Ollama endpoint | http://127.0.0.1:11434 | CLI flag |

---

## 11. Related Files

- `docs/governance-templates-v2/03_IMPLEMENTOR.md` — Implementor role definition (OpenCode)
- `docs/governance-templates-v2/04_REVIEW.md` — Review role definition
- [[02_ARCHITECT]] — Architect role definition
- [[300_SETUPINSTRUCTION]] — Full PC migration setup guide
- [[10_PROJECT]] — Project identity
- [[15_GIT_POLICY]] — Git conventions and Human-gated commit rules
- [[14_ARCHITECTURE]] — System architecture
- [[99_ROLEINTERACTION]] — Role loop and handoff rules
- [[100_BRIDGE]] — Bridge protocol details
