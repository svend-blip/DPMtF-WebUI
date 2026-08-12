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

**The invocation carries no arguments, and needs none.** Everything about the
current run is discoverable and this procedure discovers it: Step 2 finds the
active run (the newest without an END-REPORT) and reads its GOAL.md, Step 3
reads the flow counter, Step 6 establishes the handoff floor that separates
this run's work from every closed run's. If you find yourself being told the
run number, the first handoff id, or that a watchdog is already running, the
procedure should be learning that itself — fix the procedure rather than the
prompt.

**Starting a new run therefore takes two things:** a Human-approved GOAL.md in
a fresh `runs/{id}/` directory, and `/llama_SG`. The approved GOAL.md *is* the
authorisation to begin; Step 7 says what to do when it finds a run that has
opened but not started.

## Step 0: Get the State In One Call

```bash
python3 scripts/bridgeV002/supervisor_state.py
```

This answers Steps 1, 2, 3, 5 and 6 at once, and **applies the run floor while
doing so** — which `chain_watchdog` cannot, because it locks onto the newest
handoff id on disk regardless of which run owns it. It reports the resolved
bridge directory, the active run and which of its four artefacts exist, the
`First handoff id` parsed from GOAL.md, the flow counter, the handoffs this
run owns, what has been written for the current one, its last `trace.log`
signal, whether the WebUI, database, Laguna and the three tmux sessions are
up, what is missing, and a one-line assessment.

Read the assessment, then act on it:

| Assessment | What it means |
|---|---|
| `NO ACTIVE RUN` | Every run has an END-REPORT. A new run needs a Human-approved GOAL.md — never open one yourself. |
| `PARK` | GOAL.md or the handoff floor is missing. Report and wait; do not adopt what is on disk. |
| `RUN OPENED, CHAIN NOT STARTED` | Author BACKLOG.md, then write and dispatch the first handoff per Standing Approvals. |
| `HANDOFF nnn DISPATCHED` / `RESULT DELIVERED` | A role is working. Wait. Do not dispatch. |
| `VERDICT READY for nnn` | Validate the testgoals yourself, then act per 461. |

You still need Step 4 — the role definitions — and Step 7's report. **Steps
1-6 below are the long form**, kept because the script can fail and because
they explain *why* each check matters. Run them by hand only when the script
does not run or its answer looks wrong.

## Procedure

Execute these steps in order. Do not skip any step.

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

### Step 4: Read The Sections You Need

`461_LLAMA_SG_SUPERVISOR.md` is 205 lines across thirteen sections, and
`500_SUPERVISOR.md` another 63. About half is relevant to any one wake-up, and
which half depends on what Step 0 found. Read by section, not by file:

| Step 0 said | Read from 461 |
|---|---|
| `RUN OPENED, CHAIN NOT STARTED` | Wake-Up Protocol · Event Handling · **Writing a Handoff — Absolute Paths in Every Instruction** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `VERDICT READY` | Wake-Up Protocol · Event Handling · **Validating an APPROVED Verdict** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| A gate escalation | the above, plus **What a Gate Escalation Means — And What It Deliberately Does Not** |
| `PARK` or `NO ACTIVE RUN` | Stop Conditions, and nothing else — you are reporting, not acting |

Read `500_SUPERVISOR.md` once per run, not per wake-up: it is the base
contract and does not change between events.

The two sections in bold are the ones a wake-up gets wrong when it skips them,
and they are mutually exclusive — a run that is dispatching is not validating.
Reading both every time is how a five-minute rebuild becomes a fifteen-minute
one.

Hard rules 1-3 and 5-10 of `docs/StartUpNextSession.md` §3 apply; rule 4 is
adapted (commits allowed ONLY on the GOAL.md feature branch under its
Standing Approvals).

### Step 5: Verify Environment

