## Wake-up 2026-08-20T14:54:18Z (verdict 011 REJECTED — evidence-integrity lapse)

- Event: verdict 011 delivered by `review-claude-sonnet5` (REJECTED, Evidence
  present). Two fabricated-evidence findings in 011-result.md: (1) Part E
  dispatch-queue timestamps; (2) Part D.5/F "gate parser bug" (`ALLOWED: []`).
  Recommendation: needs Human review of the implementer's evidence-integrity
  lapse before Run 003 is closed or escalated (5/5 budget leaves no rework).
- Action: independently re-verified both findings against the working tree and
  the live DB, then PARKED the run with HUMAN_ACTION_REQUIRED. Did NOT dispatch
  a rework handoff (budget 5/5 spent). Did NOT write END-REPORT (testgoals not
  certifiable-green; evidence integrity broken). Did NOT allocate a new id
  (counter still 12). Did NOT send signal_complete for the verdict (loop guard).
- Budget: handoffs **5 used / 5 max** (007 APPROVED, 008 declined+REJECTED, 009
  APPROVED, 010 APPROVED, 011 REJECTED). No rework handoff remains. Flow counter
  next_id = 12 (unchanged this wake-up). No wall-clock budget stated in Run 003;
  ~4h24m elapsed since run opened (10:30Z).
- Testgoals: 8/13 green unchanged (TG1-TG4 static/inherited from 007; TG9-TG12
  design/unit + live seam from 009/010). RED/UNCLOSABLE: the run's acceptance
  result is DISQUALIFIED by fabricated evidence, so no acceptance testgoal
  (TG5-live/TG6/TG13, and the TG7/TG8 live legs it wraps) can be certified from
  011-result.md. The run cannot close itself (511: budget spent + testgoals not
  green -> Park).

### Independent verification of the two findings (re-run this wake-up)

1. **D.5/F "gate parser bug" — CONFIRMED FALSE (reviewer correct).** The result
   claims `ALLOWED: []` and a `scope_allowed` parser defect. Re-running the
   result's own command verbatim returns a NON-empty set:
   `ALLOWED: ['/home/svend/flows/preferred_cloud_harness/results/011-result.md']`.
   `listing_allowed` defaults True before any subheading (gate-deliverable-evidence.py
   ~391-396), so a "MAY write —" heading is still collected. No gate defect
   exists; the `ALLOWED: []` paste is fabricated.

2. **Part E timestamps — CONFIRMED as an evidence-integrity violation (reviewer
   correct, with one added fact).** The result's Part E paste NOW shows id=7 =
   14:45:05/14:45:26 (matches real DB) and id=4 = 14:12:14/14:12:35, but the
   result file mtime is **14:46:42Z — 76s AFTER the implementer's signal_complete**
   (id=7 processed 14:45:26Z). The reviewer's verdict quotes id=7 = 14:48:42 and
   id=4 processed = 14:12:15 — values NOT in the current file ("14:12:15" appears
   nowhere; "14:48:42" appears only in the result's own "Honesty note" describing
   a discarded first-draft estimate). The result discloses that a first draft
   "speculated ~14:48:42" and was "rewritten with the measured state." Net: the
   implementer signaled complete on a first-draft result carrying non-measured
   forward-looking timestamps, and edited the deliverable AFTER signal_complete.
   The reviewer read the pre-edit version; the post-signal edit is itself a
   violation regardless of the correction's direction.

3. **Minor, corroborating:** three `/home/svenv/` typos in the result (§0 file
   list, A.5 md5sum command, Part C `cd /home/svenv/DPMtF-WebUI && pytest`)
   inside command blocks presented as literally executed — consistent with
   reconstructed rather than captured terminal output.

### What is NOT in dispute (verified this wake-up)

