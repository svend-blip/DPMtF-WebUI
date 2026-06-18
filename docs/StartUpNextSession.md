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
| **Last handoff ID** | 097 (completed — API endpoints committed `4d92586`) |
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

### Human Final Verdict
All Spors A-G and Spor I approved. DPMtF-WebUI is a Prompt Compiler with 8 fields
and an integrated Accelerated WebUI Factory. When Deployment Strategy
"accelerated" is selected, the form switches to a 3-field "Create New
WebUI" flow that runs initialize_new_webui.py and starts the new server.
Bridge is tool-independent with ollama reload and auto-restart. Both
local sessions run OpenCode.

Spor I committed `4d92586` (API endpoints), `e568fff` (DB schema + lookup functions).
BridgeV002 database foundation is complete: 3 tables (`bridge_roles`, `bridge_flows`, `bridge_flow_steps`),
6 lookup functions in bridge_lib.py, and 5 GET endpoints exposing them via REST.
Awaiting next Spor definition for BridgeV002 UI integration or dispatch migration.

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

**Spor I complete — BridgeV002 database foundation is operational.**

BridgeV002 now has a complete database-backed configuration layer:
- SQLite tables (`bridge_roles`, `bridge_flows`, `bridge_flow_steps`) with seed data for 5 roles, 3 flows, 5 heavy steps
- Database lookup functions in bridge_lib.py (6 new functions, fully backward compatible)
- REST API endpoints under `/api/bridge-v2/` (status, list/get roles, list/get flows)
- All code committed (`e568fff`, `4d92586`) and pushed to GitHub

Next candidates for BridgeV002:
- **Spor J (UI Integration):** Add "Bridge Setup" panel to Prompt Compiler UI — flow editor, role editor, INI export/import using the new REST endpoints
- **Spor K (Dispatch Migration):** Migrate dispatch.py from INI-based `load_role_config()`/`load_flow_config()` to database-backed functions
- **ENO rebuild** — once Prompt Compiler is stable, rebuild ENO with simplified framework
- **Governance validation** — verify all governance templates are valid for bridge flow

Do NOT start new work without explicit Human instruction.

---

## 5b. BridgeV002 — Database Foundation Complete (Spor I)

**Status:** Spor I COMPLETE (handoffs 092-097, commits `52a621c`, `e568fff`, `4d92586`). Kører PARALLEL med eksisterende bridge. Ingen driftsskift før Human beslutter det.

### What Spor I Delivered

| Phase | Handoff | Commit | Deliverable |
|-------|---------|--------|-------------|
| Foundation (H1-H2) | 092-094 | `52a621c` | INI configs (`bridgeV002.ini`, `roles/default.ini`, `flows/heavy.ini`, `flows/simplified.ini`), bridge_lib.py core library, dispatch.py, role_setup.py, role_teardown.py |
| DB Schema (H3) | 095 | `e568fff` | 3 SQLite tables (`bridge_roles` 12 cols, `bridge_flows` 8 cols, `bridge_flow_steps` 13 cols), seed data: 5 roles, 3 flows, 5 heavy steps |
| DB Functions (H4) | 096 | `e568fff` | 6 lookup functions in bridge_lib.py (`_bridgev002_tables_exist`, `load_role_from_db`, `load_flow_from_db`, `list_roles_from_db`, `list_flows_from_db`) — all parameterized SQL, backward compatible with INI functions |
| REST API (H5) | 097 | `4d92586` | 5 GET endpoints under `/api/bridge-v2/`: status, list roles, get role, list flows, get flow with steps — proper 404/500 error handling |

### BridgeV002 Overview

BridgeV002 er et konfigurationsdrevet bridge-system under bygning ved siden af det eksisterende `bridge.py`. Hovedmålet: alle flow-definitioner, roller, scripts og deliverables skal være styres via database — ingen hardkodede rolle-navne i Python.

| Aspect | Eksisterende bridge | BridgeV002 (Spor I status) |
|--------|-------------------|------------------------------|
| Rollesnavne | Hardkodet (`architect`, `implementer` osv.) | Database-backed via `bridge_roles` table + INI fallback |
| Flow-definition | Ingen — manuelt defineret i kode | Database-driven via `bridge_flows` + `bridge_flow_steps` |
| Scripts | Én stor `bridge.py` med alle kommandoer | Small focused scripts (dispatch, setup, teardown) |
| Config placering | Hardcodede stier i Python | SQLite tables seeded by init_db.py, INI fallback |
| REST API | Ingen | 5 endpoints under `/api/bridge-v2/` |
| UI-integration | Ingen | ⏳ Next: Prompt Compiler "Bridge Setup" panel under Setup-gruppen |
| Dispatch migration | — | ⏳ Next: migrate dispatch.py from INI to DB functions |
| Migration | — | Parallel drift; switch til BridgeV002 først når Human beslutter |

