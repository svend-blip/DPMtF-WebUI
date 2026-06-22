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
| **Last handoff ID** | 143 (completed — H143 governance_file dynamic dropdown from disk, branch `hardening/bridgev002-phase1-config`) |
| **Implementer** | `claude_implementer` running **OpenCode 1.17.7** (`ollama/qwen3.6:27b-q4_K_M`) |
| **Review** | `claude_review` running **OpenCode 1.17.7** (`ollama/qwen3.6:27b-q4_K_M`) |
| **Architect** | `claude_architect` running **Claude Code** (`deepseek-v4-pro:cloud`) |
| **Bridge (prod)** | `/home/svend/claude-bridge/bridge.py` |
| **BridgeV002 (dev)** | Under udvikling i `DPMtF/docs/bridgeV002/` og `DPMtF/scripts/bridgeV002/` |

**No-Kill Decision:** BridgeV002 dispatch uses post-dispatch `ollama stop` — zero tmux kill/new-session calls. Sessions are persistent; context cleared by model offload.

**Full Legacy Independence:** BridgeV002 replaces ALL 4 legacy bridge.py kernel functions (`signal_send`, `signal_complete`, `signal_escalation`, `signal_answer`). Zero INI dependencies. CLI:
```bash
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-send --from-role review01 --to-role imple01
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-complete --from-role imple01
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-escalation --from-role review01 --to-role archi01
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-answer --from-role archi01 --to-role review01
```

---

## 4. Active Hard Rules

| # | Rule | Source |
|---|------|--------|
| 1 | **NO parallel work** — one role active at a time. Bridge enforces via ollama stop. | 99_ROLEINTERACTION.md, 02_ARCHITECT.md |
| 2 | **STOP after handoff** — Architect stops ALL activity after dispatch signal. No Monitor, no Bash, no background tasks. | 02_ARCHITECT.md §Post-Handoff Stop Rule |
| 3 | **NO split-brain exception** — batch dispatch prohibited. One handoff at a time. | 02_ARCHITECT.md (H3) |
| 4 | **HUMAN COMMIT GATE** — only Human may commit/push. Review prepares, Human authorizes. | 15_GIT_POLICY.md, 04_REVIEW.md (H2) |
| 5 | **Tool-independent governance** — DPMtF governance files are primary authority. | OpenCode PoC runbook §0 |
| 6 | **All inter-role communication in English (en-US)** | CLAUDE.md §2, 100_BRIDGE.md |
| 7 | **Implementer NEVER commits** — changes remain unstaged. | 03_IMPLEMENTOR.md (H2) |
| 8 | **Stop after 2 failed patching attempts** — document, escalate, do not guess. | 12_CODING_STANDARD.md |
| 9 | **Tool-independent bridge** — bridge.py auto-detects OpenCode vs Claude Code. | bridge.py (F5a) |
| 10 | **Auto-restart after handoff** — legacy bridge only; BridgeV002 no-kill mode does not kill sessions. | bridge.py (F5b) |
| 11 | **Ollama reload before dispatch** — legacy bridge only; BridgeV002 uses post-dispatch offload. | bridge.py (F5c) |
| 12 | **BridgeV002 no-kill dispatch** — ZERO tmux kill/new-session calls. Context cleared by `ollama stop`. NO `/clear`, NO soft-clear preamble. | H132+H134 |

---

## 5. Current Next Task

**Fase 1-11 complete — BridgeV002 database, UI, signals, governance integration operational.**

| Fase | Titel | Status |
|------|-------|--------|
| **Fase 1** | Konfiguration & Infrastructure | ✅ (`cef2812`) |
| **Fase 2** | Script Registry | ✅ (`65e7d9f`) |
| **Fase 3** | Convention Rules | ✅ (`dab0dba`) |
| **Fase 4** | Steps CRUD (backend + frontend) | ✅ (`729b3a5`) |
| **Fase 5** | Parameteriserede Script-kald | ✅ (`bb27ab3`) |
| **Fase 6** | Database-oprydning & Struktur | ✅ (`abab50d`) |
| **Fase 7** | No-Kill Dispatch + Hard-delete | ✅ (H111-H118) |
| **Fase 8** | Flow Management Suite | ✅ |
| **Fase 9** | No-Kill Complete + DB-driven Callbacks | ✅ (`916cfe1`) |
| **Fase 10** | Full Legacy Independence | ✅ |
| **Fase 11** | Governance Integration | ✅ (`1f3c647`) |

