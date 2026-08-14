---
name: supervised_review
description: Reconstruct the Supervisor's full context after a cold start in the supervised_review flow. Use when resuming an autonomous supervisor run, after a restart, or when the supervisor session has lost context and needs to rebuild its state from durable run artifacts (GOAL.md, RUN-LEDGER.md, BACKLOG.md).
---

# SUPERVISEDREVIEW — Supervisor Cold-Start

Invoke with `/supervised_review` to reconstruct the Supervisor's full context
after a cold start in the `supervised_review` flow. The supervisor is
stateless per wake-up BY DESIGN (451): this procedure is the same rebuild it
performs on every verdict delivery — run it manually whenever the session
starts cold outside a dispatch.

## Procedure

Execute these steps in order. Do not skip any step.

### Step 0: Get the State In One Call

```bash
python3 scripts/bridgeV002/supervisor_state.py --flow supervised_review
```

Pass `--flow supervised_review` explicitly — the script's default is another
flow (`llama_SG`), and running it bare reports a different flow's state
without any error. The report answers where the bridge directory is, which
run is active and which of its four artefacts exist, the flow counter, the
handoffs this run owns, the last `trace.log` signal, whether the WebUI,
database and tmux sessions are up, and a one-line assessment. It applies the
**run floor**, which the watchdog cannot — the watchdog locks onto the
newest handoff id on disk regardless of which run owns it.

Steps 1-6 verify and deepen what Step 0 reports; where they disagree,
investigate before acting.

### Step 1: Resolve Bridge Directory

The bridge directory is configured by `DPMTF_BRIDGE_DIR`. When that is unset,
`config.get_bridge_dir()` falls back to `[paths] bridge_dir` in `dpmtf.ini`,
and failing that to `{project_root}/flows`. Resolve it:
```bash
echo $DPMTF_BRIDGE_DIR   # must name an existing directory
```
If empty, or still pointing at a `claude-bridge` directory, the environment is
stale — export it to your flows directory before proceeding.

All bridge paths below use `{bridge_dir}` as shorthand.

### Step 2: Locate the Active Run

Run state lives under `{bridge_dir}/supervised_review/runs/{run_id}/` — the
flow's OWN run directory, which is also where Step 0 looked:
```bash
ls {bridge_dir}/supervised_review/runs/
```
Historical runs `goal-001` … `goal-023` (all closed) live under the legacy
root `{bridge_dir}/supervisor/runs/` and stay there; never open a new run
in that directory (migration 026, 451).
The active run is the newest directory WITHOUT an `END-REPORT.md`. If every
run has one, there is no active run — report that and wait for the Human
(a new run requires a Human-approved GOAL.md; never start one yourself).

For the active run, read IN THIS ORDER:
1. `GOAL.md` — the immutable Mission Contract (objective, testgoals, scope
   fence, budgets, standing approvals)
2. `RUN-LEDGER.md` — tail (last 2-3 entries): what happened, what was
   dispatched, what the scheduler should expect next
3. `BACKLOG.md` — planned/dispatched handoffs and their status

The ledger is your memory. Never reconstruct state from summaries or
recollection — only from these files plus the checks below.

### Step 3: Confirm the Flow Counter

```bash
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='supervised_review'\").fetchone()[0]); conn.close()"
```
The counter is authoritative — gaps from incomplete handoffs are normal.
Do not investigate gaps or compare against files on disk.

### Step 4: Read Role Definitions

Read `docs/governance-templates-v2/451_SUPERVISED_REVIEW_SUPERVISOR.md` (extends
`500_SUPERVISOR.md`). Confirm:
- Wake-up protocol (rebuild → stop-check → act → persist → stop)
- Event handling table (verdict APPROVED/REJECTED, escalation, watchdog,
  empty backlog, invariant breach)
- Decision matrix (decide alone vs. park for the Human)
- Stop conditions and ledger entry format

Hard rules 1-3 and 5-10 of `docs/StartUpNextSession.md` §3 apply; rule 4 is
adapted (commits allowed ONLY on the GOAL.md feature branch under its
Standing Approvals).

### Step 5: Verify Environment (451 Invariants)

```bash
cd "$(git rev-parse --show-toplevel)"
curl -s http://localhost:9130/api/health
python3 -c "import sqlite3; sqlite3.connect('databases/dpmtf.db').execute('SELECT 1'); print('DB opens OK')"
git branch --show-current   # must equal the feature branch named in GOAL.md
git status --porcelain      # no changes outside the Scope Fence
                            # (M databases/dpmtf.db = live bookkeeping, expected)

# Verify chain tmux sessions
for s in imple01sup review01sup review02sup supervisor_auto; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```
Any invariant failure → park with a ledger entry. Never dispatch onto a
broken foundation.