### Arkitektur (as-built after Spor I)

```
DPMtF-WebUI/
├── app.py                          ← 5 new /api/bridge-v2/ endpoints (handoff 097)
├── docs/bridgeV002/                ← INI-filer (fallback + reference)
│   ├── flows/
│   │   ├── heavy.ini               ← Full chain: Architect→Implementer→Review1→Review2→Human
│   │   ├── simplified.ini          ← Direct: Implementer→Review (no architect)
│   │   └── escalation.ini          ← Review→Architect escalation path
│   ├── roles/
│   │   └── default.ini             ← Alle roller [role:NAME] sektioner
│   └── bridgeV002.ini              ← Global konfiguration
├── scripts/bridgeV002/             ← Python-scripts (versioneres)
│   ├── dispatch.py                 ← ÉN genanvendbar dispatcher (--from-role, --to-role) [INI-based]
│   ├── role_setup.py               ← Start session med korrekt model/tool
│   ├── role_teardown.py            ← Kill session + unload model + fri VRAM
│   └── bridge_lib.py              ← INI-læsning + 6 DB lookup functions (handoff 096)
├── scripts/init_db.py              ← Schema creation + seed data (handoff 095)
└── databases/
    └── dpmtf.db                    ← bridge_roles, bridge_flows, bridge_flow_steps tables
```

### Database Schema (as built by handoff 095)

**bridge_roles** (12 columns): `role_key`, `tmux_session`, `start_cmd`, `model_type`, `cloud_model`, `ollama_model`, `setup_script`, `teardown_script`, `deliver_error_msg`, `is_active`, `created_at`, `updated_at`

**bridge_flows** (8 columns): `flow_key`, `name`, `description`, `step_order`, `is_default`, `is_active`, `created_at`, `updated_at`

**bridge_flow_steps** (13 columns): `id`, `flow_key`, `step_key`, `from_role`, `to_role`, `deliverable_dir`, `deliverable_pattern`, `pre_dispatch_script`, `post_dispatch_script`, `error_msg`, `sort_order`, `is_active`

### Seed Data (5 roles, 3 flows)

| Role | Session | Model Type |
|------|---------|-----------|
| architect | claude_architect | cloud |
| implementer | claude_implementer | ollama |
| review_heavy1 | claude_review | ollama |
| review_heavy2 | claude_review_2 | ollama |
| reviewer_lite | claude_review_lite | ollama |

**Flows:** `heavy` (5 steps, default), `simplified` (direct implementer→review), `escalation` (review→architect)

### Udviklingsstrategi — Små handoffs via eksisterende bridge

**BridgeV002 udvikles og testes via den nuværende bridge.** Vi bruger ikke BridgeV002 dispatcher endnu. I stedet:

1. **Architect designer** BridgeV002-funktioner som en del af handoffs
2. **Implementer skriver** kode gennem `reviewtoimplementor/{ID}-handoff.md` som ethvert andet spor
3. **Review validerer** at koden overholder governance og bridge-principper
4. **Verdict sendes til Human** for godkendelse som normalt

### Beslutninger der er taget (af Human)

- **Architect-model:** Behold cloud (`deepseek-v4-pro:cloud`) for nu — 0 GB VRAM, ingen ekstra model-skift nødvendigt
- **Placering:** `DPMtF/docs/bridgeV002/` for INI-filer, `DPMtF/scripts/bridgeV002/` for scripts
- **Bridge Setup UI-panel:** Placeres under "Setup"-gruppen i Prompt Compiler med flow-editor, role-editor og INI-export/import
- **VRAM:** Sekventiel kørsel — kun én model i context ad gangen. BridgeV002 dispatcher skal altid kill modtager før start
- **Driftsskift:** Ikke besluttet. Kører videre på eksisterende bridge indtil andet besluttes af Human

### Aktive hard rules der gælder for BridgeV002-udvikling

Samme 11 hard rules som gælder for alt arbejde — ingen nye undtagelser:
- Sekventiel kørsel (reglen #1): Ingen parallelle bridge flows under udvikling
- STOP after handoff (reglen #2): Architect skriver filer og designs scripts, men stopper efter `bridge.py send`
- Målet er at BridgeV002 skal overholde disse rules når det går i drift — ikke at omgå dem under udvikling

### Resten af BridgeV002 (Efter Spor I)

Spor I leverede database-grundlaget. Næste spor:
1. **UI Integration** — Bridge Setup panel der kalder `/api/bridge-v2/` endpoints
2. **Dispatch Migration** — flyt dispatch.py fra `load_role_config()` til `load_role_from_db()`
3. **Full round-trip test** — komplet handoff gennem BridgeV002 dispatcher (valider dispatch.py + role_setup.py + role_teardown.py med DB)

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
