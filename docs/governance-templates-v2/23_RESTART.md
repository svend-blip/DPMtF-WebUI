# 23 — RESTART / RUNBOOK

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines how to restart the application, recover from failures, and reconstruct
session state after a restart. This is the operational runbook for all roles.

## When to Use

- **After session crash or tmux session death:** Recovery procedures.
- **When restarting the application:** Runtime commands.
- **After cold start:** Use `/STRICTREVIEW` skill for Architect context reconstruction.

---

## Application Restart

### DPMtF-WebUI (Port 9130)

```bash
cd /home/svend/DPMtF-WebUI
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 9130 --reload
```

### ENO (Port 9131)

```bash
cd /home/svend/ENO
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 9131
```

### ai-pc-resource-webui-v3 (Port 9123)

```bash
cd /home/svend/ai-pc-resource-webui-v3
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 9123
```

## Tmux Session Recovery

BridgeV002 sessions are managed via the DPMtF web UI (Setup → Bridge Setup):

- **Start tmux** — creates all sessions for a flow from `bridge_roles` config.
- **Start Coding** — launches Claude Code / OpenCode in each session.
- **Stop tmux** — kills all sessions for a flow.
- **Attach tmux** — builds viewer session with linked windows.

### Manual Recovery (if UI is unavailable)

```bash
# Check which sessions are expected for your flow
python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
for r in conn.execute(\"SELECT DISTINCT r.tmux_session FROM bridge_flow_steps s JOIN bridge_roles r ON s.from_role = r.role_key WHERE s.flow_key='strict_review' AND s.is_active=1 AND r.is_active=1\"):
    print(r[0])
conn.close()
"

# Create missing sessions
python3 scripts/bridgeV002/start_tmuxflow.py strict_review

# Launch tools in sessions
python3 scripts/bridgeV002/start_coding.py strict_review

# Attach to viewer
python3 scripts/bridgeV002/attach_tmux.py strict_review
tmux attach -t flow-strict_review
```

## After Restart Reconstruction

When a role session restarts, reconstruct context in this order:

1. **Read your flow-specific governance file** (402-405 for strict_review).
2. **Read [[10_PROJECT]]** — confirm project identity, port, repository.
3. **Read [[11_SCOPE]]** — confirm phase boundaries.
4. **Check the trace log** for recent dispatch events:
   `tail -20 {bridge_dir}/trace.log`
5. **Check current.md symlink** in each deliverable directory for latest artifact.
6. **Run git baseline checks** per [[15_GIT_POLICY]]:
   - `git status --short`
   - `git log --oneline -8`
   - `git branch --show-current`
   - `git remote -v`
7. **If any information conflicts with governance files, escalate to Human.**

## Bridge Recovery

### Scenario A: Callback Does Not Arrive (5+ min)

```bash
# Check if target session is still running
tmux ls | grep <session_name>

# Check if deliverable was written
ls -la {bridge_dir}/{flow_key}/results/

# If deliverable exists → run signal_complete manually
python3 scripts/bridgeV002/dispatch.py \
  --db-flow {flow_key} --signal-complete --from-role {from_role} --id {ID}

# If no deliverable → attach and inspect target session
tmux attach -t <session_name>
```

### Scenario B: Local Session Is Dead

```bash
/home/svend/start_review_claude.sh
# Wait for model to be ready, then resend handoff
```

### Scenario C: Wrong Handoff ID

```bash
# Check latest dispatch events
tail -20 {bridge_dir}/trace.log

# Check current counter value
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='strict_review'\").fetchone()[0]); conn.close()"
```

### Scenario D: Architect Response Does Not Arrive (5+ min)

```bash
# Check if architect session is still running
tmux ls | grep archi01

# Check if response was written
ls -la {bridge_dir}/{flow_key}/escalations/

# If response exists → run signal_answer manually
python3 scripts/bridgeV002/dispatch.py \
  --db-flow {flow_key} --signal-answer --from-role archi01 --to-role {to_role} --id {ID}

# If no response → attach and inspect
tmux attach -t archi01
```

## New Session Initialization

When starting a brand new session, use the BridgeV002 UI or:

```bash
cd /home/svend/DPMtF-WebUI
# For Architect (Claude Code):
CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 claude --model qwen3.6:35b-a3b-64k
# For other roles (OpenCode): use Start Coding button in UI
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
