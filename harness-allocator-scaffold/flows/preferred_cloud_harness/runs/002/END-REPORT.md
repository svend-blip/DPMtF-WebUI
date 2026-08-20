# END-REPORT — preferred_cloud_harness Run 002: Harness Terminal Runtime Hardening

**Status:** CLOSED — 10/10 testgoals GREEN (9 automated + TG10 Human-observed)
**Handoffs:** 2 used (005, 006) — both APPROVED
**Date:** 2026-08-20

## Summary

Run 002 hardened the interactive Harness Terminal runtime of the standalone
Harness Allocator without expanding its architecture. All four objectives of the
approved Mission Contract are met:

- **Objective 1 (safe Ctrl+C)** — deterministic Ctrl+C semantics while READY,
  cancel/terminate of the active harness child while RUNNING with no orphan
  process, and a documented return to READY. Implemented with ordinary
  process/signal semantics, no supervisor framework added.
- **Objective 2 (runtime status visibility)** — a compact startup/status banner
  exposing flow, role, harness, model target, cwd, lifecycle state, sandbox,
  approval policy, workspace access, bridge-dir access and MCP-Light state, with
  unknown values reported honestly as `unknown`/`not configured` and no secrets
  exposed.
- **Objective 3 (preserve raw multiline input)** — the Run 001 binding invariant
  is preserved: one submission → one request → one request_id → one task payload
  → one harness invocation, embedded newlines intact, no line-by-line dispatch.
- **Objective 4 (preserve Run 001 lifecycle)** — READY → DISPATCH → RUNNING →
  SUCCESS | ERROR → READY, plus request identity, SHA-256 reporting, heartbeat
  visibility and duplicate-request protection all remain functional.

The run was intentionally small: a single implementation handoff (005) followed
by one Human-authorized, narrowly-scoped remediation handoff (006) that made TG1
truthfully green by repairing a pre-existing broken test fixture and removing a
shadowed duplicate test block. No production source was modified by 006; no
assertion was weakened.

## Testgoals

Verified against the working tree, not taken from any verdict. Run 002 GOAL.md
carries TG1–TG10 in prose (§6) with no ```testgoals fenced block, so
`check_testgoals.py` reports nothing to check mechanically; every testgoal was
validated by hand against the §6 validation commands.

| TG | Subject | Status | Evidence |
|----|---------|--------|----------|
| TG1 | Existing preferred_cloud_harness regression suite remains green | **GREEN** | `cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q` → **74 passed in 0.10s**, exit 0, no deselection |
| TG2 | Standalone Harness Allocator regression suite remains green | **GREEN** | `cd /home/svend/harness-allocator && python3 -m pytest tests -q` → **66 passed in 3.34s**, exit 0 |
| TG3 | Multiline submission remains atomic (20k+ chars, one request, one invocation, newlines preserved) | **GREEN** | `test_terminal_full_loop_one_invocation_for_20k_multiline` + `test_execute_argv_form_preserves_multiline_task` pass |
| TG4 | Ctrl+C during RUNNING cancels only the active execution, returns to READY, no orphan | **GREEN** | `-k "cancel or orphan or sigint"` → **7 passed**, 59 deselected |
| TG5 | Ctrl+C while READY deterministic and documented | **GREEN** | `-k "seam_idle_reader_clear or seam_idle_reader_returns_frame or seam_main_passes_cancel_event"` → **4 passed**; README.md "Ctrl+C behavior (Run 002)" section added |
| TG6 | Runtime status exposes flow/role/harness/model/cwd/lifecycle/sandbox/access without secrets | **GREEN** | `-k "seam_render_banner or seam_collect_runtime_status or seam_main_collects_status"` → **9 passed**, 65 deselected |
| TG7 | Run 001 lifecycle, request identity and duplicate protection intact | **GREEN** | `-k "terminal_repeated_turns or terminal_handled_error or terminal_duplicate or terminal_explicit_retry or terminal_same_payload or terminal_prints_request or duplicate_request_returns"` → **7 passed** |
| TG8 | DPMtF Harness resolution backward compatible | **GREEN** | `python3 -c "from scripts.bridgeV002 import harness; assert harness.resolve_harness({'allocator_client':'dsh'}) == 'dsh'"` → exit 0 |
| TG9 | Changed Python modules compile cleanly | **GREEN** | `python3 -m py_compile scripts/bridgeV002/harness_terminal.py` → exit 0; standalone `terminal.py`/`status.py`/`invoke.py` import cleanly (proven by the TG2 suite importing them) |
| TG10 | Live acceptance smoke test: one multiline submission → one DISPATCH, one invocation, returns READY | **GREEN (Human-observed)** | Human-observed live acceptance already obtained; treated as observed per Human determination — no autonomous role fabricated an observation |

**10 of 10 green.** Independently re-confirmed this wake-up: TG1 (74 passed),
TG2 (66 passed), TG8 (exit 0), TG9 seam compile (exit 0), and the coverage
subset `-v -k "eintr or cancel or sigint or multiline or atomicity or
collect_runtime_status or render_banner or duplicate" --no-header` → 14 passed,
60 deselected. `grep "Run 002 ADD-only growth"` on the test file returns exactly
one occurrence and each of the five seam tests plus the `_EintrThenFiniteData`
helper appears exactly once, confirming the duplicate block is gone.
`git status --short` matches the recorded baseline byte-for-byte — no file
changed during handoff 006.

