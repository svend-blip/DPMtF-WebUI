---
name: "9010"
description: Cold-start for the shared 9010 workspace (multi-vendor cloud composition) — the planning supervisor's lifecycle position or an ELOOP escalation, discovered in order, never assumed
---

# 9010 — Cold-Start (PLOOP / ELOOP shared workspace)

Invoke with `/9010` at the start of any session in either flow that shares
the `9010` artifact root. You are stateless by design; everything below is
discoverable. This skill holds the flow's FACTS and the reading ORDER. The
rules live in your governance file — read it in full before acting.

## Flow facts

- Flows: `9010-01-PLOOP` (planning: human-planning → planning-human) and
  `9010-02-ELOOP` (execution: decomposer → implementer → reviewer), artifact
  root `/home/svend/flows/9010`.
- Every model is resolved by model-allocator, every interface is launched by
  harness-allocator. This is a MULTI-VENDOR CLOUD composition:
  - planning supervisor: **cloud_deepseek** (deepseek-v4-pro DIRECT at
    api.deepseek.com over the claude-code Anthropic endpoint).
  - decomposer / implementer / reviewer: the **simple-harness** interface
    with **cloud_deepseek_v4pro_direct** (deepseek-v4-pro DIRECT, OpenAI
    endpoint). Needs `DEEPSEEK_API_KEY`.
  - escalation supervisor: **MiniMax-M3** over the **codex** native harness
    (its provider is configured in codex's own user config; needs
    `MINIMAX_API_KEY`).
- **No fixed target repository.** `target_project_path` is NULL in the DB —
  9010 exists to prove the vendor/harness composition, not to build one repo.
  Set a target before running a real build.
- Chain-role tool boundary: `read_file`, `write_file`, `grep`,
  `list_directory`, `search_files` are workspace-relative and reject an
  ABSOLUTE path at the permission gate. The `shell` tool is not path-checked.
  Every flow artifact and governance file lies outside the workspace: shell.

## Step 0 — cold start: minimal context diet

A cold start reads the MINIMUM needed to orient. Do not read the full
SCOPE, the governance file in full, or the ledger beyond the tail:

1. **`get_flow_state` first** — which run is executing, its phase, the
   mandate, the queue tail. One call, no file I/O.
2. **`get_flow_scope(mode="headings")` second** — scope headings only. The
   full SCOPE is read only in Phase 1–3 (discover, clarify, draft).
3. **Ledger tail of the executing run third** — `tail -60` of the executing
   Run's `RUN-LEDGER.md` (the one with an "opened" entry and no END-REPORT,
   NOT the newest directory).

### Shell fallback (when mcp-light is unavailable)

```
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 9010-02-ELOOP
grep '^#' /home/svend/flows/9010/SCOPE.md
tail -60 /home/svend/flows/9010/runs/<RUN>/RUN-LEDGER.md
```

trace.log is flow-wide and the id counters are not: filter on flow AND id
(100_BRIDGE Security Rules 7). File mtimes are local, trace is UTC.

## If you are 9010-planning-supervisor

Governance: `SUPERVISOR_PLANNING.md` — read it in full; it IS your procedure,
phase by phase, as checklists. Facts it cannot know: drafts are
`goals/{ID}-GOAL-DRAFT.md` with the bare Run number; run directories are
padded; chain deliverables are unpadded; promotion is the Human-side
`bridge_broker.py promote-goal`; testgoals are rehearsed under `dash -c`.

## If you are 9010-escalation-supervisor (ELOOP)

Governance: `SUPERVISOR_ESCALATION.md` — read it in full; it IS your
procedure. You are one-shot: ONE bounded decision — ANSWER within the GOAL's
fence, RETRY WITH CORRECTION naming the one change (new handoff id), or PARK
FOR HUMAN — recorded durably, then stand down. When the planning supervisor
is resident under a mandate, it is the wake-up target and you are not invoked.

## Flow-specific hazards (facts, measured)

- A FAILED simple-harness status usually means the endpoint env did not reach
  the session — check `SIMPLE_HARNESS_BASE_URL` / `SIMPLE_HARNESS_MODEL` (and
  `DEEPSEEK_API_KEY`) in the pane before blaming the model.
- The chain roles' shell tool has a default deadline (10 min); a helper
  started with `&` still holds the pipe until the deadline — helpers belong
  inside the test runner.
- Codex resolves ONE global provider from its own config; the escalation role
  is the only codex role here and needs `MINIMAX_API_KEY`.
- Never start another role's harness terminal; never start or stop shared
  model servers — the chain models are all cloud, nothing local to swap.
