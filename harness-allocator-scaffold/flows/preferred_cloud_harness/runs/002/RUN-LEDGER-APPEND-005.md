## Wake-up 2026-08-20T09:45:32Z (Human scope expansion — remediation 006 prepared and validated)

- Event: Human decision received — **authorize option 2** of the parked
  HUMAN_ACTION_REQUIRED state: a narrowly bounded scope expansion whose sole
  purpose is to make TG1 truthfully green. Authorization is confined to
  `/home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py`; handoff 005
  stays APPROVED and is not redesigned; production source is not to be changed
  unless a newly demonstrated defect makes it unavoidable (then PARK); TG10 is
  treated as already Human-observed, no fabrication.
- Action: Performed the remediation directly under the Human authorization and
  staged the governed handoff 006 + result 006 for the flow. No `dispatch.py`
  was run from this sandbox (`/home/svend/flows` is read-only here, no tmux
  socket — established Run 001/002 convention), so no id-counter or trace.log
  state was touched by this wake-up.
- Budget: handoffs **1/4 dispatched** (005, APPROVED); **006 staged for
  host-side dispatch** (the remediation, prepared here — not yet dispatched
  because `dispatch.py` cannot run from this sandbox). Active wall-clock ≈
  **155 min** from `trace.log` (last signal 09:23:36Z verdict-005; unchanged
  since the run parked).
- Testgoals: **TG1–TG9 green (9/9 automated); TG10 Human-observed (already
  obtained)**.

### 1. The working-tree changes (one file only)

`/home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py`, 1917 -> 1733
lines. Nothing else modified (verified `git status --short` still matches the
verdict-005 baseline; the file is untracked `??`).

1. **Repaired `test_seam_idle_reader_handles_eintr`** — replaced the
   never-idling `_InterruptOnce` stub (re-served `b"task after eintr\n"`
   forever) with a finite `_EintrThenFiniteData` stream: EINTR once -> data
   once -> EOF; the select fake reports ready only while data is pending, then
   idles. Original intent preserved: interrupted sentinel -> `clear()` -> one
   real frame. Same `assert frame.payload == "task after eintr"` now holds.
2. **Removed the shadowed duplicate block** — verified the two "Run 002
   ADD-only growth" blocks byte-identical (only trailing blank-line count
   differed); removed the FIRST (dead) copy (191 lines), kept the superseding
   copy. Each of the five seam tests + two helpers now appears exactly once.
   Updated the surviving header comment so it no longer calls the EINTR test
   "never idling".

No production source changed; no assertion weakened.

### 2. Validation (real output, this wake-up)

- **TG1 literal** `cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q`
  -> **74 passed in 0.16s** (previously 1 failed, 73 passed).
- **Relevant subsets** `... -v -k "eintr or cancel or sigint or multiline or atomicity or collect_runtime_status or render_banner or duplicate" --no-header`
  -> **14 passed, 60 deselected**.
- **Standalone suite** `cd /home/svend/harness-allocator && python3 -m pytest tests -q`
  -> **66 passed, 2 warnings** (read-only cache-write warnings only).
- Standalone TG3 multiline -> 2 passed; TG4 cancel/sigint/orphan -> 7 passed;
  TG7 lifecycle/duplicate -> 7 passed.
- `python3 -m py_compile tests/test_preferred_cloud_harness.py` -> exit 0.

### 3. Staged artifacts (host-side materialization required)

Sandbox is read-only on `/home/svend/flows`, so the following are staged under
`harness-allocator-scaffold/flows/preferred_cloud_harness/`:

- `handoffs/006-handoff.md` — the governed remediation handoff.
- `results/006-result.md` — the executed work + real outputs.
- `verdicts/006-commit-message.md` — prepared for the Human to commit.
- `runs/002/RUN-LEDGER-APPEND-005.md` — this entry.
- `runs/002/BACKLOG.md` — updated (see below).

### 4. Host-side materialization + dispatch (run after staging)

1. Copy the five staged files to the matching `/home/svend/flows/preferred_cloud_harness/...` paths
   (`handoffs/006-handoff.md`, `results/006-result.md`,
   `verdicts/006-commit-message.md`, append this block to `runs/002/RUN-LEDGER.md`,
   replace `runs/002/BACKLOG.md`).
2. Dispatch the remediation through the chain. Next flow id is **006**
   (`bridge_id_counters.preferred_cloud_harness` == 6, so
   `get_next_id_for_flow` returns 6 and bumps to 7):

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-send \
  --from-role super-deep-deep4 \
  --to-role imple-codex-minimaxM3 \
  --id 006
```

Because the working tree already carries the finished remediation, the
implementer step is a verify-and-record step (the result 006 is already staged
and matches the tree); if the host operator prefers, the review may be advanced
directly to `review-claude-sonnet5` for the 006 verdict. Either way the chain
must end with a `006-verdict.md` and then the Human commit (GOAL.md §14).

### 5. Next wake-up

- On verdict 006: validate TG1–TG9 by hand (TG1 is now green), then write
  END-REPORT.md and close the run once the Human has committed. TG10 remains
  Human-observed and already obtained — do not fabricate any additional
  observation.
