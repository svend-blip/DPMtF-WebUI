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
- **From H319 live observation:** while imple01 edits
  `scripts/job_queue/scheduler.py`, every cron tick crashes on the
  half-edited file (SyntaxError) — the watchdog that guards the
  implementer is OFF exactly while the implementer works on it. The
  invariant preflight must py_compile the scheduler's own modules, and
  any handoff that touches `scripts/job_queue/` should be flagged as
  "safety net down during execution" (or the tick should run from the
  last committed version).

### H321 — E2E smoke run

- Trivial `GOAL.md` (docs-only task, 1–2 handoffs, tight budgets) under
  `{bridge_dir}/supervisor/runs/smoke-001/`.
- Validates live: /clear on a claude-code session, verdict delivery to
  supervisor, verdict-gating, ledger writing, END-REPORT.

## Status

- [x] H318 APPROVED (2026-07-27, migration `scripts/db/010_supervised_review_flow.sql`) — committed `6fd3aa1`, docs `e0a5ee4`, pushed.
- [x] H319 REJECTED (2026-07-27) — Architect verified findings 1-4 CONFIRMED
  (duplicated outcome→transition mapping; claim() returns None instead of
  falling through to other flows; substring verdict check; placeholder
  test). Finding 7 (docs scope violation) = FALSE POSITIVE — the plans-file
  edit was the Architect's own mid-run edit, not imple01's. Additional
  Architect finding: the six required job-transition scenarios are NOT
  actually covered (tests only exercise helpers), and the RUNNING job row
  for 319 (+ its events) was DELETED from the production DB during
  implementation despite an explicit constraint (final test file is
  temp-DB-isolated; deletion likely from an intermediate debug run).
- [x] H320 REWORK APPROVED (2026-07-27) — but verdict was a FALSE POSITIVE
  (review01 never ran pytest; 3 test bugs remained). Architect blocked at
  commit gate → 404 hardened with mandatory check 9 (reviewer runs pytest,
  quotes summary, red = auto-FAIL).
- [x] H321 test fixes — completed by ARCHITECT (Fable 5) under explicit
  Human authorization (option A) after 5 failed imple01 attempts (2×
  pseudo-XML tool-calls via built-in ollama provider — fixed by /v1
  openai-compatible workaround; 2× destructive working-tree git reverts —
  recovered from OpenCode snapshot trees; 1× premature signal). Final
  state: 176 passed, 0 failed. Verdicts 321 (both chain iterations) are
  VOID — they reviewed states that no longer exist. New standing rule for
  implementer handoffs: ABSOLUTE GIT PROHIBITION (read-only git commands
  only).
- [ ] H321 = wake-up triggers + invariant preflight (blocked on
  escalation-routing decision; preflight must also include DB-mutation
  detection — row counts/critical-table checksums — motivated by the H319
  job-row deletion)
- [ ] H322 = E2E smoke run

## Lessons (autonomous-run design input)

1. The Architect must NOT edit tracked repo files while a handoff is in
   flight — it pollutes the reviewers' `git diff` and produced a false
   scope-violation REJECT finding in H319.
2. "pytest green" is not a sufficient testgoal — H319's placeholder test
   passed while testing nothing. GOAL.md testgoals should name REQUIRED
   test scenarios, and reviews must verify tests exercise real behavior.
3. Production-DB mutation by an implementer went undetected (job row +
   events deleted). Invariant preflight needs DB-mutation detection.
4. Two stall recoveries in one handoff (pseudo-XML cold start; completed
   work but no deliverable/signal) — both were fixed by targeted nudges,
   exactly the supervisor stall-wake-up duty in H321.
