## Wake-up 2026-08-20T15:15:09Z (Human ruling — budget 5->7; proceed to handoff 012)

- Event: Human ruling received (supervisor wake-up, not a verdict). The ruling:
  (1) the parked bookkeeping has been materialized; (2) Run 003 governed handoff
  budget amended 5 -> 7; (3) do NOT accept Run 003 on the current 011-result.md
  (fabricated `ALLOWED: []` + the deliverable was modified after signal_complete
  — not certifiable); (4) a separate real defect must be remediated: the
  materialize capability treats backlog replacement and run-ledger append as
  one-shot per run; (5) proceed with handoff 012, narrowly scoped to
  materialization idempotency semantics and their tests; (6) reserve 013
  exclusively for the clean end-to-end autonomous-chain acceptance (TG5-TG8,
  TG13), whose result must capture all evidence before signal_complete and not be
  modified afterward.
- Action: read the amended GOAL.md (§11 now "up to seven governed handoffs",
  formerly 4 -> 5 -> 7); re-ran supervisor_state.py (VERDICT READY for 011; flow
  counter 12; tmux sessions invisible from this sandbox, as before). Authored
  handoff 012 (narrow materialize-idempotency fix, in-fence:
  `scripts/bridgeV002/bridge_broker.py` + `tests/test_bridge_broker.py`) and
  dispatched it via the broker seam — `materialize --type handoff --id 12` then
  `enqueue --action signal-send --id 012` (super-deep-deep4 -> imple-codex-minimaxM3).
  Broker daemon pid 2336721 is RUNNING host-side and drains the materialize queue
  before the dispatch queue, so 012-handoff.md is written before signal-send.
- Budget: handoffs 5 used / 7 max (GOAL.md §11 + Human amendment). 012 = 6th;
  013 = 7th and FINAL (reserved for clean e2e acceptance). No wall-clock budget.
- Testgoals: 8/13 green unchanged (TG1-TG4 static/inherited from 007; TG9-TG12
  design/unit + live seam from 009/010). RED/DEFERRED to 013: TG5 (live), TG6,
  TG7, TG8, TG13. 012 removes the one-shot defect that blocks supervisor
  bookkeeping (a TG5-live prerequisite) but does NOT itself re-run the live chain.

### The materialize idempotency defect (what 012 fixes) — re-confirmed this wake-up

- Root cause: bridge_broker.py `cmd_materialize` skips enqueue if ANY `completed`
  row exists for `(flow_key, run_id, artifact_type)`. Run-ledger is append-mode
  and backlog is replace-mode — both meant for MULTIPLE writes — so the gate makes
  them one-shot per run. Run 003 already has completed run-ledger (id=5) and
  backlog (id=4) rows from the 011 dispatch, so every subsequent append/replace is
  silently dropped.
- Required fixed semantics (bound in handoff 012): handoff stays idempotent per
  handoff_id; end-report stays idempotent per run_id; run-ledger and backlog
  become multi-write, idempotent on IDENTICAL content only (a `pending` or
  `completed` row with identical content suppresses a repeat; a `failed` row
  never suppresses a retry). No schema change, no destination-path capability,
  no model-allocator change, no MCP-Light, no /skill. Evidence gate + scope fence
  preserved (TG11).

### Dispatch of handoff 012 — via the broker seam

Enqueued, in order:
1. `bridge_broker.py materialize --flow preferred_cloud_harness --type handoff
   --id 12 --content-stdin` — the daemon writes the AUTHORITATIVE copy to
   `/home/svend/flows/preferred_cloud_harness/handoffs/012-handoff.md` (the
   scaffold copy is authoring source only, not the delivery path).
2. `bridge_broker.py enqueue --flow preferred_cloud_harness --from-role
   super-deep-deep4 --to-role imple-codex-minimaxM3 --id 012 --action signal-send`
   (no `--handoff-path`; dispatch.py derives the canonical path from the id).
The daemon drains materialize before dispatch. The flow counter advances 12 -> 13
when signal-send processes (reserving 012), matching the 009/011 pattern.

### Notes (state re-verified this wake-up)

- Supervisor sandbox unchanged: `/home/svend/flows` READ-ONLY (the broker seam is
  the only authoritative-write path); `/home/svend/DPMtF-WebUI` writable;
  `databases/dpmtf.db` writable. Broker daemon pid 2336721 RUNNING (`ps -ef`).
- This RUN-LEDGER append and the BACKLOG replace could NOT be materialized via
  the seam (the one-shot defect) and are staged under the scaffold fallback for
  Human materialization — same as the prior parked bookkeeping. After 012 lands,
  the next wake-up should materialize bookkeeping via the seam.
- NEXT WAKE-UP (verdict 012): validate the fix by hand (re-run the cited broker
  tests; confirm second-append/second-replace behavior), then dispatch 013 (clean
  end-to-end acceptance) if 012 APPROVED. 013's result must capture ALL evidence
  BEFORE signal_complete and must not be modified afterward.
