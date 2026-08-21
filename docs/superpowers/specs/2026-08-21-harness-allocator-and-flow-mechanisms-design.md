# Design: Harness Allocator Maturation, Unified Flow Mechanisms, and Flow Startup Contract

Date: 2026-08-21
Status: Approved direction (Human, 2026-08-21) — spec pending Human review
Placement: to be moved to `docs/superpowers/specs/` in DPMtF-WebUI and committed
by the Human **after preferred_cloud_harness Run 004 closes**. Until then this
file lives outside the working tree by design (the evidence gate measures the
tree, and the tree is itself the measured object of the active run).

---

## 1. Scope and non-goals

This design covers four deliverables, in dependency order:

- **A.** Maturation goal for the `harness-allocator` carve-out (external repo).
- **B.** Unification of the mechanisms that keep BridgeV002 flows running,
  applied identically across all flows.
- **C.** A cold-start contract for flows: `docs/governance-templates-v2/101_FLOW_STARTUP.md`.
- **D.** README.md rewrite of DPMtF-WebUI to current state (last, after A–C land).

Non-goals:

- No redesign of Run 003's broker/evidence/scope architecture — it is
  authoritative (Run 004 GOAL §3).
- No change to the Model Allocator boundary: Harness Allocator never resolves,
  chooses, or substitutes a model. `execute(role, harness, model_target, cwd,
  task)` is the frozen public contract.
- No hand-edits to production mechanisms outside governed runs. Everything in
  B ships as 1–2 governed runs with DPMtF-WebUI as the target project.

## 2. Section A — Harness Allocator maturation

### A.1 Current state (measured 2026-08-21)

- `/home/svend/harness-allocator`: stdlib-only package, 66 tests, working
  argv/execute/terminal/transport/heartbeat/duplicate-protection surface.
- Git repo has **zero commits and no remote**; intended remote is
  `https://github.com/svend-blip/harness-allocator.git`.
- Product `GOAL.md` exists only in the stale staging mirror
  `DPMtF-WebUI/harness-allocator-scaffold/harness-allocator/GOAL.md`.
- The staging mirror has drifted from the live repo in all 7 modules; Run 003's
  END-REPORT already marks it "may be retired".
- Run 004 (active): MCP-Light access (Objective A) + deterministic Codex
  fresh-context lifecycle (Objective B). MCP implementation is on disk; its 33
  tests were reverted during the 017 gate loop and must be re-landed.

### A.2 Target state

1. **Run 004 completes on its existing plan**: land the reverted MCP tests
   under a parser-safe per-file scope; implement Objective B (fresh-context
   reset at the governed work-unit boundary); live acceptance + full-chain
   regression. Budget 6 handoffs, 3 used at time of writing.
2. **Repo maturation as a Human action immediately after Run 004 closes**
   (recommended over a run — it is pure git mechanics):
   - `git remote add origin git@github.com:svend-blip/harness-allocator.git`
   - Move the product GOAL.md into the repo root (updated to post-Run-004
     reality), refresh README.md, first commit of the whole tree, push.
3. **Father cleanup after Run 004 closes** (also Human or a trivial run):
   - Retire `harness-allocator-scaffold/` (git rm; history preserves it).
   - Delete stray root/tests files `harness_allocator_run001_*_task.md`.
   - Delete the empty stray `bridge.db` (0 bytes, 2026-08-18) in the Father root.
4. **Run 005**: `/skill` support in the Harness Terminal, including cold-start
   skill invocation (deferred item from Run 003).
5. **Frozen boundary**, restated as a permanent invariant: Harness Allocator
   owns harness identity, adapters, one-shot execution, terminal lifecycle,
   request identity/telemetry, duplicate protection. It does not own model
   selection, flows, roles, governance, sequencing, or the bridge DB. DPMtF
   consumes it only through `scripts/bridgeV002/harness.py` and
   `harness_terminal.py`.

### A.3 Capability model (the product thesis)

The package's end state is the ability to express: *"Launch this harness with
these governed capabilities and this context lifecycle policy."* Three governed
capabilities behind the frozen `execute()` interface:

| Capability | Delivered by | Mechanism (per harness) |
|---|---|---|
| MCP server access | Run 004 Obj. A | codex: `codex mcp add`; dsh: patch-yml plugin entry, `failOnStartupError` = required |
| Context lifecycle | Run 004 Obj. B | deterministic fresh-context reset at work-unit boundary |
| Skill invocation | Run 005 | Harness Terminal `/skill` support |

Harness-specific mechanics must never leak into DPMtF flow logic.

## 3. Section B — Unified flow mechanisms

### B.1 The three-layer model

Every flow uses the same three layers; a flow type may leave a layer thinner,
never different:

1. **Delivery** — how a prompt reaches a role: tmux injection with
   `verify_injection_submitted` (all roles), plus the persistent Harness
   Terminal with heartbeats for harness-backed roles.
2. **Advancement** — how the chain moves: the broker's two DB queues
   (`bridge_dispatch_queue`, `bridge_materialize_queue`) as the **only**
   role-facing signal path; `dispatch.py` executes host-side; the `callback`
   convention rule (migration 057) fixes verdict destinations.
