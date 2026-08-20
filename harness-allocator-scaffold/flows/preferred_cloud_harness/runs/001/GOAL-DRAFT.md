# GOAL-DRAFT.md — Harness Allocator: carve the harness-generic surface out of DPMtF (corrected)

> **STATUS: DRAFT — NOT APPROVED. Do not start the run.** This file is named
> `GOAL-DRAFT.md` on purpose: `supervisor_state.py` treats it as a draft
> awaiting the Human and will not adopt it as the active run. Approval = the
> Human signs the "Human Approval" section and renames this file to `GOAL.md`
> in the flow's `runs/001/`. Revised 2026-08-19. Everything marked **PROPOSED**
> is the drafting agent's reading, not a decision.

## First handoff id

**1.** `bridge_id_counters.next_id` for `preferred_cloud_harness` is **1** at
drafting, and this is the flow's first run, so the run owns every id from
`001` upward. There is no floor below it to confuse with a closed run.

## Measured state (2026-08-19 — drafting-time snapshot; VOLATILE, re-measure at run open)

> Live-state facts below are a point-in-time observation, not a permanent
> architectural assumption. At run open the supervisor MUST re-measure them;
> never assume they still hold.

- Flow `preferred_cloud_harness` is registered, `next_id = 1`,
  `target_project_path = /home/svend/harness-allocator`.
- Chain: `super-deep-deep4` (dsh / deepseek-v4-pro) -> `imple-codex-minimaxM3`
  (codex / MiniMax-M3) -> `review-claude-sonnet5` (claude-code / sonnet5) ->
  `super-deep-deep4`.
- At drafting, `supervisor_state.py --flow preferred_cloud_harness` reported
  **NO ACTIVE RUN**. Whether tmux sessions are currently running is transient
  and was NOT treated as a durable fact; the supervisor re-checks live state at
  run open.
- At drafting the official target `/home/svend/harness-allocator` was
  read-only to this session and held only `.claude/settings.local.json`
  (mcp-light). Writability is transient — re-check before any write; until it
  is writable and governance permits, the package is staged under
  `harness-allocator-scaffold/` in the Father project and NOT installed.
- Flow scaffolding is built and green: `pytest
  tests/test_preferred_cloud_harness.py -q` -> **41 passed** (governance
  511/512/513, cold-start skill, migrations 055/056, `harness.py`,
  `harness_terminal.py`, `runtime_owner.py`, dispatch wiring).
- Credentials required at role start: `DEEPSEEK_API_KEY` (supervisor),
  `MINIMAX_API_KEY` (implementer) — `harness.py` `REQUIRED_ENV`. A missing or
  rejected key is a stop condition, never something to hunt on disk.
- The extraction seam is documented in
  `docs/harness-terminal-extraction-notes.md` (this repository), sections 3-5.

## Architecture boundary (PROPOSED — corrected)

Harness Allocator does **NOT** resolve, select, replace, or own the model.
Model Allocator is the sole source of truth for model, provider, runtime,
endpoint, local/cloud resolution, and model lifecycle.

```
DPMtF
  -> Model Allocator
  -> resolved model_target
  -> Harness Allocator
  -> Harness Adapter
  -> bounded harness execution
```

The interface is `execute(role, harness, model_target, cwd, task)` — NOT
`execute(role, harness, model, cwd, task)`. `HarnessDefinition` describes
harness identity/configuration only; there is no `resolve_model()` and no
silent model or harness substitution.

## Objective (PROPOSED)

Run 001 begins the carve-out: stand up `/home/svend/harness-allocator` as a
standalone, harness-neutral package that owns the harness-generic surface,
extracted out of DPMtF without breaking the (already green) flow — with the
Model Allocator boundary corrected and the atomic-dispatch defect fixed.

By the end of this run:

1. **The allocator owns the generic surface.** Harness identity resolution,
   launch-command building, the Harness Terminal loop, and the
   environment/credential requirements move from DPMtF into the allocator.
2. **A clean interface with a corrected model boundary.** DPMtF resolves the
   model target through Model Allocator first, then asks the allocator to
   `execute(role, harness, model_target, cwd, task)` and receives
   `{ status, output, error, elapsed, pid, request_id, ... }`. The allocator
   never resolves or substitutes a model (or a harness).
