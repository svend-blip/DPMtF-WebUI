# 006-result.md — imple-codex-minimaxM3 (Run 002, handoff 006)

Scope expansion: repair TG1 red in `tests/test_preferred_cloud_harness.py`.
Human-authorized 2026-08-20. Exactly one file changed.

## 1. In-scope working-tree baseline (recorded at handoff start)

`/home/svend/DPMtF-WebUI` was already dirty from prior runs/handoffs. The only
file this handoff touches is `tests/test_preferred_cloud_harness.py` (untracked,
`??`). Nothing else was modified. `git status --short` shows the same
pre-existing dirty set recorded in verdict 005 (`.env.example`, `config.py`,
`databases/dpmtf.db`, `routers/bridge.py`, the `scripts/bridgeV002/*.py` files,
the other `tests/*.py` files, and the `harness-allocator-scaffold/` tree). No
new file was introduced by this handoff.

`/home/svend/harness-allocator` was NOT touched at all (read-only; only its test
suite was executed).

## 2. Files changed

Only one file:

- `/home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py` — 1917 -> 1733
  lines.

Two changes, both confined to that file:

### 2.1 Repair `test_seam_idle_reader_handles_eintr`

Replaced the `_InterruptOnce` fake stream (which re-served `b"task after
eintr\n"` forever and never idled/EOF'd) with a finite `_EintrThenFiniteData`
stream:

- `read1()` raises `errno.EINTR` exactly once, then serves
  `b"task after eintr\n"` exactly once, then returns `b""` (EOF).
- `_fake_select` reports the stream ready only while it still has bytes to
  serve, then idles, so the reader flushes exactly one frame.

The test's original intent is unchanged and now actually holds:

1. first `read_frame()` returns the `IDLE_READ_INTERRUPTED` sentinel;
2. `clear()` discards the interrupted state;
3. the next `read_frame()` returns the single real frame with
   `payload == "task after eintr"`.

### 2.2 Remove the shadowed duplicate test block

Verified byte-for-byte that the two "Run 002 ADD-only growth" blocks were
identical except for trailing blank lines (the first block ended with three
blank lines, the second with two). The first copy was dead — module-level
redefinition means pytest collected only the second copy. Removed the first
copy (header comment + `_seam_new_idle_stream` + `_seam_new_idle_select` + the
five seam test functions), 191 lines, keeping the superseding copy. Updated the
surviving header comment so it no longer describes the EINTR test as "never
idling".

After removal, each of the five seam test functions and the two helper
functions appears exactly once (verified by grep).

## 3. Tests run, and their real output

### 3.1 TG1 (literal, no deselect) — GREEN

```bash
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q
```

```
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 0.16s
```

### 3.2 Relevant coverage subsets (seam) — GREEN

```bash
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -v -k "eintr or cancel or sigint or multiline or atomicity or collect_runtime_status or render_banner or duplicate" --no-header
```

```
14 passed, 60 deselected in 0.08s
```

Selected (14): `test_terminal_full_loop_one_invocation_for_20k_multiline`,
`test_terminal_duplicate_request_returns_ready_without_second_invocation`,
`test_seam_render_banner_exposes_runtime_status_fields`,
`test_seam_render_banner_honours_unknown_and_not_configured`,
`test_seam_render_banner_strips_secret_like_values`,
`test_seam_collect_runtime_status_uses_env`,
`test_seam_collect_runtime_status_defaults_to_unknown`,
`test_seam_collect_runtime_status_filters_secret_like_env`,
`test_seam_collect_runtime_status_bridge_dir_via_config`,
`test_seam_idle_reader_handles_eintr`,
`test_seam_terminal_runner_forwards_cancel_event`,
`test_seam_idle_reader_preserves_atomicity_for_20k_multiline`,
`test_seam_main_passes_cancel_event_to_loop`,
`test_seam_collect_runtime_status_honours_explicit_config`.

### 3.3 Standalone suite (unchanged) — GREEN

```bash
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

```
66 passed, 2 warnings in 3.34s
```

(The 2 warnings are pytest cache-write warnings from the read-only sandbox;
results unaffected.)

### 3.4 Standalone Ctrl+C / multiline / lifecycle / duplicate — GREEN

```bash
cd /home/svend/harness-allocator && python3 -m pytest tests/test_harness_allocator.py::test_multiline_terminal_submission_is_one_invocation tests/test_harness_allocator.py::test_execute_argv_form_preserves_multiline_task -v
# 2 passed

cd /home/svend/harness-allocator && python3 -m pytest tests/test_harness_allocator.py -v -k "cancel or orphan or sigint" --no-header
# 7 passed, 59 deselected

cd /home/svend/harness-allocator && python3 -m pytest tests/test_harness_allocator.py -v -k "terminal_repeated_turns or terminal_handled_error or terminal_duplicate or terminal_explicit_retry or terminal_same_payload or terminal_prints_request or duplicate_request_returns" --no-header
# 7 passed, 59 deselected
```

### 3.5 Compile — GREEN

```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile tests/test_preferred_cloud_harness.py
# exit 0
```

## 4. Production behavior and assertions

No production source was modified. No existing assertion was weakened; the only
assertion change is that `test_seam_idle_reader_handles_eintr` now passes with
the same `assert frame.payload == "task after eintr"` it always carried, reached
through a finite stream instead of a never-idling one. The standalone
`harness_allocator` package and the seam `harness_terminal.py` are unchanged.

## 5. Known limitations

- `/home/svend/flows` is read-only from this sandbox, so the handoff/result are
  staged under `harness-allocator-scaffold/` for host-side materialization and
  dispatch (established Run 001/002 convention).
- The standalone suite is exercised read-only; its `.pytest_cache` write emits
  two warnings only because the sandbox filesystem is read-only.

## 6. Explicit statement on TG10

TG10 is Human-observed live acceptance. It was already obtained by the Human in
Run 002 (raw multiline -> one DISPATCH, one invocation, return to READY, no
line-by-line fragmentation). This handoff does NOT claim, re-run, or fabricate
any additional Human observation. TG10 is treated as already-obtained evidence.