3. **Recovery** — what acts when the chain does not move: chain_watchdog
   (systemd), scheduler `_advance_chain` fallback (cron), generalized stall
   wake-up to the flow's own supervisor, lease sweep, evidence gate,
   `supervisor_state.py` + cold-start skill, runtime ownership registry.

### B.2 Deliverables

1. **`bridge-broker.service`** — systemd user unit mirroring
   `chain-watchdog.service` (`Restart=always`, `RestartSec=15`), replacing the
   current hand-started `nohup … daemon --interval 2.0` on a pty. A logout must
   never kill the chain again.
2. **Broker as the universal role-facing signal path.** Every flow's
   `chain_advancement` block enqueues via `bridge_broker.py enqueue`; no role
   ever invokes `dispatch.py` directly. Direct `dispatch.py` remains documented
   as Human recovery only. (Most templates already do this — the run verifies
   and closes the stragglers.)
3. **Evidence gate on all supervisor-shaped flows.** Add
   `pre_dispatch_script = gate-deliverable-evidence.py` to reveng's two review
   steps (the only supervisor-shaped flow without it).
4. **Generalized stall wake-up.** New column `bridge_flows.supervisor_role`
   (nullable). When the watchdog/scheduler nudge budget is exhausted, the
   wake-up targets the flow's own supervisor session/harness path instead of
   the hardcoded `supervisor_auto`. NULL = current behavior (notify Human).
5. **Full runtime ownership.** `runtime_owner.record()` is called for every
   session/process DPMtF starts, in all flows (today: only the harness flow and
   supervisor sessions). Rule unchanged: started by DPMtF → stoppable by DPMtF,
   by recorded pid/session only; anything else is never touched.
6. **Documentation.** `100_BRIDGE.md` gains the three-layer model and a
   flow-type matrix. The two-stage review flows' deviation
   (`technical_review`/`verdict` rules, human terminal step,
   `post-dispatch-common.py`) is documented as a deliberate flow type, not
   harmonized away.
7. **Sequential-flow invariant (Human-raised 2026-08-21).** Flows are designed
   for sequential execution, but nothing serializes deliveries *across*
   transitions that target the same role: the broker is single-lane per row and
   dispatch's flock only guards one transition, so concurrent senders (a
   supervisor answer, a callback, a gate return) can converge on one session.
   Observed live in Run 004: the reviewer mid-turn with two queued `/clear`
   commands from injection attempts that landed while it was busy — a queued
   `/clear` wipes the context the *next* queued prompt needs. Deliverables:
   (a) the broker enforces **at most one outstanding delivery per flow** —
   a dispatch row for a flow is not claimed while an earlier delivery to any of
   the flow's roles is unconfirmed; (b) `inject_prompt` refuses to paste into a
   busy pane (activity markers present) or an interactive menu, and requeues
   with backoff instead of queuing keystrokes blindly; (c)
   `verify_injection_submitted` never presses Enter into a pane showing a
   menu/selector (the blind Enter can select an arbitrary menu option).
8. **Broker crash recovery (found live 2026-08-21).** The daemon's recovery
   queries match `processing` rows only by its **own** `broker_pid`
   (`bridge_broker.py:551`, `:974`), so a restarted daemon never recovers rows
   claimed by a dead predecessor: a row whose spawned `dispatch.py` completed
   stays cosmetically stuck (observed: row 36, delivery proven by trace.log),
   but a row killed *before* delivery would be silently lost forever.
   Deliverable: a startup sweep that requeues `processing` rows whose
   `broker_pid` no longer exists, made idempotent by checking trace.log for an
   already-completed delivery before re-running it.
9. **Handoff-id normalization (found live 2026-08-21).** The broker's
   `materialize` computes destinations as `{id:03d}` (`021-handoff.md`), but
   `enqueue` passes `--id` through verbatim to `dispatch.py`, so a role
   enqueuing `--id 21` produces a send that looks for `21-handoff.md` and
   fails against a correctly materialized `021-handoff.md` (observed: run 004
   dispatch row 47 `send_failed`; recovered by re-enqueueing with the padded
   id, duplicate-safe thanks to the idempotency guard). Deliverable: `enqueue`
   normalizes numeric ids to the same `{int:03d}` format `materialize` uses,
   in one shared helper.
10. **Runtime-ownership anchor precision (found live 2026-08-21).**
   `start_coding._pane_pid` records the tmux pane pid as the `harness_process`
   anchor — documented best-effort, but in practice that is the pane's
   interactive bash (TERM-immune), not the harness child (observed: recorded
   pid 1510133 `-bash`; real codex child 1511263). `_default_kill` also
   returns True on signal *sent*, without verifying death. Net effect: the
   Codex `work_unit` fresh-context policy reports a stop while stopping
   nothing (unit tests are green because `_kill` is mocked). Deliverables:
   resolve the harness child pid at record time, and verify process exit in
   the kill helper.
