---
name: "9000"
description: Cold-start for the shared 9000 workspace (FlowRunner build, allocator composition) — the planning supervisor's lifecycle position or an ELOOP escalation, discovered in order, never assumed
---

# 9000 — Cold-Start (PLOOP / ELOOP shared workspace)

Invoke with `/9000` at the start of any session in either flow that shares
the `9000` artifact root. You are stateless by design; everything below is
discoverable. This skill holds the flow's FACTS and the reading ORDER. The
rules live in your governance file — read it in full before acting.

## Flow facts

- Flows: `9000-01-PLOOP` (planning: human-planning → planning-human) and
  `9000-02-ELOOP` (execution: decomposer → implementer → reviewer), artifact
  root `/home/svend/flows/9000`.
- Every model is resolved by model-allocator, every interface is launched by
  harness-allocator. The planning supervisor runs claude-code; the three chain
  roles run the **simple-harness** interface with cloud_minimax (MiniMax-M3).
- **The target repository is `/home/svend/FlowRunner`** (Human decision
  2026-09-01): a real greenfield product built from `SCOPE.md`. Testgoals
  measure that tree.
- Chain-role tool boundary: `read_file`, `write_file`, `grep`,
  `list_directory`, `search_files` are workspace-relative and reject an
  ABSOLUTE path at the permission gate. The `shell` tool is not path-checked.
  Every flow artifact and governance file lies outside the workspace: shell.

## Step 0 — read in this order (both roles)

If the `mcp-light` tools are available, two calls replace steps 2-3:
`get_flow_scope("9000-01-PLOOP", mode="full")` and
`get_flow_state("9000-02-ELOOP")` — the latter returns the mandate fields,
drafts with promotability, runs classified closed / executing / waiting,
the executing Run's floor, owned ids, deliverables and ledger tail, the
queue and trace tails, and a `phase`. Read the scope in full regardless.
The shell lines below are the fallback and the paste-runnable record.

1. **Scope first, in full.** It is Human-owned and read-only to you.

```
cat /home/svend/flows/9000/SCOPE.md
```

2. **Mandate.** Empty `supervisor_mandate` = planning only; set = resident
   driving under SUPERVISOR_PLANNING.md Phases 5-6.

```
sqlite3 -readonly /home/svend/DPMtF-WebUI/databases/dpmtf.db "SELECT flow_key, supervisor_role, supervisor_mandate, commit_cadence, cold_start_skill FROM bridge_flows WHERE flow_key LIKE '9000-%'"
```

3. **State.** Both flows, drafts, runs, the backlog tail, the executing Run's
   ledger tail, the target tree, the id counters.

```
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 9000-01-PLOOP
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 9000-02-ELOOP
ls /home/svend/flows/9000/goals/          # drafts awaiting promotion
ls /home/svend/flows/9000/runs/           # promoted runs; END-REPORT.md = closed
tail -40 /home/svend/flows/9000/planning/PLOOP-BACKLOG.md
git -C /home/svend/FlowRunner status --short && git -C /home/svend/FlowRunner log --oneline -3
sqlite3 -readonly /home/svend/DPMtF-WebUI/databases/dpmtf.db "SELECT * FROM bridge_id_counters WHERE flow_key LIKE '9000%'"
```

   Then `tail -60` of the executing Run's `RUN-LEDGER.md`. The executing Run
   is the one with a ledger "opened" entry and no END-REPORT — NOT the newest
   directory. Many Runs are promoted at once; one executes.

4. **Phase.** Decide it from the table in SUPERVISOR_PLANNING.md §Phase 0 and
   state it in one sentence before doing anything.

trace.log is flow-wide and the id counters are not: filter on flow AND id
(100_BRIDGE Security Rules 7). File mtimes are local, trace is UTC.

## If you are 9000-planning-supervisor

Governance: `SUPERVISOR_PLANNING.md` — read it in full; it IS your procedure,
phase by phase, as checklists. This skill adds nothing to it. Facts you need
that it cannot know: drafts are `goals/{ID}-GOAL-DRAFT.md` with the bare Run
number; run directories are padded; chain deliverables are unpadded;
promotion is the Human-side `bridge_broker.py promote-goal`; testgoals are
rehearsed under `dash -c` and measure `/home/svend/FlowRunner`.

## If you are 9000-escalation-supervisor (ELOOP)

Governance: `SUPERVISOR_ESCALATION.md` — read it in full; it IS your
procedure. You are one-shot: ONE bounded decision — ANSWER within the GOAL's
fence, RETRY WITH CORRECTION naming the one change (new handoff id), or PARK
FOR HUMAN — recorded durably, then stand down. When the planning supervisor
is resident under a mandate, it is the wake-up target and you are not invoked.

## Flow-specific hazards (facts, measured)

- A FAILED simple-harness status usually means the endpoint env did not reach
  the session — check `SIMPLE_HARNESS_BASE_URL` / `SIMPLE_HARNESS_MODEL` in
  the pane before blaming the model.
- The chain roles' shell tool has a default deadline (10 min) since 2026-09-02;
  a helper started with `&` from the shell tool still holds the pipe until the
  deadline — helpers belong inside `go test`.
- A role once signalled into an invented `--db-path`; the broker now refuses a
  path that does not exist. The queue is never opened with sqlite3.
- Run 007's live test fires a real model call and rewrites
  `docs/EVIDENCE-run-007.md` on every full `go test ./...` in the target —
  measure with targeted tests until the Human gates it.
- Never start another role's harness terminal; never start or stop shared
  model servers — the chain is all cloud, there is nothing local to swap.
