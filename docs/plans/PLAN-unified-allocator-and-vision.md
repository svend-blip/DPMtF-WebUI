# Unified Model Allocator and Future DPMtF Runtime — Implementation Plan

Status: Implementation plan
Language: en-US
Repositories: model-allocator and DPMtF-WebUI
Execution rule: Complete tasks in order within each phase. Do not proceed through a phase gate while unresolved errors remain. Human commits both repositories.

---

## 1. Goal

Make Model Allocator the single source of truth for:

* logical model aliases
* concrete model resolution
* model backend configuration
* model startup and readiness
* model shutdown and unloading
* model context limits
* local and remote model availability

Then establish the foundations for the future DPMtF architecture:

* durable Job Queue
* secure Execution Runtime
* structured Checkpoints
* context-aware handoffs
* automatic step progression

The user-facing DPMtF UI must remain simple.

Operational complexity such as model loading, resource selection, leases, retries, context limits, worktrees, and recovery must be handled behind the scenes.

---

## 2. Architectural Boundaries

The migration must preserve a clear separation of responsibilities.

### DPMtF owns work

DPMtF owns:

* projects
* flows
* roles
* steps
* handoffs
* job state
* scheduling
* approvals
* retries
* checkpoints
* reviews
* audit history

### Model Allocator owns model capacity

Model Allocator owns:

* aliases
* model resolution
* backend selection
* runtime profiles
* model lifecycle
* context capacity
* machine availability
* model health
* load and unload behavior

### Execution Runtime owns machine safety

Execution Runtime will eventually own:

* approved filesystem operations
* command allowlists
* path validation
* isolated worktrees
* verification
* action logging
* result collection

### Models provide reasoning

Models may propose actions.

Only the runtime may authorize and execute them.

---

## 3. Important Non-Goals

This plan does not:

* move Job Queue ownership into Model Allocator
* make Model Allocator responsible for DPMtF flow transitions
* make tmux the permanent workflow state store
* build the complete production Job Queue
* build the complete secure Python Runtime
* implement automatic context splitting
* remove all rollback paths immediately after migration
* require remote llama.cpp support before existing roles can migrate

---

## 4. Current State

### DPMtF-WebUI

Repository: DPMtF-WebUI

Current responsibilities include:

* FastAPI UI and APIs
* SQLite governance data
* BridgeV002 dispatch
* role and flow configuration
* prompt and handoff handling
* tmux-based execution

Current model selection has two paths:

1. Model Allocator path
2. Direct machine-profile and command_builder.py path

### Model Allocator

Repository: model-allocator

Current responsibilities include:

* alias resolution
* model and backend configuration
* lifecycle commands
* client command generation
* validation
* configuration writing

The allocator already supports part of the DPMtF role set but does not yet provide verified feature equivalence for all currently active execution paths.

---

## 5. Migration Strategy

The migration is divided into five phases:

* Phase 0 — Establish verified inventory and safety baseline
* Phase 1 — Close allocator gaps required by active roles
* Phase 2 — Migrate roles incrementally
* Phase 3 — Stabilize and retire the direct model path
* Phase 4 — Spike the future DPMtF runtime architecture

Model selection migration and future runtime development must remain separate decision gates.

A successful allocator migration must not automatically authorize replacement of OpenCode, Claude Code, tmux, or the existing dispatch mechanism.

---

## Phase 0 — Inventory and Safety Baseline

### Objective

Create an authoritative inventory of active roles, effective model settings, clients, backends, and lifecycle requirements before changing configuration.

Do not create aliases from assumptions or documentation tables alone.

### Task 0.1 — Capture the current test baseline

Repositories: both

* Run the complete test suite in model-allocator.
* Record passed, failed, and skipped tests.
* Run the complete test suite in DPMtF-WebUI.
* Record passed, failed, and skipped tests.
* Document all known pre-existing failures.
* Confirm that future gates require no new failures relative to this baseline.

A fixed minimum test count must not be used as the primary gate because the number of tests will change during implementation.

- [ ] Run `cd /home/svend/model-allocator && python3 -m pytest -q` — record results
- [ ] Run `python3 -m pytest -q` — record results
- [ ] Document pre-existing failures in `docs/superpowers/plans/2026-07-23-test-baseline.md`
- [ ] Confirm: future gates compare against this baseline, not against a fixed number

### Task 0.2 — Generate an authoritative role inventory

Repository: DPMtF-WebUI

Create a read-only inventory script that reports every active role with:

* role_key
* role_type
* effective client
* effective model source
* effective model alias
* direct runtime
* direct provider
* direct model
* maximum output tokens
* relevant extra arguments
* step-level model overrides
* lifecycle behavior
* execution runtime, if known

The report must identify:

* human roles
* local Ollama roles
* OpenRouter or other cloud roles
* Freebuff roles
* OpenCode roles
* Claude Code roles
* roles with conflicting or incomplete settings
* roles sharing the same concrete model
* roles using the same model through different clients

Store the generated report as a migration artifact.

- [ ] Create `scripts/inventory_roles.py` — read-only script querying `bridge_roles` + `bridge_flow_steps`
- [ ] Run the script, store output as `docs/superpowers/plans/2026-07-23-role-inventory.md`
- [ ] Review the inventory: identify contradictions, shared models, client differences
- [ ] `git add scripts/inventory_roles.py docs/superpowers/plans/2026-07-23-role-inventory.md`, STOP

### Task 0.3 — Resolve configuration contradictions

Before creating aliases, explicitly resolve:

**sim01_trade**

The supplied plan maps sim01_trade to both:
* archi-local
* sim-local

Only one role-level default may be selected.

Any step-level override must be documented separately.

**Cloud naming**

Role names containing "cloud" must not be assumed to use cloud infrastructure.

The inventory must determine the actual backend.

**Freebuff**

Determine whether Freebuff is:
* a model backend supported by Model Allocator
* an execution client using another model backend
* a separate execution runtime outside Model Allocator

Do not represent Freebuff as `openai_compatible` unless its actual protocol and lifecycle behavior have been verified.

**Client-specific aliases**

Two roles may reuse an alias only when the following are compatible:
* concrete model
* backend
* context limit
* lifecycle policy
* client configuration
* extra arguments
* output token policy

- [ ] Resolve sim01_trade: determine actual model from DB (`ollama_model` column), select ONE alias
- [ ] Verify each "cloud" role's actual backend via `inventory_roles.py` output
- [ ] Investigate Freebuff: read `command_builder.py` Freebuff builder, verify protocol, document decision
- [ ] Document all contradiction resolutions in `docs/superpowers/plans/2026-07-23-contradiction-resolutions.md`
- [ ] `git add`, STOP

### Task 0.4 — Add migration preflight

Create a command or script that validates:
* every active non-human role has a known client
* every direct model has a proposed alias
* every proposed alias resolves
* every alias supports the required client
* no role has conflicting role- and step-level configuration
* no human role is assigned a model
* no required environment variable is silently absent
* no duplicate migration assignment overwrites a role unintentionally

- [ ] Create `scripts/migration_preflight.py` — validates the proposed alias mapping
- [ ] Create test: `tests/test_migration_preflight.py` — TDD for preflight checks
- [ ] Run preflight against the proposed mapping, fix all failures
- [ ] `git add`, STOP

### Phase 0 gate

Proceed only when:
* the baseline is documented
* the active role inventory is complete
* contradictions are resolved
* the proposed alias mapping is one-to-one and reviewable
* human roles are excluded
* Freebuff treatment is explicitly decided

---

## Phase 1 — Close Required Model Allocator Gaps

### Objective

Implement only the allocator capabilities required for migration of currently active roles.

Optional backend expansion must not block the critical path.

### Task 1.1 — Structured validation output

Execute the existing `PLAN-validate-json-output.md`.

Required outcomes:
* `validate --json`
* stable additive JSON output
* Father endpoint uses JSON when available
* text fallback remains available during migration
* existing CLI consumers remain compatible

Required verification:
```
validate alias
→ valid JSON
→ explicit validation status
→ non-zero exit behavior remains documented
```

- [ ] Execute `PLAN-validate-json-output.md` Task 1 — `--json` flag on `validate`
- [ ] Execute Plan Task 2 — Father `/allocator/validate` endpoint migration
- [ ] Verify: `./scripts/model-allocator validate --alias imple01-local --client opencode --json | python3 -m json.tool`
- [ ] Verify: Father endpoint returns structured JSON
- [ ] `git add` in both repos, STOP

### Task 1.2 — Configuration schema and doctor

Execute the existing `PLAN-config-schema-doctor.md`.

Required outcomes:
* backend-specific field validation
* role configuration validation
* human-readable output
* JSON output
* atomic write validation
* live configuration has zero errors

Warnings may remain only when reviewed and explicitly accepted.

Configuration writes must be blocked when they introduce schema errors.