```bash
cd "$(git rev-parse --show-toplevel)"
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

Then act on what you found, without waiting to be told again:

| What Step 6 found | What to do |
|---|---|
| **A run with GOAL.md but no BACKLOG.md, and no handoff at or above the floor** | The run has just opened. Author BACKLOG.md, then write and dispatch the first handoff per GOAL.md's Standing Approvals. Do not report and stop — opening the run *is* the Human's instruction. |
| An unprocessed event at or above the floor, all invariants green | Proceed per the 461 wake-up protocol. |
| Anything below the floor | Ignore it. It belongs to a closed run. |
| A scope breach, a repeated gate rejection, a missing GOAL.md, or a budget spent | Park with `HUMAN_ACTION_REQUIRED` and report. |

The Human opens a run by writing and approving GOAL.md. That approval is the
authorisation to start the chain; it does not need to be repeated in the
invocation.

## Framework Questions Go To mcp-light

`mcp-light` serves this flow's wiring at `http://127.0.0.1:9135/mcp`. All
three roles here run under Claude Code, which reads `~/.mcp.json`, so this
session already has it. That path is the client's, not the flow's: an
OpenCode role gets mcp-light from the `mcp` block in its own
`opencode.json`, and a Pi role from Pi's settings (101). If the tools below
are not offered to you, check whichever of those applies rather than
deriving the answers by hand. **Use it for anything about how the
flow is wired.** It answers from the database in one call, with structured
output:

| Question | Tool |
|---|---|
| Where does a deliverable go, and under what filename? | `get_flow_steps("llama_SG")` |
| What does 461 or 500 say? | `get_governance_file("461_LLAMA_SG_SUPERVISOR.md")` |
| How is a role configured? | `get_role("supervisor01_llama")` |
| What did an earlier verdict conclude? | `search_verdicts(query)` |

`get_flow_steps` returns exactly this:

```json
{"step_key": "supervisor-imple01", "deliverable_dir": "llama_SG/handoffs",
 "deliverable_pattern": "{ID}-handoff.md", "rule_key": "handoff"}
```

On 2026-08-06 a cold start spent fourteen minutes deriving that from
`dispatch.py`'s argument parsing. The tool was connected the whole time. **If a
question is about the framework rather than the run's actual work, it is a
lookup — not something to reason out.**

mcp-light knows the database and the governance templates. It knows nothing
about `{bridge_dir}/llama_SG/runs/` — the active run, GOAL.md, the ledger, the
handoff floor. Those come from Steps 1-6.

## Standing Run Context — True Of Every Run

These held for runs 005-008 and hold until this file says otherwise. **A
GOAL.md must not repeat them.** Four consecutive contracts carried
near-identical copies of the blocks below — roughly 3 KB re-read on every
wake-up, describing nothing specific to the run at hand.

### The models

Each role runs the model that suits its work, and they are never resident at
the same time. Dispatch stops the outgoing model, waits for nvidia-smi to
confirm the memory came back, and only then loads the next.

| Role | Model | Context |
|------|-------|---------|
| `supervisor01_llama` | `laguna-local` (Laguna-S-2.1-IQ4_XS) | 262144, one slot |
| `imple01SG` | `imple-fast` (qwen3.6:27b-q4_K_M) | 65536 |
| `review01SG` | `review02-local` (qwen3.6:35b-a3b-64k) | 65536 |

### Verdict discipline

The reviewer reviews the working tree, never the result file. Every accepted
claim is backed by a command the reviewer ran, with its real output in the
verdict. `git status --short` comes first. Unverified means REJECTED. Two
roles agreeing is not evidence. Paste the command you actually ran — a garbled
one costs the supervisor a re-derivation.

### What counts as a scope breach

**`databases/dpmtf.db` is never a scope breach.** The flow writes to it on
every dispatch — the id counter, `jobs`, `job_events`, `model_leases`. It is
exhaust, not deliverable. Run 006's contract failed to say so and cost the
supervisor twenty minutes proving it harmless.

A scope breach is any modified tracked file outside GOAL.md's Scope Fence,
`databases/dpmtf.db` excepted. Untracked clutter — stray `.log` files, the
`docs/superpowers/` documents — is pre-existing. Ignore it; never delete or
commit it.

### Budgets

Measure the chain's **active** working time from `trace.log`, not the wall
clock. Run 007 read 7h45m against a 3h budget because the clock ran while the
supervisor slept between signals, while the chain itself worked six minutes.

Park on a blocked dependency, a scope-fence breach, a gate rejection that
repeats, two consecutive failed nudges, or a verdict without an Evidence
section (reject once, then park) — not on the clock alone, and never on a
known infrastructure defect.

### What a GOAL.md should therefore contain

