<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>003</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
Handoff 001 materialized the standalone, stdlib-only `harness_allocator` package at
`/home/svend/harness-allocator` (verdict APPROVED). Handoff 002 rewired the DPMtF
harness-generic seam so `scripts/bridgeV002/harness.py` and
`scripts/bridgeV002/harness_terminal.py` consume that package and fix raw tmux
multiline atomicity (verdict APPROVED; TG1/TG7 + 11 ADD-only seam tests green).

What remains open is the *end-to-end integration surface* of the Mission Contract
(objectives 5, 6 and 7 of the run's GOAL.md), which handoff 002 deliberately left
to this handoff. The standalone package already implements the full behavior; the
DPMtF terminal does not yet surface all of it:

- Objective 5 (request identity/visibility): the standalone `execute()` returns
  `request_id`, `payload_chars`, `payload_lines`, `payload_sha256`, `harness`,
  `role`, `model_target`, `pid`, `elapsed`. The DPMtF terminal's `main()` loop
  currently prints only `[DISPATCH] {chars} chars / {lines} lines` — it does not
  surface request id, sha256, pid or elapsed.
- Objective 6 (heartbeat / lifecycle visibility): the standalone `run_argv` emits
  `RUNNING` + periodic `HEARTBEAT` (pid, elapsed, process-alive) through an
  `on_event` callback. The DPMtF terminal's `execute()` still uses a blocking
  `subprocess.run`, so long turns show `[RUNNING]` then nothing until
  `[SUCCESS]`/`[ERROR]` — no heartbeat, no final elapsed time.
- Objective 7 (duplicate-request protection): the standalone `run_terminal`
  records each completed `(request_id, payload_sha256)` and reports
  `[DUPLICATE_REQUEST]` instead of re-running it. The DPMtF terminal's `main()`
  loop has no duplicate check at all.

The authoritative Mission Contract is:
`/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md`.
Read it before implementing.

Binding architectural rules (unchanged from handoffs 001 and 002):

1. Model Allocator is the sole model/runtime authority. DPMtF resolves the model
   target first and passes the resolved `model_target` to Harness Allocator.
   Harness Allocator never resolves, selects, replaces, or owns the model, and
   there is no silent model or harness substitution.
2. Raw tmux multiline injection remains the supported interaction model: the
   terminal accumulates the full submission (idle-bounded byte accumulation, as
   implemented in handoff 002), the submission Enter triggers post-processing,
   and the complete accumulated text reaches the selected harness as exactly one
   prompt / one invocation. Run 001 does NOT introduce a length-delimited or
   framed DPMtF transport protocol — do not replace the idle-bounded reader with
   a framed reader.
</context>

<governance>
1. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT. Leave changes unstaged for the Human.
2. No new runtime dependencies. `harness_allocator` is a local companion package,
   not a third-party dependency.
3. No `resolve_model()` or model-selection ownership; no silent model/harness
   substitution.
4. No hardcoded `/home/svend/...` paths in reusable source. Locate the standalone
   package through `config.py` getters (e.g. `config.get_project_path(...)`) or an
   environment variable. `config.py` itself is out of scope and MUST NOT be edited.
5. Do not redesign DPMtF flows, roles, verdict handling or governance.
6. Do not replace raw tmux injection with a new externally visible transport protocol.
7. Report only measured results. Never invent test output. If a validation step
   cannot run in your environment, say so plainly and move on — never reconstruct
   what its output "would" have been. A live DeepSeek Harness call is OPTIONAL and
   bounded (see <validation>); its absence is not a failure, but fabricating one is.
8. Stop after two failed attempts at the same problem and report the blocker.
</governance>

<task>
Close objectives 5, 6 and 7 in the DPMtF harness terminal, and prove the
end-to-end path: a multiline task injected through raw tmux reaches the DeepSeek
Harness as exactly one invocation, with full lifecycle/identity/duplicate
visibility and no regression.

Required outcomes:

1. Understand the current state. Read `scripts/bridgeV002/harness.py`,
   `scripts/bridgeV002/harness_terminal.py`, and the standalone package's
   `harness_allocator/terminal.py` (its `run_terminal`), `invoke.py`
   (`execute` / `run_argv` / `run_command`), and `transport.py`
   (`compute_identity`, `RequestFrame`). The standalone package is READ-ONLY for
   you.

2. Surface request identity (objective 5) in the terminal's dispatch block. The
   terminal must print, per submission, the operational metadata the standalone
   already computes: `request_id`, `chars`, `lines`, `sha256`, `harness`, `role`,
   `model_target` — and after execution, `pid` (where available) and elapsed time.
   This is execution telemetry, never chain-of-thought.

3. Surface lifecycle/heartbeat (objective 6). Long turns must expose `[RUNNING]`
   (with pid and elapsed) followed by periodic `[HEARTBEAT]` (request_id,
   process-alive, elapsed) while the child process is alive, then
   `[SUCCESS]`/`[ERROR]` with final elapsed time, then a return to `READY`.
   The heartbeat cadence must be configurable and match the standalone's default
   (15.0s).

4. Add duplicate-request protection (objective 7). An accidental re-submission of
   the same completed `(request_id, payload_sha256)` identity must NOT invoke the
   harness a second time: report `[DUPLICATE_REQUEST]` and return to `READY`. A
   deliberate retry may be supported via the standalone's explicit `retry` flag if
   you reuse it, but the internal representation is an implementation choice.

5. Preserve the raw tmux accumulation reader from handoff 002. The idle-bounded
   `_IdleAccumulatingReader` is the DPMtF-facing input model. Do NOT switch to a
   length-delimited frame reader. Reuse the standalone's lifecycle runner (e.g.
   `run_terminal` with the DPMtF reader injected, or `execute`/`run_argv` with an
   `on_event` callback) where it removes duplication; you choose the exact
   division. Do not leave two divergent lifecycle loops.

