---
name: preferred_cloud_harness
description: Reconstruct the super-deep-deep4 supervisor context after a cold start in the preferred_cloud_harness flow. Use when resuming an autonomous supervisor run, after a restart, or when the DeepSeek Harness supervisor session has lost context and needs to rebuild its state from durable run artifacts (GOAL.md, RUN-LEDGER.md, BACKLOG.md).
---

# Preferred Cloud Harness — Supervisor Cold-Start

Invoke with `/preferred_cloud_harness` to reconstruct the **super-deep-deep4**
context after a cold start in the `preferred_cloud_harness` flow. The
supervisor is stateless per wake-up by design (511): this procedure is the
same rebuild it performs on every verdict delivery — run it manually whenever
the session starts cold outside a dispatch.

**The invocation carries no arguments, and needs none.** Everything about the
current run is discoverable and Step 0 discovers it.

**Starting a new run takes two things:** a Human-approved GOAL.md in a fresh
`runs/{id}/` directory, and this skill. The approved GOAL.md *is* the
authorisation to begin.

## The Chain

```
super-deep-deep4      →  imple-codex-minimaxM3  →  review-claude-sonnet5  →  super-deep-deep4
DeepSeek Harness (dsh)    Codex CLI               Claude Code
DeepSeek V4 Pro           MiniMax M3              Claude Sonnet 5
```

Governance: `511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md`,
`512_PREFERRED_CLOUD_HARNESS_IMPLE01.md`,
`513_PREFERRED_CLOUD_HARNESS_REVIEW01.md`.

Your harness is the **DeepSeek Harness** (`dsh`), not Claude Code. You run
shell commands the same way any coding agent does — `python3
scripts/bridgeV002/dispatch.py …`, `supervisor_state.py`, `check_testgoals.py`
— and you read and write files in the repository. The model behind you is
DeepSeek V4 Pro; the credential is `DEEPSEEK_API_KEY`.

## Step 0: Get the State In One Call

```bash
python3 scripts/bridgeV002/supervisor_state.py --flow preferred_cloud_harness
```

This answers where the bridge directory is, which run is active and which of
its four artefacts exist, the `First handoff id` from GOAL.md, the flow
counter, the handoffs this run owns, what has been written for the current
one, its last `trace.log` signal, whether the WebUI, database and tmux
sessions are up, what is missing, and a one-line assessment.

| Assessment | What it means |
|---|---|
| `NO ACTIVE RUN` | Every run has an END-REPORT. A new run needs a Human-approved GOAL.md — never open one yourself. |
| `PARK` | GOAL.md or the floor is missing. Report and wait; do not adopt what is on disk. |
| `RUN OPENED …, CHAIN NOT STARTED` | Author BACKLOG.md, then write and dispatch the first handoff per Standing Approvals. |
| `HANDOFF nnn DISPATCHED (…)` / `RESULT DELIVERED (…)` | A role is working. Wait. Do not dispatch. |
| `STALLED — …` | No movement for longer than `--stale-after` (default 3 h). **Not slowness.** See below. |
| `VERDICT READY for nnn (…)` | Validate the testgoals yourself, then act per 511. |

**`STALLED` is a stop condition, not a nudge cue.** Verify the target session
still holds the dispatch before anything else — a recycled session cannot
answer, and re-dispatching is the wrong reflex.

## Step 1: Read The Sections You Need

`511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md` is the contract. Read by section,
not by file, and let Step 0's assessment choose which:

| Step 0 said | Read from 511 |
|---|---|
| `RUN OPENED, CHAIN NOT STARTED` | Wake-Up Protocol · Event Handling · **What Harness Changes** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `VERDICT READY` | Wake-Up Protocol · Event Handling · **Validating an APPROVED Verdict** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `STALLED` | Stop Conditions first, then Event Handling — establish what is blocked before you act |
| `PARK` or `NO ACTIVE RUN` | Stop Conditions, and nothing else — you are reporting, not acting |

Read `500_SUPERVISOR.md` once per run, not per wake-up.

**Read "What Harness Changes" before your first dispatch of a run.** It is the
section that stops habits from the local flow being applied here.

## Step 2: Verify The Chain Can Run

```bash
cd "$(git rev-parse --show-toplevel)"
curl -s http://localhost:9130/api/health
for s in super-deep-deep4 imple-codex-minimaxM3 review-claude-sonnet5; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

There is no model server to check. What can fail instead is credentials and
quota, and that surfaces as an API error on the first call — not as something
you can probe in advance. Do not try.

## Framework Questions

`mcp-light` serves this project's flow wiring at `http://127.0.0.1:9135/mcp`.
If your DeepSeek Harness session has access to it, use it for wiring lookups
(`get_flow_steps("preferred_cloud_harness")`, `get_role("super-deep-deep4")`,
`get_governance_file(...)`, `search_verdicts(...)`). If it does not, do not
stall on it: the dispatch commands and file paths below are the source of
truth, and `supervisor_state.py` plus a direct database read answer the same
questions.