- [ ] Execute `PLAN-config-schema-doctor.md` Task 1 — create `schema.py`
- [ ] Execute Plan Task 2 — `doctor` CLI command
- [ ] Execute Plan Task 3 — run doctor against live config, fix all flagged errors
- [ ] Execute Plan Task 4 — wire write-blocking into `config_writer`
- [ ] Verify: `./scripts/model-allocator doctor` reports zero errors
- [ ] Verify: `./scripts/model-allocator doctor --json` returns `{"errors": []}`
- [ ] `git add`, STOP

### Task 1.3 — Claude Code environment equivalence

Execute the required parts of `PLAN-claude-env-equivalence.md`.

Verify support for:
* absolute Claude binary resolution
* maximum output token passthrough
* adaptive-thinking configuration where applicable
* client-specific extra arguments
* `--bare` or equivalent hygiene
* allocator-active model metadata
* compatible environment generation

The goal is behavioral equivalence with the active direct path — not blind copying of old implementation details.

- [ ] Execute `PLAN-claude-env-equivalence.md` Tasks 2-5
- [ ] Execute Plan Task 6 — Father passes per-role `max_output_tokens` via `--max-output-tokens`
- [ ] Verify: `./scripts/model-allocator run --role imple01 --client claude-code` output matches command_builder output for same model
- [ ] Verify: `--bare` appears in argv when configured
- [ ] Verify: `CLAUDE_CODE_MAX_OUTPUT_TOKENS` is set correctly
- [ ] `git add` in both repos, STOP

### Task 1.4 — OpenCode model and session hygiene

Execute `PLAN-opencode-session-hygiene.md`.

Required outcomes:
* do not depend on a silently ignored `--model` flag
* write the resolved model to the correct OpenCode configuration
* detect resumed sessions pinned to another model
* provide safe stale-session handling
* verify the actual model used by the live session

A successful command launch is not sufficient evidence.

The active model must be verified.

- [ ] Execute `PLAN-opencode-session-hygiene.md` Tasks 1-4
- [ ] Manual live check: start an OpenCode role via allocator, verify `opencode.json` `model` field
- [ ] Manual live check: verify session uses correct model via `ollama ps` or `/api/ps`
- [ ] `git add`, STOP

### Task 1.5 — Required backend support

Implement or verify only the backends needed by active roles.

This includes:
* local Ollama
* OpenRouter or verified OpenAI-compatible providers
* any confirmed Freebuff integration path

Remote llama.cpp lifecycle is a separate optional workstream unless an active role requires it.

It must not block the migration of existing Ollama and cloud roles.

- [ ] Verify Ollama adapter: start/stop/status/invoke against live Ollama
- [ ] Verify OpenRouter adapter: validate/reachability against live OpenRouter
- [ ] Resolve Freebuff: implement adapter or document exclusion based on Task 0.3 decision
- [ ] If Freebuff needs an adapter: create `adapters/freebuff.py` with verified protocol support
- [ ] If Freebuff is an execution runtime (not a model backend): document and exclude from allocator
- [ ] `git add`, STOP

### Task 1.6 — Model lifecycle verification

For every required backend, verify:
* start or acquire behavior
* readiness check
* keep-warm behavior
* stop or release behavior
* already-stopped behavior
* timeout behavior
* failure reporting
* effective context limit

For Ollama, model release must be verified rather than assumed.

The acceptance test is:
```
start alias
→ verify model loaded
→ stop alias
→ verify model unloaded
```

- [ ] Write `tests/test_lifecycle_verification.py` — per-backend lifecycle test
- [ ] For each required backend: start → verify loaded (via `ollama ps` or adapter status) → stop → verify unloaded
- [ ] Verify timeout behavior: `model-allocator stop --alias <alias> --timeout 1` against a loaded model
- [ ] Verify already-stopped behavior: `model-allocator stop --alias <alias>` when model not loaded
- [ ] `git add`, STOP

### Phase 1 gate

Proceed only when:
* allocator doctor reports zero errors
* all required aliases can validate
* client command generation matches required behavior
* active local and cloud backend paths are verified
* Ollama model unload is verified
* no new test failures exist relative to baseline

---

## Phase 2 — Incremental Role Migration

### Objective

Move roles to Model Allocator in controlled cohorts rather than changing all roles in one database update.

Each cohort must pass tests and a live execution check before the next cohort is migrated.

### Task 2.1 — Create aliases from the approved inventory

Repository: model-allocator

Create aliases using validated configuration-writing commands.

Each alias must declare:
* concrete model
* runtime profile
* supported clients
* context limit
* lifecycle policy
* required environment variables
* output token defaults where appropriate
* client-specific extra arguments

Avoid embedding role-specific values in shared aliases unless the values are genuinely shared.

