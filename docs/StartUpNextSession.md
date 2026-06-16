# Start Up Next Session — DPMtF Development Environment

> **en-US is the standard language for all governance-templates-v2 files.**
> **Review note:** When this file is referenced, verify the current state
> matches what is described here. Check that tmux sessions exist, ports are
> correct, and config values match the current PC. Update this file if the
> situation has changed.

---

## Purpose

Step-by-step guide to restart the DPMtF development environment after a
shutdown or `/clear`. Covers tmux session creation, Claude Code startup,
bridge configuration, and verification checks.

---

## 1. Verify Prerequisites

### 1.1 Check DPMTF_BRIDGE_DIR

```bash
echo $DPMTF_BRIDGE_DIR
```

Must print `/home/svend/claude-bridge`. If empty or wrong:

```bash
export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
```

This variable MUST be set before any `bridge.py` command. It is already in
`~/.bashrc` but may not be active in the current shell — run `source ~/.bashrc`
or export manually.

### 1.2 Verify bridge.py exists

```bash
ls -la /home/svend/claude-bridge/bridge.py
python3 /home/svend/claude-bridge/bridge.py next-id
```

Must print a number without errors.

### 1.3 Verify DPMtF-WebUI config

```bash
cd /home/svend/DPMtF-WebUI
python3 -c "import config; print('Project root:', config.get_project_root()); print('Bridge dir:', config.get_bridge_dir()); print('Port:', config.get_port())"
```

Must print correct paths for this PC.

---

## 2. Tmux Session Setup

### 2.1 Check existing sessions

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

### 2.2 Create missing sessions

If any session is missing, create it detached:

```bash
# Create all three (detached — no UI yet)
tmux new-session -d -s claude_implementer
tmux new-session -d -s claude_review
tmux new-session -d -s claude_architect
```

Verify with `tmux ls` that all three now exist.

### 2.3 Session purpose

| Session | Role | Model | Purpose |
|---------|------|-------|---------|
| `claude_implementer` | Implementor (03) | Local Ollama | Code execution — receives handoffs, writes code |
| `claude_review` | Review (04) | Cloud (cheap) | Validation & dispatch — reviews diffs, commits |
| `claude_architect` | Architect (02) | Cloud (capable) | Design & escalation — designs handoffs |

---

## 3. Start Claude Code in Each Session

### 3.1 Working directory

ALL sessions start in the project root:

```bash
cd /home/svend/DPMtF-WebUI
```

### 3.2 claude_implementer (Local Ollama model)

```bash
# Attach to the session
tmux attach -t claude_implementer

# Inside the session, start Claude Code:
ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen36-27b-q4km --permission-mode auto
```

**Model note:** `qwen36-27b-q4km` is the local Ollama model running on this PC.
If Ollama is not running, start it first: `ollama serve` (in a separate terminal).

### 3.3 claude_review (Cloud model — cheap)

```bash
# Attach to the session
tmux attach -t claude_review

# Inside the session, start Claude Code:
cd /home/svend/DPMtF-WebUI
claude --model deepseek-v4-pro:cloud --permission-mode auto
```

**Model note:** `deepseek-v4-pro:cloud` is used for review because it is
cheaper than Opus but capable enough for diff review and validation.

### 3.4 claude_architect (Cloud model — capable)

```bash
# Attach to the session
tmux attach -t claude_architect

# Inside the session, start Claude Code:
cd /home/svend/DPMtF-WebUI
claude --model deepseek-v4-pro:cloud --permission-mode auto
```

**First prompt:** Paste the content from `NextStartPrompt.md` into this session
to reconstruct full project context.

### 3.5 Detach from a session

Press `Ctrl+B` then `D` to detach from a tmux session (leaves it running).

---

## 4. Bridge Communication Workflow

### 4.1 The 3-Layer Loop

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
    │  commits if approved
    │  escalates to architect if needed: bridge.py ask-architect {ID}
    ▼