## What Happened

- **Handoff 005 (APPROVED)** — the Implementer implemented the four objectives
  in the in-scope seam (`scripts/bridgeV002/harness_terminal.py`): wall-clock
  drain bound on the idle accumulator, `collect_runtime_status()` reporting the
  bridge dir only when explicitly configured, README documentation for Ctrl+C
  and runtime status, plus ADD-only seam tests in both repositories. One
  pre-existing test (`test_seam_idle_reader_handles_eintr`) carried a
  never-idling fake that could not pass under the new wall-clock bound, leaving
  TG1 red (73 passed, 1 failed) and was honestly disclosed. The evidence gate
  flagged five out-of-fence files whose mtimes overlapped the run; the Human
  cleared this as the false-positive shape GOAL.md §5 names (concurrent/external
  dirty files are not evidence of a breach), and the verdict was APPROVED with
  TG2–TG9 green and TG1 red on the one disclosed broken test.
- **Handoff 006 (APPROVED)** — the Human authorized a narrowly bounded scope
  expansion confined to `tests/test_preferred_cloud_harness.py` to make TG1
  truthfully green. The remediation repaired `test_seam_idle_reader_handles_eintr`
  with a finite `_EintrThenFiniteData` fixture (EINTR once → data once → EOF) and
  removed the shadowed duplicate copy of the five seam tests. No production
  source changed; no assertion weakened. The reviewer independently reproduced
  74 passed (no deselection), the 14-test coverage subset, and the 66-pass
  standalone suite, and confirmed the working tree was unchanged during the
  handoff. Verdict APPROVED.

## Chain Timings

```
2026-08-19T21:03:56Z  005  super-deep-deep4->imple-codex-minimaxM3  dispatched
2026-08-19T21:20:25Z  005  super-deep-deep4->imple-codex-minimaxM3  signal_complete
2026-08-20T07:08:05Z  005  super-deep-deep4->imple-codex-minimaxM3  dispatched
2026-08-20T08:42:50Z  005  imple-codex-minimaxM3->review-claude-sonnet5 gate_rejected
2026-08-20T08:50:51Z  005  imple-codex-minimaxM3->review-claude-sonnet5 gate_escalation_required
2026-08-20T09:18:58Z  005  imple-codex-minimaxM3->review-claude-sonnet5 signal_complete
2026-08-20T09:23:36Z  005  review-claude-sonnet5->super-deep-deep4  signal_complete
2026-08-20T09:55:33Z  006  super-deep-deep4->imple-codex-minimaxM3  dispatched
2026-08-20T09:58:16Z  006  imple-codex-minimaxM3->review-claude-sonnet5 gate_rejected
2026-08-20T10:05:54Z  006  imple-codex-minimaxM3->review-claude-sonnet5 signal_complete
2026-08-20T10:08:06Z  006  review-claude-sonnet5->super-deep-deep4  signal_complete
```

Active wall-clock ≈ 197 min (two sessions: ~17 min on 08-19 and ~180 min on
08-20, excluding the ~9 h 48 min overnight chain-down idle), measured from
`trace.log` — under the 300 min cap. Handoffs used: 2 of 4 (under budget).

## Action Items for Human

1. **Commit the deliverable** (GOAL.md §14 — only the Human commits). A prepared
   commit message is at
   `/home/svend/flows/preferred_cloud_harness/verdicts/006-commit-message.md`.
   The changes are left unstaged; no autonomous role staged/committed/reverted
   anything.
2. In-scope changed files for this run: the seam
   `scripts/bridgeV002/harness_terminal.py`, ADD-only tests in
   `tests/test_preferred_cloud_harness.py` and
   `/home/svend/harness-allocator/tests/test_harness_allocator.py`, and docs
   `/home/svend/harness-allocator/README.md`.
3. Do **NOT** commit `databases/dpmtf.db` — it is flow dispatch exhaust, not a
   run deliverable (the standing exception, as recorded in the run ledger).
