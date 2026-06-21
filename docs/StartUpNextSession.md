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

The Architect designs technical approaches, generates implementation
handoffs, makes architectural decisions for escalations, and maintains
cross-project oversight per 21_ALIGNMENT.md.

> **Note:** Session name, model, and tool assignments are managed by the
> BridgeV002 no-kill dispatch protocol (see §4, Rule 12). Do not hardcode
> them here — they live in `bridge_roles` (database) and are resolved at
> runtime by `bridge_lib.load_role_from_db()`.

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
| **Last handoff ID** | 138 (completed — H138 signal-send, full legacy bridge.py independence achieved, branch `hardening/bridgev002-phase1-config`) |
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
| **Hardening F4** | 105 | BridgeV002 Steps CRUD — 4 backend endpoints (GET list, POST create, PUT update, DELETE soft-delete), frontend Steps panel with flow selector + step cards + inline form w/ dropdowns, convention auto-fill logic. 6 new i18n labels (LBL-1000277-LBL-1000282). ~577 lines across 4 files. Commit `729b3a5`. |
| **Hardening F5** | 108 | BridgeV002 Parameteriserede Script-kald — dispatch.py DB-driven path, payload builder, CLI converter, parameterised script calls. Commit `bb27ab3`. |
| **Hardening F6** | 109 | BridgeV002 Database-oprydning & Struktur — eno.db removed, H99 backups cleaned, .gitignore `databases/*.db`, dpmtf.db untracked from git, BACKUP-STRATEGY.md documented. Initial REJECTED → rework → APPROVED. Commit `abab50d`. |
| **Hardening UX** | 110 | BridgeV002 UX Flow↔Steps Integration — Manage Steps button on Flow cards, step count badge replacing read-only steps table, backend `all_steps` flat array with `flow_key` annotation, auto-select first flow on load, "View All Steps" export button. 4 subtasks, APPROVED første gang. Commit `e0aa8f8`. |
| **Hardening H111** | 111 | BridgeV002 No-Kill Phase 1 — dispatch control flow restructure: remove kill/start/reload from run_flow_step_db(), add session_alive() + post-dispatch offload (~47 lines) |
| **Hardening H112** | 112 | BridgeV002 No-Kill Phase 2 — prompt_template enrichment in convention_rules + dispatch integration: ALTER TABLE, verdict_feedback convention with StartUpNextSession.md reference |
| **Hardening H113** | 113 | BridgeV002 Phase 3 — first post-dispatch script archi01-imple01.py in scripts/bridgeV002/ |
| **Hardening H114** | 114 | Post-dispatch common refactoring: archi01-imple01.py → post-dispatch-common.py, convention-agnostic post-dispatch for all 4 heavy flow steps; role reactivation upsert logic replacing hard 409; convention autofill condition guard + delete step JSON-parse fix |
| **Hardening H116** | 116 | GET list_steps filters inactive + DELETE row_factory — fixed `is_active=1` filter removal and sqlite3.Row on DELETE. Commit `7e94c25`. |
| **Hardening H117** | 117 | Step & Flow hard-delete consistency — all steps delete permanently (hard), GET removes is_active filter, CREATE auto-reactivates roles, DELETE flow checks step count first + hard-deletes. Commit `e43f0d2`. |
| **Hardening H118** | 118 | start_tmuxflow.py — script that creates missing tmux sessions per flow key; POST /api/bridge-v2/flows/{flow_key}/start-tmux endpoint; frontend "Start tmux" button on all flow cards; i18n labels lbl_bridge_start_tmux + lbl_bridge_starting. Commit `60b8b71`. |
| **Hardening H119** | 119 | BridgeV002 start-coding — POST /api/bridge-v2/flows/{flow_key}/start-coding endpoint; scripts/bridgeV002/start_coding.py (execute start_cmd for all roles in a flow); frontend "Start code interface" button; dedup by role_key, ordered by sort_order. +174 lines. Commit `6a8b6a7`. |
| **Hardening H120** | 120 | BridgeV002 stop-tmux — POST /api/bridge-v2/flows/{flow_key}/stop-tmux endpoint; scripts/bridgeV002/stop_tmuxflow.py (kill all tmux sessions for a flow via `tmux kill-session -t`); frontend "Stop tmux" button (dpmtf-btn-danger) with confirm dialog. +130 lines. Commit `ae6d3db`. |
| **Hardening H121** | 121 | BridgeV002 fix: start-tmux endpoint parsing bug — removed broken JSON-parsing of stdout response in start_tmux_for_flow endpoint (result.stdout contained "Done: N session(s) created" not JSON). +1 line cleanup. Commit `6b4179c`. |
| **Hardening H123** | 123 | BridgeV002 attach-tmux — POST /api/bridge-v2/flows/{flow_key}/attach-tmux endpoint; scripts/bridgeV002/attach_tmux.py (open terminal tabs for each flow session); frontend "Attach tmux" button; auto-detect terminal (xfce4-terminal → gnome-terminal → x-terminal-emulator). DELETE flow bugfix: res.text() → error before JSON parse. +87 lines JS + new script. Commit `a2745f9`. |
| **Hardening H131** | 131 | BridgeV002 DB-driven callbacks — 7 new columns across 4 tables (auto_complete_enabled, auto_chain_to_next, validation_required, restart_policy, content_template, validation_schema, rule_type), convention seeds for callback/handoff/verdict templates, resolve_content_template_from_db() + validate_deliverable_against_schema() in bridge_lib.py, PATCH /api/bridge-v2/conventions endpoint, Convention admin UI with textareas, auto_complete checkbox on Flow cards, auto_chain/validation checkboxes on Step forms. 7 DB columns, 6 files changed (~935 lines). Commit `916cfe1`. |
| **Hardening H132** | 132 | BridgeV002 eliminate ALL tmux kill/start — remove kill-session from role_teardown.py, remove all tmux lifecycle from role_setup.py, delete kill_session()/start_session() functions and calls from dispatch.py, drop restart_policy column/labels/UI. Only ollama stop/pull remains. 5 files changed. |
| **Hardening H134** | 134 | BridgeV002 eliminate remaining tmux kill/start from stop_tmuxflow.py + start_tmuxflow.py — replace stop_sessions() with session inspection + ollama unload, replace create_missing_sessions() with inspection + ollama preload. Zero tmux lifecycle calls remain in ALL bridgeV002 Python files. 2 files changed. |
| **Hardening H136** | 136 | BridgeV002 signal-complete: replace legacy bridge.py cmd_complete() — callback dispatch via signal_complete(), DB-driven with convention content_template, tool-aware injection, VRAM cleanup, symlink update, trace logging. Commit `cad6295`. |
| **Hardening H137** | 137 | BridgeV002 signal-escalation + signal-answer: replace legacy cmd_ask_architect()/cmd_answer_review() — DB-driven role-aware escalation supporting multiple review roles (review01, review02). Commit `955a256`. |
| **Hardening H138** | 138 | BridgeV002 signal-send: replace legacy cmd_send() — initial handoff dispatch with 10-step sequential dispatch, XML section validation, model stop+reload for clean context, convention template resolution. Commit `60250bb`. |