### Step 6: Determine Chain Position

Let `{ID}` be the highest handoff id present in
`{bridge_dir}/supervised_review/handoffs/`. Check which chain deliverables
exist for it (`results/{ID}-result.md`, `reviews/{ID}-review01.md`,
`verdicts/{ID}-verdict.md`) and what `{bridge_dir}/trace.log` shows as the
last signal for `{ID}`. The watchdog does this mechanically:

```bash
python3 scripts/bridgeV002/chain_watchdog.py --flow supervised_review --once --dry-run
```

| Watchdog status | Meaning | Your action |
|-----------------|---------|-------------|
| `complete` | Final signal review02sup→supervisor_auto delivered | If the ledger has no entry for this verdict, the wake-up was missed — process it now per 451 (verify testgoals yourself, checkpoint, next handoff or run end) |
| `active` | A role is working or a signal was just delivered | Wait. Do NOT dispatch. Ensure a live watchdog is running (see Rules) |
| `nudged` (dry-run: "NOT sent") | Stall detected — the log line names the stalled role and which of the two forms it is | Verify via trace.log, then either let a non-dry-run watchdog pass nudge, or nudge manually per 451 (once), then ledger it |
| `idle` | Chain not started, or the stalled role has already used its 2 nudges | Diagnose from trace.log + panes; park if the budget is spent |

Two known failure modes, both repaired by re-delivering the SENDER's
callback but diagnosed differently:

- **Sender stall** (run goal-001, handoff 5): a role writes its deliverable
  and ends its turn without signal-complete. No signal_complete on
  trace.log; timed by the deliverable's mtime.
- **Receiver stall** (run goal-006, handoff 21): a role is dispatched,
  produces NOTHING, and goes idle. The signal IS on trace.log; timed by
  that signal's age, because the sender's file age says nothing about how
  long the receiver has been silent.

**Do not decide either from the pane.** capture-pane history is useless for
this (TUI redraw), and the status line is worse than useless: it is
frontend-specific and wrong in both directions. Measured 2026-08-12 — an
OpenCode role one minute into real work showed no `esc interrupt` and read
as idle, while a role whose request had died showed `esc interrupt` for two
hours and read as busy. A Pi pane fails differently again: its footer
carries a token counter containing `↓`, which is itself one of the markers,
so a finished Pi role reads as busy forever.

Two sources are factual rather than cosmetic, and both should agree before
you act:

- **`{bridge_dir}/trace.log`** — what was delivered, when, and to whom.
- **The role's own session, read from the client it actually runs.** For
  OpenCode: `opencode session list` then `opencode export <id>`, with the
  role's `OPENCODE_CONFIG` set and its working directory as cwd; a turn
  still in flight has no `completed` timestamp. For Pi: its session files,
  unless the role runs `--no-session`, in which case trace.log is all there
  is. For a locally served model, `curl :8080/slots` reports
  `is_processing`, which is the one signal no TUI can misreport.

Which of those applies depends on the role's `allocator_client`, not on
this flow — see `101_CODE_FRONTENDS.md`.

### Step 7: Report to Human

Summarize in a compact table:

| Field | Value |
|-------|-------|
| Flow | supervised_review |
| Run | {run_id} ({active / no active run}) |
| Testgoals | {green}/{total} per latest ledger entry |
| Budgets | handoffs {used}/{max}, wall-clock remaining |
| Last handoff | {ID + title from BACKLOG.md} |
| Chain position | {watchdog status + which deliverables exist} |
| Next handoff ID | {from database counter} |
| tmux sessions | imple01sup/review01sup/review02sup/supervisor_auto running / NOT RUNNING |
| Invariants | green / FAILED: {which} |
| Assessment | ready / waiting for verdict / stall — action needed / parked |

Then wait for the Human (or, mid-run with all invariants green and an
unprocessed event found in Step 6, proceed per the 451 wake-up protocol).

## Rules

- **Execute steps 0-7 in order. Do not skip. Do not add extra investigation.**
- **A run without an approved GOAL.md must not start** — park with
  `HUMAN_ACTION_REQUIRED`.
- **Loop guard:** never send signal-complete for a verdict delivery you are
  processing — the next handoff gets a NEW id via the flow counter.
- **Run a watchdog alongside every autonomous run:**
  `python3 scripts/bridgeV002/chain_watchdog.py --flow supervised_review --max-minutes {run budget}`
  (it catches the wrote-output-but-never-signaled stall; max 2 nudges/step).
- **Append a ledger entry for every action taken after a cold start** — the
  ledger, not the session, is the run's memory.
- **All communication in English (en-US)** except direct Human interaction.