6. Preserve the model boundary. DPMtF resolves the model target and passes it
   through; the harness never resolves or substitutes it. TG7 must stay green.

7. Preserve DPMtF regression. The flow regression suite
   (`tests/test_preferred_cloud_harness.py`) must stay green WITHOUT modifying any
   existing test function — the 41 original tests AND the 11 seam tests from
   handoff 002 (52 total) are all untouchable. Note specifically:
   `test_harness_terminal_execute_uses_build_task_invocation` and
   `test_harness_terminal_execute_invokes_harness_once_per_submission` both patch
   `harness_terminal.subprocess.run` and assert its argv shape and its
   CompletedProcess-like return (`.returncode`/`.stdout`/`.stderr`). Keep the
   `harness_terminal.execute(harness_key, role_config, task, cwd)` boundary
   behaving as those tests require, or change the approach so they still pass —
   but do not edit them.

8. Prove the changed terminal with ADD-only test growth (new test functions and/or
   a new test file). The new tests must, at minimum, prove: (a) the full terminal
   loop, fed a 20k+ character multiline paste through the idle reader, produces
   exactly one harness invocation with embedded newlines preserved; (b) heartbeat
   events are emitted while a child stays alive; (c) a re-submitted completed
   identity reports `DUPLICATE_REQUEST` and does NOT invoke the harness a second
   time; (d) the request identity block (request_id, sha256, chars, lines) is
   printed for a submission.

9. Leave the standalone package at `/home/svend/harness-allocator` unchanged. If
   you find its public API insufficient, do NOT modify it silently — report the
   specific gap under deviations/limitations in your result.