11. **Codex MCP under the governed profile (found live 2026-08-21).** Codex
   0.148 rejects every MCP tool call under `--ask-for-approval never`
   ("MCP tool call requires approval, but approval policy is never");
   per-server `trusted`/`requires_approval` config probes do not help (known
   upstream: openai/codex#24135). The working governed mode is
   `--approve-for-me` (stable `guardian_approval` feature): approvals route
   through automatic review (observed: "risk: low" allow, then a successful
   live `mcp-light.get_panel_groups` call). The flag implies the
   workspace-write sandbox and conflicts with explicit `--sandbox` /
   `--ask-for-approval` flags. Deliverable: `build_launch_command`'s codex
   branch emits `--approve-for-me` (and drops the conflicting flags) when MCP
   servers are configured for the role.

### B.3 Execution

Ship as 1–2 governed runs with **DPMtF-WebUI as target project** (flow:
preferred_cloud or preferred_cloud_harness), after Run 004 closes. Suggested
split: Run α = items 1–3 (pure hardening, small fence); Run β = items 4–6
(schema + scheduler + docs). Each GOAL.md carries testgoals rehearsed under
`dash -c` per the standing contract method.

Out of scope for these runs: the legacy job_queue scheduler's internals (it
stays as the cron-driven fallback layer), LightWorker remote mechanisms.

## 4. Section C — `101_FLOW_STARTUP.md` (cold-start contract)

One authoritative governance document defining, per flow type, what it takes to
start a flow from nothing. Binding table per type:

| | Supervisor-driven | Architect-driven | Bare/other |
|---|---|---|---|
| Flows | llama_SG, preferred_cloud, preferred_cloud_harness, reveng | strict_review, cloud_llm, cloud_pay | supervisor, pi_test, lightworker |
| Start artifacts | `runs/NNN/GOAL.md` + `BACKLOG.md` + `RUN-LEDGER.md` | handoff file in `{flow}/handoffs/` | per-flow minimal contract |
| GOAL requirements | testgoals block + scope fence + budget | n/a (contract lives in the handoff) | n/a |
| Author | Human approves GOAL (rename `GOAL-DRAFT.md` → `GOAL.md` **is** the approval act); supervisor may materialize BACKLOG/LEDGER via broker | Human/Architect writes the handoff | Human |
| First dispatch | wake-up to the supervisor role (broker enqueue or `dispatch.py --signal-send`) | `--signal-send` Human → first role | manual |
| Verification | `supervisor_state.py --flow {flow}` assessment string | role cold-start skill (STRICTREVIEW/CLOUDLLM/CLOUDPAY) | n/a |
| Session bring-up | `start_tmuxflow.py` → `start_coding.py` → harness terminal for harness roles → broker daemon check | same minus harness terminal | per flow |

Additional binding rules to encode:

- A directory is not a run until it holds a run artifact; `GOAL-DRAFT.md` is
  never adopted (`supervisor_state.py` behavior, commit 02bc058).
- Broker daemon liveness is a **precondition** of starting any flow whose roles
  are sandboxed; the startup sequence must check it.
- The document is referenced from every cold-start skill and from
  `start_coding.py`'s startup banner.

Authoring: the document itself is a docs-only change, but it still lands via
the normal approval path (governance dir requires Human approval) and only
after Run 004 closes.

## 5. Section D — README.md rewrite

After A–C land: rewrite DPMtF-WebUI's README.md to describe current reality —
Father/Prompt-Compiler identity, BridgeV002 with the broker seam, the
three-layer mechanism model, flow types with links to 100/101 governance docs,
the harness-allocator and model-allocator boundaries, and the standard
validation checklist. No aspirational content; only what is live.

## 6. Ordering and gates

1. **Now**: supervise Run 004 to closure (no working-tree writes).
2. **After Run 004 closes**: Human commits the in-flight gate/broker fixes and
   the run's landings; Human executes A.2 step 2 (repo maturation) and step 3
   (Father cleanup); this spec moves into `docs/superpowers/specs/` and is
   committed.
3. **Then**: Run α / Run β (Section B), each with its own GOAL contract.
4. **Then**: Run 005 (`/skill`) in preferred_cloud_harness.
5. **Then**: 101_FLOW_STARTUP.md authored and approved; README rewritten.

## 7. Risks and mitigations

- **Broker daemon dies before Run 004 closes** (nohup on a pty): monitored
  live; if it dies mid-run the immediate recovery is restarting the same
  command line — the systemd unit ships in Run α, not by hand-edit now.
- **Reviewer session parked in an interactive menu** (017-era): the role's
  `fresh_session_command=/clear` clears it on next dispatch; do not intervene
  pre-emptively (an intervention leaves a mode behind).
- **Generalized stall wake-up loops** (supervisor wakes supervisor): keep the
  once-per-flow/handoff/step marker semantics from the existing
  `_record_stall_wake_up` when generalizing.
- **Gate scope regressions while unifying**: every run GOAL binds criteria to
  files by exact path; rehearse red and green against a complete fixture and
  under `dash -c`, per the standing supervision doctrine in CLAUDE.md.