### Human Final Verdict

All Spors A-J approved. DPMtF-WebUI is a Prompt Compiler with 8 fields
and an integrated Accelerated WebUI Factory. When Deployment Strategy
"accelerated" is selected, the form switches to a 3-field "Create New
WebUI" flow that runs initialize_new_webui.py and starts the new server.
Bridge is tool-independent with ollama reload and auto-restart. Both
local sessions run OpenCode.

**Spor J (UI Integration):** Full-stack BridgeV002 CRUD UI delivered across 4 handoffs (H98-H101). Test-kørt af Human: alle CRUD-operationer PASS, da-DK sprog-skift fikset ved domain-migration (`bridge_setup` → `main`) i commit `4d3b1ed`.

**No-Kill Decision (2026-06-20):** BridgeV002 dispatch protocol shifts from pre-dispatch kill+restart to post-dispatch ollama stop. Tmux sessions become persistent; server-side context cleared by model offload. 85-90% of existing code reused unchanged (~47 lines modified). Architect cross-cycle state preserved via this file's save-state mechanism (§5b.5). Analysis: `~/Dokumenter/Bridgeflowfuture/ReuseMostParts.md`.

**Full Legacy Independence (2026-06-21):** BridgeV002 now replaces ALL 4 legacy bridge.py kernel functions (send, complete, ask-architect, answer-review) with DB-driven equivalents (`signal_send`, `signal_complete`, `signal_escalation`, `signal_answer`). Legacy `claude-bridge/bridge.py` is functionally superseded. BridgeV002 CLI:
```bash
# Initial handoff dispatch (replaces bridge.py send):
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-send --from-role review01 --to-role imple01

# Signal completion (replaces bridge.py complete):
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-complete --from-role imple01

# Escalation to architect (replaces bridge.py ask-architect):
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-escalation --from-role review01 --to-role archi01

# Architect answer back to review (replaces bridge.py answer-review):
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-answer --from-role archi01 --to-role review01
```

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
| 10 | **Auto-restart after handoff** — implementer session is killed and restarted with fresh context after each `bridge.py complete`. Configured via `DPMTF_IMPLEMENTER_START_CMD` env var. Prevents context token accumulation. Uses detached subprocess (start_new_session=True) to survive own death. NOTE: This applies to the legacy bridge only; BridgeV002 no-kill mode (Rule 12) does not kill sessions. | bridge.py (F5b, F5e, F5f) |
| 11 | **Ollama reload before dispatch** — ollama model is stopped and restarted before each handoff dispatch to ensure fresh server-side context. Configured via DPMTF_OLLAMA_MODEL and DPMTF_OLLAMA_START_SCRIPT in .env. NOTE: This applies to the legacy bridge only; BridgeV002 no-kill mode uses post-dispatch offload instead. | bridge.py (F5c, F5d) |
| 12 | **BridgeV002 no-kill dispatch** — BridgeV002 `run_flow_step_db()` must NOT call `kill_session()`, `start_session()`, or `reload_ollama_model()` in the dispatch path. ZERO tmux kill/new-session calls exist in ANY bridgeV002 Python file (H132+H134). Sessions are persistent; server-side context is cleared by post-dispatch `ollama stop` of the predecessor's model. Client-side state is cleared by `/clear` (Claude Code) or soft-clear preamble (OpenCode). Architect restores cross-cycle state via StartUpNextSession.md save-state mechanism (§5b.4). | ReuseMostParts.md §3, BridgeV002NoTmuxKill.md §2, H132+H134 commit `916cfe1` |

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
| **Fase 4** | Steps CRUD (backend + frontend) | API endpoints, Flow-card "Manage Steps", form dropdowns, auto-fill fra conventions | ✅ Komplet (`729b3a5`) |
| **Fase 5** | Parameteriserede Script-kald | dispatch.py payload-samling, CLI invocation med argparse, example-scripts | ✅ Komplet (`bb27ab3`) |
| **Fase 6** | Database-oprydning & Struktur | eno.db fjernet, H99-backups ryddet, .gitignore `databases/*.db`, dpmtf.db untracked, BACKUP-STRATEGY.md | ✅ Komplet (`abab50d`) |
| **Fase 7** | No-Kill Dispatch + Hard-delete | Session persistence, post-dispatch offload, hard-delete for steps+flows, start_tmuxflow.py | ✅ Komplet (H111-H118) |
| **Fase 8** | Flow Management Suite | start-coding, stop-tmux, attach-tmux, i18n labels, H121 parsing fix. Commits `6a8b6a7`, `ae6d3db`, `6b4179c`, `a2745f9`. | ✅ Komplet |
| **Fase 9** | No-Kill Complete + DB-driven Callbacks | Eliminate ALL tmux lifecycle (H132+H134), add DB content templates + validation schemas (H131), convention admin UI. Commits `916cfe1`. | ✅ Komplet |
| **Fase 10** | Full Legacy Independence | Replace all 4 legacy bridge.py kernel functions with BridgeV002 equivalents: signal-send (H138), signal-complete (H136), signal-escalation + signal-answer (H137). Commits `cad6295`, `955a256`, `60250bb`. | ✅ Komplet |

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
| 3.2 | Seed data | "handoff", "callback", "verdict" templates + rule_type classifications |
| 3.3 | API endpoints | GET/POST/PUT/DELETE `/api/bridge-v2/conventions` + PATCH/{rule_key} (H131) |
| 3.4 | bridge_flow_steps ALTER | Erstat rå-strings med FK-reference: rule_key istedet for individuelle strings |
| 3.5 | **NEW (H131)**: content_template + validation_schema columns for DB-driven template rendering |

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

