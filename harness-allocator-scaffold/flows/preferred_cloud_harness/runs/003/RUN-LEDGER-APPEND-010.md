## Wake-up 2026-08-20T13:34:16Z (Human decision — Objective 3 materialization)

- Event: Human decision received for Run 003 Objective 3. Two parts:
  1. The DSH headless CLI surface (`dsh --profile headless --help`) exposes NO
     sandbox / add-dir / workspace-root / mount / allow-path capability, so the
     previously preferred option (a) — adding only `/home/svend/flows` as an
     extra writable DSH root — is **not available** through the supported DSH
     launch surface.
  2. Authorize option (b): extend the host-side bridge broker with a **NARROW
     governed artifact materialization** capability (BACKLOG create/replace,
     RUN-LEDGER create/append, HANDOFF materialization for an explicit id,
     END-REPORT create), deriving the canonical destination under
     `/home/svend/flows/preferred_cloud_harness/` from flow/run/handoff identity
     and artifact type, with NO arbitrary host path accepted and full validation
     of flow identity, active run, handoff id, artifact type, canonical
     destination, and governance/scope constraints. Keep the DB-backed
     transition queue + host-side tmux dispatch design. NO danger-full-access,
     NO unrestricted `/home/svend/flows` for the DSH role, NO model-allocator
     change, NO MCP-Light or /skill work.
- Action: re-verified run state (see Notes), then determined the instruction's
  own gate — "use the final remaining governed handoff only if the scope and
  budget permit this narrow materialization extension plus the end-to-end
  acceptance; otherwise PARK" — resolves to **PARK: budget conflict**. Did NOT
  dispatch handoff 010. Did NOT allocate a new id. No completion signal sent.
- Budget: handoffs **3 used / 4 max** (007 APPROVED, 008 declined+REJECTED, 009
  APPROVED). Flow counter re-read: next_id = 10. No wall-clock budget stated in
  Run 003.
- Testgoals: unchanged. 8/13 green (TG1-TG4 static/inherited from 007;
  TG9-TG12 design/unit+live-seam from 009). RED/DEFERRED: TG5 (supervisor
  authoritative write), TG6-TG8 (live autonomous dispatch), TG13 (full live
  cycle).

### The exact budget/scope conflict (reported, not improvised)

The authorized materialization extension and the end-to-end acceptance are TWO
distinct governed cycles, and only ONE governed handoff (010) remains:

1. **Materialization extension = handoff 010.** It is a code change to
   `bridge_broker.py` (+ its test). The supervisor cannot implement it directly
   — implementation flows through the governed chain (implementer -> reviewer),
   so it consumes the 4th and final handoff (010).

2. **End-to-end acceptance = a 5th governed handoff (011).** GOAL.md TG6/TG7/
   TG8/TG13 (§8, §15.13) require one complete governed autonomous live cycle
   super-deep-deep4 -> imple-codex-minimaxM3 -> review-claude-sonnet5 ->
   super-deep-deep4 with NO manual cp/dispatch/tmux steps. TG6 is explicit:
   "The Supervisor shall create and dispatch a governed test handoff" — that
   test handoff is a governed dispatch (id 011) through the implementer (TG7)
   and reviewer (TG8). It is a 5th governed handoff.

3. **The two cannot be merged into 010 (bootstrap).** 010's own dispatch
   requires `010-handoff.md` to already exist at the canonical
   `/home/svend/flows/preferred_cloud_harness/handoffs/` path — which is exactly
   the write the materialization extension (delivered BY 010) does not yet
   provide. 010's dispatch would therefore be the last manual Human
   materialization, so 010's own cycle cannot satisfy TG6/TG13's "no manual
   steps" requirement. The e2e acceptance must be a SEPARATE post-010 cycle.

Net: materialization (010) + e2e acceptance (011) = 2 governed handoffs
required, 1 available. The run would exceed GOAL.md §11's cap of "up to four
governed handoffs". Scope is NOT the blocker — the extension is narrow
(bridge_broker.py + test_bridge_broker.py) and gate-parseable; the blocker is
the §11 handoff cap alone.

### Resolution options (Human decision required — parked)

- **A.** Amend GOAL.md §11 to raise the cap to five governed handoffs, so 010 =
  materialization and 011 = e2e acceptance. (GOAL amendment is a Human authority,
  GOAL.md §3 Objective 8.)
- **B.** Rule that the e2e-acceptance live cycle is a non-development acceptance
  activity NOT counted in the §11 development-handoff cap (a budget-accounting
  ruling only the Human can make), leaving 010 = materialization and the e2e
  cycle as the closing acceptance.
- **C.** Keep the park (no further action) — leaves Objective 3 unsolved and the
  run unable to satisfy §15 items 5/6/13 or close.

### Notes (state re-verified this wake-up)

- Sandbox re-probe unchanged: `/home/svend/flows` READ-ONLY (touch -> Errno 30);
  `/home/svend/DPMtF-WebUI` writable; DB writable. This read-only mount is the
  Objective 3 symptom itself and is why this ledger entry is staged under
  `harness-allocator-scaffold/` for Human materialization.
- Broker daemon RUNNING on the host (pid 2187005, ~25 min elapsed). Queue rows:
  id=2 (preferred_cloud_harness, review01->supervisor signal_complete for 009,
  completed 13:08:39Z) — TG8 seam proven live; id=3 (a different
  `preferred_cloud` flow row, not this run). No pending rows.
- Flow counter re-read: next_id = 10 (unchanged) -> 010 is the next id.
- The Human decision's constraints are all preserved: no danger-full-access, no
  unrestricted `/home/svend/flows` for the DSH role, no model-allocator change,
  no MCP-Light or /skill work. None of these is touched by parking.
- No new handoff id allocated, no dispatch, no completion signal (loop guard).
  Run remains OPEN, parked on the Human for resolution option A, B, or C above.
