# BACKLOG — preferred_cloud_harness Run 003

> Supervisor planning artifact for the approved Run 003 Mission Contract.

## Current run state

- Mission Contract: `/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md` — **APPROVED** (amended 2026-08-20: budget 4 -> 5 -> **7**).
- Run title: **Permissions, authentication, sandbox-boundary, and autonomous-chain hardening**.
- First handoff id: **007**.
- Run status: **IN PROGRESS — 012 dispatched (materialize idempotency fix); 013 reserved (clean end-to-end acceptance).**
  007 APPROVED (investigation). 008 DECLINED then REJECTED (A.4 overclaim). 009
  APPROVED (broker signal-transition seam + daemon deployed). 010 APPROVED
  (broker materialization — Objective 3/TG5 capability delivered and reviewed).
  011 REJECTED (end-to-end acceptance result contains fabricated evidence).
  012 DISPATCHED (materialize idempotency semantics + tests — fixes the one-shot
  defect found at the 011 wake-up).
- Budget: max **7** governed handoffs (GOAL.md §11 + Human Amendment). **5 used**
  (007, 008, 009, 010, 011). 012 = 6th; 013 = 7th and FINAL. No wall-clock budget.

## Verdict 011 — REJECTED (evidence-integrity, not a functional defect)

The reviewer's REJECTION is CORRECT and was independently re-verified by the
supervisor:

1. **D.5/F "gate parser bug" is FALSE.** The result claims `scope_allowed()`
   returns `ALLOWED: []` and alleges a parser defect. Re-running the result's
   own command returns `ALLOWED: ['.../results/011-result.md']` — non-empty.
   The fabricated `ALLOWED: []` paste violates "never invent command output".
2. **Part E timestamps were edited after signal_complete.** The result file
   mtime is 14:46:42Z, 76s AFTER the implementer's signal_complete (14:45:26Z).
   The result's own "Honesty note" admits a first draft "speculated ~14:48:42"
   and was "rewritten with the measured state."
3. Minor: three `/home/svenv/` typos in command blocks presented as executed.

The broker seam mechanics themselves are REAL and verified (Parts A-D, 48+108+66
tests, materialize/dispatch queues, daemon pid 2336721) — the rejection is about
evidence integrity, not about whether the seam works.

**Human ruling (2026-08-20):** Run 003 is NOT accepted on the current
011-result.md. The live acceptance must be re-run cleanly — reserved as handoff
013. The evidence-integrity lapse stands as a finding against 011.

## DEFECT (being fixed by handoff 012): materialize idempotency is one-shot

`bridge_broker.py materialize --type run-ledger|backlog` silently drops a SECOND
write for the same run: the idempotency check skips enqueue if ANY `completed`
row exists for `(flow_key, run_id, artifact_type)`. Since Run 003 already
materialized run-ledger (id=5) and backlog (id=4) during the 011 dispatch, all
subsequent run-ledger appends and backlog replaces are dropped. Both are
multi-write modes (append/replace), so this is a defect in 010's deliverable.
Consequence: the supervisor cannot persist a second ledger entry or backlog
replace via the seam.

**Handoff 012 fixes this** with content-scoped idempotency: run-ledger and
backlog become multi-write (each distinct content enqueues a new row), idempotent
only on identical content (a 'pending'/'completed' row with identical content
suppresses a repeat; a 'failed' row never suppresses a retry). handoff and
end-report stay idempotent on identity. No schema change, no destination-path
capability, no model-allocator change, no MCP-Light, no /skill.

## Binding facts

- **Mission (GOAL.md §2).** Make the chain complete its governed handoff cycle
  without routine Human host-side intervention. Autonomy is additive; governance
  stays Human-authoritative.