### Gap Analysis Summary

Bugs B1-B4: FIXED. Gaps G1-G4: FIXED. Se commit history for detaljer.

| # | Gap | Status |
|---|-----|--------|
| **G5** | Governance file seed data key mismatch — two role naming schemes | 🟠 OPEN |
| **M1-M5** | Medium gaps — auto_complete, hardcoded dirs, ID counters, simplified flow, verdict template | ⏸ Low priority |

### Open Work Items

- [ ] Fix G5 — Role key alignment in governance_file seed data
- [ ] Rewrite governance files — 02_ARCHITECT, 03_IMPLEMENTOR, 04_REVIEW, 100_BRIDGE
- [ ] Medium gaps M1-M5 (configuration / data issues)

---

## 5b. BridgeV002 Dispatch Protocol — No-Kill Mode

**Replace pre-dispatch kill+restart with post-dispatch ollama stop.**
~47 lines changed out of ~5000 BridgeV002 lines (0.94%).

### Architect Context Gap — Save-State Mechanism

This file (`StartUpNextSession.md`) is the durable save-state for the Architect across `ollama stop` cycles:

1. **Before dispatch:** Architect writes cycle snapshot (§5b.5) to this file
2. **During chain:** `ollama stop` clears volatile context; file on disk survives
3. **After verdict:** Architect reads this file first → full design intent restored

### 5b.5 Active Cycle Snapshot

> **Update this section before each dispatch.**

--- BEGIN CYCLE SNAPSHOT ---

**Last cycle:** G2/G4 — BridgeV002 Enriched Callback + Verdict Templates (COMPLETED)
**All Fases 1-11 complete.** BridgeV002 is fully database-driven with zero INI dependencies.

**Migration Status — Legacy → BridgeV002:**
| Legacy Function | BridgeV002 Replacement | Commit |
|-----------------|----------------------|--------|
| `cmd_send()` | `signal_send()` (H138) | `60250bb` |
| `cmd_complete()` | `signal_complete()` (H136) | `cad6295` |
| `cmd_ask_architect()` | `signal_escalation()` (H137) | `955a256` |
| `cmd_answer_review()` | `signal_answer()` (H137) | `955a256` |

Legacy bridge (`claude-bridge/bridge.py`) is functionally superseded.

**Open work items:**
- [ ] Fix G5 — Role key alignment in governance_file seed data
- [ ] Rewrite governance files — 02_ARCHITECT, 03_IMPLEMENTOR, 04_REVIEW, 100_BRIDGE

--- END CYCLE SNAPSHOT ---

**Save-state update procedure:** Before dispatching any handoff, update the cycle snapshot block above with:
- Current handoff ID and title
- Original task description (extracted from handoff `<task>` section)
- Key design decisions
- Verification checklist for verdict review
Then proceed to dispatch. Do not skip this step — it is the Architect's memory across ollama stop cycles.

---

## 5d. Architecture (as-built after Hardening H143)

```
DPMtF-WebUI/
├── app.py                          ← /api/bridge-v2/ endpoints (12 total) + governance-files endpoint
├── static/js/dpmtf-app.js          ← BridgeV002 funktioner (render, create, update, delete, export, governance-file dropdown)
├── templates/index.html            ← Bridge Setup panel med Roles/Flows sektioner
├── scripts/bridgeV002/
│   ├── bridge_lib.py               ← DB lookup functions only, content template resolver, deliverable validator
│   ├── dispatch.py                 ← DB-driven dispatch (--db-flow mandatory), signal_send/complete/escalation/answer
│   ├── post-dispatch-common.py     ← Convention-agnostic post-dispatch for all heavy flow steps
│   ├── role_setup.py               ← Ollama pull only (no tmux lifecycle)
│   └── role_teardown.py            ← Ollama stop + fri VRAM only (no tmux kill)
├── scripts/init_db.py              ← Schema + seed data + i18n labels
└── databases/
    └── dpmtf.db                    ← bridge_roles, bridge_flows, bridge_flow_steps, bridge_convention_rules, bridge_scripts
```

