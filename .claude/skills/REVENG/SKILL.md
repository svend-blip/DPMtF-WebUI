---
name: Rev-Eng
description: Reconstruct the Rev_Supervisor context after a cold start in the reveng flow. Use when resuming an autonomous supervisor run, after a restart, or when the supervisor session has lost context and needs to rebuild its state from durable run artifacts (GOAL.md, RUN-LEDGER.md, BACKLOG.md).
---

# Rev-Eng — Supervisor Cold-Start

Invoke with `/Rev-Eng` to reconstruct the **Rev_Supervisor** context after a
cold start in the `reveng` flow. The supervisor is stateless per
wake-up by design (491): this procedure is the same rebuild it performs on
every verdict delivery — run it manually whenever the session starts cold
outside a dispatch.

**This file is read by both clients.** Rev_Supervisor runs under OpenCode,
which discovers it at `.claude/skills/REVENG/SKILL.md` in the Father
repository and offers it both as a skill and as the `/Rev-Eng` command; the
Human's own Claude Code session reads the same file from the same path. There
is no second copy to keep in step, and none should be made — verified with
`opencode debug skill` on 2026-08-12.

**The invocation carries no arguments, and needs none.** Everything about the
current run is discoverable and Step 0 discovers it. If you find yourself
being told the run number, the first handoff id, or that a guard is already
running, fix the procedure rather than the prompt.

**Starting a new run takes two things:** a Human-approved GOAL.md in a fresh
`runs/{id}/` directory, and `/Rev-Eng`. The approved GOAL.md *is* the
authorisation to begin.

## The Chain

```
Rev_Supervisor        →  Rev_Imple    →  Rev_Review       →  Rev_Supervisor
GLM-4.5-Air-Derestr.     MiniMax M3      Claude Sonnet 5
opencode (LOCAL)         opencode        claude-code
llama.cpp :8080          hosted          hosted
```

Governance: `491_REVENG_SUPERVISOR.md`,
`492_REVENG_IMPLE.md`, `493_REVENG_REVIEW.md`.

You are the only local model in this chain (`glm-air-derestricted-local`,
IQ4_XS, 65536-token window). The other two are hosted APIs. Optional session
switches are Human decisions made in the database or the allocator.

## Step 0: Get the State In One Call

```bash
python3 scripts/bridgeV002/supervisor_state.py --flow reveng
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
| `RUN OPENED, CHAIN NOT STARTED` | Author BACKLOG.md, then write and dispatch the first handoff per Standing Approvals. |
| `HANDOFF nnn DISPATCHED` / `RESULT DELIVERED` | A role is working. Wait. Do not dispatch. |
| `VERDICT READY for nnn` | Validate the testgoals yourself, then act per 491. |

The report is flow-aware: it names this flow's own tmux sessions, and since
2026-08-12 it probes `:8080` and prints `local model  reachable`, because one
role in this flow — yours — is now locally served. That line is for the Human.
See Step 2 for why it is not a precondition for you.

## Step 1: Read The Sections You Need

`491_REVENG_SUPERVISOR.md` is the contract. Read by section, not by
file, and let Step 0's assessment choose which:

| Step 0 said | Read from 491 |
|---|---|
| `RUN OPENED, CHAIN NOT STARTED` | Wake-Up Protocol · Event Handling · **What A Mixed Flow Changes** (incl. *Signalling Stops Your Own Model*) · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `VERDICT READY` | Wake-Up Protocol · Event Handling · **Validating an APPROVED Verdict** · **Signalling Stops Your Own Model** · Decision Matrix · Ledger Entry Format · Stop Conditions |
| `PARK` or `NO ACTIVE RUN` | Stop Conditions, and nothing else — you are reporting, not acting |

Read `500_SUPERVISOR.md` once per run, not per wake-up.

**Read "What A Mixed Flow Changes" before your first dispatch of a run.** It
is the section that keeps habits from the all-local and all-cloud flows from
being applied wholesale here, where one role is local and two are hosted. Its
subsection *Signalling Stops Your Own Model* is the one rule you can get
wrong by acting in a reasonable-looking order.

## Step 2: Verify The Chain Can Run

```bash
cd "$(git rev-parse --show-toplevel)"
curl -s http://localhost:9130/api/health
for s in Rev_Supervisor Rev_Imple Rev_Review; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

Step 0 already probes your own model server on `:8080` and prints
`local model  reachable`. Do not probe it a second time, and do not treat it
as a precondition to verify: you are running, so it started. It is in the
report for the Human, not for you.

For Rev_Imple and Rev_Review there is nothing to probe at all. What fails
there is credentials and quota, and that surfaces as an API error on the
first call — not as something you can check in advance. Do not try.

## Framework Questions Go To mcp-light

`mcp-light` serves this flow's wiring at `http://127.0.0.1:9135/mcp`. You run
under OpenCode, which does not read `~/.mcp.json` — yours is declared in the
`mcp` block of `~/.config/opencode-roles/Rev_Supervisor/opencode.json`, and
the allocator's config refresh preserves it. If the tools below are not
offered to you, that block is what to check; do not fall back to deriving the
answers by hand. Use it for anything about how the flow is wired:

