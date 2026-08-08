# DPMtF — ROADMAP.md

> **Status:** Future architecture roadmap — assessed against the built system 2026-08-08
> **Language:** en-US
> **Purpose:** Guide DPMtF development beyond the current stable architecture without overengineering
> **Principle:** Prefer proven operational needs over speculative abstraction

---

## 1. Current Architecture Baseline

DPMtF currently consists of four clearly separated components:

```text
model-allocator                  model-allocator
(Father machine)                 (worker machine)
      │                               │
      ▼                               ▼
DPMtF-WebUI / Father  ◄────────  DPMtF-LightWorker
      │                               │
      └────────── mcp-light ──────────┘
```

The current responsibility split is:

### DPMtF-WebUI / Father

Owns:

* Job Queue state
* flows
* steps
* roles
* BridgeV002 dispatch
* handoffs
* validation (envelope, patch base cross-check, artifact re-hash)
* evidence
* checkpoints
* watchdog (chain_watchdog, always-on systemd unit)
* flow advancement
* patch application (throwaway worktree → `lightworker/<flow>-<handoff>` branch)
* per-worker authentication (token hashes, identity enforcement)
* authoritative project state

### Model Allocator

Runs on every machine that executes models.

Owns:

* stable logical model aliases
* role-to-model resolution
* runtime profiles
* backend adapters
* client adapters (opencode, claude-code, headless, freebuff)
* context/offload configuration
* validation
* runtime lifecycle
* client configuration rendering

### DPMtF-LightWorker

Runs on remote execution machines.

Owns:

* polling Father
* claiming one role execution
* worker-local model execution
* disposable Git worktree
* worker-local tmux
* client startup
* handoff execution
* heartbeat (paced during deliverable wait)
* patch/deliverable production (commit-before-diff, binary-safe)
* structured result return (including refused completions)
* local retention sweep (hourly, journal-logged, never fatal)

A LightWorker executes one role at a time and does not control the complete
DPMtF flow.

### mcp-light

Provides optional read-only access to:

* governance
* flows
* roles
* verdicts
* project context

Local Father roles normally use the loopback instance.

Remote LightWorker roles may use the optional Tailscale-bound instance.

The execution envelope remains sufficient for a worker to operate without
mcp-light.

---

# 2. Roadmap Principle

The current architecture should be treated as the stable baseline.

The immediate objective is **not** to add more architectural layers.

Development should follow this rule:

> First make one remote role execution boringly reliable. Add new
> orchestration concepts only when repeated operational use demonstrates a
> real need.

Avoid introducing new top-level services unless the responsibility cannot
naturally belong to:

```text
Father
Model Allocator
LightWorker
mcp-light
```

---

# 3. Phase 1 — Stabilize Sequential Remote Role Execution

## Goal

Make remote execution of one DPMtF role on a LightWorker fully reliable.

The reference path is the `lightworker` flow (the strict_review roles
archi01/imple01/review01 are deliberately all-local as of 2026-08-08 and are
not the remote reference):

```text
Father dispatch
   │
   ▼
remote implementer role
svend3060 LightWorker
   │
   ▼
patch + deliverable
   │
   ▼
Father (validate, apply to branch)
   │
   ▼
reviewer role
```

## Required capabilities

The complete path must reliably support:

1. Father selects a remote role.
2. Father selects `model_source = model_allocator`.
3. Father selects a stable logical alias.
4. Static routing selects the LightWorker (`execution_target` on the role).
5. LightWorker polls Father.
6. LightWorker claims one role execution.
7. Worker validates the execution envelope.
8. Worker prepares an exact-base disposable worktree.
9. Worker-local Model Allocator validates the alias.
10. Worker-local Model Allocator prepares the model runtime and client config.
11. Worker creates an execution-specific tmux session.
12. Worker starts the allocator-produced client command.
13. Worker injects the handoff exactly once.
14. The role performs its work.
15. Worker creates the required deliverable.
16. Patch-producing roles create a local result commit.
17. Worker produces a binary-safe patch.
18. Worker returns structured evidence to Father.
19. Father validates the result.
20. Father applies or stores the result.
21. Father advances the flow independently.
22. Worker cleans up local execution resources.

## Status (2026-08-08)

All 22 capabilities above are **built and live-proven**: remote execution
end-to-end (run 001), the rework loop, claim expiry with heartbeat grace,
patch mode at real complexity (run 003, merged), artifact transfer, and
per-worker authentication. The protocol specification stands at 25/27 proven
lines (§42); the two remaining lines require a second consumer of a shared
alias and wait on reality, not on code.