### BridgeV002 Development Rules — Session Protection

**CRITICAL:** During development of BridgeV002, handoffs MUST NOT instruct the
implementer to run dispatch code (`dispatch.py --flow`, `dispatch.py --db-flow`,
`role_teardown.py --role X --force`) that would disrupt active sessions.

- **No-kill mode (Rule 12):** The new dispatch protocol does not kill tmux
  sessions. It injects prompts into running sessions and offloads models post-dispatch.
- **Allowed model offload:** Only post-dispatch `ollama stop` of the predecessor's model.
- **Prohibited during development:** Anything that calls `tmux kill-session` on an active
  Architect, Review, or Implementer session (except legacy bridge.py auto-restart).
- **Validation:** Only `py_compile` and `--help` tests. No dispatch or teardown calls.

### Hvad skal IKKE være hardcoded (Human krav)

| Felt | Nuværende tilstand | Måltilstand |
|------|-------------------|-------------|
| `deliverable_dir` i steps | Hardcoded strings i init_db.py seed | Beregnet fra convention_rules templates ved runtime ✅ H131 |
| `deliverable_pattern` i steps | Hardcoded `{ID}-handoff.md` osv. | Template fra convention_rules ✅ H131 |
| `error_msg` i steps | Hardcoded med forkerte navne/referencer | Template: "Failed to deliver {step_type} to {to_role}." ✅ H131 |
| `pre_dispatch_script` | NULL alle steder, ingen registry | Dropdown-valg fra `bridge_scripts` tabel |
| `post_dispatch_script` | NULL alle steder, ingen registry | Dropdown-valg fra `bridge_scripts` tabel |
| `base_bridge_path` | Ingen konfiguration — implicit `/home/svend/claude-bridge/` | `[bridge] base_path` i dpmtf.ini + config.py getter ✅ H131 |
| **Template content** | Hardcoded XML i legacy bridge.py (lines 424-470) | DB-driven via `content_template` column ✅ H131 |
| **Validation schema** | None — deliverables unvalidated | JSON schema in DB via `validation_schema` column ✅ H131 |

