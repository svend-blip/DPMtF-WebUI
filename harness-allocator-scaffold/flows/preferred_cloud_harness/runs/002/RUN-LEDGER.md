# RUN-LEDGER — preferred_cloud_harness Run 002

Append-only run memory. Rebuild context on every supervisor wake-up from:
GOAL.md -> RUN-LEDGER.md tail -> BACKLOG.md.

First handoff id: 005.

---

## Wake-up 2026-08-19T21:00:00Z — Run opened

- Human-approved Mission Contract exists at
  `/home/svend/flows/preferred_cloud_harness/runs/002/GOAL.md` (status APPROVED,
  title "Harness Terminal Runtime Hardening").
- First handoff id is **005**; flow counter was **5** at run opening (next_id=5,
  confirmed against `bridge_id_counters`).
- Run opened with no implementation handoff dispatched yet (chain not started).
- Chain: `super-deep-deep4` -> `imple-codex-minimaxM3` ->
  `review-claude-sonnet5` -> `super-deep-deep4` (DeepSeek Harness / Codex CLI /
  Claude Code; DeepSeek V4 Pro / MiniMax M3 / Sonnet 5).
- Model Allocator remains model/runtime authority. Harness Allocator never
  resolves or silently substitutes the model (GOAL.md §4).
- Budgets: max **4** governed handoffs, **300** minutes active wall-clock
  measured from `trace.log` (GOAL.md §13). Stop-after-two-failed-patches per
  problem governs rework (GOAL.md §10).
- Scope fence (GOAL.md §5): DPMtF seam
  `/home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py`; standalone
  `/home/svend/harness-allocator/harness_allocator/{terminal,status,invoke}.py`;
  ADD-only tests in `tests/test_preferred_cloud_harness.py` (DPMtF-WebUI) and
  `tests/test_harness_allocator.py` (harness-allocator); docs
  `/home/svend/harness-allocator/README.md`. All other paths out of scope.

### Testgoal validation note

Run 002 GOAL.md §6 states TG1–TG10 in prose, **without** a ```testgoals fenced
block. `scripts/bridgeV002/check_testgoals.py` therefore reports "nothing to
check mechanically" for this contract. Every verdict must be validated by
re-running the §6 validation commands by hand. Recorded here so no later
wake-up wastes time trying the mechanical checker first.

### Host / sandbox verification

- `/home/svend/flows` — readable, **not writable** from this supervisor sandbox
  (read-only filesystem). Same as Run 001's situation.
- `/home/svend/harness-allocator` — readable, **not writable** from this sandbox.
- tmux socket not visible from this sandbox (`tmux ls` ->
  `error connecting to /tmp/tmux-1000/default`). Host-side session liveness
  cannot be verified from inside the DeepSeek Harness sandbox; `supervisor_state`
  reports all three role sessions "NOT RUNNING" only because the socket is
  invisible here. The host-side dispatch below will fail its `session_alive`
  check if the target session (`imple-codex-minimaxM3`) is not actually running
  on the host — a prerequisite the host operator must confirm.
- `trace.log` is readable (last entry: handoff 004 `signal_complete`
  2026-08-19T20:27:39Z, run 001 closure) but not writable here.
- Consequence: `dispatch.py --signal-send` cannot be run from this sandbox — it
  would bump the id counter and then fail on the read-only `trace.log` write /
  unreachable tmux session, leaving a partial state (the exact trap documented
  in Run 001's ledger). Artifacts are therefore staged under
  `/home/svend/DPMtF-WebUI/harness-allocator-scaffold/` and the host-side
  materialization + dispatch is documented below. The host paths are writable on
  the host; the sandbox read-only condition is not a host blocker.

### Staging history

Supervisor-prepared BACKLOG, RUN-LEDGER and handoff 005 are staged under
`/home/svend/DPMtF-WebUI/harness-allocator-scaffold/flows/preferred_cloud_harness/`
for host-side materialization into the authoritative
`/home/svend/flows/preferred_cloud_harness/` (established Run 001 staging
convention). No `dispatch.py` was run from this sandbox, so no id-counter or
trace.log state was touched.

### Host-side materialization + dispatch (run after staging)

1. Copy
   `harness-allocator-scaffold/flows/preferred_cloud_harness/runs/002/BACKLOG.md`
   -> `/home/svend/flows/preferred_cloud_harness/runs/002/BACKLOG.md`
2. Copy
   `harness-allocator-scaffold/flows/preferred_cloud_harness/runs/002/RUN-LEDGER.md`
   -> `/home/svend/flows/preferred_cloud_harness/runs/002/RUN-LEDGER.md`
3. Copy
   `harness-allocator-scaffold/flows/preferred_cloud_harness/handoffs/005-handoff.md`
   -> `/home/svend/flows/preferred_cloud_harness/handoffs/005-handoff.md`
4. Dispatch handoff 005:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-send \
  --from-role super-deep-deep4 \
  --to-role imple-codex-minimaxM3 \
  --id 005
```

The explicit `--id 005` makes the staged file provably the file that goes out;
`bump_id_counter_past` advances the counter 5 -> 6.

### Next wake-up

When verdict 005 lands: validate TG1–TG9 by hand against GOAL.md §6, then per
511 Event Handling dispatch handoff 006 (review/remediation) — or close early
if testgoals are green and the backlog is empty.
