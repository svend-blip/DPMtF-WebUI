# RUN-LEDGER — preferred_cloud_harness run 001

Append-only. The run's memory; the session is not. Rebuild on every wake-up:
GOAL.md → this ledger (tail) → BACKLOG.md (511 §Run Artifacts / Wake-Up Protocol).

First handoff id: 001.

---

## Wake-up 2026-08-19T15:59:03Z (run-open — GOAL.md approved)

- Event: The Human approved the Mission Contract — `GOAL-DRAFT.md` renamed to
  `GOAL.md` at `/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md`.
  Run 001 is opened.
- Action: Authored `BACKLOG.md` (planned handoffs 001–004) and this opening
  entry. Chain NOT started — handoff 001 is staged but NOT dispatched (gated on
  target writability, blocker #1). Nothing dispatched, nothing signalled, no
  implementation started.
- Budget: handoffs 0/4, active 0 min from trace.log.
- Testgoals: 0/8 green (0 measured — the chain has not started).
- Notes:
  - First handoff id: 001. Flow counter: 1. This is the flow's first run, so
    the run owns every id from 001 upward; no floor below it to confuse with a
    closed run (GOAL.md §First handoff id).
  - Chain: `super-deep-deep4` → `imple-codex-minimaxM3` →
    `review-claude-sonnet5` → `super-deep-deep4` (GOAL.md §Preferred Cloud
    Harness Chain). Harnesses resolved by Harness Allocator; models resolved by
    Model Allocator — the allocator never resolves or substitutes a model.
  - Budgets: max 4 handoffs, 5 h active wall-clock, 2 rework attempts per
    handoff, 2 consecutive no-progress cycles (GOAL.md §Budgets).
  - Measured at run open, 2026-08-19: target `/home/svend/harness-allocator`
    READ-ONLY to this session; bridge dir `/home/svend/flows` READ-ONLY to this
    session; disk 98% full (48 GiB free on `/`). tmux sessions for all three
    roles not running (expected before the first dispatch).
  - Handoff 001 (materialize the standalone package at the final path and prove
    TG2/TG3/TG4/TG5/TG6/TG8) is **gated on target writability (blocker #1)**.
    Handoff 002 (the DPMtF-side extraction) is writable but depends on 001's
    package being importable at its final path (BACKLOG.md §Notes).
  - Blocker #2 workaround: this ledger, `BACKLOG.md` and `001-handoff.md` are
    staged under `harness-allocator-scaffold/` in the DPMtF-WebUI working tree
    because the authoritative bridge dir is read-only in this session. The Human
    materializes them into `/home/svend/flows/preferred_cloud_harness/` on the
    host. No authoritative bridge or target-project file was modified by this
    staging.
  - No dispatch, no signal, no implementation was performed. The chain starts
    when the Human resolves target writability and handoff 001 is dispatched per
    GOAL.md Standing Approvals.