Per-role database values such as `max_output_tokens` should be passed as execution overrides when supported.

- [ ] Create each alias via `./scripts/model-allocator config set-alias --name <alias> --json '<definition>'`
- [ ] Run `./scripts/model-allocator doctor` — verify zero errors
- [ ] Run `./scripts/model-allocator validate --alias <alias> --client <client> --json` for each
- [ ] Add role mappings in `roles.yaml` for all migrated roles
- [ ] Run `./scripts/model-allocator resolve --role <role> --client <client>` for each
- [ ] `git add models.yaml roles.yaml`, STOP

### Task 2.2 — Add role mappings

Add role mappings only after all referenced aliases exist and validate.

For every role, verify:
```
role
→ client
→ alias
→ backend
→ concrete model
→ effective context
```

Step-level overrides must continue to take precedence over role-level defaults.

- [ ] Verify each role mapping resolves correctly
- [ ] Verify step-level overrides still work via `get_effective_model_source()`
- [ ] `git add`, STOP

### Task 2.3 — Create a reversible database migration

Repository: DPMtF-WebUI

The migration must:
* change only explicitly listed roles
* exclude human roles
* set `default_model_source = 'model_allocator'`
* set a non-empty valid alias
* preserve old direct columns during migration
* include a down migration or equivalent rollback script
* fail if a target role is missing
* fail if the number of changed rows differs from the expected migration manifest

Do not use repeated updates that assign the same role to different aliases.

The migration manifest should be generated from the approved role inventory.

The migration files and tests are authoritative.

Committing a modified live SQLite database should follow the repository's existing database policy; it should not replace reproducible migration scripts.

- [ ] Create `scripts/db/005_unified_allocator_migration.sql` — generated from approved inventory
- [ ] Create `scripts/db/005_unified_allocator_migration_rollback.sql` — down migration
- [ ] Write test: `tests/test_migration_005.py` — verify migration + rollback
- [ ] Write test: `tests/test_migration_005_rowcount.py` — verify changed row count matches manifest
- [ ] Write test: `tests/test_migration_005_no_human.py` — verify no human role is migrated
- [ ] Run migration, run tests, verify all pass
- [ ] `git add`, STOP

### Task 2.4 — Migrate a pilot cohort

Recommended pilot:
* one local Claude Code role
* one local OpenCode role
* one cloud role
* no human role
* no Freebuff role unless its adapter is already verified

For each pilot role:
1. resolve alias
2. validate alias
3. start the role
4. verify the actual model
5. execute a minimal bounded task
6. complete the step
7. stop the model
8. verify model unload
9. confirm existing dispatch behavior

Only after the pilot is successful should additional roles migrate.

- [ ] Select pilot cohort (e.g. `archi01` Claude+Ollama, `review01` OpenCode+Ollama, `archi01pay` Claude+OpenRouter)
- [ ] For each pilot role: resolve → validate → start → verify model via `ollama ps` → bounded task → complete → stop → verify unload
- [ ] Record results in `docs/superpowers/plans/2026-07-23-pilot-cohort-results.md`
- [ ] If any pilot fails: fix the alias/config, re-test, do not proceed
- [ ] `git add`, STOP

### Task 2.5 — Migrate remaining role cohorts

Suggested order:
1. core `strict_review` roles
2. remaining general development roles
3. trade analysis roles
4. trade review and simulation roles
5. exceptional runtimes such as Freebuff

After each cohort:
* run both test suites
* run compile checks
* run allocator doctor
* resolve every migrated role
* perform at least one live bounded execution
* verify correct stop behavior

- [ ] Migrate cohort 1 (strict_review: archi01, imple01, review01, review02)
- [ ] Test + verify: `python3 -m pytest -q` both repos, `doctor`, `resolve` each role
- [ ] Migrate cohort 2 (remaining dev: archi01cloud, review01cloud, review02cloud)
- [ ] Test + verify
- [ ] Migrate cohort 3 (trade analysis: trend01_trade, market01_trade, analyst01_trade, risk01_trade)
- [ ] Test + verify
- [ ] Migrate cohort 4 (trade review/sim: review01_trade, sim01_trade, portfolio01_trade, score01_trade, learn01_trade)
- [ ] Test + verify
- [ ] Migrate cohort 5 (exceptional: imple01cloud Freebuff, imple01pay OpenRouter, archi01pay, review01pay, review02pay)
- [ ] Test + verify
- [ ] `git add` after each cohort, STOP

### Task 2.6 — Simplify start_coding.py