Only what is true of *this* run: why it exists, the measured work, the
testgoals with their mechanical green criteria, the Scope Fence file list, the
budget numbers, and the Standing Approvals. Nothing above.

### Testgoals go in a machine-readable block

Alongside the prose, a GOAL.md carries its criteria in a fenced `testgoals`
block so they can be run rather than re-derived:

```
​```testgoals
id: TG1
what: No "# Default:" line states one machine's answer
run: grep -n '^# Default:' .env.example | grep '/home/'
expect: empty

id: TG2
what: The four "# Example:" lines are untouched
run: grep -c '^# Example: /home/svend' .env.example
expect: equals 4
​```
```

`expect:` takes `empty`, `equals N`, `at least N`, `at most N`,
`contains TEXT` or `exit 0`. Validate with:

```bash
python3 scripts/bridgeV002/check_testgoals.py {bridge_dir}/llama_SG/runs/{run_id}/GOAL.md
```

**This settles the facts, not the verdict.** It tells you what each criterion
returned against what the contract asked. Whether the verdict's claims are
honest, whether its evidence was really gathered, and whether a green testgoal
was reached the right way remain yours to judge — that judgement is the only
thing a supervisor is genuinely needed for.

### Ledger entries and END-REPORTs have a generator too

```bash
python3 scripts/bridgeV002/run_report.py ledger --event verdict-012-APPROVED
python3 scripts/bridgeV002/run_report.py end-report
```

It prints a skeleton with the facts already in it — which run, which handoffs,
what each criterion returned, and the chain's active time computed from
`trace.log` rather than the wall clock. Nothing is written to disk: review it,
replace every `TODO`, and save it yourself.

**Every field that is a judgement is left as `TODO` on purpose.** What the
event meant, what you did about it, whether the content is right and not
merely counted — those are yours. A skeleton that quietly asserted a
conclusion would read like your own words.

Do not go looking at closed runs for the format. Run 009 spent 1m53s reading
two of them to work out what an END-REPORT looks like.

It also catches garbled evidence outright. Run 007's verdict cited
`grep -icE "VRAM\|GPU"`, which under extended regex matches the literal string
and returns 0 while the contract's form returns 5; the checker reports both in
a second instead of costing a re-derivation.

## Dispatching — The Exact Commands

**You do not need to read `dispatch.py` to use it, and you should not.** On
2026-08-06 a cold start spent fourteen minutes reading the dispatcher's
argument parsing to work out how `--id` locates the handoff file. Everything
it was looking for is below, taken from `bridge_flow_steps` and the argument
definitions themselves.

Write the handoff first, to the path the flow step defines:

| Step | Deliverable path (under `{bridge_dir}`) |
|---|---|
| `supervisor-imple01` | `llama_SG/handoffs/{ID}-handoff.md` |
| `imple01-review01` | `llama_SG/results/{ID}-result.md` |
| `review01-supervisor` | `llama_SG/verdicts/{ID}-verdict.md` |

`{ID}` is the handoff id, **zero-padded to three digits** — `011`, not `11`.

Then dispatch it, from the project root:

```bash
python3 scripts/bridgeV002/dispatch.py --db-flow llama_SG \
    --signal-send --from-role supervisor01_llama --to-role imple01SG --id {ID}
```

`--id` is optional — omitted, the dispatcher allocates the next value from
`bridge_id_counters`. **Always pass it explicitly anyway**, so the file you
just wrote is provably the file that goes out. Omitting it makes the id a
side effect of when you happened to run the command.

The other signals follow the same shape:

```bash
--signal-complete   --from-role {role} --id {ID}
--signal-escalation --from-role {from} --to-role {to} --id {ID}
--signal-answer     --from-role {from} --to-role {to} --id {ID}
```

**A dispatch takes 40-60 seconds, and its effects land in this order:**

1. the handoff file exists — you wrote it, it proves nothing about dispatch
2. `bridge_id_counters` advances
3. the outgoing model stops and the incoming one loads — most of the elapsed time
4. the prompt is injected into the target session
5. `trace.log` records `| {ID} | dispatched |`

Only step 5 means the handoff is delivered. Checking between steps 1 and 5
looks like failure and is not — the file existing is too early a signal, and
a silent `trace.log` during the swap is too early a conclusion. If you need
to know whether a dispatch succeeded, read `trace.log`.

