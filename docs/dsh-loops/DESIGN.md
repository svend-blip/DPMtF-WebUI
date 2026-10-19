# DSH Two-Loop Design — Planning Supervisor + Execution Workflow

> **Moved 2026-10-19:** the template, the locked workflow, the three skills
> and copies of the four role contracts now live in the standalone
> `~/dsh-two-loop/` (skills installed via `~/.dsh/skills/`). This directory
> keeps the design history and validation reports.

Status: CONFIRMED by live audits + first isolated run (updates: persistence
audit, DSH capability probe, test-project execution 2026-10-18). Date:
2026-10-18. Goal: run DPMtF's two loops as two independent DeepSeek Harness
(DSH) sessions with minimal special development — no new service, database,
allocator, WebUI, plugin or framework.

Evidence base: `docs/ANALYSE-DSH-ROLLE-MODELSKIFT-2026-10-18.md`,
`docs/dsh-loops/contract-analysis-supervisor-decomposer.md` (15 conflicts),
`docs/dsh-loops/contract-analysis-implementor-review.md` (12 conflicts),
live route/scope/skill probes 2026-10-18 (see VALIDATION report).

Confirmed runtime facts (measured, not assumed):
- Provider config: `llm-pi-ai.providers.<route>`; keyless llama.cpp endpoints
  still need a resolvable credential — a dummy ref in
  `~/.dsh/.credentials.yaml` (`P620_1/2_LOCAL_API_KEY: dummy`) satisfies
  `getClientApiKey`; llama.cpp ignores the Authorization header. Settings
  re-read per request (no restart). Routes verified live in child logs:
  `llamacpp-p620-1/qwen35-122b-a10b-q5`, `llamacpp-p620-2/glm45-air-iq4xs`,
  `strata-local/qwen3.8-flash-next-gptq-nvfp4`.
- Workflow engine: `agent()` opts = label/phase/schema/provider/model only;
  schemas are a JSON-Schema subset and `enum` REQUIRES `type`; route/child
  failures resolve `agent()` to `null` (script must handle null → stopped);
  scripts have no filesystem (only agent/parallel/pipeline/phase/log/args).
- Child logs: `~/.dsh/sessions/<cwd-slug>/<uuid>/session.v3.jsonl.zstd`,
  model identity at `request/header → data.header.config.provider|model`.
- Skills: DSH scans `<projectRoot>/.dsh/skills/` (rank 100) — NOT
  `.claude/skills`. Sessions launch headless per project:
  `dsh --profile headless "<task>"` from the project dir (own DSH process;
  default model from `agent-default-model`; roles override per call).
- Hook inheritance: child agents inherit session hooks (they see generic
  "call scope-mcp status" hints) — role prompts pin the task explicitly.

## 1. Shape

- **Session 1 — Planning Supervisor** (`SUPERVISOR_PLANNING`,
  strata-local/qwen3.8-flash-next-gptq-nvfp4): owns project scope, ideas,
  priorities; creates RUNs far ahead of execution; ONLY creator of RUNs;
  resumes its own DSH session across days.
- **Session 2 — Execution**: DSH session driving one locked, reusable
  workflow artifact per READY RUN:
  `EXECUTION_DECOMPOSER (llamacpp-p620-1/qwen35-122b-a10b-q5)` →
  per HANDOFF `IMPLEMENTOR (strata-local/qwen3.8-flash-next-gptq-nvfp4)` →
  `REVIEW (llamacpp-p620-2/glm45-air-iq4xs, APPROVED|REJECTED)` →
  `EXECUTION SUPERVISOR` (SUPERVISOR_PLANNING role+model, current RUN only).
  Approved → git commit (+push only if allowed) → next READY RUN, no manual
  role activation.

Determinism: chain order lives in the workflow JS script (code), not in
prompts. Each `agent()` call names provider/model explicitly; DSH validates
routes before a child runs; model identity is verifiable per request in the
child session logs (`~/.dsh/sessions/.../session.v3.jsonl.zstd`, fields
`provider`/`model`).

## 2. Shared persistence — file-based RUN backlog (no new database)

Rationale: mcp-light tools are read-only (documented requirement); the DPMtF
DB is the old runtime's state and DPMtF runtime is out of the new path;
scope-mcp must not become an orchestration engine and its DB resolution is
split (shared `dsh web` server db vs per-workspace hook dbs; §7). The DPMtF run-directory convention
(`runs/{NNN}/GOAL.md`, `{ID}-handoff.md`, `{ID}-result.md`,
`{ID}-verdict.md`) already matches what the loop needs, and both sessions
share the filesystem + git. Therefore: **one directory per project, files
only, git-tracked.**

Layout inside the target project root:

```
SCOPE.md                      # owned by Planning Supervisor (Human-approved intent)
dsh-loop/
  loop-config.json            # per-repo runtime config (see §5) — the RECORDED MANDATE
  runs/
    R004-add-subtract/
      RUN.md                  # run contract + status + result (see §3)
      01-handoff.md           # written by EXECUTION_DECOMPOSER
      01-result.md            # written by IMPLEMENTOR
      01-verdict.md           # written by REVIEW
      END-REPORT.md           # written by EXECUTION SUPERVISOR at closure
```

Concurrency/protection: Planning edits only runs whose status is DRAFT or
READY. A RUN goes READY→IN_PROGRESS only by the Execution Supervisor, which
writes `locked_by` + bumps `version`; Planning must not edit an IN_PROGRESS
run (it may append to an `## Amendment requests` section for the supervisor
to consider — never silent edits). The workflow re-reads RUN.md at start and
stops on lock/status mismatch. Explicit limitation instead of a lock system:
ONE execution session per project at a time (the markdown `locked_by` is a
claim marker, not atomic; a stale IN_PROGRESS claim from a crashed driver
is re-claimed by the next driver per the execloop skill).

## 3. RUN.md contract (front-matter fields)

```
run_id: R004            title/description
scope_ref: SCOPE.md#…   acceptance: testgoal commands + criteria (runnable)
priority: N             depends_on: [R00x, …]
status: DRAFT|READY|IN_PROGRESS|BLOCKED|COMPLETED|CANCELLED
version: N              locked_by: (execution session, when IN_PROGRESS)
handoffs: [ids]         result: SUCCESS|PARTIAL|FAILED|<pending>
commit: <sha>           push: ok|failed|denied|n-a
```

Terminal rule: **COMPLETED only when** all handoffs APPROVED (measured
verdicts, supervisor re-measures the tree per SP §5d), run acceptance
criteria measured green, END-REPORT written, and commit recorded (push
recorded honestly as ok/failed/denied — a failed push is never ok).
Cap-hit or repeated failure → status BLOCKED with reason, never COMPLETED.

## 4. Session launchers (skills, project-local, under `<projectRoot>/.dsh/skills/`)

- `.dsh/skills/dsh-planloop/SKILL.md` → Session 1 role: read
  `SUPERVISOR_PLANNING.md` + SCOPE.md + backlog; maintain scope; create/
  revise RUNs (DRAFT→READY); never execute; never edit IN_PROGRESS runs.
- `.dsh/skills/dsh-execloop/SKILL.md` → Session 2 driver: pick lowest
  READY run with satisfied dependencies → lock IN_PROGRESS → invoke the
  workflow tool with `dsh-loop/execution-loop.workflow.js` VERBATIM +
  run context → on return, verify/repair status honestly → next READY run.
- Role contracts (`docs/governance-templates-v2/*.md`) are referenced by
  absolute path in each agent prompt and read by the child itself — reused
  1:1, no rewrites. A **runtime overlay** block in the prompt re-anchors
  BridgeV002-specific mechanics (documented in the conflict lists; no
  hidden governance change): deliverable paths = run dir, completion =
  return (no signals), id allocation = next number in run dir, cap values =
  loop-config, commit/push authority = Execution Supervisor only,
  per task decision + 15_GIT_POLICY.md supervisor-mandate exception.

## 5. loop-config.json (the recorded mandate; frontend-editable plain file)

```
{ "project": "...", "roles": {
    "planning_supervisor": {"provider":"strata-local","model":"qwen3.8-flash-next-gptq-nvfp4"},
    "execution_decomposer":{"provider":"llamacpp-p620-1","model":"qwen35-122b-a10b-q5"},
    "implementor":         {"provider":"strata-local","model":"qwen3.8-flash-next-gptq-nvfp4"},
    "review":              {"provider":"llamacpp-p620-2","model":"glm45-air-iq4xs"},
    "execution_supervisor":{"provider":"strata-local","model":"qwen3.8-flash-next-gptq-nvfp4"} },
  "git": {"allow_push": false, "remote": "origin", "branch": "master"},
  "caps": {"max_rework_per_handoff": 2, "max_extra_handoffs": 3,
           "max_total_handoffs": 8, "max_supervisor_rounds": 4},
  "contracts_root": "/home/svend/DPMtF-WebUI/docs/governance-templates-v2" }
```

Default caps mirror the contracts (IMP stop-after-2; ED budget ≈4) but are
values, not prose. Cap exhaustion ⇒ BLOCKED (+reason), never COMPLETED.

## 6. Execution workflow (locked artifact, ~90 lines JS)

`dsh-loop/execution-loop.workflow.js` — script text fixed in advance and
passed verbatim; args carry {project, runId, runDir, config, contractsRoot}.
Structure (mirrors the mandated diagram):

