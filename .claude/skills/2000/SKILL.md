---
name: "2000"
description: Cold-start for the shared 2000 workspace (FlowRunner + Export FlowApp test on a cloud model) — the planning supervisor's lifecycle position, discovered in order, never assumed
---

# 2000 — Cold-Start (PLOOP / ELOOP shared workspace)

Invoke with `/2000` at the start of any session in either flow that shares
the `2000` artifact root. You are stateless by design; everything below is
discoverable. This skill holds the flow's FACTS and the reading ORDER. The
rules live in your governance file — read it in full before acting.

## Flow facts

- Flows: `2000-01-PLOOP` (planning: human-planning → planning-human) and
  `2000-02-ELOOP` (execution: decomposer → implementer → reviewer), artifact
  root `/home/svend/flows/2000`.
- **Every agent role runs the `simple-harness` interface on `cloud_qwen38flash`**
  (Qwen3.8-Flash via the Qwen Cloud Token Plan, model-allocator alias
  `cloud_qwen38flash` → runtime profile `qwencloud`). This includes the
  planning supervisor — unlike 9000, there is no claude-code role here.
- **Purpose:** this family exists to test **FlowRunner + Export FlowApp**
  against a cloud model. The DPMtF flow is exported to a FlowApp (the
  `/flowapp-export/description?format=flowrunner` bridge), installed under
  FlowRunner's flowapps dir, and run there. The target repository is the
  one the flow's `target_project_path` names (set in the DB when the Human
  points the test at a repo) — not a fixed path.
- **Timing:** the Token Plan quota renews during the day; if a role's
  simple-harness session fails to reach the model, the plan may not be live
  yet. Created ahead of the plan; run once it is.
- **Persistent sessions (continue-session):** when exported, the
  `planning-supervisor` AND the `execution-decomposer` steps are persistent
  (both hold state across a run — the supervisor across drafts, the
  decomposer across handoffs); `implementer` and `reviewer` stay ephemeral.
- Chain-role tool boundary: `read_file`, `write_file`, `grep`,
  `list_directory`, `search_files` are workspace-relative and reject an
  ABSOLUTE path at the permission gate. The `shell` tool is not path-checked.
  Every flow artifact and governance file lies outside the workspace: shell.

## Step 0 — cold start: minimal context diet

A cold start reads the MINIMUM needed to orient. Do not read the full
SCOPE, do not read the governance file in full, and do not read the ledger
beyond the tail. The order is deterministic:

1. **`get_flow_state` first.** Which run is executing, its phase, the
   mandate, the queue tail. One call, no file I/O.
2. **`get_flow_scope(mode="headings")` second.** Scope headings only. The
   full SCOPE is read only in Phase 1–3 (discover, clarify, draft).
3. **Ledger tail of the executing run third.** `tail -60` of the executing
   Run's `RUN-LEDGER.md` — the run with an "opened" entry and no END-REPORT,
   NOT the newest directory.

### Context-diet rules

- **Full SCOPE only in Phase 1–3.** At cold start, headings suffice.
- **Governance by section, never the whole file** — mcp-light
  `get_governance_file` for the section relevant to the phase at hand.

### Shell fallback (when mcp-light is unavailable)

```
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/supervisor_state.py --flow 2000-02-ELOOP
grep '^#' /home/svend/flows/2000/SCOPE.md
tail -60 /home/svend/flows/2000/runs/<RUN>/RUN-LEDGER.md
```

trace.log is flow-wide and the id counters are not: filter on flow AND id
(100_BRIDGE Security Rule 7). File mtimes are local, trace is UTC.

## If you are 2000-planning-supervisor

Governance: `SUPERVISOR_PLANNING.md` — read it in full; it IS your procedure,
phase by phase, as checklists. This skill adds nothing to it. Facts it cannot
know: drafts are `goals/{ID}-GOAL-DRAFT.md` with the bare Run number; run
directories are padded; chain deliverables are unpadded; promotion is the
Human-side `bridge_broker.py promote-goal`; testgoals are rehearsed under
`dash -c`. The SCOPE arrives as the human-planning request; when this flow is
run through FlowRunner, the SCOPE is the run's task / the session's first
message, and continue-session preserves it.

## Flow-specific hazards (facts, measured)

- All roles are cloud (Qwen Cloud Token Plan). A FAILED simple-harness status
  usually means the endpoint env did not reach the session — check the
  DASHSCOPE / SIMPLE_HARNESS base-url and key in the pane before blaming the
  model. If every role fails to reach the model, the Token Plan quota may not
  be live yet.
- This family deliberately omits 9000's gate-test-impact pre-dispatch and the
  README-impact contract — it is a clean export test vehicle, not a build
  flow. Do not reintroduce them without a Human decision.
- There is no escalation-supervisor; the resident planning supervisor is the
  wake-up target under a mandate.
- Never start another role's harness terminal; never start or stop shared
  model servers — the chain is all cloud, there is nothing local to swap.
