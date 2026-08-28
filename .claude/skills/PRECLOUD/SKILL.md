---
name: Pre-Cloud
description: Reconstruct the Pre-super-cl context after a cold start in the preferred_cloud flow. Use when resuming an autonomous supervisor run, after a restart, or when the supervisor session has lost context and needs to rebuild its state from durable run artifacts (GOAL.md, RUN-LEDGER.md, BACKLOG.md).
---

# Pre-Cloud — Supervisor Cold-Start

> **Governance resolution (2026-08-28):** the flow-specific 4xx originals were retired when their content was absorbed into the generic role files (DPMtF commit `0e9b141`, repointed in `d339028`). The authoritative per-role contract is `bridge_roles.governance_file` — verify with mcp-light `get_role(<role_key>)` or `sqlite3 databases/dpmtf.db "SELECT governance_file FROM bridge_roles WHERE role_key='<role>';"` — never a hardcoded filename.

Invoke with `/Pre-Cloud` to reconstruct the **Pre-super-cl** context after a
cold start in the `preferred_cloud` flow. The supervisor is stateless per
wake-up by design (the supervisor contract, SUPERVISOR_AUTONOMOUS.md): this procedure is the same rebuild it performs on
every verdict delivery — run it manually whenever the session starts cold
outside a dispatch.

**The invocation carries no arguments, and needs none.** Everything about the
current run is discoverable and Step 0 discovers it. If you find yourself
being told the run number, the first handoff id, or that a guard is already
running, fix the procedure rather than the prompt.

**Starting a new run takes two things:** a Human-approved GOAL.md in a fresh
`runs/{id}/` directory, and `/Pre-Cloud`. The approved GOAL.md *is* the
authorisation to begin.

## The Chain

```
Pre-super-cl  →  Pre-imple-cl  →  Pre-review-cl  →  Pre-super-cl
Claude Opus 5    MiniMax M3       Claude Sonnet 5
claude-code      opencode         claude-code
```

Governance: `SUPERVISOR_AUTONOMOUS.md`,
`IMPLEMENTOR.md`, `REVIEW.md`.

Optional session switches, both Human decisions made in the database or the
allocator: Pre-super-cl → Fable 5, Pre-review-cl → Fable.

## Step 0: Get the State In One Call

```bash
python3 scripts/bridgeV002/supervisor_state.py --flow preferred_cloud
```

This answers where the bridge directory is, which run is active and which of
its four artefacts exist, the `First handoff id` from GOAL.md, the flow
counter, the handoffs this run owns, what has been written for the current
one, its last `trace.log` signal, whether the WebUI, database and tmux
sessions are up, what is missing, and a one-line assessment.

It applies the **run floor**, which `chain_watchdog` cannot — the watchdog
locks onto the newest handoff id on disk regardless of which run owns it, and
that is how a run once adopted a closed run's handoff and parked on a budget
already spent.

| Assessment | What it means |
|---|---|
| `NO ACTIVE RUN` | Every run has an END-REPORT. A new run needs a Human-approved GOAL.md — never open one yourself. |
| `PARK` | GOAL.md or the floor is missing. Report and wait; do not adopt what is on disk. |
| `RUN OPENED …, CHAIN NOT STARTED` | Author BACKLOG.md, then write and dispatch the first handoff per Standing Approvals. |
| `HANDOFF nnn DISPATCHED (…)` / `RESULT DELIVERED (…)` | A role is working. Wait. Do not dispatch. Each carries how long since the chain last moved — read it. |
| `STALLED — …` | No movement for longer than `--stale-after` (default 3 h). **Not slowness.** See below. |
| `VERDICT READY for nnn (…)` | Validate the testgoals yourself, then act per SUPERVISOR_AUTONOMOUS.md. |

Every line about the current handoff now carries an age, and a
`Last movement` line names the newest evidence behind it — a trace signal, the
handoff file's mtime, the ledger's, or GOAL.md's. Read the age. On 2026-08-09
handoff 035 was dispatched, the implementer's session was recycled the same
evening, and this report said *"the implementer is working"* for three and a
half days: it was right that no result existed and wrong about what that meant,
because nothing measured how long the absence had lasted.