Known open items, in scope for this phase:

* shared-alias lifecycle under contention (the two unproven §42 lines)
* `applied_commit` is not durably persisted after patch application
* remote acknowledge-and-idle recovery is manual (a text nudge); an
  automatic second-stage text nudge is a candidate, not built

## Completion criteria

This phase is complete when remote execution can be used repeatedly without
manual recovery becoming normal operational behavior.

The target is not merely one successful demo — that exists. The target is
predictable repeated execution, which only accumulated operational use can
demonstrate. **Phase 1 is therefore in its operational-maturity period, not
finished.**

---

# 4. Freeze Point

After sequential LightWorker execution is stable, pause architectural
expansion.

Use the system in real DPMtF work.

Observe:

* failure modes
* patch quality
* worker reliability
* context requirements
* model quality
* execution duration
* Git integration problems
* watchdog behavior
* retries
* operational burden

Do not immediately add:

* dynamic worker routing
* distributed scheduling
* parallel role execution
* worker-to-worker communication
* automatic failover
* generalized event infrastructure
* additional control-plane services

New architecture should be justified by observed limitations.

---

# 5. Phase 2 — Introduce a Patcher Role

## Goal

Introduce a dedicated integration role between remote implementation and
technical review.

Initial sequential flow:

```text
architect role
   │
   ▼
implementer role
LightWorker
   │
   ▼
candidate patch
   │
   ▼
patcher01
strong model
   │
   ▼
integrated authoritative result
   │
   ▼
reviewer role
```

## Purpose

`patcher01` acts as the controlled integration boundary between a
LightWorker candidate result and the authoritative project state.

Today that boundary is mechanical: `worker_results.py` validates the patch
(checksum, envelope base cross-check) and applies it in a throwaway worktree
to a `lightworker/` branch; the merge is Human-gated. Patcher slots in
between the mechanical apply and review.

It should answer:

> Is this candidate patch suitable for integration, and what is the safest
> correct way to apply it?

## Responsibilities

Patcher may:

* inspect the execution handoff
* inspect the LightWorker deliverable
* inspect the candidate patch
* confirm the expected base commit
* verify patch scope
* reject unrelated changes
* apply the patch in an authoritative integration worktree
* resolve bounded integration conflicts
* preserve intended implementation behavior
* run relevant checks and tests
* produce an integration report
* produce the authoritative candidate state for review

## Non-responsibilities

Patcher should not normally:

* redesign the architecture
* replace the implementer
* implement a completely different solution from scratch
* approve its own result
* advance the flow independently
* bypass review
* modify governance
* merge to main — the merge remains Human-gated

Patcher is an integration role, not a second architect or unrestricted
implementer.

---

# 6. Why Patcher Is Useful Before Parallelism

Patcher provides value even when only one LightWorker exists.

Without Patcher:

```text
LightWorker
→ patch
→ Father applies patch mechanically
→ review
```

With Patcher:

```text
LightWorker
→ candidate patch
→ intelligent integration
→ review
```

This adds a model-assisted integration gate while preserving the current
sequential flow architecture.

It also creates a natural future **fan-in point** if multiple LightWorkers
are introduced later.

---

# 7. Phase 3 — Candidate Patch Evaluation

## Goal

Extend Patcher from simple integration to candidate evaluation.

Father may eventually collect more than one candidate implementation for the
same requested change.

Example:

```text
Implementation task
    │
    ├── candidate A
    └── candidate B
            │
            ▼
        patcher01
            │
            ▼
      selected result
```

Initially, multiple candidates do not require simultaneous execution.

Candidates may be generated sequentially for evaluation experiments.

## Patcher evaluation responsibilities

Patcher should be able to evaluate candidate patches based on:

* scope compliance
* correctness
* simplicity
* regression risk
* test evidence
* maintainability
* architectural consistency
* unnecessary change volume
* deliverable quality

Possible verdicts:

```text
SELECT_A
SELECT_B
COMBINE
REJECT_ALL
NEEDS_REWORK
```

`COMBINE` should only be allowed when changes can be integrated safely and
the combined result remains understandable.

---

# 8. Phase 4 — Ensemble Implementation

## Goal

Allow the same implementation task to be executed independently by multiple
LightWorkers or execution targets.

This is DPMtF's coding-oriented form of ensemble reasoning.

Example:

```text
                 ┌── LightWorker A ── patch A
                 │
task ────────────┼── LightWorker B ── patch B
                 │
                 └── LightWorker C ── patch C
                                      │
                                      ▼
                                  patcher01
                                      │
                                      ▼
                               selected result
```