### Database Schema (5 tabeller)

**bridge_roles** (14 cols): `role_key`, `tmux_session`, `start_cmd`, `model_type`, `cloud_model`, `ollama_model`, `setup_script`, `teardown_script`, `deliver_error_msg`, `is_active`, `governance_file`, `created_at`, `updated_at`, `restart_policy`

**bridge_flows** (9 cols): `flow_key`, `name`, `description`, `step_order`, `is_default`, `is_active`, `created_at`, `updated_at`, `auto_complete_enabled`

**bridge_flow_steps** (16 cols): `id`, `flow_key`, `step_key`, `from_role`, `to_role`, `deliverable_dir`, `deliverable_pattern`, `pre_dispatch_script`, `post_dispatch_script`, `error_msg`, `sort_order`, `is_active`, `auto_chain_to_next`, `validation_required`, `rule_key`

**bridge_convention_rules**: `rule_key`, `step_type`, `dir_template`, `pattern_template`, `error_template`, `prompt_template`, `content_template`, `validation_schema`, `rule_type`

**bridge_scripts**: `script_key`, `path`, `stage`, `params_required`

### strict_review Flow Definition

| sort_order | step_key | from_role | to_role | deliverable_dir | pattern | convention |
|---|---|---|---|---|---|---|
| 1 | archi01-imple01 | archi01 | imple01 | reviewtoimplementor | {ID}-handoff.md | handoff |
| 2 | imple01-review01 | imple01 | review01 | implementertoreview | {ID}-imple01.md | callback |
| 3 | review01-review02 | review01 | review02 | implementertoreview | {ID}-review01.md | verdict |
| 4 | review02-human | review02 | human | implementertoreview | {ID}-verdict.md | verdict |

### Key Principles (of Human)

1. **BridgeV002 is part of DPMtF-repo** — scripts are versioned, deliverable folders external
2. **No hardcoded data** — everything configurable via frontend dropdowns and templates
3. **Scripts receive parameters** — all 6 params sent to script at call time
4. **Conventions first** — templates governed via `bridge_convention_rules`
5. **No tmux lifecycle in scripts** — session creation/destruction only via REST endpoints
6. **Fully database-driven** — zero INI dependencies

### BridgeV002 Development Rules

- **No-kill mode:** Handoffs MUST NOT instruct implementer to run dispatch code that disrupts active sessions.
- **Allowed:** Only post-dispatch `ollama stop` of the predecessor's model.
- **Validation:** Only `py_compile` and `--help` tests. No dispatch or teardown calls.

---

## 6. Stop Condition

Stop ALL activity and wait for Human (Svend) after:

- Dispatching a handoff via `dispatch.py --signal-send` or BridgeV002 API endpoint
- Completing an escalation response via `dispatch.py --signal-answer`
- Hitting an ambiguity that requires Human decision
- Human explicitly says "stop" or "wait"
- Encountering a governance violation

**Do NOT:**
- Start new work without explicit Human instruction
- Poll for results with Monitor or Bash after dispatch
- Pre-write handoff files for future tasks
- Continue working after signaling completion

---

## 7. Tmux Session Setup

### 7.1 Check existing sessions
```bash
tmux ls
```

Expected: `archi01`, `claude_architect`, `claude_implementer`, `claude_review`, `imple01`, `review01`, `review02`

### 7.3 Session purpose