**`STALLED` is a stop condition, not a nudge cue.** Verify the target session
still holds the dispatch before anything else — a recycled session cannot
answer, and re-dispatching is the wrong reflex. Check too whether the handoff is
still runnable: 035's own md5 guard pinned 23 files that had since moved, so
replaying it would have failed against correct work. The bound sits at three
hours deliberately, above the 128 minutes handoff 034 legitimately took; a guard
that fires on a working chain is worse than no guard. Lower it with
`--stale-after MINUTES` when you have reason to, never to make a quiet report.

The report is flow-aware: it names this flow's own tmux sessions, and it does
not probe a local model server, because none of these three roles has one.

## Step 1: Read The Sections You Need

`SUPERVISOR_AUTONOMOUS.md` is the contract. Read by section, not by
file, and let Step 0's assessment choose which:

| Step 0 said | Read from SUPERVISOR_AUTONOMOUS.md |
|---|---|
| `RUN OPENED, CHAIN NOT STARTED` | Wake-Up Protocol · Event Handling · **What Cloud Changes** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `VERDICT READY` | Wake-Up Protocol · Event Handling · **Validating an APPROVED Verdict** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `STALLED` | Stop Conditions first, then Event Handling — establish what is blocked before you act |
| `PARK` or `NO ACTIVE RUN` | Stop Conditions, and nothing else — you are reporting, not acting |

Read `500_SUPERVISOR.md` once per run, not per wake-up.

**Read "What Cloud Changes" before your first dispatch of a run.** It is the
section that stops habits from the local flow being applied here.

## Step 2: Verify The Chain Can Run

```bash
cd "$(git rev-parse --show-toplevel)"
curl -s http://localhost:9130/api/health
for s in Pre-super-cl Pre-imple-cl Pre-review-cl; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

There is no model server to check. What can fail instead is credentials and
quota, and that surfaces as an API error on the first call — not as something
you can probe in advance. Do not try.

## Framework Questions Go To mcp-light

`mcp-light` serves this flow's wiring at `http://127.0.0.1:9135/mcp`. You
run under Claude Code, which reads `~/.mcp.json`, so this session already
has it — but that path is the client's, not the flow's. Pre-imple-cl runs
under OpenCode and gets mcp-light from the `mcp` block in its own
`opencode.json`; a Pi role would get it from Pi's settings (101). Do not
assume a role has it because you do. Use it for anything about how the flow
is wired:

| Question | Tool |
|---|---|
| Where does a deliverable go, and under what name? | `get_flow_steps("preferred_cloud")` |
| What does the supervisor contract or 500 say? | `get_governance_file("SUPERVISOR_AUTONOMOUS.md")` |
| How is a role configured? | `get_role("Pre-super-cl")` |
| What did an earlier verdict conclude? | `search_verdicts(query)` |

If a question is about the framework rather than the run's actual work, it is
a lookup — not something to reason out. A cold start in another flow once
spent fourteen minutes deriving from `dispatch.py` what `get_flow_steps`
returns in one call.

## Dispatching — The Exact Commands

Write the handoff first, to the path the flow step defines:

| Step | Deliverable path (under `{bridge_dir}`) |
|---|---|
| `supervisor-imple01` | `preferred_cloud/handoffs/{ID}-handoff.md` |
| `imple01-review01` | `preferred_cloud/results/{ID}-result.md` |
| `review01-supervisor` | `preferred_cloud/verdicts/{ID}-verdict.md` |

`{ID}` is zero-padded to three digits — `014`, not `14`.

```bash
python3 scripts/bridgeV002/dispatch.py --db-flow preferred_cloud \
    --signal-send --from-role Pre-super-cl --to-role Pre-imple-cl --id {ID}
```

`--id` is optional — omitted, the dispatcher takes the next value from
`bridge_id_counters`. **Pass it explicitly anyway**, so the file you just
wrote is provably the file that goes out.