## Ensemble reasoning

In this mode, several independent executions solve the same or substantially
overlapping task.

The purpose is not primarily speed.

The purpose is to increase implementation quality by producing independent
candidate solutions.

Different executions may use:

* different local models
* different prompting strategies
* different worker hardware
* different implementation approaches
* different model families

A strong Patcher can then compare the actual code changes rather than
relying on one model's reasoning alone.

---

# 9. Ensemble Execution Contract

All competing candidates should normally share:

```text
same job
same handoff
same task
same base commit
same expected deliverable contract
different execution IDs
```

Conceptually:

```text
JOB-123
└── implementation candidate set
    ├── EXEC-123-A
    ├── EXEC-123-B
    └── EXEC-123-C
```

Each execution receives the same authoritative base:

```text
base_commit = abc123
```

Each candidate is returned independently.

No candidate should see another candidate's result before completion unless
the flow explicitly defines collaborative behavior.

This preserves independence.

---

# 10. Phase 5 — Parallel Fan-Out / Fan-In

## Goal

Only after candidate evaluation is proven useful should DPMtF support true
parallel execution.

The flow model then evolves from:

```text
A → B → C → D
```

to supporting:

```text
          ┌→ B1 ─┐
A ────────┼→ B2 ─┼→ C → D
          └→ B3 ─┘
```

This introduces explicit:

```text
fan-out
fan-in
```

semantics.

## Fan-out

One parent step creates several child role executions.

## Fan-in

A downstream step becomes eligible when the required child executions reach
their defined terminal conditions.

Patcher is the natural initial fan-in role.

---

# 11. Parallelism Must Be Explicit

Parallelism should not be implemented simply by changing:

```text
max_parallel_executions = 1
```

to:

```text
max_parallel_executions = N
```

True flow parallelism affects:

* Job Queue semantics
* execution parent/child relationships
* completion rules
* retries
* cancellation
* watchdog logic
* artifact grouping
* checkpoints
* evidence
* patch integration
* failure policy

Therefore fan-out/fan-in must be introduced as a deliberate flow concept.

---

# 12. Two Types of Parallel Work

DPMtF should distinguish between two future use cases.

## 12.1 Competitive parallelism

Several executions solve the same task.

```text
same task
├── candidate A
├── candidate B
└── candidate C
```

Purpose:

* improve quality
* reduce dependence on one model
* compare implementation strategies

Patcher acts primarily as evaluator.

## 12.2 Decomposed parallelism

Architect divides a larger task into independent subtasks.

```text
parent task
├── backend implementation
├── frontend implementation
└── tests/migration
```

Purpose:

* reduce total wall-clock time
* use specialized workers/models
* divide a large implementation safely

Patcher acts primarily as integrator.

These modes should not be conflated.

---

# 13. Future Parallel Flow Example

A future implementation flow could become:

```text
Supervisor / Architect
        │
        ▼
Implementation Plan
        │
        ├───────────────┬───────────────┐
        ▼               ▼               ▼
LightWorker A       LightWorker B    LightWorker C
local model         local model      local model
        │               │               │
        └──────── candidate patches ─────┘
                        │
                        ▼
                    patcher01
                strong cloud model
                        │
                        ▼
                    review01
                independent review
                        │
                        ▼
                  Supervisor
```

The roles remain deliberately distinct.

### Implementers

Produce candidate changes.

### Patcher

Selects and integrates the best implementation.

### Reviewer

Judges the resulting integrated implementation.

### Supervisor

Owns higher-level flow decisions.

---

# 14. Patcher and Reviewer Must Remain Separate

This separation is important.

Patcher asks:

> What is the best integrated implementation from the available candidate
> changes?

Reviewer asks:

> Is the resulting implementation technically correct, compliant and
> acceptable?

The same execution should not normally both integrate and independently
approve the result.

This preserves adversarial review.

---

# 15. Model Strategy

A future ensemble flow does not require all roles to use expensive cloud
models.

A likely model hierarchy is:

```text
Architect / Supervisor
    strong reasoning model

Implementers
    inexpensive local or lower-cost models

Patcher
    strong cloud reasoning/coding model

Reviewer
    independent strong model
```

This allows DPMtF to use local compute to generate multiple candidate
implementations while spending expensive cloud tokens mainly on:

* selection
* integration
* review
* difficult architecture decisions

The economic objective is:

> Generate alternatives cheaply; spend expensive reasoning where comparison
> and judgment have the highest value.