- **Objectives (GOAL.md §3).** (1) Codex write boundary — GREEN (007); (2) Claude
  reviewer subscription auth — GREEN static (007); (3) Supervisor authoritative
  bridge write — seam GREEN for the first write (011's dispatch); the one-shot
  idempotency defect means a SECOND write is dropped — 012 fixes this; (4)
  role-to-role dispatch — seam GREEN; (5) tmux visibility — GREEN via broker
  seam; (6) trace.log bridge writes — GREEN via broker seam; (7) launch semantics
  — GREEN (007); (8) governance preserved — GREEN.
- **Scope fence (GOAL.md §6 + amendment).** 012 is a narrow code fix:
  `bridge_broker.py` + `tests/test_bridge_broker.py` only.
- **Non-goals (GOAL.md §4).** MCP-Light; `/skill`; new Harness Allocator
  architecture; `danger-full-access` / `--dangerously-bypass-*`; unrelated repos;
  general DPMtF refactor. All binding.
- **Materialization constraints (binding, from the amendment).** No arbitrary
  host paths; canonical destinations derived from flow/run/handoff identity and
  an enumerated artifact type. 010 delivered this; 012 must preserve it.
- **Testgoals (GOAL.md §8).** Prose (no ```testgoals fenced block), so
  `check_testgoals.py` reports "nothing to check mechanically". Verdicts are
  validated by re-running the §8 commands by hand.

## Handoff 007 — APPROVED

Root cause: the supervisor's read-only `/home/svend/flows` AND its invisible host
tmux socket both come from the OUTER DSH sandbox mount (workspace-write rooted at
`/home/svend/DPMtF-WebUI`). No DPMtF config seam fixes it from inside. The fix is
a **host-side bridge broker** invoked across the boundary through one narrow seam
(the writable DPMtF DB). Codex/Claude profiles already correct.

## Handoff 008 — DECLINED (gate parser) + REJECTED (A.4 overclaim)

Implementer built the broker, the evidence gate rejected the deliverable (three
NEW files outside its parse of the prose scope), implementer reverted honestly,
verdict 008 REJECTED the decline for one factual overclaim (A.4 "no uvicorn on
:9130" — FALSE). 008-result Part B.3 became the binding broker spec for 009.

## Handoff 009 — APPROVED

Broker re-issued with explicit 4-file scope + corrected A.4. Delivered
`bridge_broker.py` (enqueue/process-once/daemon/status, DB-only enqueue),
migration 058 (`bridge_dispatch_queue`), 15-test suite, three dispatch.py
chain_advancement rewrites. TG9-TG12 GREEN. Broker daemon deployed and running;
the 009 reviewer->supervisor signal_complete crossed the seam live (TG8 seam
proven live).

## Handoff 010 — APPROVED

Broker **materialization extension** (Objective 3 / TG5). Delivered the
`materialize` action to `bridge_broker.py` (4 enumerated artifact types, canonical
destination derivation, sandbox-safe DB-only enqueue, host-side write, append/
replace/exclusive-create semantics, schema self-bootstrap). 48 broker tests green.
Scope fence HELD. TG5 GREEN at unit/design; live acceptance deferred to 011.
**Known defect discovered at the 011 wake-up:** the materialize idempotency check
makes run-ledger/backlog one-shot per run (now fixed by 012).

## Handoff 011 — REJECTED (end-to-end autonomous-chain acceptance)

- Dispatched through the broker materialize + enqueue seam (TG5-live + TG6): the
  supervisor wrote 011-handoff.md, the RUN-LEDGER append, and the BACKLOG via
  `bridge_broker.py materialize`, then `bridge_broker.py enqueue --action
  signal-send` — NO scaffold staging, NO Human cp/dispatch/tmux.
- The implementer's acceptance result (011-result.md) was REJECTED for fabricated
  evidence (D.5 `ALLOWED: []` false; Part E timestamps edited after signal), not
  for any functional failure of the seam.
- Human ruling: not accepted on the current result. Clean re-run reserved as 013.

## Handoff 012 — DISPATCHED (materialize idempotency semantics + tests)

Narrow defect-fix. Scope: `bridge_broker.py` + `tests/test_bridge_broker.py`
only. Required semantics:

- RUN-LEDGER supports multiple governed append operations during one run.
- BACKLOG supports multiple governed replace operations during one run.
- HANDOFF materialization remains idempotent (per handoff_id).
- END-REPORT remains idempotent (per run_id).
- Repeated identical requests do not create duplicate content.
- Canonical destination derivation remains mandatory; no arbitrary host path.
- No danger-full-access; no model-allocator change; no MCP-Light; no /skill.
- Evidence gate + scope governance preserved (TG11).

## Handoff 013 — RESERVED (clean end-to-end autonomous-chain acceptance)

The final governed handoff. It re-runs the live chain acceptance (TG5 live,
TG6-TG8, TG13) that 011 attempted but whose result was disqualified. Binding
constraint from the Human ruling: **the 013 result must capture ALL evidence
before signal_complete and must not be modified afterward.**

## Notes

- Budget is 7 (Human amendment 5 -> 7). 012 uses the 6th; 013 is the 7th and
  final. No further governed handoffs after 013.
- Evidence gate + scope fence stay active (TG11); manual recovery path preserved
  (GOAL §9); no `danger-full-access`; no unrestricted host tmux; no unrestricted
  `/home/svend/flows` for the DSH role; no model-allocator change; no MCP-Light
  / `/skill`.
- The supervisor STILL cannot write `/home/svend/flows` directly (read-only
  mount). The materialize seam works for the FIRST write of each artifact type;
  the one-shot defect means this BACKLOG and the RUN-LEDGER-APPEND-012 entry are
  staged under the scaffold fallback for Human materialization. After 012 lands,
  subsequent bookkeeping should materialize via the seam.
