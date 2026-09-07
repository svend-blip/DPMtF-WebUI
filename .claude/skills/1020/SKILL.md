---
name: "1020"
description: Cold-start for the shared 1020 workspace (AI_AdvisoryBoard build, pure-cloud allocator composition) — the planning supervisor's lifecycle position, discovered in order, never assumed
---

# 1020 — Cold-Start (PLOOP / ELOOP shared workspace)

Invoke with `/1020` at the start of any session in either flow that shares
the `1020` artifact root. You are stateless by design; everything below is
discoverable. This skill holds the flow's FACTS and the reading ORDER. The
rules live in your governance file — read it in full before acting.

## Flow facts

- Flows: `1020-01-PLOOP` (planning: human-planning → planning-human) and
  `1020-02-ELOOP` (execution: decomposer → implementer → reviewer), artifact
  root `/home/svend/flows/1020`.
- Every model is resolved by model-allocator, every interface is launched by
  harness-allocator. The planning supervisor runs claude-code on opus5; the
  three chain roles run the **simple-harness** interface with
  cloud_deepseek_v4pro_direct (deepseek-v4-pro DIRECT at api.deepseek.com).
  This pair is PURE CLOUD — no local model server to start or stop.
- **The target repository is `/home/svend/AI_AdvisoryBoard`** (Human decision
  2026-09-07): a new project built from `SCOPE.md`. Testgoals measure that tree.
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
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 1020-02-ELOOP
grep '^#' /home/svend/flows/1020/SCOPE.md
tail -60 /home/svend/flows/1020/runs/<RUN>/RUN-LEDGER.md
```

trace.log is flow-wide and the id counters are not: filter on flow AND id
(100_BRIDGE Security Rules 7). File mtimes are local, trace is UTC.

## If you are 1020-planning-supervisor

Governance: `SUPERVISOR_PLANNING.md` — read it in full; it IS your procedure,
phase by phase, as checklists. This skill adds nothing to it. Facts you need
that it cannot know: drafts are `goals/{ID}-GOAL-DRAFT.md` with the bare Run
number; run directories are padded; chain deliverables are unpadded;
promotion is the Human-side `bridge_broker.py promote-goal`; testgoals are
rehearsed under `dash -c` and measure `/home/svend/AI_AdvisoryBoard`.

## No escalation role

The 1020 family has NO escalation supervisor (Human decision 2026-09-07). A
handoff the ELOOP cannot resolve within the GOAL's fence PARKS FOR THE HUMAN
through the planning supervisor's ladder — there is no one-shot escalation
target to wake.

## Flow-specific hazards (facts, measured)

- A FAILED simple-harness status usually means the endpoint env did not reach
  the session — check `SIMPLE_HARNESS_BASE_URL` / `SIMPLE_HARNESS_MODEL` in
  the pane before blaming the model. The chain needs `DEEPSEEK_API_KEY`.
- The chain roles' shell tool has a default deadline (10 min); a helper
  started with `&` from the shell tool still holds the pipe until the
  deadline — helpers belong inside the test runner.
- A role once signalled into an invented `--db-path`; the broker refuses a
  path that does not exist. The queue is never opened with sqlite3.
- Never start another role's harness terminal; never start or stop shared
  model servers — the pair is all cloud, there is nothing local to swap.
