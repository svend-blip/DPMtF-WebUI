# Production Job Queue — Implementation Plan

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps.

**Goal:** Build a production Job Queue on top of the verified spike (Task 4.2 GO). The Job Queue owns durable job lifecycle, atomic claims, leases, retry, and dependency scheduling. Model Allocator resolves models. Dispatch.py executes handoffs.

**Architecture:** A new `jobs` table + `job_events` table in SQLite. A scheduler function (called by cron-tick or standing service) picks up APPROVED jobs, runs context-fit preflight, resolves the model via allocator, compiles the prompt, dispatches via dispatch.py, monitors completion, writes checkpoint, and transitions job state. All transitions go through the transition service (illegal transitions rejected).

**Tech Stack:** Python 3.10+ stdlib, SQLite, pytest, existing bridge_lib + dispatch.py + prompt_compiler.

## Cold-Start Context

- DPMtF-WebUI at `/home/svend/DPMtF-WebUI` — FastAPI + SQLite on port 9130.
- Spike code at `scripts/python-runtime/job_queue_spike.py` — 12 tests green.
- Migration 005 applied — all non-human roles use `model_allocator`.
- `start_coding.py strict_review` verified live — allocator resolves all roles.
- `dispatch.py` has `_run_allocator_start` + `_run_allocator_stop` for warmup/unload.
- `prompt_compiler.py` has `compile` → `assign-handoff-id` → `dispatch` endpoints.
- Run tests: `python3 -m pytest -q` → 63 passed, 0 failures.

## Global Constraints

- `python3 -m py_compile` MUST pass on every touched Python file.
- All 63 existing tests stay green.
- TDD: failing test → implement → green.
- No new dependencies. SQLite + stdlib only.
- No hardcoded `/home/svend/...` paths.
- Parameterized SQL only — `?` placeholders.
- Git: Human commits. Tasks end with `git add <files>` and STOP.

---

### Task 1: Database migration — jobs + job_events tables

**Files:**
- Create: `scripts/db/007_job_queue_tables.sql`
- Test: `tests/test_migration_007.py`

**Schema:** Based on spike schema, productionized.

- [ ] Step 1: Write the migration SQL

```sql
-- Migration 007: Job Queue tables
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    workflow_run_id TEXT,
    flow_key TEXT NOT NULL,
    step_key TEXT,
    role_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    allocator_alias TEXT,
    handoff_id TEXT,
    idempotency_key TEXT UNIQUE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    lease_owner TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    priority INTEGER DEFAULT 0,
    goal TEXT NOT NULL,
    target_project TEXT NOT NULL,
    scope_version TEXT,
    checkpoint_path TEXT,
    context_fit_state TEXT,
    parent_job_id TEXT,
    continuation_index INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    actor TEXT,
    detail TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(lease_owner, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_jobs_flow ON jobs(flow_key, status);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id);
```