| Question | Tool |
|---|---|
| Where does a deliverable go, and under what name? | `get_flow_steps("reveng")` |
| What does 491 or 500 say? | `get_governance_file("491_REVENG_SUPERVISOR.md")` |
| How is a role configured? | `get_role("Rev_Supervisor")` |
| What did an earlier verdict conclude? | `search_verdicts(query)` |

If a question is about the framework rather than the run's actual work, it is
a lookup — not something to reason out. A cold start in another flow once
spent fourteen minutes deriving from `dispatch.py` what `get_flow_steps`
returns in one call.

## Dispatching — The Exact Commands

Write the handoff first, to the path the flow step defines:

| Step | Deliverable path (under `{bridge_dir}`) |
|---|---|
| `supervisor-imple01` | `reveng/handoffs/{ID}-handoff.md` |
| `imple01-review01` | `reveng/results/{ID}-result.md` |
| `review01-supervisor` | `reveng/verdicts/{ID}-verdict.md` |

`{ID}` is zero-padded to three digits — `014`, not `14`.

```bash
python3 scripts/bridgeV002/dispatch.py --db-flow reveng \
    --signal-send --from-role Rev_Supervisor --to-role Rev_Imple --id {ID}
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
| `{bridge_dir}/reveng/runs/{id}/GOAL.md` | this run's Mission Contract |
| `{target_project}/GOAL.md` | the product specification |

`{target_project}` comes from `bridge_flows.target_project_path` — ask
mcp-light's `get_flow` rather than assuming it.

Write the path, never the bare name. Roles have confused the two twice — once
citing a path that exists nowhere, once reporting a contract's tables missing
after grepping the specification for them.

## Validating A Verdict

```bash
python3 scripts/bridgeV002/check_testgoals.py \
    {bridge_dir}/reveng/runs/{run_id}/GOAL.md
```

**This settles the facts, not the verdict.** Whether the claims are honest,
whether the evidence was gathered, and whether a green testgoal was reached
the right way remain yours to judge. That judgement is the only thing a
supervisor is genuinely needed for.

A count cannot read. Where a testgoal asks whether prose says something,
read it and quote the sentence.

## Ledger Entries And END-REPORTs

```bash
python3 scripts/bridgeV002/run_report.py ledger --flow reveng --event {event}
python3 scripts/bridgeV002/run_report.py end-report --flow reveng
```

Prints a skeleton with the facts filled in and every judgement left as `TODO`.
Nothing is written to disk: review it, replace every `TODO`, save it yourself.
Do not go looking at closed runs for the format.

## What Applies Here, And What Does Not

Until 2026-08-12 this section said the flow was entirely hosted. One role —
yours — is now local, so the list has both kinds of entry. Read which is
which; half of it is the `llama_SG` habit being right again.

**Now true of you, having been false before:**

- **Your model is swapped.** `glm-air-derestricted-local` is stopped when you
  hand off and started when a verdict returns (~35s). The VRAM settle check in
  the dispatch log now has something to wait for.
- **`ConnectionRefused` on `:8080` right after your own `signal-send` is
  routine** — the dispatcher stopped your server as part of that step. Do all
  your writing, including the ledger entry, *before* you signal. Do not park
  over it and do not retry.

**Still true — do not import these from `llama_SG`:**

- **Rev_Imple and Rev_Review are hosted.** Nothing about them is VRAM, a
  lease, or a swap. A failed call there is network, credentials or an outage.
- **Backlog items 5, 6 and 7 do not apply.** They are defects of a chain with
  three local models contending for one card. You are one local model.
- **Do not run `laguna_swap_guard.py`.** It watches a model this flow does not
  use — though note `laguna-local` shares your port, so a `llama_SG` run that
  left its server resident is one of the few things that can stop you starting.
- **Cost still governs the other two.** Your own tokens are free; every token
  Rev_Imple and Rev_Review spend is billed. A rate limit or quota error from
  them is a stop condition, not a transient — retry once, then park with the
  error text.

**New, and about you rather than the chain:** your window is 65536 tokens and
prompt processing runs near 121 tok/s. Reading a whole governance file costs
minutes of wall-clock before you emit a token, which is why Step 1 sends you
to sections. That instruction is now load-bearing, not tidiness.

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
- **Finish writing before you signal.** `signal-send` stops your own model as
  part of the step. Handoff written, ledger entry appended, files saved —
  then signal, then stop. Afterwards you have no model to compose with, and
  the entry that explains what you did is the thing that goes missing.
- **Do not delegate to a subagent or an OpenCode agent.** Everything here is a
  file read, a `grep`, an `ls`, a database query or an mcp-light call you can
  make directly.
- **Do not read the source of the tools you are told to run.** Their
  invocations are documented above, and in CLAUDE.md §8 if you need more —
  that file is not loaded into your context, so read the section, not the
  whole file.
- **Loop guard:** never send `signal_complete` for a verdict delivery you are
  processing — the next handoff gets a new id from the flow counter.
- **Append a ledger entry for every action** — the ledger, not the session, is
  the run's memory.
- **All communication in English (en-US)** except direct Human interaction.