After all non-human roles have migrated:
* make Model Allocator the required model source
* retain an explicit migration fallback only if rollback policy requires it
* unknown sources must produce a clear error
* human roles remain excluded
* per-role execution values are passed as allocator overrides
* client selection remains explicit

Do not remove the old implementation in the same task that activates the new path.

- [ ] Write test: `tests/test_start_coding_allocator_only.py` — verify all roles use allocator
- [ ] Modify `start_coding.py`: allocator path is the only active path; direct path is disabled (not yet removed)
- [ ] Run test, compile, full suite
- [ ] `git add`, STOP

### Task 2.7 — Route setup and teardown through Model Allocator

Update:
* role setup (`role_setup.py`)
* role teardown (`role_teardown.py`)
* dispatch warmup (`warm_ollama_model` → `_run_allocator_start`)
* dispatch unload (`unload_ollama_model` → `_run_allocator_stop`)

These components must no longer call raw:
```
ollama pull
ollama stop
Ollama generate warmup
```

They must call Model Allocator using the effective alias.

Longer term, start and stop should evolve toward acquire and release semantics so one job cannot unload a model still used by another job.

- [ ] Write test: `tests/test_role_setup_allocator.py` — verify `role_setup.py` calls `model-allocator start`
- [ ] Write test: `tests/test_role_teardown_allocator.py` — verify `role_teardown.py` calls `model-allocator stop`
- [ ] Rewrite `role_setup.py` — call `model-allocator start --alias <alias>`
- [ ] Rewrite `role_teardown.py` — call `model-allocator stop --alias <alias>`
- [ ] Add `_run_allocator_start` to `dispatch.py` (parallel to `_run_allocator_stop`)
- [ ] Replace `warm_ollama_model()` calls with `_run_allocator_start(alias)`
- [ ] Replace `unload_ollama_model()` calls with `_run_allocator_stop(alias)`
- [ ] Run tests, compile, full suite
- [ ] `git add`, STOP

### Task 2.8 — Sequential live flow validation

The live validation must reflect the intended local-resource policy.

Do not preload all large local role models simultaneously.

Validate the flow step by step:
```
resolve role
→ start model
→ verify model
→ execute bounded step
→ persist result
→ stop model
→ verify unload
→ continue to next role
```

Test at least:
* `strict_review`
* one trade flow

For every role, record:
* resolved alias
* backend
* concrete model
* active model verification
* completion result
* unload result

- [ ] Stop all sessions: `python3 scripts/bridgeV002/stop_tmuxflow.py strict_review`
- [ ] Start fresh: `python3 scripts/bridgeV002/start_tmuxflow.py strict_review`
- [ ] Start coding: `python3 scripts/bridgeV002/start_coding.py strict_review`
- [ ] For each role in the flow: resolve → verify model via `ollama ps` → record results
- [ ] Dispatch a handoff: `python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-send ...`
- [ ] Verify post-dispatch model unload via `ollama ps` and `trace.log`
- [ ] Repeat for `trade_cockpit_simulation_v001`
- [ ] Record all results in `docs/superpowers/plans/2026-07-23-flow-validation-results.md`
- [ ] `git add`, STOP

### Phase 2 gate

Proceed only when:
* every active non-human role has a valid allocator alias
* every migrated role has been resolved and validated
* sequential live flow execution succeeds
* model unload succeeds between exclusive local steps
* human roles remain untouched
* step-level overrides still work
* rollback remains available
* no new test failures exist relative to baseline

---

## Phase 3 — Stabilization and Direct-Path Retirement

### Objective

Observe the unified path before deleting the rollback implementation.

### Task 3.1 — Introduce a stabilization window

During stabilization:
* Model Allocator remains the default
* direct model selection is disabled by configuration
* old columns remain available for rollback
* direct code remains isolated and marked deprecated
* all allocator failures are logged
* role resolution drift is monitored

Complete multiple representative flow runs before removing code.

Recommended validation coverage:
* strict review flow
* trade flow
* local Claude Code role
* local OpenCode role
* cloud role
* exceptional runtime role

- [ ] Run `strict_review` flow 3 times, record results
- [ ] Run `trade_cockpit_simulation_v001` flow 3 times (or via cronjob), record results
- [ ] Monitor: `ollama ps` before/after each flow — verify models load/unload correctly
- [ ] Monitor: `trace.log` — verify all dispatch events use allocator stop, not raw ollama stop
- [ ] Monitor: `model-allocator doctor` daily — verify zero errors
- [ ] Document stabilization results in `docs/superpowers/plans/2026-07-23-stabilization-results.md`
- [ ] `git add`, STOP

