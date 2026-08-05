---
name: llama_SG
description: Reconstruct the supervisor01_llama context after a cold start in the llama_SG flow. Use when resuming an autonomous supervisor run, after a restart, or when the supervisor session has lost context and needs to rebuild its state from durable run artifacts (GOAL.md, RUN-LEDGER.md, BACKLOG.md).
---

# LLAMASG — Supervisor Cold-Start

Invoke with `/llama_SG` to reconstruct the supervisor01_llama full context
after a cold start in the `llama_SG` flow. The supervisor is stateless per
wake-up BY DESIGN (461): this procedure is the same rebuild it performs on
every verdict delivery — run it manually whenever the session starts cold
outside a dispatch.

## Procedure

Execute these steps in order. Do not skip any step.

### Step 1: Resolve Bridge Directory

The bridge directory is configured by `DPMTF_BRIDGE_DIR` (env var, default
`/home/svend/flows`). Resolve it:
```bash
echo $DPMTF_BRIDGE_DIR   # should be /home/svend/flows
```
If empty or pointing to `/home/svend/claude-bridge`, the environment is stale —
`export DPMTF_BRIDGE_DIR=/home/svend/flows` before proceeding.

All bridge paths below use `{bridge_dir}` as shorthand.

### Step 2: Locate the Active Run

Run state lives under `{bridge_dir}/llama_SG/runs/{run_id}/`:
```bash
ls {bridge_dir}/llama_SG/runs/
```
The active run is the newest directory WITHOUT an `END-REPORT.md`. If every
run has one, there is no active run — report that and wait for the Human
(a new run requires a Human-approved GOAL.md; never start one yourself).

For the active run, read IN THIS ORDER:
1. `GOAL.md` — the immutable Mission Contract (objective, testgoals, scope
   fence, budgets, standing approvals, and **`First handoff id:`**)
2. `RUN-LEDGER.md` — tail (last 2-3 entries): what happened, what was
   dispatched, what the scheduler should expect next
3. `BACKLOG.md` — planned/dispatched handoffs and their status

**Note the `First handoff id:` as you read GOAL.md** — it is the counter
value at the moment the run opened, and it is what separates this run's work
from every earlier run's. Handoff ids, `trace.log` and the handoffs
directory are flow-wide and never reset, so without that number a fresh run
cannot tell its own chain from a closed one's. Step 6 depends on it.

Every new run's GOAL.md must state it. When opening a run, read the counter
(Step 3) and record that value.

The ledger is your memory. Never reconstruct state from summaries or
recollection — only from these files plus the checks below.

### Step 3: Confirm the Flow Counter

```bash
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='llama_SG'\").fetchone()[0]); conn.close()"
```
The counter is authoritative — gaps from incomplete handoffs are normal.
Do not investigate gaps or compare against files on disk.

### Step 4: Read Role Definitions

Read `docs/governance-templates-v2/461_LLAMA_SG_SUPERVISOR.md` (extends
`500_SUPERVISOR.md`). Confirm:
- Wake-up protocol (rebuild → stop-check → act → persist → stop)
- Event handling table (verdict APPROVED/REJECTED, escalation, watchdog,
  empty backlog, invariant breach)
- Decision matrix (decide alone vs. park for the Human)
- Stop conditions and ledger entry format

Hard rules 1-3 and 5-10 of `docs/StartUpNextSession.md` §3 apply; rule 4 is
adapted (commits allowed ONLY on the GOAL.md feature branch under its
Standing Approvals).

### Step 5: Verify Environment

