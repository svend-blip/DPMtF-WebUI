## Wake-up 2026-08-20T09:09:00Z (gate escalation 005 — Human determination, independent validation, proceed to review)

- Event: Evidence gate escalated on handoff 005 (`gate_escalation_required` at
  08:50:51Z, after `gate_rejected` at 08:42:50Z). The gate flagged 5 files
  outside the scope fence whose mtimes postdate the 07:08:05Z dispatch. Human
  determination received this wake-up: the 2nd gate rejection is NOT evidence of
  an implementer scope-fence breach; GOAL.md §5 makes concurrent/external dirty
  files outside the fence non-evidence; 005-result.md now declares the 5 files;
  clear the gate attribution and proceed with governed review. Do NOT re-dispatch
  005 to the implementer, do NOT revert/modify the 5 files.
- Action: Independently validated handoff 005 against GOAL.md (in-scope changes,
  TG1–TG9 by hand, out-of-fence dependency check). CLEARED the gate attribution
  finding per Human determination. Staged the governed-review dispatch below for
  host-side materialization (sandbox is read-only on `/home/svend/flows` and has
  no tmux socket — the established Run 001/002 convention).
- Budget: handoffs **1/4** dispatched (005; no verdict yet). Active wall-clock
  ≈ 40 min signal-to-signal since run open (21:00:00Z → last signal 08:50:51Z,
  less the ~10 h overnight chain-down idle); 300 min cap not at risk.
- Testgoals: **8/10 confirmed green by my own runs** (TG2–TG9); **TG1 RED**
  (1 pre-existing broken test, honestly disclosed by the implementer); **TG10**
  Human-observed live acceptance, still future.

### 1. In-scope changes — VERIFIED

The implementer's declared edits (005-result.md §3.1–§3.4) are real, in-fence,
and postdate dispatch. Measured directly (`stat -c '%y %n'`, local +0200):

- `/home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py` 10:30:46 —
  seam. Two edits confirmed by reading the file: `collect_runtime_status()` now
  reports the bridge dir only when explicitly configured (env `DPMTF_BRIDGE_DIR`
  or a non-fallback `config.get_bridge_dir()`), else "not configured"; and
  `_IdleAccumulatingReader.read_frame()` gained a wall-clock drain bound
  (`max(2.0, idle*50)`). Both in the fence (seam file).
- `/home/svend/harness-allocator/README.md` 10:35:16 — added "Ctrl+C behavior
  (Run 002)" (line 116) and "Runtime status (Run 002)" (line 153) sections. In
  fence (docs).
- `/home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py` 10:34:30 — five
  ADD-only seam tests (lines 1594/1614/1644/1668/1704). NOTE: the same five test
  bodies are defined a SECOND time at lines 1785/1805/1835/1859/1895 after the
  "Run 002 ADD-only growth" header; the later definitions shadow the earlier
  ones (module-level redefinition), so pytest collects 5, not 10. Dead duplicate
  block — a tidiness defect, not a scope or correctness issue.
- `/home/svend/harness-allocator/tests/test_harness_allocator.py` 10:36:12 — one
  ADD-only test `test_run_terminal_sigint_when_no_runner_sets_ready_interrupt`
  (line 1290). In fence.

In-scope but NOT modified (mtimes predate the 07:08:05Z dispatch): standalone
`terminal.py` (08:49 local), `status.py` (08-19 23:10), `invoke.py` (08-19
23:21). 005-result.md §3.5 states this correctly. The standalone package already
carried the Run 002 Ctrl+C/status/lifecycle logic before the second dispatch.

### 2. TG1–TG9 — run by hand, real output

- **TG1** `cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q`
  → **73 passed, 1 failed** in 2.21s. The failure is
  `test_seam_idle_reader_handles_eintr` (a PRE-EXISTING test whose fake stub
  never idles and re-serves the same bytes; with the new wall-clock bound it
  exits instead of hanging, but fails the payload assertion). The implementer
  deselected it (`--deselect ...::test_seam_idle_reader_handles_eintr`) and
  reported "73 passed, 1 deselected", disclosing the deselection in §6.1 and
  §7.1. **This is a real TG1 red as GOAL.md §6 writes it (no deselect).**
- **TG2** `cd /home/svend/harness-allocator && python3 -m pytest tests -q`
  → **66 passed** in 3.34s. GREEN.
- **TG3** `...::test_multiline_terminal_submission_is_one_invocation ...::test_execute_argv_form_preserves_multiline_task -v`
  → **2 passed**. GREEN.
- **TG4** `... -k "cancel or orphan or sigint" --no-header` → **7 passed,
  59 deselected**. GREEN.
- **TG5** `... -k "seam_idle_reader_clear or seam_idle_reader_returns_frame or seam_main_passes_cancel_event" --no-header --deselect ...handles_eintr`
  → **4 passed, 70 deselected**. GREEN. (The implementer's §6.5 paste shows 3 of
  the 4 test lines with "4 passed" — a transcription slip, not a wrong count.)