claude_architect (escalation target)
    │  answers architectural questions
    │  signals: bridge.py answer-review {ID}
```

### 4.2 Bridge commands

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

### 4.3 Bridge directory structure

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

### 4.4 Bridge rules

1. **Sequential only** — one role active at a time. Bridge enforces this with `/clear`.
2. **All 4 functions send `/clear` first** — fixed in handoff 029.
3. **DPMTF_BRIDGE_DIR must be set** — otherwise bridge falls back to `~/.dpmtf/bridge/`.
4. **Bridge is a git repo** — `git log` shows change history. Remote: `github.com:svend-blip/claude-bridge`.

---

## 5. Current Project Status

### 5.1 Completed Spors

| Spor | Handoffs | What |
|------|----------|------|
| **Spor A** | 023-029 | Hardcoding cleanup — config.py foundation, all paths via getters |
| **Spor B** | 030-036 | Prompt Compiler PoC — knowledge fragments, auto-selection, deployment strategy |

### 5.2 Key files modified

| File | Status | Key changes |
|------|--------|-------------|
| `config.py` | Spor A | Central config — 15 getter functions |
| `dpmtf.ini` | Spor A | App-config defaults |
| `.env` | Spor A | DPMTF_BRIDGE_DIR + session names |
| `bridge.py` | Spor A + 029 | Env vars, /clear consistency, git repo |
| `app.py` | Spor A + B | Zero hardcoded paths, fragment auto-selection, deployment_strategy |
| `scripts/init_db.py` | Spor A + B | Config getters, deployment_strategy field + options |
| `static/js/dpmtf-app.js` | Spor B | Deployment section in Prompt Compiler UI |
| `12_CODING_STANDARD.md` | Spor A | Config Lookup Pattern, auto-fail hardcoded paths |
| `16_FILE_ACCESS.md` | Spor A | Project Root Resolution via config.py |
| `02_ARCHITECT.md` | Spor A | Rule 9 — config getters in generated prompts |
| `knowledge-fragments/` | Spor B | 10 curated .md fragments (new directory) |
| `300_SETUPINSTRUCTION.md` | Docs | PC migration guide |

### 5.3 Next planned work

- **Spor C** — Accelerated WebUI Factory (skeleton files, project init scripts)
- **Spor D** — Governance Centralization (deferred, single governance source)

### 5.4 Git repositories

| Repo | Remote | Branch | Status |
|------|--------|--------|--------|
| DPMtF-WebUI | github.com:svend-blip/DPMtF-WebUI | master | Up to date |
| claude-bridge | github.com:svend-blip/claude-bridge | master | Up to date |

---

## 6. Quick Verification After Startup

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
```

---

## 7. PC-Specific Notes

> **These values apply ONLY to this PC (svend-MS-7D75). Change them when
> moving to another machine. See 300_SETUPINSTRUCTION.md for the full guide.**

| Setting | Value | Where |
|---------|-------|-------|
| Username | svend | System |
| Home directory | /home/svend | System |
| Project root | /home/svend/DPMtF-WebUI | dpmtf.ini |
| Bridge directory | /home/svend/claude-bridge | .env + ~/.bashrc |
| Ollama endpoint | http://127.0.0.1:11434 | CLI flag |
| Local model | qwen36-27b-q4km | CLI flag |
| Cloud model (review) | deepseek-v4-pro:cloud | CLI flag |
| Cloud model (architect) | deepseek-v4-pro:cloud | CLI flag |

---

## Related Files

- [[NextStartPrompt.md]] — Architect context recovery prompt
- [[02_ARCHITECT]] — Architect role definition
- [[300_SETUPINSTRUCTION]] — Full PC migration setup guide
- [[10_PROJECT]] — Project identity
- [[14_ARCHITECTURE]] — System architecture
- [[99_ROLEINTERACTION]] — Role loop and handoff rules
- [[100_BRIDGE]] — Bridge protocol details