```bash
cd /home/svend/DPMtF-WebUI
curl -s http://localhost:9130/api/health
python3 -c "import sqlite3; sqlite3.connect('databases/dpmtf.db').execute('SELECT 1'); print('DB opens OK')"

# Verify Laguna is reachable (required for supervisor to work)
curl -s http://127.0.0.1:8080/health && echo "Laguna: reachable" || echo "Laguna: NOT REACHABLE"

# Verify chain tmux sessions
for s in supervisor01_llama imple01SG review01SG; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

### Step 6: Determine Chain Position

**First: establish this run's handoff floor.**

Handoff ids are allocated from a flow-wide counter and never reset, so the
handoffs directory, `trace.log` and the watchdog all carry every run's work
mixed together. A run owns only the ids allocated **after it opened**.

GOAL.md records `First handoff id:` for the run. Every id below it belongs
to an earlier run that is already closed, and is none of your business —
however unfinished it looks, and however empty your own ledger is.

This matters because the two obvious signals point the wrong way for a fresh
run: the highest id on disk belongs to the *previous* run, and your ledger
has no entry for it precisely because it was never yours. On 2026-08-05 run
004 cold-started, found run 003's handoff 006, re-validated a verdict that
run 003's END-REPORT had already settled, and parked run 004 on the previous
run's exhausted budget.

If GOAL.md carries no `First handoff id:`, take it from the run's opening
ledger entry. If neither states it, treat the run as not started and ask the
Human rather than adopting whatever is on disk.

Let `{ID}` be the highest handoff id in `{bridge_dir}/llama_SG/handoffs/`
**that is greater than or equal to the run's first handoff id**. If no id
qualifies, the chain has not started for this run: write the first handoff
per 461 and do not process anything older.

Then check which chain deliverables exist for `{ID}`
(`results/{ID}-result.md`, `verdicts/{ID}-verdict.md`) and what
`{bridge_dir}/trace.log` shows as the last signal for it. The watchdog does
this mechanically, but note it has **no notion of run boundaries** — it
locks onto the newest id on disk regardless of which run owns it. Apply the
floor yourself before believing what it reports:

```bash
python3 scripts/bridgeV002/chain_watchdog.py --flow llama_SG --once --dry-run
```

| Watchdog status | Meaning | Your action |
|-----------------|---------|-------------|
| `complete` | Final signal review01SG→supervisor01_llama delivered | **Check the floor first.** If the id is below this run's first handoff id, it belongs to a closed run — ignore it entirely. Otherwise, if the ledger has no entry for this verdict, the wake-up was missed — process it now per 461 |
| `active` | A role is working or a signal was just delivered | Wait. Do NOT dispatch. Ensure a live watchdog is running |
| `nudged` (dry-run: "NOT sent") | Stall detected | Verify via trace.log, then either let a non-dry-run watchdog pass nudge, or nudge manually per 461 (once), then ledger it |
| `idle` | Chain not started, or the stalled role has already used its 2 nudges | Diagnose from trace.log + panes; park if the budget is spent |

### Step 7: Report to Human

Summarize in a compact table:

| Field | Value |
|-------|-------|
| Flow | llama_SG |
| Run | {run_id} ({active / no active run}) |
| Testgoals | {green}/{total} per latest ledger entry |
| Budgets | handoffs {used}/{max}, wall-clock remaining |
| Last handoff | {ID + title from BACKLOG.md} |
| Chain position | {watchdog status + which deliverables exist} |
| Next handoff ID | {from database counter} |
| tmux sessions | supervisor01_llama/imple01SG/review01SG running / NOT RUNNING |
| Laguna | reachable / NOT REACHABLE |
| Assessment | ready / waiting for verdict / stall — action needed / parked |

Then wait for the Human (or, mid-run with all invariants green and an
unprocessed event found in Step 6, proceed per the 461 wake-up protocol).

## Rules

- **Execute steps 1-7 in order. Do not skip. Do not add extra investigation.**
- **A run without an approved GOAL.md must not start** — park with
  `HUMAN_ACTION_REQUIRED`.
- **Loop guard:** never send signal-complete for a verdict delivery you are
  processing — the next handoff gets a NEW id via the flow counter.
- **Run a watchdog alongside every autonomous run:**
  `python3 scripts/bridgeV002/chain_watchdog.py --flow llama_SG --max-minutes {run budget}`
- **Append a ledger entry for every action taken after a cold start** — the
  ledger, not the session, is the run's memory.
- **All communication in English (en-US)** except direct Human interaction.