## Dispatching — The Exact Commands

Write the handoff first, to the path the flow step defines:

| Step | Deliverable path (under `{bridge_dir}`) |
|---|---|
| `supervisor-imple01` | `preferred_cloud_harness/handoffs/{ID}-handoff.md` |
| `imple01-review01` | `preferred_cloud_harness/results/{ID}-result.md` |
| `review01-supervisor` | `preferred_cloud_harness/verdicts/{ID}-verdict.md` |

`{ID}` is zero-padded to three digits — `014`, not `14`.

```bash
python3 scripts/bridgeV002/dispatch.py --db-flow preferred_cloud_harness \
    --signal-send --from-role super-deep-deep4 --to-role imple-codex-minimaxM3 --id {ID}
```

`--id` is optional — omitted, the dispatcher takes the next value from
`bridge_id_counters`. **Pass it explicitly anyway**, so the file you just
wrote is provably the file that goes out.

**The XML envelope is not your job.** `auto_prepend_xml_sections` supplies
`<handoff_id>`, `<source_role>`, `<deliverable_input>` and
`<deliverable_output>` from known values before validation. Write content.

**A dispatch here is fast.** In the local flow most of the elapsed time is a
model swap; there is none here. Only the `dispatched` line in `trace.log`
means delivered — if you need to know whether a dispatch worked, read
`trace.log`.

## Two GOAL.md Files — Always Say Which

| Path | What it is |
|---|---|
| `{bridge_dir}/preferred_cloud_harness/runs/{id}/GOAL.md` | this run's Mission Contract |
| `{target_project}/GOAL.md` | the product specification |

`{target_project}` comes from `bridge_flows.target_project_path` (this flow
sets none, so it is Father). Write the path, never the bare name.

## Validating A Verdict

```bash
python3 scripts/bridgeV002/check_testgoals.py \
    {bridge_dir}/preferred_cloud_harness/runs/{run_id}/GOAL.md
```

**This settles the facts, not the verdict.** A count cannot read. Where a
testgoal asks whether prose says something, read it and quote the sentence.

## Ledger Entries And END-REPORTs

```bash
python3 scripts/bridgeV002/run_report.py ledger --flow preferred_cloud_harness --event {event}
python3 scripts/bridgeV002/run_report.py end-report --flow preferred_cloud_harness
```

Prints a skeleton with the facts filled in and every judgement left as `TODO`.
Nothing is written to disk: review it, replace every `TODO`, save it yourself.

## What Does Not Apply Here

Habits from `llama_SG` that are wrong in this flow:

- **No model swapping.** None of the three roles owns a local server; start
  and stop are credential checks at most. The swap-failure defects of the
  local flow cannot occur.
- **`ConnectionRefused` is not routine.** Here it means an API or harness is
  genuinely unreachable. Park and report it.
- **Do not run `laguna_swap_guard.py`.** It watches for a local model that
  does not exist in this flow.
- **Cost replaces contention.** Every token is billed. A rate limit or quota
  error is a stop condition, not a transient — retry once, then park with the
  error text.

## The Supervisor Invocation — Headless One-Shot

The installed DeepSeek Harness has **no `tui` profile** — do not use
`--profile tui`. The supervisor is therefore **not a resident process**: its
tmux session hosts a persistent shell (the role environment), and **every
wake-up invokes the harness fresh, headless, one turn at a time**:

```bash
npx @deepseek-ai/dsh --profile headless --patch <v4-pro-patch> "<task>"
```

This is exactly the `stateless-per-wakeup rebuild` the governance describes:
each invocation starts cold, reads the durable state (Step 0), acts once,
persists to the ledger, and exits — leaving the tmux shell available for the
next wake-up. The completed `dsh` process is one-shot and needs no shutdown;
the tmux session remains owned by the flow and is torn down by `Stop tmux`.

`<v4-pro-patch>` is the patch overlay that pins provider `deepseek-official`
and model `deepseek-v4-pro`; its path is configuration (`DSH_V4_PRO_PATCH`),
not something this skill spells out.

## Rules

- **A run without an approved GOAL.md must not start** — park with
  `HUMAN_ACTION_REQUIRED`.
- **Write the END-REPORT to disk, then prove it** with `ls -la` on the exact
  path. Composing it in your reply is not writing it.
- **Check that your signals worked.** If a signal reports
  `signal_complete_failed`, the deliverable is not where dispatch looked.
  Fix it and signal again.
- **Do not delegate to a subagent.** Everything here is a file read, a `grep`,
  an `ls`, a database query or a command you can run directly.
- **Loop guard:** never send `signal_complete` for a verdict delivery you are
  processing — the next handoff gets a new id from the flow counter.
- **Append a ledger entry for every action** — the ledger, not the session, is
  the run's memory.
- **All communication in English (en-US)** except direct Human interaction.