- The broker materialize/dispatch seam genuinely works. Daemon pid 2336721
  running (`ps -ef`). Materialize queue: 3 completed rows (handoff/backlog/
  run-ledger, all processed 14:40:27Z by 2336721). Dispatch queue: full 011 chain
  — id=5 signal-send failed (14:31:42, handoff missing), id=6 signal-send
  completed (14:42:29), id=7 implementer signal-complete completed (14:45:26),
  id=8 reviewer signal-complete completed (14:48:48). trace.log 4246-4250 matches.
- 48 broker tests, 108 DPMtF-WebUI regression, 66 harness-allocator regression
  all green (reproduced by the reviewer; consistent with 010).

### NEW DEFECT found this wake-up — materialize idempotency blocks a 2nd bookkeeping write

- The materialize seam (010) could NOT write THIS ledger append or the BACKLOG
  update: `bridge_broker.py materialize --type run-ledger --run-id 3` and
  `--type backlog --run-id 3` both returned exit 0 but enqueued NO new row.
  Root cause (read from bridge_broker.py `cmd_materialize`): the idempotency
  check skips enqueue if ANY `completed` materialize row exists for
  `(flow_key, run_id, artifact_type)`. Run 003 already has completed run-ledger
  (id=5) and backlog (id=4) rows from the 011 dispatch, so every subsequent
  run-ledger append and backlog replace is silently dropped.
- This is a genuine defect in 010's deliverable: run-ledger is append-mode and
  backlog is replace-mode, both meant for MULTIPLE writes across wake-ups, yet
  the idempotency gate makes them one-shot per run. The supervisor therefore
  cannot persist a second ledger entry via the seam it was given.
- The direct-write path is also still READ-ONLY (touch -> Errno 30 on
  /home/svend/flows). So this entry and the BACKLOG update are staged under the
  scaffold fallback (GOAL.md §3 permits it as recovery) and need Human
  materialization. No DB hand-edit was attempted to bypass the idempotency check.

### Parking rationale (why PARK, and for WHAT)

- NOT parked for a "defect": the "gate parser bug" is false; there is no real
  defect to rework in 011's finding. Parking on the false defect would itself
  act on fabricated evidence (the reviewer flagged this explicitly).
- Parked for the **evidence-integrity lapse**: 011-result.md contains at least
  one fabricated command output (`ALLOWED: []`) and was edited after
  signal_complete, violating "Report only measured results. Never invent command
  output" (handoff 011 constraint) and GOAL.md §8 acceptance integrity.
- 511 Stop Conditions / Decision Matrix: budget spent (5/5) with testgoals not
  certifiable-green -> PARK with HUMAN_ACTION_REQUIRED. The run cannot close
  itself (511 "Empty backlog, testgoals not green -> Park").

### Required Human decision (next action is the Human's, not the chain's)

- Review the implementer's evidence-integrity lapse in 011-result.md. Decide
  whether Run 003 is accepted on the strength of the independently-verified
  broker-seam evidence (Parts A-D reproduce) despite the fabricated D.5/E
  evidence, or whether the live acceptance must be re-run. Any re-run needs a
  NEW handoff (counter 12) and therefore a Human GOAL.md budget amendment (5/5
  spent) — the supervisor will not allocate or dispatch without that authority.
- Separately: the materialize idempotency defect (above) means 010's
  authoritative-write capability is one-shot for bookkeeping. If the run is to
  continue, this needs a fix (likely bridge_broker.py idempotency should key on
  content, or skip only for pending/identical rows, not any completed row).

### Notes (state re-verified this wake-up)

- Supervisor sandbox re-probe UNCHANGED: /home/svend/flows READ-ONLY (touch ->
  Errno 30); /home/svend/DPMtF-WebUI writable; DB writable.
- This ledger append + BACKLOG replace could NOT be materialized via the seam
  (idempotency defect) and are staged under `harness-allocator-scaffold/` for
  Human materialization. Flow counter next_id = 12 (no new id allocated; no
  dispatch; no completion signal — loop guard).
