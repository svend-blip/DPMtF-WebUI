# Handoff Series — Supervisor Autonomous Loop (H318–H321)

> Architect planning document for wiring the autonomous supervisor loop
> (governance: `501_SUPERVISOR_AUTONOMOUS.md`). One handoff dispatched at a
> time through `strict_review` (hard rule 3 — no batch dispatch). This file
> is the durable series plan across Architect cold starts.

## Design Decisions (Architect)

1. **New flow `supervised_review`, strict_review untouched.** The autonomous
   loop gets its own flow key. Step structure mirrors strict_review with two
   changes: the handoff step originates from `supervisor` (not `archi01`),
   and the verdict step delivers to `supervisor` (not `human`). Because the
   verdict delivery is a real dispatch into the supervisor's claude-code
   session, **verdict wake-ups come free from the flow wiring** — no
   scheduler code needed for that trigger.
2. **Supervisor gets `fresh_session_command='/clear'`** — stateless
   wake-ups per 501, and the first live validation of the /clear path
   (run 317 only validated /new).
3. **Roles imple01/review01/review02 are reused** across both flows
   (flow steps are per-flow rows; sessions and governance are shared).
4. **Open decision — escalation routing:** 404/405 instruct reviewers to
   escalate to archi01. In supervised_review escalations must reach the
   supervisor. Editing 404/405 requires Human approval (16_FILE_ACCESS).
   To be resolved by Architect before H320 dispatch — candidate options:
   flow-aware escalation target in the content template, or new
   504/505 governance files for the supervised flow.

## The Series

| # | Title | Points covered | Files (expected) |
|---|-------|----------------|------------------|
| 318 | DB wiring: supervised_review flow + supervisor /clear (migration 009) | 1 + 3 (+4 verdict trigger via wiring) | `scripts/db/009_*.sql` |
| 319 | Verdict-gating in the scheduler | 2 | `scripts/job_queue/scheduler.py`, `models.py`, tests |
| 320 | Supervisor wake-up triggers + invariant preflight | 4 (rest) | `scripts/job_queue/scheduler.py`, tests |
| 321 | E2E smoke: mini supervised run with trivial GOAL.md | validation | run artifacts only |

### H318 — DB wiring (migration 009)

- `bridge_roles.supervisor.fresh_session_command = '/clear'`.
- New flow `supervised_review` + 4 steps:
  `supervisor→imple01` (handoff, auto-chain) → `imple01→review01` →
  `review01→review02` → `review02→supervisor` (verdict delivery, real
  dispatch, chain ends). Deliverable dirs under the bridge dir for
  `supervised_review`, pattern per migration 008.
- `bridge_id_counters` row for `supervised_review`.
- Idempotent, additive-only; existing strict_review/supervisor rows
  untouched except the single supervisor UPDATE.

### H319 — Verdict-gating (scheduler)

- On chain completion, parse the verdict outcome and transition the job:
  APPROVED → COMPLETED; REJECTED → CHANGES_REQUESTED.
- The scheduler claims the next APPROVED job for a flow only when the flow
  has no RUNNING job and the previous verdict is resolved.
- pytest coverage for both outcomes and the gating condition.

### H320 — Wake-up triggers + invariant preflight (scheduler)

- Dispatch the supervisor with event context on: REJECTED verdict
  (rework), watchdog stall timeout, backlog empty while a run is active.
  (APPROVED verdict wake-up already covered by flow step 4.)
- Invariant preflight before every dispatch (501 §Invariants): health
  endpoint, DB opens, correct branch, no changes outside the scope fence.
  Failure → job HUMAN_ACTION_REQUIRED, no dispatch.
- Escalation-routing decision (see Open decision above) lands here.
- **From H318 verification:** the step-4 rule_key `agent_delivery` has no
  row in `bridge_convention_rules` (empty prompt_template fallback) — the
  supervisor wake-up prompt content must be defined here, including a
  reference to `501_SUPERVISOR_AUTONOMOUS.md` (the role's
  `governance_file` points at 500, the Human-paired mode).

### H321 — E2E smoke run

- Trivial `GOAL.md` (docs-only task, 1–2 handoffs, tight budgets) under
  `{bridge_dir}/supervisor/runs/smoke-001/`.
- Validates live: /clear on a claude-code session, verdict delivery to
  supervisor, verdict-gating, ledger writing, END-REPORT.

## Status

- [x] H318 APPROVED (2026-07-27, migration `scripts/db/010_supervised_review_flow.sql`) — awaiting Human commit. Architect re-verified all 7 checklist items in DB + API.
- [ ] H319
- [ ] H320 (blocked on escalation-routing decision)
- [ ] H321