### Key Principles (of Human)

1. **BridgeV002 is part of DPMtF-repo** — scripts are versioned, deliverable folders external
2. **No hardcoded data** — everything configurable via frontend dropdowns and templates
3. **Scripts receive parameters** — all 6 params (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern) sent to script at call time
4. **Conventions first** — templates governed via `bridge_convention_rules`, not manually
5. **No tmux lifecycle in scripts** — session creation/destruction only via REST endpoints ✅ H132+H134

---

## 5b. BridgeV002 Dispatch Protocol Decision — No-Kill Mode

> **Decision date:** 2026-06-20
> **Analysis artifacts:** `~/Dokumenter/Bridgeflowfuture/ReuseMostParts.md`,
> `~/Dokumenter/Bridgeflowfuture/BridgeV002NoTmuxKill.md`,
> `~/Dokumenter/Bridgeflowfuture/BridgeV002StartUpSessionState.md`

### 5b.1 The Decision

**Replace pre-dispatch kill+restart with post-dispatch ollama stop.**

| Current (kill-before) | New (offload-after) |
|----------------------|---------------------|
| Kill tmux session, unload model, restart session, reload model before injecting prompt | Inject prompt into running session, then offload predecessor's model after injection |
| 15-step dispatch sequence | 9-step dispatch sequence |
| ~5600ms per dispatch | ~1600ms per dispatch (71% faster) |

**Rationale:** Tmux sessions are persistent. Server-side context is cleared by `ollama stop` + lazy reload. Client-side state is cleared by `/clear` (Claude Code) or soft-clear preamble (OpenCode). 85-90% of existing BridgeV002 code is reused unchanged.

### 5b.2 What Changes in dispatch.py

| Removed from dispatch path | Added to dispatch path |
|---------------------------|----------------------|
| `kill_session(tmux)` before injection | `session_alive()` check — single call, no poll loop |
| `unload_ollama_model()` pre-dispatch | Deliverable existence verification |
| `start_session()` + `wait_session_ready()` | `/clear` prefix for Claude Code sessions |
| `reload_ollama_model()` + sleep(3) | Post-dispatch offload of predecessor's model |

Total: ~47 lines changed out of ~5000 BridgeV002 lines (0.94%).

### 5b.3 What Stays Unchanged

- Database schema — no migrations for Phase 1
- `bridge_lib.py` — all lookup functions work identically
- All 12 API endpoints (`/api/bridge-v2/...`)
- Convention rules (handoff, callback, verdict)
- Frontend CRUD UI
- Seed data in `init_db.py`
- `role_setup.py` and `role_teardown.py` — same code, different frequency

### 5b.4 Architect Context Gap — Resolved by Save-State Mechanism

When the Architect receives verdict feedback after `ollama stop`, it has zero server-side memory. This is resolved by using this file (`StartUpNextSession.md`) as durable save-state:

1. **Before dispatch:** Architect writes cycle snapshot (§5b.5) to this file
2. **During chain:** `ollama stop` clears volatile context; file on disk survives
3. **After verdict:** Architect reads this file first → full design intent restored
4. **Architect evaluates:** "Did implementation match my original design?"

This is a process change, not a code change. The dispatch protocol already injects file paths as prompts. For verdict-feedback steps, the injected prompt references both this file and the verdict:

```
"Read docs/StartUpNextSession.md first. Then read {verdict_file}."
```

### 5b.5 Active Cycle Snapshot

> **Update this section before each dispatch.** Append the current handoff's design intent below. On restore (after ollama stop), read everything under this heading to reconstruct context.

--- BEGIN CYCLE SNAPSHOT ---

