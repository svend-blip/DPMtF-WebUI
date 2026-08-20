# BACKLOG — preferred_cloud_harness Run 002

> Supervisor planning artifact for the approved Run 002 Mission Contract.

## Current run state

- Mission Contract: `/home/svend/flows/preferred_cloud_harness/runs/002/GOAL.md` — **APPROVED**.
- Run title: **Harness Terminal Runtime Hardening**.
- First handoff id: **005** (flow counter was **5** at run opening).
- **Run status: CLOSED — 10/10 testgoals GREEN.**
  Handoff 005 implemented and verdict **APPROVED** (`verdicts/005-verdict.md`,
  review `signal_complete` 09:23:36Z). The Human authorized option 2 of the
  parked state: a narrowly bounded scope expansion confined to
  `/home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py` to make TG1
  truthfully green. That remediation landed as handoff 006; verdict 006 is
  **APPROVED** (`verdicts/006-verdict.md`, review `signal_complete` 10:08:06Z),
  independently re-validated this wake-up (TG1 74 passed, TG2 66 passed,
  coverage subset 14 passed, TG8/TG9 green). END-REPORT.md written; run closed.
  Remaining Human action only: commit per GOAL.md §14 using the prepared
  `verdicts/006-commit-message.md`.
- Budgets: max **4** governed handoffs, **300** minutes active wall-clock
  (measured from `trace.log`, not the wall clock).
- Rework discipline (GOAL.md §10): stop after two failed patch attempts against
  the same problem and return the actual failure to the Supervisor. No separate
  numeric rework cap is stated in Run 002; 511 §Decision Matrix/§Stop Conditions
  (gate rejection on the same handoff twice, two consecutive failed nudges) still
  govern.

## Binding facts

- **Scope fence (GOAL.md §5).** In-scope for modification:
  - `/home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py`
  - `/home/svend/harness-allocator/harness_allocator/terminal.py`
  - `/home/svend/harness-allocator/harness_allocator/status.py`
  - `/home/svend/harness-allocator/harness_allocator/invoke.py`
  - ADD-only tests in `/home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py`
    and `/home/svend/harness-allocator/tests/test_harness_allocator.py`
  - docs `/home/svend/harness-allocator/README.md`
  All other source paths are outside the fence unless the Supervisor parks for
  Human approval before expanding scope.
- **Raw multiline input is binding (Objective 3).** One Human submission MUST
  produce one request, one request_id, one task payload and one harness
  invocation; embedded newlines preserved; no line-by-line tmux dispatch. The
  idle-bounded accumulation reader may be retained unless a strictly smaller or
  safer correction is necessary.
- **Lifecycle must stay (Objective 4).** `READY → DISPATCH → RUNNING →
  SUCCESS | ERROR → READY`, plus request identity, SHA-256 reporting,
  heartbeat/lifecycle visibility and duplicate-request protection. A `CANCELLED`
  token may be added; existing status semantics must stay backward compatible
  unless a test proves a correction is necessary.
- **Model boundary unchanged (GOAL.md §4).** Harness Allocator never resolves,
  selects, replaces or owns the model; no silent model or harness substitution;
  no `resolve_model()` in Harness Allocator.
- **Non-goals (GOAL.md §3) are extensive and binding.** In particular: MCP-Light
  integration, `/skill`, cold-start skill abstraction, new allocator
  architecture, sandbox redesign, autonomous-chain permissions, and the known
  Codex/Claude/DeepSeek sandbox visibility fixes are ALL deferred. Objective 2's
  MCP-Light field is a read-only state **label**, not MCP-Light integration.
- **`check_testgoals.py` cannot run this contract mechanically.** Run 002 GOAL.md
  carries TG1–TG10 in prose (§6), not a ```testgoals fenced block. Every testgoal
  must be validated by hand against the §6 validation commands.

## Planned handoffs

| # | Focus | Scope | Testgoals | Status |
|---|---|---|---|---|
| 005 | Implement Harness Terminal runtime hardening: safe Ctrl+C (Obj 1), runtime status visibility (Obj 2), preserve raw multiline (Obj 3) and Run 001 lifecycle (Obj 4) | GOAL.md §5 fence | TG1–TG9 (automated); enables TG10 | **APPROVED** (verdict 005 APPROVED; TG2–TG9 green, TG1 red on 1 pre-existing broken test, TG10 Human-observed) |
| 006 | Scope expansion (Human-authorized): repair `test_seam_idle_reader_handles_eintr` + remove shadowed duplicate test block | `tests/test_preferred_cloud_harness.py` only | TG1 literal green; TG2–TG9 re-verified | **APPROVED** (verdict 006 APPROVED; TG1 74 passed, no deselection; tree unchanged during handoff) |
| 007 | Review verdict 006 → END-REPORT → close run | approved scope only | TG1–TG10 | **DONE** (verdict 006 APPROVED; END-REPORT.md written; run CLOSED; Human commit remains per §14) |

## Notes

- Handoff 005 is the single implementation handoff for all four objectives.
  Do not expand scope; the Supervisor does not have to consume all four handoffs
  — close early if testgoals are green and the backlog is empty.
- The implementer MUST record the in-scope working-tree baseline at handoff
  start (`git status --short` / `git diff --stat` in both repositories) so
  pre-existing dirty files are not misattributed to this run (GOAL.md §5).
- Test growth is ADD-only where practical; never weaken existing assertions
  merely to make the new implementation pass (GOAL.md §9).
- No commit/push/stage/stash/revert by autonomous roles (GOAL.md §14). Only the
  Human commits.
- TG10 (live acceptance smoke test) is Human-observed after implementation; the
  implementer must NOT claim it, only ensure the underlying path is correct.

## Human decision — RESOLVED

The Human authorized **option 2** (scope expansion) on 2026-08-20. The
remediation is confined to `tests/test_preferred_cloud_harness.py` and is DONE
in the working tree (TG1 green, no deselection). Staged as handoff 006.

Remaining steps (no further Human decision is required, but only the Human
commits — GOAL.md §14):

1. ~~Review verdict 006 (`verdicts/006-verdict.md`).~~ → **APPROVED**, 10:08:06Z.
2. Human commits (`verdicts/006-commit-message.md` is prepared) — **the only
   open item; this is a Human action, not a chain step.**
3. ~~Write END-REPORT.md and close the run.~~ → **DONE**, 2026-08-20T10:12:48Z.

The run is closed. No further handoff or completion signal is dispatched.