- **TG6** `... -k "seam_render_banner or seam_collect_runtime_status or seam_main_collects_status" --no-header --deselect ...handles_eintr`
  → **9 passed, 65 deselected**. GREEN.
- **TG7** `... -k "terminal_repeated_turns or terminal_handled_error or terminal_duplicate or terminal_explicit_retry or terminal_same_payload or terminal_prints_request or duplicate_request_returns"`
  → **7 passed, 59 deselected** (lifecycle/duplicate-request/identity). GREEN.
- **TG8** `cd /home/svend/DPMtF-WebUI && python3 -c "from scripts.bridgeV002 import harness; assert harness.resolve_harness({'allocator_client':'dsh'}) == 'dsh'"`
  → exit 0. GREEN.
- **TG9** seam `python3 -m py_compile scripts/bridgeV002/harness_terminal.py`
  → exit 0. Standalone `python3 -m py_compile harness_allocator/terminal.py harness_allocator/status.py harness_allocator/invoke.py`
  → blocked by read-only fs on the bytecode write (`[Errno 30] Read-only file
  system`); the modules parse/import cleanly (TG2 imports them), so no
  SyntaxError. The only module the implementer changed (the seam) compiles.
- **TG10** — Human-observed live acceptance; remains for the Human. The
  implementer correctly did not claim it.

### 3. The 5 flagged files are NOT required by the 005 implementation — VERIFIED

The 5 files (005-gate-rejection.md list):
1. `/home/svend/harness-allocator/harness-allocator.ini` — all-commented codex
   placeholders (`codex_workdir`, `codex_add_dirs`, `codex_sandbox`,
   `codex_ask_for_approval`).
2. `/home/svend/harness-allocator/harness_allocator/__init__.py` — re-exports the
   same `get_codex_*` getters.
3. `/home/svend/harness-allocator/harness_allocator/adapter.py` — `_codex_argv`
   now emits `-C/--add-dir/--sandbox/--ask-for-approval`.
4. `/home/svend/harness-allocator/harness_allocator/config.py` — the new
   `get_codex_workdir/get_codex_add_dirs/get_codex_sandbox/get_codex_ask_for_approval`.
5. `/home/svend/DPMtF-WebUI/harness-allocator-scaffold/.../RUN-LEDGER-APPEND-002.md`
   — this supervisor's own cold-start ledger entry.

Files 1–4 are Codex-harness invocation configuration (how the Codex CLI for the
IMPLEMENTER role is launched). The 005 objectives are the DeepSeek-Harness
(`dsh`) terminal runtime: Ctrl+C, status visibility, multiline atomicity,
lifecycle. The seam imports only `harness_allocator.transport` and
`harness_allocator.status` (with a fallback shim, harness_terminal.py:112–159),
never `config`/`adapter`. `invoke.build_task_argv("dsh")` → `build_dsh_argv` →
pre-existing `get_dsh_bin/get_dsh_profile/get_dsh_patch_path`, never the codex
getters. The standalone codex tests inject a `_FakeCfg` stub, so they do not
depend on the real `config.py` either. File 5 is run-memory, not code.

Conclusion: the gate's mtime-based attribution of these 5 files to
imple-codex-minimaxM3 is the exact false-positive shape GOAL.md §5 names
("Existing dirty files outside this Scope Fence are not evidence of a breach by
this run merely because their mtimes overlap the run"). CLEARED.

### 4. Host-side materialization + governed review dispatch

Not runnable from this sandbox (read-only `/home/svend/flows`, no tmux socket).
The review of 005 is the `imple01-review01` step; re-running the implementer's
completion with the 5 concurrent paths excluded from the gate's
`undeclared_changes` scan (the gate's own `DPMTF_GATE_IGNORE_PATHS` mechanism —
it does NOT modify the files) advances the chain to `review-claude-sonnet5`:

```bash
DPMTF_GATE_IGNORE_PATHS="harness-allocator.ini,harness_allocator/__init__.py,harness_allocator/adapter.py,harness_allocator/config.py,RUN-LEDGER-APPEND-002.md" \
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 005
```

The reviewer (`review-claude-sonnet5`) then reviews the working tree against
005-result.md per 513 and writes `verdicts/005-verdict.md`. The reviewer's own
verdict passes the gate's `undeclared_changes` check automatically
(`owns_the_fence` is False for verdicts), so it will not re-trip on the 5 files.

### Notes for the next wake-up

- Carry the **TG1 red** into the review: `test_seam_idle_reader_handles_eintr`
  is a pre-existing test with a never-idling fake; the implementer could not fix
  it (ADD-only). The reviewer should judge whether this blocks APPROVED or needs
  a Human decision (the test itself is broken, not the seam).
- The duplicate test block in `test_preferred_cloud_harness.py` (dead first copy,
  lines 1578–1726) is worth a reviewer note; it does not affect results.
- Do NOT re-dispatch 005 to the implementer (Human determination). Do NOT revert
  or modify the 5 files.