1. ELOOP, one handoff at a time (mirrors DPMtF 2000-ELOOP: decomposer →
   implementer → reviewer → decomposer). Each decomposer wake writes ONE
   `NN-handoff.md` and returns `{action: HANDOFF|DONE|ESCALATE, file, last,
   reason}`. Every verdict wakes it again with the verdict's status and
   findings: APPROVED → next handoff or DONE; REJECTED → a rework handoff
   for the same work item (the reviewer's `routing` is passed along as a
   hint). Consecutive rejections beyond `max_rework_per_handoff` ⇒ STOPPED;
   distinct handoffs beyond `max_total_handoffs` ⇒ STOPPED; an approved
   handoff returned again ⇒ STOPPED.
   Time: `last: true` on a handoff means nothing remains once it is
   approved, so its APPROVED verdict goes straight to the supervisor (no
   empty DONE wake on the 122B decomposer). The overlay tells every child
   to batch commands into one bash call and to load no skill — measured
   2026-10-19: reviews averaged 20 steps and were 62% of chain time.
   Resume (re-drive after a stop, cancel or crash): the first wake of a
   drive reads the run dir and continues from its state — a newest handoff
   without a verdict is returned as is, approved ones are never redone.
2. implement → review per handoff: implementor agent (writes result, may
   change code inside fence, runs tests) → reviewer agent (schema
   `{status:"APPROVED"|"REJECTED", reasons[], routing}`; measures the tree
   itself; writes verdict.md).
3. supervisor round when the decomposer returns DONE (or the `last`
   handoff is approved): agent (SUPERVISOR_PLANNING variant, current RUN
   only, schema `{decision:"CLOSE"|"ADDITIONAL_HANDOFF"|"NEEDS_DECOMPOSITION"
   |"BLOCK", newHandoffs, reason, commit, push}`): ADDITIONAL_HANDOFF = the
   supervisor writes exactly one handoff itself (≤ max_extra_handoffs), it
   runs implement → review and its verdict wakes the decomposer as usual;
   NEEDS_DECOMPOSITION = the supervisor writes nothing, its reason becomes
   the decomposer's next wake input (≤ max_supervisor_rounds).
4. CLOSE (verified order): supervisor verifies tree+criteria → writes
   END-REPORT.md → commits `[run-RNNN] <objective>` staging in-fence files
   EXCLUDING this run's RUN.md, but INCLUDING the RUN.md of every earlier
   run that is COMPLETED/CANCELLED and still untracked or modified (never a
   DRAFT/READY/IN_PROGRESS/BLOCKED run's, never RUNS-BACKLOG.md) → verifies
   the sha → pushes iff `git.allow_push` → THEN writes final RUN.md fields
   (COMPLETED + exact sha + honest push); that last edit stays uncommitted
   by design (no bookkeeping commit) and is carried by the next run's CLOSE
   commit — only the latest closed run's RUN.md is ever uncommitted; the
   driver independently verifies commit existence, RUN.md fields and remote
   state before accepting CLOSE.
   No force-push, protected branch untouched.
5. Any unavailable route / child failure ⇒ explicit stop: workflow returns
   `{stopped:{role,error}}`; RUN stays IN_PROGRESS/BLOCKED; never COMPLETED.

## 7. Scope + isolation

- Persistent project scope: `SCOPE.md` in the project (git-tracked) — the
  durable intent both sessions read. scope-mcp stays the Planning session's
  checkpoint tool but is NOT the orchestration store.
- scope-mcp split (CONFIRMED): the `dsh web` process pins ONE shared
  scope-mcp stdio child at the install dir (all web sessions share the
  M196-project db; hooks use per-workspace dbs). Minimal fix, verified
  live: run each loop as its own DSH headless process launched from the
  project dir — scope-mcp then resolves `{project}/.scope-mcp/state.db`
  (matches the hooks), zero code/profile changes, M196 data untouched.
  A web-GUI session in `dsh web` still shares the install-dir db —
  documented limitation; removing the profile `cwd` pin needs a server
  restart (deferred to keep running sessions).
- Production protection: everything new lives under `docs/dsh-loops/`
  (Father) and `dsh-loops-test/` (isolated test project with an explicit
  local bare remote as the only push target). No commits to existing repos
  without explicit Human approval.

## 8. Reuse inventory (no new code where DSH already provides)

sessions/model-routing/subagents/workflow engine/schema output/goals/skills:
DSH native · contracts: DPMtF files 1:1 · context queries: mcp-light
(read-only) · checkpoints: scope-mcp · endpoints: existing 3 inference
servers. New artifacts only: two skills, one locked workflow script, one
loop-config schema, one RUN.md convention (+template copies in Father
docs/dsh-loops/).