**Last cycle:** Handoff 138 — BridgeV002 signal-send: replace legacy cmd_send() (COMPLETED)
**Previous cycles completed:** H123 (attach-tmux), H131 (DB-driven callbacks), H132 (eliminate ALL tmux lifecycle), H134 (clean up flow scripts to zero tmux calls), H136 (signal-complete), H137 (signal-escalation + signal-answer), H138 (signal-send)

**Migration Status — Legacy → BridgeV002:**
| Legacy Function | BridgeV002 Replacement | Commit |
|-----------------|----------------------|--------|
| `cmd_send()` | `signal_send()` (H138) | `60250bb` |
| `cmd_complete()` | `signal_complete()` (H136) | `cad6295` |
| `cmd_ask_architect()` | `signal_escalation()` (H137) | `955a256` |
| `cmd_answer_review()` | `signal_answer()` (H137) | `955a256` |

All 4 legacy bridge.py kernel functions now replaced with DB-driven equivalents in BridgeV002.
Legacy bridge (`claude-bridge/bridge.py`) is functionally superseded.

**Open design decisions:**
- [x] H111 implement: remove kill/start/reload fra run_flow_step_db(), tilføj session_alive() + post-dispatch offload (~47 lines) — COMPLETED
- [x] H112: prompt_template enrichment in convention_rules + dispatch integration — COMPLETED
- [x] H113: First post-dispatch script (archi01-imple01.py) — COMPLETED (`d479eeb`)
- [x] H114: post-dispatch-common.py replacing archi01-imple01.py — COMPLETED (`ae4b1c0`)
- [x] H115: Convention autofill condition guard + delete step JSON-parse fix — COMPLETED (`6549710`, `ae4b1c0`)
- [x] H116: GET filter inactive steps + DELETE row_factory — COMPLETED (`7e94c25`)
- [x] H117: Step & Flow hard-delete consistency — COMPLETED (`e43f0d2`)
- [x] H118: start_tmuxflow.py + POST /start-tmux endpoint + frontend button — COMPLETED (`60b8b71`)
- [x] H119: start_coding.py + POST /start-coding endpoint + frontend "Start code interface" button — COMPLETED (`6a8b6a7`)
- [x] H120: stop_tmuxflow.py + POST /stop-tmux endpoint + frontend "Stop tmux" button — COMPLETED (`ae6d3db`)
- [x] H121: start-tmux endpoint parsing bugfix — removed broken stdout JSON parsing — COMPLETED (`6b4179c`)
- [x] H123: attach_tmux.py + POST /attach-tmux endpoint + frontend "Attach tmux" button + DELETE flow res.text() fix — COMPLETED (`a2745f9`)
- [x] H131: DB-driven callback system — 7 columns across 4 tables, convention templates + validation_schema seeds, resolve_content_template_from_db(), PATCH endpoint, Convention admin UI — COMPLETED (`916cfe1`)
- [x] H132: Eliminate ALL tmux kill/start from role_teardown.py, role_setup.py, dispatch.py — only ollama stop/pull remains — COMPLETED (`916cfe1`)
- [x] H134: Fix stop_tmuxflow.py + start_tmuxflow.py to zero tmux lifecycle — replace stop_sessions with inspection+ollama unload, replace create_missing_sessions with inspection+ollama preload — COMPLETED (`916cfe1`)
- [x] H136: signal_complete() replacing legacy cmd_complete() — callback dispatch via DB convention, tool-aware injection, VRAM cleanup — COMPLETED (`cad6295`)
- [x] H137: signal_escalation() + signal_answer() replacing legacy cmd_ask_architect()/cmd_answer_review() — role-aware escalation supporting multiple review roles — COMPLETED (`955a256`)
- [x] H138: signal_send() replacing legacy cmd_send() — initial handoff dispatch with XML validation, model stop+reload, convention templates — COMPLETED (`60250bb`)
- [ ] Implement periodic hard-reset gate for OpenCode sessions (Phase 3, long-term)