3. **Atomic semantic dispatch.** ONE complete semantic task = EXACTLY ONE
   harness invocation. A length-delimited frame transports large multi-line
   tasks; embedded newlines never define the request boundary. Regression
   coverage uses a 20k+ character multi-line task.
4. **Request identity and payload verification.** Every dispatched request
   exposes `request_id`, payload character count, payload line count, a stable
   payload `sha256`, harness alias, role, and model-target identity (execution
   metadata, never chain-of-thought).
5. **Heartbeat / progress visibility.** Long turns expose RUNNING state, PID,
   elapsed time, periodic heartbeat, SUCCESS/ERROR, final duration, and return
   to READY — without exposing private reasoning.
6. **READY lifecycle reliability.** After SUCCESS, a handled ERROR, or a
   compatible cancellation, the terminal returns to READY; repeated turns are
   covered by automated tests.
7. **Duplicate-request protection.** A completed `request_id` + payload `sha256`
   is recorded for the terminal session and must NOT execute twice. A repeat of
   that identity reports `DUPLICATE_REQUEST` and returns to READY without
   invoking the harness; the only way to re-run a completed identity is an
   explicit `retry` frame (`encode_request(..., retry=True)`), which re-executes
   and re-records it. Regression coverage asserts `DUPLICATE_REQUEST -> READY`
   and that an explicit retry re-executes.
8. **DPMtF stays green and optional.** The 41 flow tests keep passing; DPMtF
   keeps its own dispatch, database, roles, verdicts and governance, and keeps
   working through Model Allocator with or without Harness Allocator.

This is the first of a multi-run carve-out. The notes file's section 4
blockers (an allocator-owned config surface; role identity passed in rather
than read from `bridge_roles`) are the seams this run works across; section 5
is the contract each later run converges on.

## Preferred Cloud Harness Chain (preserved)

Models are resolved by Model Allocator; harnesses are resolved/adapted by
Harness Allocator.

| Role | Harness | Model |
|------|---------|-------|
| Supervisor | DeepSeek Harness | DeepSeek V4 Pro |
| Implementor | Codex | MiniMax M3 |
| Reviewer | Claude Code | Sonnet 5 |

Codex + MiniMax M3 and Claude Code + Sonnet 5 are **NOT** claimed end-to-end
operational until their adapters are actually implemented and tested. Only the
DeepSeek Harness path is currently exercised one-shot (`--profile headless`).

## Reviewer Policy (preserved)

Reviewer: Claude Code + Sonnet 5, independent harness session, repository
read-only by default, may inspect repository / diff / tests / surrounding code,
reports defects, and does **not** silently repair the implementation. Repair may
only exist later as an explicitly governed mode.

## Testgoals

PROPOSED — written against the package name `harness_allocator` and the final
location `/home/svend/harness-allocator`; the exact layout is an implementer
decision inside the fence and is pinned when the Human approves this contract.
Commands run from the DPMtF-WebUI project root (the `check_testgoals.py`
default) unless they `cd` elsewhere.

