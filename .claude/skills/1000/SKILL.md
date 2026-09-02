---
name: "1000"
description: Cold-start reconstruction for the shared 1000 workspace — PLOOP planning state or an ELOOP escalation, discovered, never assumed
---

# 1000 — Cold-Start (PLOOP / ELOOP shared workspace)

Invoke with `/1000` to reconstruct context after a cold start in either flow
that shares the `1000` artifact root. You are stateless by design; everything
below is discoverable, and discovering it beats being told it.

**Two flows, one workspace, split authority — verify, then act within yours:**

| | `1000-01-PLOOP` | `1000-02-ELOOP` |
|---|---|---|
| Owns | Run IDs, GOAL-DRAFT, (via Human-approved promotion) GOAL | handoff ids, handoffs, results, verdicts |
| Never | writes into `1000/handoffs/` | allocates a Run number |

## Step 0 — discover the state (both roles)

```
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 1000-01-PLOOP
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 1000-02-ELOOP
ls /home/svend/flows/1000/goals/          # drafts awaiting approval
ls /home/svend/flows/1000/runs/           # promoted runs; END-REPORT.md = closed
tail -30 /home/svend/flows/1000/RUNS-BACKLOG.md
cat /home/svend/flows/1000/SCOPE.md      # the Human-owned standing scope
```

trace.log is flow-wide and the id counter is not: filter on flow AND id
(100_BRIDGE Security Rules 7). File mtimes are local, trace is UTC.

## If you are 1000-planning-supervisor (PLOOP)

Governance: `SUPERVISOR_PLANNING.md` — read it in full; it IS your procedure,
phase by phase (scope first, clarify, draft, Human promotion, drive ELOOP
under a recorded mandate, close and loop). **Your standing input is
`/home/svend/flows/1000/SCOPE.md` — Human-owned, read-only to you.** Every
draft you author must fall inside its "In scope" and stay clear of its
"Out of scope"; wanting something out-of-scope is a question for the Human,
never a drafting decision. You may propose scope changes as prose in a
planning deliverable, never by editing the file. Your deliverable channel is
`1000/goals/{ID}-GOAL-DRAFT.md` via ordinary dispatch — the deliverable id
BECOMES the Run id. You may create and revise drafts. **You may not promote:**
`GOAL.md` means the Human approved the Run, promotion is the Human-side
`bridge_broker.py promote-goal` (it parse-gates the testgoals block and
records who approved), and the materialize queue has no "goal" type — the
transition is unreachable from your side by construction, not by trust.

A draft's testgoals must parse (`check_testgoals.py` one line per field,
`expect:` forms `equals/at least/at most/contains`) and be measured RED
before approval — rehearse under `dash -c`, never bash.

## If you are 1000-escalation-supervisor (ELOOP)

Governance: `SUPERVISOR_ESCALATION.md` — read it in full; it IS your
procedure. You are one-shot: the escalation question arrives in your
invocation or sits newest in `1000/escalations/`. ONE bounded decision —
ANSWER within the GOAL's fence, RETRY WITH CORRECTION naming the one change
(new handoff id; consumed ids are refused by design), or PARK FOR HUMAN —
recorded durably (broker run-ledger), then stand down. Parking on an
accurate diagnosis is success. Measure before concluding: a sandboxed view
of host processes proves nothing, and never edit anything a check reads.

## What a cold start never does

Never re-signal a step whose last event is an escalation; never touch the
target repository's working tree outside a governed handoff; never commit or
push (Human-only); never start or stop shared model servers — the GPU swap
boundaries at auto_dispatch=0 steps belong to the orchestrating session.