### Task 3.2 — Remove direct model selection

After stabilization succeeds:
* remove direct-path imports from active orchestration
* archive or delete `command_builder.py` model-selection logic
* remove raw Ollama unload fallback
* remove direct OpenCode model-field updates
* remove dead machine-profile model resolution from active code
* retain only unrelated command-building utilities still in use

Search-based tests may support this cleanup but should not replace behavioral tests.

- [ ] Write test: `tests/test_no_direct_path.py` — verify no active code imports `command_builder` or calls `unload_ollama_model`
- [ ] Remove direct-path imports from `start_coding.py`
- [ ] Archive `command_builder.py` to `scripts/bridgeV002/_deprecated/`
- [ ] Remove `unload_ollama_model` from `dispatch.py`
- [ ] Remove `ensure_opencode_model_field` direct-role usage from `start_coding.py`
- [ ] Run `grep -rn "build_start_command\|unload_ollama_model\|ensure_opencode_model_field" scripts/bridgeV002/*.py` — verify empty
- [ ] Run full suite, compile checks
- [ ] `git add`, STOP

### Task 3.3 — Deprecate old database columns

Initially:
* retain old columns
* mark them deprecated
* stop reading them in active execution
* document rollback handling

Dropping columns should be a later migration after the rollback window has ended.

SQLite schema limitations and table-rebuild requirements must be handled explicitly if physical removal is later approved.

- [ ] Create `scripts/db/006_deprecate_direct_columns.sql` — documentation migration
- [ ] Write test: `tests/test_migration_006.py` — verify migration applies cleanly
- [ ] Update `CLAUDE.md` and governance docs: note that `default_runtime`/`default_provider`/`default_model` are deprecated
- [ ] `git add`, STOP

### Phase 3 gate

The direct path may be considered retired when:
* all production role resolution uses Model Allocator
* no active code reads direct model columns
* no active code calls raw model lifecycle commands
* representative flows have completed during stabilization
* rollback evidence has been recorded
* full test suites remain at or above baseline quality

---

## Phase 4 — Future DPMtF Architecture Spikes

These spikes are decision gates.

They must not be treated as production implementations.

### Task 4.1 — Secure Python Runtime spike

**Question:** Can a bounded Python runtime reliably perform implementation actions without unrestricted shell or file access?

**Required characteristics:**

The spike must:
* resolve its model through Model Allocator
* operate inside a temporary isolated project
* use a small allowlisted action schema
* validate all paths
* reject traversal and symlink escape
* avoid unrestricted `shell=True`
* record actions and results
* run verification after edits
* produce a structured checkpoint
* impose a maximum action and retry budget

**Minimum initial actions:**

```
READ_FILE
REQUEST_CONTEXT
APPLY_PATCH
RUN_REGISTERED_CHECK
FINISH
```

Prefer patch operations over unrestricted full-file replacement for existing files.

**Decision gate:**

Proceed only if:
* edit application is reliable
* unsafe paths are consistently rejected
* results are reproducible
* failures are observable
* model output can be validated without depending on prompt obedience

If the spike fails, retain OpenCode or Claude Code as the execution adapter while continuing other architecture work.

- [ ] Create `scripts/python-runtime/runtime_spike.py` — minimal bounded loop
- [ ] Resolve model via allocator: `model-allocator resolve --role imple01 --client opencode` → get real_model, context, api_base
- [ ] Implement action schema: `READ_FILE`, `REQUEST_CONTEXT`, `APPLY_PATCH`, `RUN_REGISTERED_CHECK`, `FINISH`
- [ ] Implement `safe_resolve()` — path validation with symlink rejection
- [ ] Write tests: `tests/test_runtime_safe_resolve.py` — all path escape attempts rejected
- [ ] Write tests: `tests/test_runtime_action_schema.py` — only allowlisted actions accepted
- [ ] Write tests: `tests/test_runtime_verification.py` — post-edit verification runs automatically
- [ ] Write measurement harness: `scripts/python-runtime/spike_measure.sh` — 10 runs, record reliability
- [ ] Write verdict: `scripts/python-runtime/SPIKE-VERDICT.md` — GO/NO-GO with score + failure analysis
- [ ] `git add`, STOP

### Task 4.2 — Durable Job Queue spike

**Question:** What is the correct durable job abstraction for DPMtF?

The spike must compare:
1. extending `workflow_runs`
2. introducing a separate `jobs` table linked to `workflow_runs`

A workflow run and an execution job should be treated as different concepts unless the spike proves otherwise.

**Required job behavior:**

