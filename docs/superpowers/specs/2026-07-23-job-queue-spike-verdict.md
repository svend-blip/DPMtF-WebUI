# Job Queue Spike — Verdict

**Date:** 2026-07-23

## Question
What is the correct durable job abstraction for DPMtF?

## Approach
Compared:
1. Extending `workflow_runs` (existing table)
2. Separate `jobs` table linked to `workflow_runs`

## Results

### Separate `jobs` table — RECOMMENDED

A separate `jobs` table is the correct choice because:
- A workflow run and an execution job are different concepts: a run tracks prompt compilation + hitrate; a job tracks execution lifecycle
- The `jobs` table has 22+ columns (leases, heartbeats, retry counts, idempotency keys, allocator aliases) that don't belong in `workflow_runs`
- `job_events` table provides audit trail of every state transition
- Atomic claims use `BEGIN IMMEDIATE` for true worker exclusion
- FK from `jobs.workflow_run_id` to `workflow_runs.run_id` links them

### Tested capabilities (12 tests, all green):
- Legal/illegal state transitions (14 states, enforced by state machine)
- Atomic claim — two workers cannot claim the same job
- Lease recovery — expired leases are auto-re-queued
- Heartbeat — extends lease
- Idempotency key — prevents duplicate job creation
- Full lifecycle: DRAFT → AWAITING_APPROVAL → APPROVED → QUEUED → RUNNING → VERIFYING → COMPLETED
- Allocator alias stored on each job

## Verdict: GO

The separate `jobs` table approach is viable and recommended.
Production implementation should add:
- Dependency scheduling (job A blocks on job B)
- Human approval gate (AWAITING_APPROVAL → APPROVED transition)
- Cancellation propagation to dependent jobs
- Scheduler daemon (cron-tick or standing service)
