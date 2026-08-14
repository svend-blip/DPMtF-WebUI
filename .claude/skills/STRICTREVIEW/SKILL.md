---
name: strict_review
description: Reconstruct the Architect's full context after a cold start or ollama stop cycle in the strict_review flow. Use when resuming work in the strict_review BridgeV002 flow, after a restart, or when the Architect session has lost context and needs to rebuild its state from durable files.
---

# STRICTREVIEW — Architect Cold-Start

Invoke with `/strict_review` to reconstruct the Architect's full context after
a cold start or `ollama stop` cycle in the `strict_review` flow.

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

Read `docs/bridgeV002/current-cycle-strict-review.json`. Extract:
- `last_handoff` — the most recent handoff ID (null if none)
- `title` — what the last handoff was about
- `active_role` — which role is currently active
- `design_notes` — key design decisions from the last cycle
- `verification_checklist` — what to verify when the verdict returns
- `open_gaps` — any unresolved issues
- `branch` and `commit` — current git state

Confirm the current counter value (next handoff will use this number):
```bash
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='strict_review'\").fetchone()[0]); conn.close()"
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

Read `docs/governance-templates-v2/402_STRICT_REVIEW_ARCHI01.md`. Confirm:
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

# Verify all 4 strict_review tmux sessions are running
for s in archi01 imple01 review01 review02; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

### Step 6: Determine Next Action

Based on `active_role` in current-cycle-strict-review.json:

| active_role | Action |
|-------------|--------|
| `archi01` | You are active. If `last_handoff` is set and `verification_checklist` has items, a verdict may have returned — check `{bridge_dir}/strict_review/verdicts/{last_handoff}-verdict.md`. Otherwise, wait for Human instruction or start next handoff. |
| `imple01` | Implementer is active. Wait — do NOT start new work. |
| `review01` | Review layer 1 is active. Wait. |
| `review02` | Review layer 2 is active. Wait. |
| `human` | Human has the verdict. Wait for Human instruction. |

### Step 7: Report to Human

Summarize in a compact table:

| Field | Value |
|-------|-------|
| Flow | strict_review |
| Active role | {from current-cycle-strict-review.json} |
| Last handoff | {ID + title from current-cycle-strict-review.json} |
| Next handoff ID | {from database counter} |
| tmux sessions | all 4 running / NOT RUNNING: {list} |
| Assessment | ready / waiting for verdict / waiting for Human |

Do NOT list gaps, missing files, or discrepancies — the counter is authoritative.
Then wait for Human to give the next instruction.

## The Frontend Is A Database Fact

Which client each role runs under is recorded in
`bridge_roles.allocator_client`, and only there — this procedure works
unchanged under Claude Code, OpenCode and Pi (`101_CODE_FRONTENDS.md`).
Never assume a client from habit or from an older version of this file;
look it up:

```bash
sqlite3 -readonly databases/dpmtf.db "SELECT role_key, allocator_client, \
  fresh_session_command FROM bridge_roles WHERE role_key IN ('archi01','imple01','review01','review02')"
```

The one trap with a shared name is context reset. Claude Code's `/clear`
genuinely clears the conversation; OpenCode's `/clear` is a prompt that
costs window instead of freeing it — an OpenCode role resets with `/new`.
The role's `fresh_session_command` in the same table is authoritative: the
dispatcher uses it, and so should you.

## Framework Questions Go To mcp-light

`mcp-light` serves this flow's wiring at `http://127.0.0.1:9135/mcp`. How
it reaches you depends on the client: Claude Code reads `~/.mcp.json`,
OpenCode reads the `mcp` block in the role's `opencode.json` (the
allocator's config refresh preserves it), Pi declares it in settings or an
extension. If the tools below are not offered, that is what to check — do
not fall back to deriving the answers by hand. Use it for anything about
how the flow is wired:

| Question | Tool |
|---|---|
| Where does a deliverable go, and under what name? | `get_flow_steps("strict_review")` |
| What does 402 say? | `get_governance_file("402_STRICT_REVIEW_ARCHI01.md")` |
| How is a role configured? | `get_role("archi01")` |
| What did an earlier verdict conclude? | `search_verdicts(query)` |

## Rules

- **Execute steps 1-7 in order. Do not skip. Do not add extra investigation.**
  The procedure is complete when Step 7 is done — stop there.
- **NEVER start work if another role is active** (Rule 1 — NO parallel work).
- **NEVER dispatch without updating current-cycle-strict-review.json first** (§4 save-state procedure).
- **All communication in English (en-US)** except direct Human interaction.