**Key design decisions from H111:**
- Kun kontrol-flow i dispatch.py — ingen nye filer, ingen schema ændringer
- session_alive(): enkelt tmux has-session kald, ikke polling loop
- deliverable eksistens-check før injection (fail fast)
- Post-dispatch: unload_ollama_model(fra_role's model) istedet for pre-dispatch unload
- reload_ollama_model() og kill_session() bevares som funktioner — IKKE kaldt fra dispatch-stien
- run_flow_step() (INI-baseret) og manual_dispatch() er uforandret
- Em dash i docstring → double hyphen (Python encoding workaround)
- from_ollama_model = "" placeholder til Phase 2

**Key design decisions from H112:**
- prompt_template column tilføjet til bridge_convention_rules via ALTER TABLE
- verdict_feedback convention med enriched prompt (StartUpNextSession.md + verdict reference)
- Convention templates bruger {bridge_dir} placeholder som dispatcher resolverer ved runtime
- Ingen schema migration nødvendigt — ALTER TABLE er idempotent hvis kolomnen allerede eksisterer
- build_step_payload() returnerer prompt_template fra convention; tom → fallback til "Read and execute {file}"
- run_flow_step_db() enricher prompt via placeholder-replace ({bridge_dir}, {handoff_id}) før injection

**Key design decisions from H113:**
- archi01-imple01.py: first post-dispatch script in scripts/bridgeV002/
- Ingen hardcoded stier — bridge_dir fra config.get_bridge_base_path(), db_path fra config.get_db_path()
- Deliverable pattern resolveres fra DB ({ID} placeholder) — ændres i DB uden script-retur
- Ollama stop er altid sidste handling post-dispatch; "already unloaded" er success (idempotent)
- Script modtager --deliverable-pattern ikke --deliverable-dir med hardcoded filnavn

**Key design decisions from H114:**
- Alle post-dispatch scripts er identiske — convention rules påvirker kun fil-sti og prompt-injektion, IKKE post-dispatch logik
- post-dispatch-common.py lookupker from_role's model dynamisk i bridge_roles ved runtime
- Nye steps behøver kun DB seed-entry med post_dispatch_script = "post-dispatch-common" — ingen kodeændringer fremover
- archi01-imple01.py slettes; post-dispatch-common.py genbruges af alle 4 heavy flow steps

**Key design decisions from H115:**
- Convention auto-fill kun på NEW steps: `isNewStep = !_bridgeEditingStepId` flag i `_showStepForm()` gater `_autoFillFromConvention`
- Delete step JSON-parse fix: `if (!res.ok) throw new Error("HTTP " + res.status)` før `res.json()` — forhindrer "JSON.parse unexpected character" på failed HTTP responses
- Role upsert: erstatter hard 409 med op-sert logic der reaktiverer soft-deleted roles
- bridge_v2_update_step fikset med `conn.row_factory = sqlite3.Row` (manglede tidligere → dict access fejl)

**Key design decisions from H117:**
- Steps slettes permanent (hard-delete), ikke soft — ingen ghost-rows mere i tabellen
- GET list_steps fjerner is_active=1 filter — ikke længere nødvendigt når DELETE er hard
- POST create step auto-reaktiverer from_role/to_role hvis de er soft-deleted (ligesom H115's role upsert)
- DELETE flow kan kun køre hvis flow har 0 steps tilbage — check COUNT *før* nogen opsætning
- Flow slettes permanent (hard-delete), ikke soft — ingen is_active-blanding
- Ingen DB schema ændringer — alle ændringer er app.py CRUD-endpoints alene

**Key design decisions from H118:**
- start_tmuxflow.py itererer over alle active steps i en flow, lookupker from_role's tmux_session fra DB
- Eksisterende tmux-sessioner tjekkes via `tmux list-sessions` — kun manglende oprettes med `tmux new-session -d -s`
- Script importerer config.py via importlib.util fra projekt-roden (undgår ModuleNotFoundError når script køres fra /home/svend/)
- POST /api/bridge-v2/flows/{flow_key}/start-tmux endpoint kører script som subprocess med 30 sek timeout
- Frontend "Start tmux" button (dpmtf-btn-success) på alle flow cards, kaldes via fetch til above endpoint
- i18n labels: lbl_bridge_start_tmux ("Start tmux") og lbl_bridge_starting ("Starting...") i alle 4 i18n-lag
- Ingen DB schema ændringer — bruger eksisterende bridge_roles.tmux_session kolonne

**Key design decisions from H119:**
- start_coding.py itererer over alle active steps i en flow, lookupker from_role's tmux_session + start_cmd fra DB
- Deduplikation by role_key (første forekomst vinder), sorteret af sort_order
- Execute start_cmd i eksisterende tmux session via `tmux send-keys`; forudsætter sessions er oprettet via start_tmuxflow.py first
- resolve_placeholders() fra bridge_lib resolverer {bridge_dir} og {project_root} placeholders i start_cmd
- Script importerer config.py via importlib.util (undgår ModuleNotFoundError når kørt fra /home/svend/)
- POST endpoint: subprocess.run med 30 sek timeout; returnerer stdout som status message
- Frontend "Start code interface" button (dpmtf-btn-info) på alle flow cards — ingen i18n label brugt (hardcoded tekst)
- Ingen DB schema ændringer — bruger eksisterende bridge_roles.start_cmd kolonne

**Key design decisions from H120:**
- stop_tmuxflow.py: modsat af start_tmuxflow.py — itererer over alle active steps, lookupker from_role's tmux_session. EFTER H134: IKKE longer kalder `tmux kill-session` — kun session inspection + ollama unload
- Silent failure på ikke-eksisterende sessions (kun log WARNING)
- POST /stop-tmux endpoint med samme pattern som /start-tmux og /start-coding: subprocess.run 30s timeout
- Frontend "Stop tmux" button (dpmtf-btn-danger) med confirm dialog ("Stop all tmux sessions for 'X'?")
- i18n label lbl_bridge_stop_tmux ("Stop tmux")
- Ingen DB schema ændringer — bruger eksisterende bridge_roles.tmux_session kolonne

**Key design decisions from H121:**
- Bugfix: start-tmux endpoint forsøgte at parse stdout som JSON (result.stdout indeholder "Done: N session(s) created" ikke JSON)
- fjernet broken `.split(": ")` parsing — kun returner simple status/message object
- Ingen andre ændringer; pure cleanup

**Key design decisions from H123:**
- attach_tmux.py: modsat af stop_tmuxflow.py — finder terminal emulator (xfce4-terminal → gnome-terminal → x-terminal-emulator), åbner ny tab for hver session
- attach_in_new_tab() bruger terminal-specifikke args (xfce4: --command, gnome: --, generic: -e)
- Tjekker eksistens af hver session via `tmux has-session` før attach (skipper ikke-kørende)
- POST /attach-tmux endpoint med samme subprocess pattern som andre flow-endpoints
- Frontend "Attach tmux" button (dpmtf-btn-info) — ingen confirm dialog (non-destructive action)
- DELETE flow bugfix: added `if (!res.ok) return res.text().then(function(txt) { throw new Error(txt); })` før res.json() — forhindrer JSON parse error på HTTP error responses (samme princip som H115's delete step fix)
- Ingen DB schema ændringer — bruger eksisterende bridge_roles.tmux_session kolonne

**Key design decisions from H131:**
- 7 ADD COLUMN migrations across 4 tables — all with DEFAULT values, zero data deletion
- restart_policy column added but later dropped in H132 (meaningless without session lifecycle)
- Convention templates stored in content_template column (TEXT), validation_schema as JSON array
- resolve_content_template_from_db() replaces hardcoded XML template strings
- validate_deliverable_against_schema() reads required tags from DB, validates file content
- PATCH /api/bridge-v2/conventions/{rule_key} enables inline editing via UI textareas
- Convention admin section added to Setup panel between Roles and Export

**Key design decisions from H132:**
- role_teardown.py: removed tmux kill-session, kept only ollama stop for VRAM cleanup
- role_setup.py: removed ALL tmux lifecycle (kill + new-session), kept only ollama pull
- dispatch.py: deleted kill_session() and start_session() functions entirely (~50 lines)
- Legacy run_flow_step() and manual_dispatch() paths use session_alive() instead of kill/start
- restart_policy column dropped from init_db.py, seed labels removed (LBL-1000290-LBL-1000294)
- bridgeV002 no-kill policy: only ollama stop/pull permitted as lifecycle operations

**Key design decisions from H134:**
- stop_tmuxflow.py: replaced stop_sessions() with list_flow_sessions() + unload_ollama_models()
- start_tmuxflow.py: replaced create_missing_sessions() with get_active_flow_roles() + preload_ollama_models()
- Both scripts now return inspection-only output — report sessions needed, preload models only
- Session creation/destruction delegated to /api/bridge-v2/start-tmux and stop-tmux endpoints
- zero executable tmux lifecycle calls remain in ALL bridgeV002 Python files

**Key design decisions from H136:**
- signal_complete() follows same 9-step golden rule sequential dispatch as run_flow_step_db
- Resolves both roles from bridge_roles DB table — no hardcoded session names
- Deliverable existence check with convention pattern matching (fail fast)
- Prompt built from callback convention content_template with placeholder replacement
- Post-dispatch: unload_ollama_model() on from_role's model for VRAM cleanup
- Escalation directory symlink updated for traceability

**Key design decisions from H137:**
- signal_escalation() + signal_answer() are symmetric — opposite directions, same structure
- Role-aware design: both require explicit --from-role AND --to-role parameters
- No role_type field in bridge_roles table — auto-detection of architect role impossible, must be explicit
- Multiple review role support (review01, review02) — legacy only supported one hardcoded review session
- Escalation question file validation: review must write question file before signaling escalation
- New "escalation" convention in bridge_convention_rules with content_template + validation_schema

**Key design decisions from H138:**
- signal_send() follows 10-step golden rule sequential dispatch (pre-dispatch model stop+reload, not post)
- XML section validation matches legacy cmd_send: requires <role>, <task>, <constraint> tags
- Model stop→sleep(1)→pull→sleep(3) cycle ensures clean server-side context for initial dispatch
- Prompt built from handoff convention content_template with {handoff_id}, {source_role}, {next_role}, {bridge_dir} placeholders
- All 4 signal functions now cover the complete legacy bridge.py kernel: send → complete → escalation → answer

--- END CYCLE SNAPSHOT ---

**Save-state update procedure:** Before dispatching any handoff, update the cycle snapshot block above with:
- Current handoff ID and title
- Original task description (extracted from handoff `<task>` section)
- Key design decisions
- Verification checklist for verdict review
Then proceed to dispatch. Do not skip this step — it is the Architect's memory across ollama stop cycles.

Do NOT start hardening or no-kill work without explicit Human instruction per phase.

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
│   ├── bridge_lib.py               ← INI + DB lookup functions, content template resolver, deliverable validator
│   ├── dispatch.py                 ← DB-driven dispatch (run_flow_step_db), legacy INI paths preserved as dead code
│   ├── role_setup.py               ← Preload Ollama model (no tmux)
│   └── role_teardown.py            ← Unload Ollama model + fri VRAM (no tmux kill)
├── scripts/init_db.py              ← Schema + seed data + i18n labels
└── databases/
    └── dpmtf.db                    ← bridge_roles, bridge_flows, bridge_flow_steps
```

### Database Schema (3 tabeller)

**bridge_roles** (13 cols): `role_key`, `tmux_session`, `start_cmd`, `model_type`, `cloud_model`, `ollama_model`, `setup_script`, `teardown_script`, `deliver_error_msg`, `is_active`, `created_at`, `updated_at`, `restart_policy`

**bridge_flows** (9 cols): `flow_key`, `name`, `description`, `step_order`, `is_default`, `is_active`, `created_at`, `updated_at`, `auto_complete_enabled`

**bridge_flow_steps** (16 cols): `id`, `flow_key`, `step_key`, `from_role`, `to_role`, `deliverable_dir`, `deliverable_pattern`, `pre_dispatch_script`, `post_dispatch_script`, `error_msg`, `sort_order`, `is_active`, `auto_chain_to_next`, `validation_required`, `rule_key`

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

### 8.6 BridgeV002 No-Kill Dispatch Protocol (NEW — Rule 12)

> This section describes the **target state** for BridgeV002's dispatch
> protocol after no-kill migration. The legacy bridge (§8.5) remains active
> until no-kill is implemented.

The new `run_flow_step_db()` dispatch sequence (9 steps, not 15):

```
Current dispatch (15 steps):          New dispatch (9 steps):
────────────────────                  ────────────────────
kill_session(target)                  [check] session_alive(target) — one-shot boolean
unload_ollama_model()                 [check] deliverable file exists → fail fast
time.sleep(1)                         [inject] /clear + prompt (Claude Code)
start_session(target)                       or soft-clear + paste-buffer (OpenCode)
wait_session_ready(target)             [offload] ollama stop predecessor_model
reload_ollama_model()                 [update] symlink + trace.log
time.sleep(3)
execute_pre_dispatch_script()        (same as before, but no kill/start/reload)
inject_prompt(target)
execute_post_dispatch_script()
update_symlink()
log_dispatch()
```

**Key behavioral change:** Tmux sessions are never killed by BridgeV002 dispatch. Sessions persist across multiple dispatch cycles. Server-side LLM context is cleared by `ollama stop` of the predecessor's model after each injection, not by process termination.

**Architect save-state cycle:**
```
Cycle N — Architect dispatches handoff {ID}:
  1. Reads StartUpNextSession.md (§5b.5) → restores context from prior cycle
  2. Designs handoff, writes {ID}-handoff.md
  3. Updates §5b.5 with cycle snapshot (saves state before ollama stop)
  4. Executes dispatch command
  5. STOP — wait for Human (Rule 2)

  POST-DISPATCH: ollama stop Architect_model
    → Server-side context cleared, file on disk survives

Cycle N — Verdict feedback arrives:
  1. Architect model lazy-loads (BLANK server-side context)
  2. FIRST ACTION: reads StartUpNextSession.md → restores design intent
  3. SECOND ACTION: reads verdict file → new input for this cycle
  4. Evaluates: "Did implementation match my original design?"
  5. Writes assessment, updates §5b.5 with outcome
```

**Migration scope:** ~47 lines changed in dispatch.py (0.94% of BridgeV002 codebase). Database schema unchanged for Phase 1. All API endpoints unchanged. See `~/Dokumenter/Bridgeflowfuture/ReuseMostParts.md` for full analysis.

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