Where the Reviewer is meant to be independent, prefer a different model
family from the Patcher — same-family review has already been observed to
add no diversity (preferred_cloud run 007).

---

# 16. Resource Strategy

LightWorkers should remain simple execution nodes.

A future worker pool may contain machines with different capabilities:

```text
worker-a
RTX 3060
small local coder

worker-b
RTX 5090
large local coder

worker-c
CPU/RAM-heavy llama.cpp model

cloud execution target
API model
```

Model Allocator remains responsible for the model/runtime details on each
machine.

Father remains responsible for deciding which role execution is assigned to
which execution target.

Do not move distributed scheduling policy into Model Allocator.

---

# 17. Static Routing Before Dynamic Routing

Even after multiple LightWorkers exist, static routing should remain the
first mechanism.

Example:

```text
imple-a → worker-a
imple-b → worker-b
imple-c → worker-c
```

Dynamic resource-aware routing should only be introduced if static mappings
become an operational burden.

Possible future dynamic inputs could include:

* worker availability
* VRAM requirement
* required backend
* required model alias
* context requirement
* estimated execution cost
* current worker load

But dynamic routing is explicitly not required for the current architecture.

---

# 18. Git Strategy for Parallel Candidates

Parallel candidate executions should use the same existing isolation
principle.

Each candidate starts from the same exact base commit:

```text
base_commit
├── worktree A → candidate patch A
├── worktree B → candidate patch B
└── worktree C → candidate patch C
```

Workers should continue to:

* avoid pushes (workers never receive push access)
* avoid merges
* avoid shared working trees
* return patches or deliverables

Patcher receives the candidate artifacts and integrates only on the Father
side.

This keeps Git authority centralized even when execution becomes
distributed.

---

# 19. Candidate Artifact Grouping

Future fan-out executions should belong to a common candidate set.

Conceptual identifiers:

```text
job_id
parent_step_id
candidate_set_id
execution_id
attempt_id
```

Example:

```text
JOB-123
candidate_set: CS-123-IMPLE
├── EXEC-A
├── EXEC-B
└── EXEC-C
```

Patcher receives:

```text
candidate_set_id
base_commit
candidate artifacts
candidate evidence
candidate test summaries
```

Candidate grouping should be added only when ensemble execution is actually
implemented.

It is not required for current LightWorker V1.

---

# 20. Failure Policy for Future Fan-Out

A parallel candidate set does not necessarily require every candidate to
succeed.

Possible policies:

```text
ALL_REQUIRED
MIN_SUCCESSFUL_N
FIRST_SUCCESS
BEST_BEFORE_DEADLINE
```

For ensemble implementation, a likely policy is:

```text
MIN_SUCCESSFUL_N
```

Example:

```text
requested candidates: 3
minimum successful: 2
```

Patcher can proceed once enough valid candidates exist.

This should be introduced as flow configuration rather than hardcoded
scheduler logic.

---

# 21. Watchdog Evolution

Current remote execution liveness is based on LightWorker heartbeats.

This should remain the basis for future parallel executions.

For fan-out:

```text
parent step
├── child execution A heartbeat
├── child execution B heartbeat
└── child execution C heartbeat
```

Watchdog should evaluate each child execution independently.

A failed or silent child should not automatically invalidate other healthy
candidates.

Remote executions must continue to avoid automatic duplicate signal nudging
— a re-sent signal mints a second offer, which is worse than the stall it
tries to fix.

---

# 22. Checkpoint Evolution

Current checkpoints represent progression through sequential steps.

Future fan-out may require a checkpoint to reference:

```text
parent step
candidate set
candidate artifacts
selected candidate
Patcher integration result
```

The authoritative checkpoint should still be created after Patcher
integration, not after every candidate becomes available.

Individual candidate execution state belongs to execution evidence.

---

# 23. What Should Not Be Built Prematurely

Do not build the following solely to prepare for hypothetical scale:

```text
distributed consensus
worker election
message broker
Kafka
Kubernetes
distributed database
worker-to-worker RPC
global event sourcing
automatic GPU bidding
automatic model migration
live context migration
automatic cross-worker failover
generic plugin marketplace
distributed Git authority
```

The existing Father-centered architecture should remain unless a
demonstrated limitation requires otherwise.

---

# 24. Decision Gates

Each major roadmap phase should require an explicit evidence gate.

## Gate A — Before Patcher

Require:

* repeated successful remote role executions
  — *partially met 2026-08-08: runs 001-003 succeeded, including a rework
  loop and patch mode at real complexity; sustained repetition without
  manual recovery is still accumulating*
* stable patch transport — *built and proven (checksum + base cross-check +
  artifact re-hash)*
* stable Father-side patch validation — *built and proven*
* reliable LightWorker cleanup — *built (disposable worktrees + retention
  sweep); needs operational time*
* no recurring Git authority problems — *none observed yet; needs
  operational time*

## Gate B — Before Ensemble Candidates

Require:

* Patcher proven useful with single candidate patches
* reliable Patcher integration behavior
* independent Reviewer still catches errors
* clear evidence that multiple implementations could improve outcomes

## Gate C — Before Parallel Fan-Out

Require:

* multiple candidate generation proven useful
* sequential multiple-candidate experiments show quality gain
* wall-clock cost justifies parallel execution
* Job Queue changes have clear requirements

## Gate D — Before Dynamic Routing

Require:

* several active workers
* static routing has become operationally limiting
* worker capability differences materially affect scheduling

---

# 25. Recommended Near-Term Roadmap

## Now

Focus only on:

```text
remote role
→ LightWorker
→ patch/deliverable
→ Father
→ next sequential role
```

## Next

Potentially add:

```text
remote implementer
→ patcher01
→ reviewer
```

still completely sequential.

## Later

Experiment with:

```text
same task
→ candidate A
→ candidate B
→ patcher comparison
```

initially even if the candidates are produced sequentially.

## Only after proven value

Introduce:

```text
parallel fan-out
→ multiple LightWorkers
→ Patcher fan-in
```

## Much later, only if needed

Consider:

```text
dynamic worker routing
resource-aware scheduling
specialized worker pools
```

---

# 26. Long-Term DPMtF Direction

The long-term system may evolve toward a model where expensive reasoning is
concentrated at decision points while implementation work is distributed
across inexpensive execution capacity.

Conceptually:

```text
Strong Supervisor
       │
       ▼
     Plan
       │
       ▼
distributed candidate work
       │
       ▼
Strong Patcher
       │
       ▼
Independent Reviewer
       │
       ▼
Supervisor decision
```

This preserves DPMtF's core philosophy:

* explicit roles
* explicit governance
* explicit handoffs
* evidence-based progression
* controlled model selection
* deterministic integration boundaries

while allowing greater use of local and remote compute.

---

# 27. Architectural Invariants

The following rules should remain true even if parallel execution is added
later.

### Father remains authoritative

Father owns:

* job state
* flow semantics
* validation
* checkpoints
* final progression

### Model Allocator remains model/runtime authority

No worker or flow implementation should hardcode backend-specific model
lifecycle logic.

### LightWorkers remain replaceable execution nodes

A worker executes assigned role work.

It does not become a distributed Father.

### Git authority remains centralized

Workers return candidate results and never receive push access.

Father-side integration owns authoritative project state.

### Merges to main remain Human-gated

Automated integration produces branches and reports. The decision to merge
stays with the Human until explicitly delegated — this holds for Patcher as
it holds for the mechanical apply today.

### Patcher does not replace Reviewer

Integration and independent approval remain separate concerns.

### Remote context remains optional

Execution envelopes remain sufficient for execution.

mcp-light may enrich role context but should not become a mandatory
dependency for remote execution.

### No state a check reads is edited to pass the check

This binds every role in every phase, including future Patcher and any
supervisor. A check that is wrong is reported with evidence, not silenced.

---

# 28. Final Roadmap Summary

```text
CURRENT
=======

Father
  ↓
one remote role
  ↓
LightWorker
  ↓
patch / deliverable
  ↓
Father
  ↓
next sequential role


NEXT POSSIBLE STEP
==================

Father
  ↓
LightWorker implementer
  ↓
candidate patch
  ↓
Patcher
  ↓
integrated result
  ↓
Reviewer


FUTURE ENSEMBLE
===============

                  ┌→ LightWorker A → patch A ─┐
Father / Architect├→ LightWorker B → patch B ─┼→ Patcher → Reviewer
                  └→ LightWorker C → patch C ─┘


FUTURE PARALLEL SUBTASKS
========================

                  ┌→ backend worker ──┐
Architect / Plan ─┼→ frontend worker ─┼→ Patcher → Reviewer
                  └→ test worker ─────┘
```

The roadmap intentionally stops short of defining a general distributed
execution platform.

The immediate priority is operational maturity of the architecture already
built.

Parallelism, ensemble reasoning and dynamic routing are future options, not
current requirements.