| Session | Role | Tool/Model | Purpose |
|---------|------|------------|---------|
| `claude_implementer` | Implementor (03) | OpenCode (`ollama/qwen3.6:27b-q4_K_M`) | Code execution |
| `claude_review` | Review (04) | OpenCode (`ollama/qwen3.6:27b-q4_K_M`) | Validation & dispatch |
| `claude_architect` | Architect (02) | Claude Code (`deepseek-v4-pro:cloud`) | Design & escalation |
| `archi01` | BridgeV002 Architect | OpenCode | strict_review flow |
| `imple01` | BridgeV002 Implementer | OpenCode | strict_review flow |
| `review01` | BridgeV002 Review Primary | OpenCode | strict_review flow |
| `review02` | BridgeV002 Review Secondary | OpenCode | strict_review flow |

---

## 8. Bridge Communication Workflow

> **NOTE:** Legacy bridge (`claude-bridge/bridge.py`) is functionally superseded by BridgeV002 but still used for current Architect→Review→Implementer development.

### 8.1 The 3-Layer Loop (Legacy Bridge)

```
claude_architect (design) → writes handoff, signals: bridge.py send {ID}
    ↓
claude_review (dispatch) → validates, dispatches to implementer
    ↓
claude_implementer (execute) → executes, signals: bridge.py complete {ID}
    ↓
claude_review (validate) → reviews diff, PREPARES commit (does NOT commit/push)
    ↓
claude_architect (escalation target) ← if needed: bridge.py ask-architect {ID}
```

### 8.2 Bridge commands

```bash
export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
python3 /home/svend/claude-bridge/bridge.py send {ID}
python3 /home/svend/claude-bridge/bridge.py complete {ID}
python3 /home/svend/claude-bridge/bridge.py ask-architect {ID}
python3 /home/svend/claude-bridge/bridge.py answer-review {ID}
python3 /home/svend/claude-bridge/bridge.py next-id
```

### 8.3 Bridge rules

1. **Sequential only** — one role active at a time. BridgeV002: ollama stop (0 tokens). Legacy: `/clear`.
2. **DPMTF_BRIDGE_DIR must be set** — otherwise bridge falls back to `~/.dpmtf/bridge/`.
3. **Bridge is a git repo** — remote: `github.com:svend-blip/claude-bridge`.

### 8.4 Tool-Independent Bridge

| Tool | Detection | Injection Method |
|------|-----------|-----------------|
| **OpenCode** | `pane_current_command` contains "opencode" | `tmux load-buffer` + `paste-buffer` |
| **Claude Code** | `pane_current_command` contains "node" or "claude" | `tmux send-keys` + `Enter` |

---

## 9. Quick Verification After Startup

```bash
# 1. Config loads correctly
cd /home/svend/DPMtF-WebUI
python3 -c "import config; print(config.get_project_root()); print(config.get_bridge_dir())"

# 2. Bridge works
export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
python3 /home/svend/claude-bridge/bridge.py next-id

# 3. Database is intact
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print('Labels:', conn.execute('SELECT COUNT(*) FROM ui_labels').fetchone()[0])"

# 4. Tmux sessions exist
tmux ls | grep -E "claude_implementer|claude_review|claude_architect"

# 5. App compiles
python3 -m py_compile app.py && echo "OK"
python3 -m py_compile scripts/init_db.py && echo "OK"
node --check static/js/dpmtf-app.js && echo "OK"

# 6. BridgeV002 tables exist
python3 scripts/bridgeV002/bridge_lib.py | grep -q "Database-backed lookup" && echo "OK" || echo "FAIL"

# 7. BridgeV002 API responds
curl -s http://localhost:9130/api/bridge-v2/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('available') else 'FAIL')"
```

---

## 10. PC-Specific Notes

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

- `docs/governance-templates-v2/02_ARCHITECT.md` — Architect role definition
- `docs/governance-templates-v2/03_IMPLEMENTOR.md` — Implementor role definition
- `docs/governance-templates-v2/04_REVIEW.md` — Review role definition
- `docs/governance-templates-v2/100_BRIDGE.md` — Bridge protocol details
- `docs/governance-templates-v2/300_SETUPINSTRUCTION.md` — Full PC migration setup guide