The spike must test:
* explicit allowed state transitions
* atomic claim of the oldest eligible job
* single-worker ownership
* leases
* heartbeat
* expired-lease recovery
* retry count
* idempotency key
* dependencies
* human approval gate
* blocked state
* cancellation
* event history
* allocator alias association

**Suggested lifecycle:**

```
DRAFT
→ AWAITING_APPROVAL
→ APPROVED
→ QUEUED
→ WAITING_FOR_RESOURCES
→ RUNNING
→ VERIFYING
→ REVIEW_REQUIRED
→ COMPLETED
```

**Alternative terminal or corrective states:**

```
CHANGES_REQUESTED
BLOCKED
FAILED
CANCELLED
HUMAN_ACTION_REQUIRED
```

Direct SQL updates that allow arbitrary transitions are not sufficient.

A transition service or database-enforced validation must reject illegal transitions.

**Atomic claim requirement:**

The scheduler spike must prove that two workers cannot successfully claim the same job.

- [ ] Write spike: `scripts/job_queue_spike.py` — job lifecycle + state machine + atomic claim
- [ ] Write tests: `tests/test_job_queue_spike.py` — lifecycle transitions, illegal transition rejection
- [ ] Write tests: `tests/test_job_queue_atomic_claim.py` — two workers, same job, only one wins
- [ ] Write tests: `tests/test_job_queue_lease_recovery.py` — expired lease → job re-queued
- [ ] Compare approaches: `workflow_runs` extension vs separate `jobs` table
- [ ] Write verdict: `docs/superpowers/specs/2026-07-23-job-queue-spike-verdict.md`
- [ ] `git add`, STOP

### Task 4.3 — Checkpoint spike

**Question:** Can every completed step produce a durable, model-independent continuation record?

Define a versioned checkpoint schema containing:
* checkpoint schema version
* job ID
* handoff ID
* workflow run ID
* flow key
* step key
* role key
* approved scope version
* scope hash
* base commit
* result commit
* changed files
* verification results
* test results
* implementation summary
* unresolved items
* artifacts
* model alias
* resolved backend
* resolved concrete model
* execution adapter
* timestamps

The schema must be validated, not merely represented as an unvalidated Python dictionary.

The spike must prove that the next role can start from:
* the approved contract
* the checkpoint
* the relevant diff
* required artifacts

It must not require the previous model conversation or tmux scrollback.

- [ ] Define checkpoint schema: `scripts/python-runtime/checkpoint_schema.py` — dataclass + validation
- [ ] Write tests: `tests/test_checkpoint_schema.py` — schema validation, missing fields rejected
- [ ] Write tests: `tests/test_checkpoint_continuation.py` — next role starts from checkpoint, no conversation needed
- [ ] Write verdict: `docs/superpowers/specs/2026-07-23-checkpoint-spike-verdict.md`
- [ ] `git add`, STOP

### Task 4.4 — Handoff fit and context-budget spike

**Question:** Can DPMtF determine whether a handoff is safely executable by the selected local model before queueing it?

Model Allocator supplies:
* effective context window
* recommended input limit
* output reserve
* backend capability
* model availability

DPMtF evaluates:
* estimated initial context
* expected peak context
* governance overhead
* required file context
* expected tool output
* output reserve
* recovery reserve
* likely changed-file count
* architectural spread
* verification scope

**Suggested fit states:**

```
FITS
FITS_WITH_LOW_MARGIN
CONTEXT_REDUCTION_REQUIRED
SPLIT_REQUIRED
LARGER_MODEL_REQUIRED
HUMAN_REDESIGN_REQUIRED
```

Only approved fit states may enter the executable queue.

The spike should test continuation creation when a handoff exceeds its safe runtime budget.

- [ ] Write spike: `scripts/context_fit_spike.py` — context budget estimator
- [ ] Write tests: `tests/test_context_fit_spike.py` — various handoff sizes vs various model context limits
- [ ] Test continuation creation: when handoff exceeds budget, split into continuation jobs
- [ ] Write verdict: `docs/superpowers/specs/2026-07-23-context-fit-spike-verdict.md`
- [ ] `git add`, STOP

---

## 6. Future Runtime Flow

If the spikes are successful, the intended architecture becomes:

```
Human approves objective
        ↓
DPMtF creates workflow run
        ↓
Handoff Compiler creates bounded jobs
        ↓
Context-fit preflight
        ↓
Job Queue
        ↓
Scheduler selects next eligible job
        ↓
Model Allocator resolves and acquires model capacity
        ↓
Execution adapter runs bounded step
        ↓
Runtime verifies result
        ↓
Checkpoint is persisted
        ↓
Model lease is released
        ↓
Local model is unloaded when no lease remains
        ↓
Fresh-context review job
        ↓
Human final gate when required
```