When implementation and validation are complete, write the governed result to:
`/home/svend/flows/preferred_cloud_harness/results/003-result.md`

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 003
```

If signaling fails, report the real failure; do not fabricate completion.
</task>

<scope>
MAY modify inside `/home/svend/DPMtF-WebUI`, only as required to close objectives
5/6/7 in the terminal and prove the end-to-end path:

- `scripts/bridgeV002/harness.py`
- `scripts/bridgeV002/harness_terminal.py`
- `scripts/bridgeV002/start_coding.py`
- `scripts/bridgeV002/dispatch.py`

MAY ADD (new files and/or new test functions only — do not modify existing
tests) test coverage proving the changed terminal.

MAY READ (do not modify):

- `/home/svend/harness-allocator/` — the approved standalone package.

MUST NOT modify:

- `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`, `.env`
- governance files under `docs/governance-templates-v2/`
- `.git/` internals
- other flows' files
- the standalone package `/home/svend/harness-allocator/`
- ANY existing test function in `tests/test_preferred_cloud_harness.py`

Do not commit or push.
</scope>

<validation>
Run and read the real output of all applicable checks:

1. TG1 (flow regression, must stay green — 41 original + 11 seam = 52 tests):
```bash
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q
```

2. TG7 (model boundary — DPMtF still resolves the harness):
```bash
cd /home/svend/DPMtF-WebUI && \
python3 -c "import sys; sys.path.insert(0,'scripts/bridgeV002'); import harness; assert harness.resolve_harness({'allocator_client':'dsh'}) == 'dsh'"
```

3. Standalone package regression (must stay green):
```bash
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

4. Compile every changed Python module:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/harness.py \
  scripts/bridgeV002/harness_terminal.py scripts/bridgeV002/start_coding.py \
  scripts/bridgeV002/dispatch.py
```

5. Your new terminal test(s) proving: full-loop one-invocation for a 20k+
   multiline paste; heartbeat emitted while a child stays alive; duplicate
   request reports `DUPLICATE_REQUEST` without a second invocation; the request
   identity block is printed. Run them and paste the real output.

6. An end-to-end argv-level proof that a multiline task reaches the DeepSeek
   Harness runner as exactly one invocation with the complete payload as one argv
   element (the canonical `npx @deepseek-ai/dsh --profile headless ...` shape).
   A LIVE DeepSeek Harness round-trip is OPTIONAL: only run it if `DEEPSEEK_API_KEY`
   and network access are available, keep it to a single short probe, and report
   the real outcome. Do not fabricate a live result if you could not run one.

7. Inspect working-tree truth (this project IS a git repository):
```bash
cd /home/svend/DPMtF-WebUI && git status --short && git diff --stat
```

Paste real outputs in `003-result.md`.
</validation>

<constraint>
- No new runtime dependencies.
- No model resolution/substitution ownership; no silent model/harness fallback.
- No hardcoded `/home/svend/...` paths in reusable source — use config.py getters
  or environment variables.
- Raw tmux multiline input remains the external interaction assumption; keep the
  idle-bounded accumulation reader — no new length-delimited/framed DPMtF
  transport protocol.
- Exactly one complete submitted prompt must produce exactly one harness invocation.
- The 52 existing regression tests (41 original + 11 seam) must stay green without
  editing them; ADD-only test growth.
- Heartbeat/identity output is operational telemetry only — never chain-of-thought.
- A completed request identity must not invoke the harness twice; report
  `[DUPLICATE_REQUEST]` and return to READY.
- Do not commit/push/stage/stash/revert.
- Do not modify the standalone package at `/home/svend/harness-allocator`.
</constraint>

<deliverable>
`/home/svend/flows/preferred_cloud_harness/results/003-result.md` containing:

- files changed
- how the terminal now surfaces request identity, heartbeat/lifecycle and
  duplicate protection (which standalone primitives it reuses, and the delegation
  boundary)
- how raw tmux multiline accumulation and the one-invocation invariant are preserved
- tests/checks run with real output (including the new ADD-only tests)
- whether a live DeepSeek Harness round-trip was run, and its real outcome if so
- deviations or limitations (including any standalone-package API gap, if found)
- known follow-up work

Then signal completion exactly once as specified in `<task>`.
</deliverable>
