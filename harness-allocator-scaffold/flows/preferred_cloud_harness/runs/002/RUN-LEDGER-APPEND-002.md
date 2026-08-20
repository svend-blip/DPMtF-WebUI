## Wake-up 2026-08-20T07:12:00Z (cold-start — manual reconstruction)

- Event: Human-initiated cold-start wake-up of the super-deep-deep4 supervisor
  (no verdict delivered). `supervisor_state.py` reported **STALLED**: last
  trace.log signal 2026-08-19T21:20:25Z (handoff 005 `signal_complete` to
  imple-codex-minimaxM3), 9h46m prior; all three role tmux sessions reported
  NOT RUNNING.
- Action: Per the cold-start skill ("STALLED is a stop condition, not a nudge
  cue — verify the target session still holds the dispatch before anything
  else; a recycled session cannot answer, and re-dispatching is the wrong
  reflex"), I verified chain liveness against the live process table before
  acting. Finding: the chain is **alive and actively working**, so I did **not**
  re-dispatch handoff 005 and did not touch any dispatch state.
  - imple-codex-minimaxM3: `codex -m MiniMax-M3` PID 1281130 (started
    09:06:54 local) with a live child PID 1286222 running
    `python3 -m pytest tests/test_preferred_cloud_harness.py -q` in
    /home/svend/DPMtF-WebUI since 09:08 local — the implementer is actively
    executing handoff 005's TG1 validation.
  - review-claude-sonnet5: `claude --model claude-sonnet-5` PID 1281182
    (started 09:06 local).
  - super-deep-deep4: `harness_terminal.py --role super-deep-deep4` PID 1281121
    (started 09:06 local).
  - The "NOT RUNNING" tmux report is the known sandbox false-negative: the host
    tmux socket (/tmp/tmux-1000/default) is not visible from inside the DeepSeek
    Harness sandbox, while the role processes are plainly visible via `ps`.
  - `/home/svend/flows` remains read-only from this sandbox (re-confirmed with a
    `touch` probe → read-only filesystem); no `dispatch.py` was run, so no
    id-counter or trace.log state was touched.
- Budget: handoffs **1/4** (005 dispatched, no result/verdict yet). Active
  wall-clock from trace.log ≈ 20 min (run open 21:00:00Z → last signal
  21:20:25Z); the ~10 h gap was overnight chain-down idle, not active work.
  The 300 min active cap is not at risk.
- Testgoals: **0/10 confirmed** — no result/verdict 005 exists, so TG1–TG9 are
  unvalidated and TG10 (Human-observed live smoke) remains future.
- Notes:
  - Next wake-up: when result/verdict 005 lands, validate TG1–TG9 by hand
    against GOAL.md §6 (check_testgoals.py cannot parse this prose testgoal
    contract — see opening entry) and act per 511 Event Handling: dispatch 006
    (review/remediation) or close early. Do not re-dispatch 005.
  - Observed (not actionable now): the implementer's codex sandbox mounts root
    read-only and only /home/svend/harness-allocator writable. The in-scope
    DPMtF seam file (…/scripts/bridgeV002/harness_terminal.py) lives outside
    that writable set; if the implementer needs to write it, it must surface a
    blocker or request escalation — the supervisor does not pre-empt this.
  - This entry is staged under
    harness-allocator-scaffold/flows/preferred_cloud_harness/runs/002/ because
    the bridge dir is read-only in-sandbox (established Run 001 convention).
    Host-side materialization: append this block to
    /home/svend/flows/preferred_cloud_harness/runs/002/RUN-LEDGER.md.