## Known Infrastructure Defects — Do Not Investigate These

These are open, recorded in `{bridge_dir}/llama_SG/RUNS-BACKLOG.md`, and are
Human work. They are not any role's failure and not any run's work. Recognise
them, note them in the ledger, and carry on.

**The model swap can fail between review01SG and supervisor01_llama.**
`model_leases` records nothing, so dispatch has nothing to release. Ollama
evicts its own previous model — which is why the earlier swaps in a cycle
succeed — but Laguna is a separate llama.cpp server, so nothing evicts the
reviewer's model and Laguna may not fit. It then exits early, and dispatch
injects your callback anyway. **If you wake to `ConnectionRefused` or
`503 Loading model`, wait.** It failed this way in run 006 and succeeded by
timing in run 007. Do not conclude the run is broken; do not spend a handoff.
Backlog items 5, 6 and 7.

**A `model-allocator stop` can report success without stopping.** The Ollama
adapter returns `{"stopped": true}` while the model is still resident. Confirm
against `/api/ps` or `nvidia-smi` before believing it. Backlog item 6.

**Nothing checks your bookkeeping.** The evidence gate runs on results and
verdicts, not on RUN-LEDGER, BACKLOG or END-REPORT. In run 007 the supervisor
composed the END-REPORT in its reply, recorded "END-REPORT written" in the
ledger, and never wrote the file — then ended its turn believing the run was
closed. Nothing caught it, and the next cold start would have read run 007 as
still active. See the END-REPORT rule below. Backlog item 17.

## Rules

- **Execute steps 1-7 in order. Do not skip. Do not add extra investigation.**
- **Do not delegate to a subagent.** Everything this procedure needs is a file
  read, a `grep`, an `ls`, a database query or an mcp-light call you can make
  directly. On 2026-08-05 a cold start spawned a `general-purpose` agent to
  "find supervisor run state files" — a question `ls` answers — and it consumed
  55,900 tokens and fourteen minutes before returning. That is the single most
  expensive thing measured in this flow. If a task looks big enough to
  delegate, it is a task the Human should have scoped: park and say so.
- **Do not read the source of the tools you are told to run.** `dispatch.py`,
  `chain_watchdog.py` and `gate-deliverable-evidence.py` are infrastructure
  you invoke, not code you audit — their invocations are documented above and
  in CLAUDE.md §8. If a command's behaviour is genuinely undocumented, say so
  in the ledger and ask the Human; do not derive it from the source. Reading
  the dispatcher has cost two runs a quarter-hour each and changed no outcome.
- **Write the END-REPORT to disk, then prove it.** Before recording a run as
  closed, run `ls -la {bridge_dir}/llama_SG/runs/{run_id}/END-REPORT.md` and
  read the real output. Composing the report in your reply is not writing it.
  The same applies to any ledger entry claiming a file exists.
- **When you validate a verdict, re-run the commands it cites.** Run 007's
  verdict cited `grep -icE "VRAM\|GPU"`, which under extended regex matches
  the literal string `VRAM|GPU` and returns 0. The claim was true; the
  evidence was garbled. A wrong command in the evidence is a transcription
  error, not a fabrication — check the underlying claim before rejecting.
- **A run without an approved GOAL.md must not start** — park with
  `HUMAN_ACTION_REQUIRED`.
- **Loop guard:** never send signal-complete for a verdict delivery you are
  processing — the next handoff gets a NEW id via the flow counter.
- **Run a watchdog alongside every autonomous run — but check for one first:**
  ```bash
  pgrep -af 'chain_watchdog|watchdog-loop' | grep -v pgrep
  ```
  If that prints anything, a watchdog is already running. **Do not start a
  second one.** On 2026-08-05 this rule was followed blindly while a wrapper
  was already live; both nudged the same stalled handoff and produced three
  gate escalations in 23 seconds, burning the rejection budget on a
  deliverable nobody had touched. Only if nothing is running:
  `python3 scripts/bridgeV002/chain_watchdog.py --flow llama_SG --max-minutes {run budget}`
- **Append a ledger entry for every action taken after a cold start** — the
  ledger, not the session, is the run's memory.
- **All communication in English (en-US)** except direct Human interaction.
