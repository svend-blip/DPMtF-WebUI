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

## Step 0 — cold start: minimal context diet

A cold start reads the MINIMUM needed to orient. Do not read the full
SCOPE, do not read the governance file in full, and do not read the
ledger beyond the tail. The order is deterministic:

1. **`get_flow_state` first.** This orients you: which run is executing,
   what phase it is in, the mandate, the queue tail. One call, no file I/O.

2. **`get_flow_scope(mode="headings")` second.** Scope headings only —
   enough to know what the run is fenced to, without loading the full
   document. The full SCOPE is read only in Phase 1–3 (discover, clarify,
   draft), never at cold start.

3. **Ledger tail of the executing run third.** `tail -60` of the executing
   Run's `RUN-LEDGER.md`. The executing Run is the one with a ledger
   "opened" entry and no END-REPORT — NOT the newest directory.

### Context-diet rules

- **Full SCOPE only in Phase 1–3** (discover, clarify, draft). At cold
  start, headings via `get_flow_scope(mode="headings")` are sufficient.
- **Governance by section, never the whole file.** Use mcp-light
  `get_governance_file` to read only the section relevant to the phase at
  hand. Reading the entire governance file at cold start is prohibited.

### Shell fallback (when mcp-light is unavailable)

If the `mcp-light` tools are unavailable, the equivalent shell commands are:

```
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 9000-02-ELOOP
grep '^#' /home/svend/flows/9000/SCOPE.md
tail -60 /home/svend/flows/9000/runs/<RUN>/RUN-LEDGER.md
```

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