---

## 7. Local Model Scheduling Policy

The first production Job Queue should assume one large local GPU model step at a time per GPU.

This is a resource rule, not a global workflow rule.

```yaml
resource_limits:
  local_large_model_gpu0:
    max_concurrent: 1
  cpu_verification:
    max_concurrent: 2
  cloud_model:
    max_concurrent: 2
```

Within one local step, the model may remain loaded across multiple calls.

At the step boundary:

1. stop accepting new actions
2. complete or cancel active requests
3. persist validated output
4. write checkpoint
5. release model lease
6. unload when no lease remains
7. verify resource release
8. start the next eligible local step

---

## 8. Minimal UI Requirements

The future UI must not expose internal orchestration complexity by default.

The primary UI should answer only:

**What is running?**
* project
* flow
* current step
* current role
* status

**What is waiting?**
* approved work
* queued work
* blocked work

**What requires human action?**
* scope approval
* blocked decision
* final approval
* retry exhaustion

**What completed?**
* result summary
* review result
* test status
* checkpoint history

The default UI should not require the user to manage:
* model aliases
* model loading
* Ollama stop
* context windows
* GPU leases
* worktrees
* retry counters
* session cleanup
* backend URLs

Advanced diagnostics may exist in a separate operational view.

---

## 9. Continuous Verification

### Per task

Run:
* repository-specific tests
* compile checks for touched Python files
* JavaScript syntax checks for touched JavaScript files
* allocator doctor when configuration changes
* targeted live validation when lifecycle behavior changes

Security checks should be scoped to relevant active files and should avoid false positives caused by documentation, fixtures, or archived code.

### Per migration cohort

Verify:
* every migrated role resolves
* alias supports the selected client
* correct concrete model is active
* output-token override is applied
* session hygiene is correct
* step completes
* model unload succeeds
* no other active job loses its model unexpectedly

### Per future-runtime spike

Each spike must produce:
* test evidence
* limitations
* observed failures
* security findings
* GO or NO-GO verdict
* recommended next plan

---

## 10. Acceptance Criteria

### Unified allocator foundation

* Every active non-human role has a valid effective Model Allocator alias.
* Every human role remains model-free.
* Every effective role and step override resolves through Model Allocator.
* Allocator doctor reports no errors.
* Required aliases validate for their actual clients.
* Local model start and verified unload work through Model Allocator.
* Cloud roles resolve to the correct verified provider.
* Freebuff has an explicit, verified architectural treatment.
* No active orchestration code calls raw Ollama lifecycle commands.
* Direct model-selection code is disabled before it is removed.
* Sequential live validation succeeds for strict review and trade flows.
* Both repositories have no new unexplained test failures relative to baseline.
* No new hardcoded machine-specific project paths are introduced.

### Future architecture spikes

* Python Runtime produces a documented GO or NO-GO verdict.
* Job Queue schema and concurrency behavior produce a documented GO or NO-GO verdict.
* Checkpoint schema and continuation behavior produce a documented GO or NO-GO verdict.
* Handoff context-fit handling produces a documented GO or NO-GO verdict.
* No spike is promoted to production without a separate approved implementation plan.

---

## 11. Recommended Follow-On Plans

Only after the relevant spikes succeed:

1. **Production Job Queue**
   * separate jobs and job events
   * atomic claims
   * leases and recovery
   * dependency scheduling
   * human gates

2. **Secure Execution Runtime**
   * action schemas
   * path policies
   * command registry
   * isolated worktrees
   * verification runner

3. **Structured Checkpoints**
   * versioned schema
   * durable storage
   * artifact references
   * fresh-context continuation

4. **Handoff Compiler**
   * scope decomposition
   * model-fit calculation
   * context manifests
   * continuation jobs

5. **Model Lease Integration**
   * allocator acquire and release
   * resource-aware scheduling
   * reference-counted unload
   * verified GPU release

6. **Minimal Operations UI**
   * current work
   * queue health
   * human actions
   * completed results
   * advanced diagnostics hidden by default

---

## 12. Core Architecture Rules

DPMtF owns work.
Model Allocator owns model capacity.
Execution Runtime owns safety.
Models provide reasoning.
Checkpoints preserve progress.
Model context is disposable.
Job state is durable.

The migration is successful when model management becomes simpler for DPMtF without moving workflow ownership out of DPMtF or exposing additional complexity to the user.
