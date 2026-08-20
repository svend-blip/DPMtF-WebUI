<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>002</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
Handoff 001 materialized the standalone, stdlib-only `harness_allocator` package
at `/home/svend/harness-allocator` (verdict APPROVED; TG2–TG6 and TG8 all green).
That package exposes the approved boundary `execute(role, harness, model_target,
cwd, task)` plus argv-style invocation, a READY/RUNNING/SUCCESS/ERROR lifecycle,
request metadata, and duplicate-request protection. It is importable in place and
needs no install step.

This handoff is the DPMtF-side extraction: make the DPMtF harness-generic seam
actually consume that standalone package, and fix the raw tmux multiline
atomicity defect in the process.

The authoritative Mission Contract is:
`/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md`.
Read it before implementing.

The current seam (in this repository) still carries the pre-extraction surface:

- `scripts/bridgeV002/harness.py` builds launch/task commands itself
  (`build_task_invocation`, `build_dsh_invocation`, `shlex.quote` string building).
- `scripts/bridgeV002/harness_terminal.py` reads stdin one line at a time with
  `sys.stdin.readline()` and runs `task = line.strip()` per line. A multiline
  prompt injected via raw tmux therefore fragments into several turns — each
  embedded newline becomes a separate submission. That is the exact defect the
  Mission Contract corrects: a multiline prompt must be accumulated as ONE
  submission and reach the selected harness as exactly ONE invocation, with
  embedded newlines preserved as prompt content.

Two architectural rules remain binding (unchanged from handoff 001):

1. Model Allocator is the sole model/runtime authority. DPMtF resolves the model
   target first and passes the resolved `model_target` to Harness Allocator.
   Harness Allocator never resolves, selects, replaces, or owns the model, and
   there is no silent model or harness substitution.
2. Raw tmux multiline injection remains the supported interaction model. The
   Harness Terminal accumulates the full submission; the submission Enter
   triggers the post-processing step; the complete accumulated text reaches the
   selected harness as exactly one prompt / one invocation.
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
   what its output "would" have been.
8. Stop after two failed attempts at the same problem and report the blocker.
</governance>

<task>
Rewire the DPMtF harness-generic seam so it consumes the standalone
`harness_allocator` package, and make raw tmux multiline injection reach the
harness as one complete submission.

Required outcomes:

1. Understand the current state. Read `scripts/bridgeV002/harness.py`,
   `scripts/bridgeV002/harness_terminal.py`, the call sites in
   `scripts/bridgeV002/start_coding.py` and `scripts/bridgeV002/dispatch.py`
   that launch/use the terminal, and the standalone package at
   `/home/svend/harness-allocator/harness_allocator/` (read-only).

2. Make the seam consume the standalone package's execution primitives
   (`execute`, `build_task_argv`, `run_argv`, `run_terminal`, and the request
   metadata they already provide) instead of duplicating command building and
   subprocess handling. The existing public interface of `scripts/bridgeV002/harness.py`
   (`resolve_harness`, `is_native`, `missing_env`, `describe_missing`,
   `build_launch_command`, `build_dsh_invocation`, `build_task_invocation`) is a
   consumer surface tested by the flow regression suite; keep it working while
   having it delegate to the standalone package where that removes duplication.
   You choose the exact division; do not leave two divergent command builders
   carrying the same harness logic.

3. Fix raw tmux multiline atomicity in `harness_terminal.py`. The terminal must
   accumulate a complete submission so that a 20k+ character prompt containing
   hundreds of embedded newlines is delivered to the harness as exactly one
   invocation, embedded newlines preserved verbatim. The submission Enter and the
   embedded newlines must be separable. One complete submitted prompt => exactly
   one harness invocation. (The standalone package already implements the
   accumulation/one-invocation behavior; prefer reusing it over re-implementing.)

4. Preserve the model boundary. DPMtF resolves the model target and passes it
   through; the harness never resolves or substitutes it. TG7 must stay green.

5. Preserve DPMtF regression. The flow regression suite
   (`tests/test_preferred_cloud_harness.py`, 41 tests) must stay green WITHOUT
   modifying existing test functions. If your rewire would break an existing
   assertion, change the seam's approach to keep the observable behavior the test
   asserts, rather than editing the test.

6. Prove the changed seam with ADD-only test growth (new test functions and/or a
   new test file). The new tests must, at minimum, prove that a multiline prompt
   submitted through the terminal produces exactly one harness invocation with
   embedded newlines preserved, and that the seam's execution path now delegates
   to the standalone package.

7. Leave the standalone package at `/home/svend/harness-allocator` unchanged. If
   you find its public API insufficient for the seam, do NOT modify it silently —
   report the specific gap under deviations/limitations in your result.

When implementation and validation are complete, write the governed result to:
`/home/svend/flows/preferred_cloud_harness/results/002-result.md`

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 002
```

If signaling fails, report the real failure; do not fabricate completion.
</task>

<scope>
MAY modify inside `/home/svend/DPMtF-WebUI`, only as required to consume Harness
Allocator and make raw tmux multiline injection reach the harness as one complete
submission:

- `scripts/bridgeV002/harness.py`
- `scripts/bridgeV002/harness_terminal.py`
- `scripts/bridgeV002/start_coding.py`
- `scripts/bridgeV002/dispatch.py`

MAY ADD (new files and/or new test functions only — do not modify existing
tests) test coverage proving the changed seam.

MAY READ (do not modify):

- `/home/svend/harness-allocator/` — the approved standalone package.

MUST NOT modify:

- `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`, `.env`
- governance files under `docs/governance-templates-v2/`
- `.git/` internals
- other flows' files
- the standalone package `/home/svend/harness-allocator/`
- existing test functions in `tests/test_preferred_cloud_harness.py`

Do not commit or push.
</scope>

<validation>
Run and read the real output of all applicable checks:

1. TG1 (flow regression, must stay green — all 41 tests):
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

5. Your new seam test(s) proving multiline => one invocation and delegation to
   the standalone package. Run them and paste the real output.

6. Inspect working-tree truth (this project IS a git repository):
```bash
cd /home/svend/DPMtF-WebUI && git status --short && git diff --stat
```

Paste real outputs in `002-result.md`.
</validation>

<constraint>
- No new runtime dependencies.
- No model resolution/substitution ownership; no silent model/harness fallback.
- No hardcoded `/home/svend/...` paths in reusable source — use config.py getters
  or environment variables.
- Raw tmux multiline input remains the external interaction assumption.
- No mandatory length-delimited/framed DPMtF transport protocol.
- Exactly one complete submitted prompt must produce exactly one harness invocation.
- Existing flow regression tests must stay green without editing them.
- ADD-only test growth.
- Do not commit/push/stage/stash/revert.
- Do not modify the standalone package at `/home/svend/harness-allocator`.
</constraint>

<deliverable>
`/home/svend/flows/preferred_cloud_harness/results/002-result.md` containing:

- files changed
- how the seam now consumes the standalone package (which primitives, which
  delegation boundary)
- the multiline accumulation / one-invocation approach taken
- tests/checks run with real output (including the new ADD-only tests)
- deviations or limitations (including any standalone-package API gap, if found)
- known follow-up work

Then signal completion exactly once as specified in `<task>`.
</deliverable>
