---
name: cloud-llm
description: Reconstruct the Architect's full context after a cold start or ollama stop cycle in the cloud_llm flow. Use when resuming work in the cloud_llm BridgeV002 flow, after a restart, or when the Architect session has lost context and needs to rebuild its state from durable files.
---

# CLOUDLLM — Architect Cold-Start

Invoke with `/CLOUDLLM` to reconstruct the Architect's full context after
a cold start or `ollama stop` cycle in the `cloud_llm` flow.

## Procedure

Execute these steps in order. Do not skip any step.

### Step 1: Resolve Bridge Directory

The bridge directory is configured by `DPMTF_BRIDGE_DIR`. When that is unset,
`config.get_bridge_dir()` falls back to `[paths] bridge_dir` in `dpmtf.ini`,
and failing that to `{project_root}/flows`.
Resolve it:
```bash
echo $DPMTF_BRIDGE_DIR   # must name an existing directory
```
If empty, or still pointing at a `claude-bridge` directory, the environment is
stale — export it to your flows directory before proceeding.

All bridge paths below use `{bridge_dir}` as shorthand for this resolved directory.

### Step 2: Read Cycle State

Read `docs/bridgeV002/current-cycle-cloud-llm.json`. Extract:
- `last_handoff` — the most recent handoff ID (null if none)
- `title` — what the last handoff was about
- `active_role` — which role is currently active
- `design_notes` — key design decisions from the last cycle
- `verification_checklist` — what to verify when the verdict returns
- `open_gaps` — any unresolved issues
- `branch` and `commit` — current git state

Confirm the current counter value (next handoff will use this number):
```bash
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='cloud_llm'\").fetchone()[0]); conn.close()"
```
The counter is authoritative — gaps from incomplete handoffs are normal.
Do not investigate gaps or compare against files on disk.

### Step 3: Read Durable Reference

Read `docs/StartUpNextSession.md`. Confirm:
- Your role (Architect / Handoff Writer)
- The 10 hard rules
- Tmux session layout
- PC-specific paths and ports

### Step 4: Read Flow-Specific Role Definition

Read `docs/governance-templates-v2/412_CLOUD_LLM_ARCHI01CLOUD.md`. Confirm:
- Handoff format (required XML sections)
- Dispatch command (`signal_send`)
- Post-handoff stop rule
- Escalation response format

### Step 5: Verify Environment

Run these checks:
```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m py_compile app.py && echo "app.py OK"
curl -s http://localhost:9130/api/health
curl -s http://localhost:9130/api/bridge-v2/status
curl -s http://localhost:9130/api/bridge-v2/flows

# Verify all 4 cloud_llm tmux sessions are running
for s in archi01cloud imple01cloud review01cloud review02cloud; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

### Step 6: Determine Next Action

Based on `active_role` in current-cycle-cloud-llm.json:

| active_role | Action |
|-------------|--------|
| `archi01cloud` | You are active. If `last_handoff` is set and `verification_checklist` has items, a verdict may have returned — check `{bridge_dir}/cloud_llm/verdicts/{last_handoff}-verdict.md`. Otherwise, wait for Human instruction or start next handoff. |
| `imple01cloud` | Implementer is active. Wait — do NOT start new work. |
| `review01cloud` | Review layer 1 is active. Wait. |
| `review02cloud` | Review layer 2 is active. Wait. |
| `humancloud` | Human has the verdict. Wait for Human instruction. |

### Step 7: Report to Human

Summarize in a compact table:

| Field | Value |
|-------|-------|
| Flow | cloud_llm |
| Active role | {from current-cycle-cloud-llm.json} |
| Last handoff | {ID + title from current-cycle-cloud-llm.json} |
| Next handoff ID | {from database counter} |
| tmux sessions | all 4 running / NOT RUNNING: {list} |
| Assessment | ready / waiting for verdict / waiting for Human |

Do NOT list gaps, missing files, or discrepancies — the counter is authoritative.
Then wait for Human to give the next instruction.

## Rules

- **Execute steps 1-7 in order. Do not skip. Do not add extra investigation.**
  The procedure is complete when Step 7 is done — stop there.
- **NEVER start work if another role is active** (Rule 1 — NO parallel work).
- **NEVER dispatch without updating current-cycle-cloud-llm.json first** (§4 save-state procedure).
- **All communication in English (en-US)** except direct Human interaction.