- [ ] Step 2: Write test
- [ ] Step 3: Run test — verify fail (tables don't exist yet)
- [ ] Step 4: Apply migration
- [ ] Step 5: Run test — verify pass
- [ ] Step 6: Full suite green
- [ ] Step 7: `git add`, STOP

### Task 2: Job model + transition service

**Files:**
- Create: `scripts/job_queue/models.py` — Job dataclass, state machine, transition service
- Test: `tests/test_job_models.py`

**Interfaces:**
- `class Job` — dataclass mirroring jobs table
- `STATES`, `LEGAL_TRANSITIONS`, `TERMINAL_STATES` — from spike
- `class JobRepository` — CRUD + transition + claim + heartbeat + lease recovery
- `class IllegalTransitionError(Exception)`

- [ ] Step 1: Write tests for transition service (legal/illegal, event recording)
- [ ] Step 2: Run tests — verify fail
- [ ] Step 3: Implement models.py (port from spike, productionize)
- [ ] Step 4: Run tests — verify pass
- [ ] Step 5: Compile + full suite
- [ ] Step 6: `git add`, STOP

### Task 3: Scheduler — claim + dispatch + monitor

**Files:**
- Create: `scripts/job_queue/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- `class Scheduler` — picks up APPROVED jobs, runs preflight, dispatches, monitors
- `Scheduler.tick()` — one pass: claim oldest APPROVED → preflight → compile → dispatch → monitor
- `Scheduler.dispatch_job(job)` — calls prompt_compiler internally, then dispatch.py
- `Scheduler.check_completion(job)` — checks deliverable file + validation

- [ ] Step 1: Write tests (claim, dispatch mock, completion check)
- [ ] Step 2: Run tests — verify fail
- [ ] Step 3: Implement scheduler.py
- [ ] Step 4: Run tests — verify pass
- [ ] Step 5: Compile + full suite
- [ ] Step 6: `git add`, STOP

### Task 4: API endpoints — create/approve/list/status

**Files:**
- Modify: `routers/bridge.py` — add job endpoints
- Test: `tests/test_job_endpoints.py`

**Endpoints:**
- `POST /api/jobs` — create a job (body: goal, flow_key, target_project, role_key)
- `PUT /api/jobs/{id}/approve` — approve a draft job
- `GET /api/jobs` — list jobs (filter by status)
- `GET /api/jobs/{id}` — job detail + events
- `POST /api/jobs/{id}/cancel` — cancel a job
- `POST /api/jobs/scheduler/tick` — run one scheduler pass

- [ ] Step 1: Write tests for each endpoint
- [ ] Step 2: Run tests — verify fail (404)
- [ ] Step 3: Implement endpoints in bridge.py
- [ ] Step 4: Run tests — verify pass
- [ ] Step 5: Compile + full suite
- [ ] Step 6: `git add`, STOP

### Task 5: Context-fit preflight integration

**Files:**
- Modify: `scripts/job_queue/scheduler.py` — add context-fit check before dispatch
- Test: `tests/test_scheduler_context_fit.py`

- [ ] Step 1: Write test — job with SPLIT_REQUIRED should not dispatch
- [ ] Step 2: Implement context-fit check in scheduler
- [ ] Step 3: Run tests — verify pass
- [ ] Step 4: Compile + full suite
- [ ] Step 5: `git add`, STOP

### Task 6: Checkpoint integration

**Files:**
- Modify: `scripts/job_queue/scheduler.py` — write checkpoint after completion
- Test: `tests/test_scheduler_checkpoint.py`

- [ ] Step 1: Write test — completed job has checkpoint
- [ ] Step 2: Implement checkpoint creation in scheduler
- [ ] Step 3: Run tests — verify pass
- [ ] Step 4: Compile + full suite
- [ ] Step 5: `git add`, STOP

### Task 7: Cron-tick entry point

**Files:**
- Create: `scripts/job_queue/cron_tick.py` — entry point for cronjob
- Test: `tests/test_cron_tick.py`

- [ ] Step 1: Write test — cron_tick runs one scheduler pass
- [ ] Step 2: Implement cron_tick.py
- [ ] Step 3: Run tests — verify pass
- [ ] Step 4: Compile + full suite
- [ ] Step 5: `git add`, STOP

### Task 8: Dependency scheduling

**Files:**
- Modify: `scripts/job_queue/models.py` — add dependency support
- Test: `tests/test_job_dependencies.py`

- [ ] Step 1: Write tests — job with dependency cannot be claimed until parent completes
- [ ] Step 2: Implement dependency check in claim logic
- [ ] Step 3: Run tests — verify pass
- [ ] Step 4: Compile + full suite
- [ ] Step 5: `git add`, STOP

### Task 9: Lease recovery + retry

**Files:**
- Modify: `scripts/job_queue/scheduler.py` — lease recovery in tick
- Test: `tests/test_lease_recovery.py`

- [ ] Step 1: Write tests — expired lease recovery, retry count increment, max retries
- [ ] Step 2: Implement lease recovery in scheduler.tick()
- [ ] Step 3: Run tests — verify pass
- [ ] Step 4: Compile + full suite
- [ ] Step 5: `git add`, STOP

## Acceptance Criteria

1. `jobs` and `job_events` tables exist with correct schema.
2. State machine rejects all illegal transitions.
3. Atomic claim — two workers cannot claim the same job.
4. Scheduler picks up APPROVED jobs, runs preflight, dispatches, monitors.
5. Context-fit check blocks oversized handoffs from dispatch.
6. Completed jobs produce structured checkpoints.
7. Expired leases are recovered with retry count.
8. API endpoints work for create/approve/list/status/cancel/tick.
9. Cron-tick entry point runs one scheduler pass.
10. Dependencies block dependent jobs until parents complete.
11. All 63 existing tests + all new tests green.
