# BACKLOG — preferred_cloud_harness Run 001

> Supervisor planning artifact for the approved Run 001 Mission Contract.

## Current run state

- Mission Contract: `/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md` — **APPROVED**.
- First handoff id: **001**.
- Flow counter at opening: **1**; at this wake-up: **4** (handoff 004 allocated,
  id 004).
- **Run status: CLOSED** (2026-08-19T20:27Z). Verdict 004 landed APPROVED —
  a genuine confirmation-and-closure pass with no code changes (mtimes verified).
  Testgoals 8/8 green and the backlog empty, so per 511 Event Handling the
  supervisor wrote `END-REPORT.md` and parked. No completion signal was sent for
  handoff 004. The out-of-fence change in
  `/home/svend/AI-Genealogy-Research-Assistant` is cleared as legitimate
  out-of-run work that overlapped in time; those files remain unmodified, are not
  part of this run's scope, and were left untouched.
- **Handoff 001: COMPLETE — verdict APPROVED** (review-claude-sonnet5, 2026-08-19).
  Standalone `harness_allocator` package materialized at
  `/home/svend/harness-allocator`, TG2–TG6/TG8 green.
- **Handoff 002: COMPLETE — verdict APPROVED** (review-claude-sonnet5, 2026-08-19).
  DPMtF-side seam rewire: `harness.py` + `harness_terminal.py` now consume the
  standalone package; raw tmux multiline atomicity fixed. 52 tests green
  (41 original + 11 ADD-only seam tests); TG1/TG7 green; standalone regression
  51/51. See `handoffs/002-handoff.md`.
- **Handoff 003: COMPLETE — verdict APPROVED (re-evaluated)**
  (review-claude-sonnet5, 2026-08-19; re-evaluated by the supervisor
  2026-08-19T20:05Z). In-fence work verified correct (56/56 tests, TG1–TG8
  green, no hardcoded paths, nothing staged). The sole rejection basis — a
  scope-fence breach on seven files in
  `/home/svend/AI-Genealogy-Research-Assistant` — was CLEARED by the Human as
  legitimate out-of-run work; the verdict is re-evaluated APPROVED on the in-scope
  evidence only. Objectives 5/6/7 (request identity, heartbeat/lifecycle,
  duplicate protection) are closed and proven.
- **Handoff 004: COMPLETE — verdict APPROVED** (review-claude-sonnet5,
  2026-08-19). Final review/closure pass: "if nothing is broken, change nothing".
  The reviewer independently confirmed no in-scope file was modified (mtimes
  predate the 004 dispatch), TG1–TG8 8/8 green, standalone package unchanged
  (51 passed), and the previously-blocking out-of-fence repository clean. No
  remediation was required or applied.
- Host verification on 2026-08-19 confirmed:
  - `/home/svend/flows` is writable on the host.
  - `/home/svend/harness-allocator` is writable on the host.
  - `DEEPSEEK_API_KEY` and `MINIMAX_API_KEY` are present in the host environment.
- DeepSeek Harness sandbox visibility may differ from host visibility. Sandbox
  read-only/missing-tmux observations are not host blockers and must not be
  treated as authoritative host state.
- The staged reference prototype under
  `/home/svend/DPMtF-WebUI/harness-allocator-scaffold/harness-allocator/` was
  reference material only; the authoritative package now lives at
  `/home/svend/harness-allocator` (handoff 001 output).

## Binding transport direction

Run 001 does **not** introduce a new required framing protocol for normal DPMtF
flow transport.

The required behavior is:

```text
raw tmux multiline injection
        -> Harness Terminal input accumulation
        -> submission Enter
        -> post-process complete accumulated text
        -> exactly one harness invocation
```

Embedded newlines are prompt content. The complete prompt must reach the
selected harness as one string/value. Internal buffering/framing may be used
inside Harness Allocator if useful, but it is not a DPMtF-facing architectural
requirement.

## Planned handoffs

| # | Focus | Scope | Testgoals | Status |
|---|---|---|---|---|
| 001 | Materialize the standalone Harness Allocator package in `/home/svend/harness-allocator`, correct the staged prototype where necessary, and prove the package contract including raw multiline one-invocation behavior | target project | TG2–TG6, TG8 | **APPROVED** |
| 002 | Extract/rewire the DPMtF harness-generic seam so `harness.py` and `harness_terminal.py` consume the standalone package while preserving raw tmux injection and Enter-as-submit | DPMtF seam | TG1, TG7 + package regression + ADD-only seam tests | **APPROVED** |
| 003 | End-to-end Preferred Cloud harness-terminal validation: close objectives 5/6/7 (request identity, heartbeat/lifecycle, duplicate protection) in the DPMtF terminal; prove multiline tmux injection reaches DeepSeek Harness as one invocation; no regression | integration seam | TG1–TG8 | **APPROVED (re-evaluated; scope breach cleared by Human)** |
| 004 | Final review/remediation if required, all testgoals green, then END-REPORT | approved scope only | TG1–TG8 | **APPROVED** (2026-08-19T20:27Z) |

## Notes

- Handoff 001 completed and approved. The standalone package is the approved
  output; handoffs 002 and 003 must read it, not modify it.
- Handoff 002 completed and approved. `harness.py` delegates command-building and
  identity to the standalone; `harness_terminal.py` accumulates raw tmux input via
  an idle-bounded reader. The terminal's `execute()` still uses `subprocess.run`
  (pinned by existing tests), so objectives 5/6/7 (identity/telemetry, heartbeat,
  duplicate protection) are NOT yet surfaced in the terminal — that is handoff
  003's job.
- Handoff 003's implementer MUST keep the 52 existing regression tests
  (41 original + 11 seam) green WITHOUT editing them, and MUST use ADD-only test
  growth. The idle-bounded reader is the binding input model — no framed protocol.
- The Implementor decides HOW to surface heartbeat/identity/duplicate protection;
  the Mission Contract specifies the observable behavior, not a mandatory frame
  format. Reusing the standalone's `run_terminal`/`execute`/`run_argv` (with an
  `on_event` callback) is preferred over re-implementing.
- No new runtime dependencies.
- No commit/push by autonomous roles.
- MCP-Light remains deferred to Run 002 after the core execution path is stable.
- Handoff 003 re-evaluated APPROVED (2026-08-19T20:05Z): the scope-fence breach
  on seven `/home/svend/AI-Genealogy-Research-Assistant` files was cleared by the
  Human as legitimate out-of-run work. Those files are left unmodified and are
  outside this run's scope; the verdict stands on the in-scope evidence only
  (TG1–TG8 8/8 green).
- Handoff 004 DISPATCHED (2026-08-19T20:14Z): the Human directed the run to
  proceed per governance. Verdict 003 APPROVED + non-empty backlog → dispatch the
  next handoff (511 Event Handling). Handoff 004 is the final review/remediation
  pass; after its verdict the backlog is empty and the supervisor writes
  END-REPORT. Handoff 004 explicitly forbids touching
  `/home/svend/AI-Genealogy-Research-Assistant`.
- **Run 001 CLOSED (2026-08-19T20:27Z).** Verdict 004 APPROVED, 8/8 testgoals
  green, backlog empty → `END-REPORT.md` written and the supervisor parked. All
  four handoffs APPROVED; budget 4/4 handoffs, 237.3 min active wall-clock
  (under the 300 min cap). The run has no further wake-ups; any later activity
  belongs to a future run allocated from the flow counter (now past id 004).