```testgoals
id: TG1
what: Flow scaffolding regression — the preferred_cloud_harness tests still pass
run: python3 -m pytest tests/test_preferred_cloud_harness.py -q
expect: exit 0

id: TG2
what: The allocator package imports with no DPMtF coupling and no resolve_model
run: cd /home/svend/harness-allocator && python3 -c "import harness_allocator as h; assert not hasattr(h,'resolve_model')"
expect: exit 0

id: TG3
what: execute() returns the documented shape including operational metadata
run: cd /home/svend/harness-allocator && python3 -c "from harness_allocator import execute; r=execute(role='probe', harness='codex', model_target='MiniMax-M3', cwd='.', task='x'); assert set(r) >= {'status','output','error','elapsed','request_id','payload_chars','payload_lines','payload_sha256','harness','role','model_target'}, r"
expect: exit 0

id: TG4
what: No DPMtF coupling and no model resolution in the package
run: grep -RInE "bridge_roles|sqlite3|DPMtF-WebUI|scripts/bridgeV002|resolve_model" /home/svend/harness-allocator/harness_allocator/ || true
expect: empty

id: TG5
what: Package test suite green (atomic transport, request identity, heartbeat, READY lifecycle)
run: cd /home/svend/harness-allocator && python3 -m pytest tests -q
expect: exit 0

id: TG6
what: A 20k+ character multi-line task round-trips as exactly ONE atomic frame
run: cd /home/svend/harness-allocator && python3 -c "from harness_allocator import encode_request, extract_frame; p='line\n'*5000; f,r=extract_frame(encode_request('ha-1',p)); assert r==b'' and f.payload==p and len(p)>=20000"
expect: exit 0

id: TG7
what: DPMtF still resolves the flow's harnesses after the extraction
run: python3 -c "import sys; sys.path.insert(0,'scripts/bridgeV002'); import harness; assert harness.resolve_harness({'allocator_client':'dsh'}) == 'dsh'"
expect: exit 0

id: TG8
what: A completed request_id/payload_hash is not executed twice — DUPLICATE_REQUEST returns to READY
run: cd /home/svend/harness-allocator && python3 -c "import io; from harness_allocator import encode_request, FrameReader, run_terminal, SUCCESS, DUPLICATE_REQUEST; f=encode_request('ha-dup','same task'); r=FrameReader(io.BytesIO(f+f)); w=io.StringIO(); calls=[]; run_terminal(role='probe',harness='dsh',model_target='m',cwd='.',reader=r,writer=w,runner=lambda **k: calls.append(k) or {'status':SUCCESS,'output':'ok','error':'','elapsed':0.1,'pid':1,'request_id':k['request_id']}); out=w.getvalue(); assert len(calls)==1 and '[DUPLICATE_REQUEST]' in out and out.count('Status: READY')==3, (len(calls), out)"
expect: exit 0
```

## Scope Fence (PROPOSED)

MAY create/modify:

1. Everything under `/home/svend/harness-allocator/` (the new standalone
   package) once it is writable and governance permits.
2. In DPMtF-WebUI, the extraction seam and its consumer wiring:
   `scripts/bridgeV002/harness.py`, `scripts/bridgeV002/harness_terminal.py`,
   and the DPMtF-side code that reaches the harness
   (`scripts/bridgeV002/start_coding.py`, `scripts/bridgeV002/dispatch.py`)
   only as needed to consume the allocator — including switching the harness
   dispatch transport to the framed protocol (`encode_request`).
3. `tests/` ADD-only growth for whatever moves.

MUST NOT touch (without a fresh Human decision):

- `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`, `.env` (Human
  approval required by the project's file-access rules).
- Governance files, `databases/dpmtf.db`, `.git/` internals.
- Any other flow's files under the bridge dir.
- New dependencies (none without Human approval).

## Out of scope for Run 001 (deferred to Run 002)

- **Full MCP-Light integration.** Run 002 is the expected architectural seam
  that adds shared MCP capability through Harness Allocator for DeepSeek
  Harness, Codex, and Claude Code. MCP-Light is modeled as a shared harness
  capability, not duplicated DPMtF-specific integration:

  ```
  Harness profile
    -> MCP capability
    -> native harness MCP support where available
    -> adapter MCP bridge where native MCP is unavailable
    -> MCP-Light
  ```

  Heartbeat/progress telemetry should later report MCP connection and MCP
  tool-call activity where observable.

## Budgets (PROPOSED)

| Budget | Value |
|--------|-------|
| Max handoffs | 4 |
| Max active wall-clock | 5 h |
| Max rework attempts per handoff | 2 |
| Max consecutive no-progress cycles | 2 |

## Standing Approvals (PROPOSED — confirmed only by Human approval)

- Target project: `/home/svend/harness-allocator`.
- Dependencies: NONE new.
- Commit after each APPROVED verdict: NO (Human decision).
- Push / merge: NO (Human decision at END-REPORT).
- Schema changes: NONE.

## Human Approval

For the run to start, the Human must:

1. Confirm the objective (or edit it).
2. Confirm the budgets and scope fence.
3. Confirm the standing approvals.
4. Confirm the target project path (`/home/svend/harness-allocator`) and the
   package name/layout the testgoals are written against.
5. Confirm the corrected Model Allocator boundary and the atomic-dispatch
   requirement (ONE task = ONE invocation) are binding for this run.
6. Rename this file to `GOAL.md` in the flow's `runs/001/` — that rename, not
   this draft, is what opens the run. `databases/dpmtf.db` is the standing
   write exception the flow touches on every dispatch; say so here
   deliberately.
