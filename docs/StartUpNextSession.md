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
| **Last handoff ID** | 089 |
| **Implementer** | `claude_implementer` running **OpenCode 1.17.7** (`ollama/qwen3.6:27b-q4_K_M`) |
| **Review** | `claude_review` running **OpenCode 1.17.7** (`ollama/qwen3.6:27b-q4_K_M`) |
| **Architect** | `claude_architect` running **Claude Code** (`deepseek-v4-pro:cloud`) |
| **Bridge** | `/home/svend/claude-bridge/bridge.py` |

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

### Human Final Verdict
All Spors A-G approved. DPMtF-WebUI is a Prompt Compiler with 8 fields
and an integrated Accelerated WebUI Factory. When Deployment Strategy
"accelerated" is selected, the form switches to a 3-field "Create New
WebUI" flow that runs initialize_new_webui.py and starts the new server.
Bridge is tool-independent with ollama reload and auto-restart. Both
local sessions run OpenCode. Awaiting next Spor definition.

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

**Spor G complete — Prompt Compiler is operational with 8 fields + Accelerated WebUI Factory.**

The Accelerated WebUI Factory is integrated into the Prompt Compiler UI:
- Select "accelerated" in Deployment Strategy → form switches to WebUI creation mode
- Fill in New webui (name), Port, Title → "Create New WebUI" runs the factory script
- "Start WebUI Server" launches uvicorn → clickable link to new project
- Manual step: create 10_PROJECT.md and 11_SCOPE.md in new project's docs/dpmtf/

Next candidates:
- ENO rebuild — once Prompt Compiler is stable, rebuild ENO with simplified framework
- Governance validation — verify all governance templates are valid for bridge flow
- New feature Spor — to be defined by Human

Do NOT start new work without explicit Human instruction.

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