**The XML envelope is not your job.** `auto_prepend_xml_sections` supplies
`<handoff_id>`, `<source_role>`, `<deliverable_input>` and
`<deliverable_output>` from known values before validation. Write content.

**A dispatch here is fast.** In the local flow most of the elapsed time is a
model swap; there is none here, so the effects land almost together:

1. the handoff file exists — you wrote it, it proves nothing
2. `bridge_id_counters` advances
3. the prompt is injected into the target session
4. `trace.log` records `| {ID} | dispatched |`

Only step 4 means delivered. If you need to know whether a dispatch worked,
read `trace.log`.

## Two GOAL.md Files — Always Say Which

| Path | What it is |
|---|---|
| `{bridge_dir}/preferred_cloud/runs/{id}/GOAL.md` | this run's Mission Contract |
| `{target_project}/GOAL.md` | the product specification |

`{target_project}` comes from `bridge_flows.target_project_path` — ask
mcp-light's `get_flow` rather than assuming it.

Write the path, never the bare name. Roles have confused the two twice — once
citing a path that exists nowhere, once reporting a contract's tables missing
after grepping the specification for them.

## Validating A Verdict

```bash
python3 scripts/bridgeV002/check_testgoals.py \
    {bridge_dir}/preferred_cloud/runs/{run_id}/GOAL.md
```

**This settles the facts, not the verdict.** Whether the claims are honest,
whether the evidence was gathered, and whether a green testgoal was reached
the right way remain yours to judge. That judgement is the only thing a
supervisor is genuinely needed for.

A count cannot read. Where a testgoal asks whether prose says something,
read it and quote the sentence.

## Ledger Entries And END-REPORTs

```bash
python3 scripts/bridgeV002/run_report.py ledger --flow preferred_cloud --event {event}
python3 scripts/bridgeV002/run_report.py end-report --flow preferred_cloud
```

Prints a skeleton with the facts filled in and every judgement left as `TODO`.
Nothing is written to disk: review it, replace every `TODO`, save it yourself.
Do not go looking at closed runs for the format.

## What Does Not Apply Here

Habits from `llama_SG` that are wrong in this flow:

- **No model swapping.** All three aliases are `cloud_noop`; start and stop are
  credential checks. There are no lifecycle scripts on the steps, and the
  swap-failure defects (backlog items 5, 6, 7) cannot occur.
- **`ConnectionRefused` is not routine.** In the local flow it is the ordinary
  state after a dispatch, because the supervisor's model was stopped to make
  room. Here it means the API is genuinely unreachable. Park and report it.
- **Do not run `laguna_swap_guard.py`.** It watches for a local model that
  does not exist in this flow.
- **Cost replaces contention.** Every token is billed. A rate limit or quota
  error is a stop condition, not a transient — retry once, then park with the
  error text.

## Rules

- **A run without an approved GOAL.md must not start** — park with
  `HUMAN_ACTION_REQUIRED`.
- **Write the END-REPORT to disk, then prove it** with `ls -la` on the exact
  path. Composing it in your reply is not writing it, and a run whose report
  does not exist is still open.
- **Check that your signals worked.** If a signal reports
  `signal_complete_failed`, the deliverable is not where dispatch looked.
  Fix it and signal again — a claimed signal that failed leaves the chain
  blocked with nobody aware.
- **Do not delegate to a subagent.** Everything here is a file read, a `grep`,
  an `ls`, a database query or an mcp-light call you can make directly.
- **Do not read the source of the tools you are told to run.** Their
  invocations are documented above and in CLAUDE.md §8.
- **Loop guard:** never send `signal_complete` for a verdict delivery you are
  processing — the next handoff gets a new id from the flow counter.
- **Append a ledger entry for every action** — the ledger, not the session, is
  the run's memory.
- **All communication in English (en-US)** except direct Human interaction.

Flow startup contract: docs/governance-templates-v2/103_FLOW_STARTUP.md
