---
name: strict-review
description: Reconstruct the Architect's full context after a cold start or ollama stop cycle in the strict_review flow. Use when resuming work in the strict_review BridgeV002 flow, after a restart, or when the Architect session has lost context and needs to rebuild its state from durable files.
---

# STRICTREVIEW — Architect Cold-Start

Invoke with `/strict-review` to reconstruct the Architect's full context after
a cold start or `ollama stop` cycle in the `strict_review` flow.

## Procedure

Execute these steps in order. Do not skip any step.

### Step 1: Resolve Bridge Directory

The bridge directory is configured by `DPMTF_BRIDGE_DIR` (env var, default `/home/svend/flows`).
Resolve it:
```bash
echo $DPMTF_BRIDGE_DIR   # should be /home/svend/flows
```
If empty or pointing to `/home/svend/claude-bridge`, the environment is stale —
`export DPMTF_BRIDGE_DIR=/home/svend/flows` before proceeding.

All bridge paths below use `{bridge_dir}` as shorthand for this resolved directory.

### Step 2: Read Cycle State

Read `docs/bridgeV002/current-cycle.json`. Extract:
- `last_handoff` — the most recent handoff ID (null if none)
- `title` — what the last handoff was about
- `active_role` — which role is currently active
- `design_notes` — key design decisions from the last cycle
- `verification_checklist` — what to verify when the verdict returns
- `open_gaps` — any unresolved issues
- `branch` and `commit` — current git state

Cross-check with the database and trace log for the actual latest handoff:
```bash
# Latest handoff ID from database counter (next_id - 1)
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='strict_review'\").fetchone()[0] - 1); conn.close()"

# Latest dispatch events
tail -5 {bridge_dir}/trace.log
```

### Step 3: Read Durable Reference

Read `docs/StartUpNextSession.md`. Confirm:
- Your role (Architect / Handoff Writer)
- The 10 hard rules
- Tmux session layout
- PC-specific paths and ports

### Step 4: Read Flow-Specific Role Definition

Read `docs/governance-templates-v2/402_STRICT_REVIEW_ARCHI01.md`. Confirm:
- Handoff format (required XML sections)
- Dispatch command (`signal_send`)
- Post-handoff stop rule
- Escalation response format

### Step 5: Verify Environment

Run these checks:
```bash
cd /home/svend/DPMtF-WebUI
python3 -m py_compile app.py && echo "app.py OK"
curl -s http://localhost:9130/api/health
curl -s http://localhost:9130/api/bridge-v2/status
curl -s http://localhost:9130/api/bridge-v2/flows

# Verify all 4 strict_review tmux sessions are running
for s in archi01 imple01 review01 review02; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

### Step 6: Determine Next Action

Based on `active_role` in current-cycle.json:

| active_role | Action |
|-------------|--------|
| `archi01` | You are active. If `last_handoff` is set and `verification_checklist` has items, a verdict may have returned — check `{bridge_dir}/strict_review/verdicts/{last_handoff}-verdict.md`. Otherwise, wait for Human instruction or start next handoff. |
| `imple01` | Implementer is active. Wait — do NOT start new work. |
| `review01` | Review layer 1 is active. Wait. |
| `review02` | Review layer 2 is active. Wait. |
| `human` | Human has the verdict. Wait for Human instruction. |

### Step 7: Report to Human

Summarize your findings in 3-5 lines:
- Current flow and active role
- Last handoff (ID and title, if any)
- Open gaps (if any)
- Your assessment: ready to work, waiting for verdict, or waiting for Human

Then wait for Human to give the next instruction.

## Rules

- **Execute steps 1-7 in order. Do not skip. Do not add extra investigation.**
  The procedure is complete when Step 7 is done — stop there.
- **NEVER start work if another role is active** (Rule 1 — NO parallel work).
- **NEVER dispatch without updating current-cycle.json first** (§4 save-state procedure).
- **All communication in English (en-US)** except direct Human interaction.
