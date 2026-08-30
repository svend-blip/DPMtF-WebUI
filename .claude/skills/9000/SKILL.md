---
name: "9000"
description: Cold-start reconstruction for the shared 9000 TEST workspace (allocator-composition proof) — PLOOP planning state or an ELOOP escalation, discovered, never assumed
---

# 9000 — Cold-Start (PLOOP / ELOOP shared TEST workspace)

Invoke with `/9000` to reconstruct context after a cold start in either flow
that shares the `9000` artifact root. You are stateless by design; everything
below is discoverable, and discovering it beats being told it.

**The 9000 workspace exists to prove wiring, not to build software.** These
are TEST flows (Human decision 2026-08-30): every model is resolved by
model-allocator, every interface is launched via harness-allocator. The
planning supervisor runs claude-code (opus5); the three chain roles run the
**simple-harness** interface with cloud_minimax (MiniMax-M3). The target is
the throwaway repository `/home/svend/9000-sandbox` — nothing in it matters
beyond being a real git worktree the chain can read, edit, and be
gate-measured against. Keep runs SMALL: the deliverable is evidence that the
composition works, not features.

**Two flows, one workspace, split authority — verify, then act within yours:**

| | `9000-01-PLOOP` | `9000-02-ELOOP` |
|---|---|---|
| Owns | Run IDs, GOAL-DRAFT, (via Human-approved promotion) GOAL | handoff ids, handoffs, results, verdicts |
| Never | writes into `9000/handoffs/` | allocates a Run number |

## Step 0 — discover the state (both roles)

```
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 9000-01-PLOOP
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 9000-02-ELOOP
ls /home/svend/flows/9000/goals/          # drafts awaiting approval
ls /home/svend/flows/9000/runs/           # promoted runs; END-REPORT.md = closed
git -C /home/svend/9000-sandbox status --short && git -C /home/svend/9000-sandbox log --oneline -3
```

trace.log is flow-wide and the id counter is not: filter on flow AND id
(100_BRIDGE Security Rules 7). File mtimes are local, trace is UTC.

## If you are 9000-planning-supervisor (PLOOP)

Governance: `500_SUPERVISOR.md`. Your deliverable channel is
`9000/goals/{ID}-GOAL-DRAFT.md` via ordinary dispatch — the deliverable id
BECOMES the Run id. You may create and revise drafts. **You may not
promote:** `GOAL.md` means the Human approved the Run; promotion is the
Human-side `bridge_broker.py promote-goal`.

Plan runs that exercise the WIRING: a role reads a file, edits `hello.py`,
a verdict lands, the trace shows the full chain. A draft's testgoals must
parse (`check_testgoals.py`) and be measured RED before approval — rehearse
under `dash -c`, never bash. Testgoals measure `/home/svend/9000-sandbox`.

## If you are 9000-escalation-supervisor (ELOOP)

Governance: `SUPERVISOR_ESCALATION.md` — read it in full; it IS your
procedure. You are one-shot: ONE bounded decision — ANSWER within the GOAL's
fence, RETRY WITH CORRECTION naming the one change (new handoff id), or PARK
FOR HUMAN — recorded durably, then stand down. Parking on an accurate
diagnosis is success.

## What a cold start never does

Never re-signal a step whose last event is an escalation; never touch
`/home/svend/9000-sandbox` outside a governed handoff; never commit or push
in ANY repo (Human-only); never start or stop shared model servers — all
9000 chain roles are cloud (MiniMax), there is nothing local to swap. A
FAILED simple-harness status event usually means the endpoint env did not
reach the session — check `SIMPLE_HARNESS_BASE_URL`/`SIMPLE_HARNESS_MODEL`
in the pane's environment before blaming the model.
