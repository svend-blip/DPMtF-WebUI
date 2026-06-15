# 23 — RESTART / RUNBOOK

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines how to restart the application, recover from failures, and reconstruct
session state after `/clear`. This is the operational runbook for all roles.

## When to Use

- **After `/clear`:** Reconstruction checklist.
- **After session crash or tmux session death:** Recovery procedures.
- **When restarting the application:** Runtime commands.

---

## Application Restart

### DPMtF-WebUI (Port 9130)

```bash
cd /home/svend/DPMtF-WebUI
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130
```

### ENO (Port 9131)

```bash
cd /home/svend/ENO
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9131
```

### ai-pc-resource-webui-v3 (Port 9123)

```bash
cd /home/svend/ai-pc-resource-webui-v3
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9123
```

## Tmux Session Recovery

### Check Session Status

```bash
tmux ls
# Expected: claude_architect, claude_implementer, claude_review
```

### Restart Dead Sessions

```bash
# Start Implementor session (local model)
/home/svend/start_review_claude.sh

# For Architect and Review, start Claude Code in the project directory:
# cd /home/svend/DPMtF-WebUI && claude
```

### Manual Session Attachment

```bash
tmux attach -t claude_implementer
# Detach: Ctrl+b, d
```

## After `/clear` Reconstruction Checklist

When `/clear` is executed (manually or via bridge), the role MUST reconstruct
context in this exact order:

1. **Read [[27_NEXT_CONTEXT]]** — identify current role, phase, remaining work.
2. **Read [[10_PROJECT]]** — confirm project identity, port, repository.
3. **Read the active role file** (01, 02, 03, or 04) — understand responsibilities.
4. **Read [[11_SCOPE]]** — confirm phase boundaries.
5. **Read previous role's output** — handoff file, result file, or escalation response.
6. **Run git baseline checks** per [[15_GIT_POLICY]]:
   - `git status --short`
   - `git log --oneline -8`
   - `git branch --show-current`
   - `git remote -v`
7. **If any information conflicts with governance files, escalate to Human.**

## Bridge Recovery

### Scenario A: Notification Does Not Arrive (5+ min)

```bash
# Check if local session is still running
tmux ls | grep claude_implementer

# Check if result was written anyway
ls -la /home/svend/claude-bridge/implementertoreview/

# If result exists → run complete manually
python3 /home/svend/claude-bridge/bridge.py complete {ID}

# If no result → attach and inspect
tmux attach -t claude_implementer
```

### Scenario B: Local Session Is Dead

```bash
/home/svend/start_review_claude.sh
# Wait for model to be ready, then resend handoff
```

### Scenario C: Wrong Handoff ID

```bash
# Check used IDs across all layers
grep -E "C→L|R→A" /home/svend/claude-bridge/trace.log
# Use next available
python3 /home/svend/claude-bridge/bridge.py next-id
```

### Scenario D: Architect Response Does Not Arrive (5+ min)

```bash
# Check if architect session is still running
tmux ls | grep claude_architect

# Check if response was written anyway
ls -la /home/svend/claude-bridge/architecttoreview/

# If response exists → run answer-review manually
python3 /home/svend/claude-bridge/bridge.py answer-review {ID}

# If no response → attach and inspect
tmux attach -t claude_architect
```

## New Session Initialization

When starting a brand new session (not after `/clear`):

```bash
cd /home/svend/DPMtF-WebUI
claude
```

First prompt:
```
Read and apply:
/home/svend/DPMtF-WebUI/docs/governance-templates-v2/{ROLE_FILE}.md
Read:
/home/svend/DPMtF-WebUI/docs/governance-templates-v2/27_NEXT_CONTEXT.md
Continue where we left off.
```

---
