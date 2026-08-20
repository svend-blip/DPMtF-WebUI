<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>004</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
Run 001 is functionally complete. Handoff 001 materialized the standalone,
stdlib-only `harness_allocator` package at `/home/svend/harness-allocator`
(verdict APPROVED). Handoff 002 rewired the DPMtF harness-generic seam so
`scripts/bridgeV002/harness.py` and `scripts/bridgeV002/harness_terminal.py`
consume that package and fix raw tmux multiline atomicity (verdict APPROVED).
Handoff 003 closed objectives 5 (request identity), 6 (heartbeat/lifecycle) and
7 (duplicate-request protection) in the terminal and proved the 20k+ multiline
raw-tmux one-invocation path (verdict APPROVED, re-evaluated on in-scope
evidence after the Human cleared an out-of-fence finding in an unrelated
repository).

All eight testgoals (TG1–TG8) are green. The flow regression suite
`tests/test_preferred_cloud_harness.py` holds 56 tests (41 original + 11 seam +
4 ADD-only), all passing, and the standalone package's 51 tests are unchanged
and passing.

This is the FINAL pass. Its purpose is confirmation and closure: re-verify the
complete state, apply final in-scope remediation only if a real defect is
found, and report so the supervisor can write the END-REPORT and close the run.

Do NOT introduce new work, refactors, or scope expansion. This is a
confirmation-and-closure pass, not a new feature handoff. If nothing is
broken, a clean confirmation with the real measured outputs is the correct
result — changing working code to look busy is a defect, not diligence.

The authoritative Mission Contract is:
`/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md`.
Read it before proceeding.

Binding architectural rules (unchanged from handoffs 001–003):

1. Model Allocator is the sole model/runtime authority. DPMtF resolves the model
   target first and passes the resolved `model_target` to Harness Allocator.
   Harness Allocator never resolves, selects, replaces, or owns the model, and
   there is no silent model or harness substitution.
2. Raw tmux multiline injection remains the supported interaction model: the
   terminal accumulates the full submission (idle-bounded byte accumulation), the
   submission Enter triggers post-processing, and the complete accumulated text
   reaches the selected harness as exactly one prompt / one invocation. Run 001
   does NOT introduce a length-delimited or framed DPMtF transport protocol.
</context>

<governance>
1. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT. Leave changes unstaged for the Human.
2. No new runtime dependencies. `harness_allocator` is a local companion package,
   not a third-party dependency.
3. No `resolve_model()` or model-selection ownership; no silent model/harness
   substitution.
4. No hardcoded `/home/svend/...` paths in reusable source. Locate the standalone
   package through `config.py` getters or the `HARNESS_ALLOCATOR_PATH` env var.
   `config.py` itself is out of scope and MUST NOT be edited.
5. Do not redesign DPMtF flows, roles, verdict handling or governance.
6. Do not replace raw tmux injection with a new externally visible transport protocol.
7. Report only measured results. Never invent test output. If a validation step
   cannot run in your environment, say so plainly and move on.
8. Stop after two failed attempts at the same problem and report the blocker.
9. Do NOT modify `/home/svend/AI-Genealogy-Research-Assistant` or any path
   outside the scope fence. This is strictly forbidden by the Human.
</governance>

<task>
Final review/remediation pass. Required outcomes:

1. Re-run all eight testgoals (TG1–TG8) and confirm every one is green. Paste
   the real output of `check_testgoals.py` against the Mission Contract.

2. Confirm the standalone package at `/home/svend/harness-allocator` is
   unchanged and its 51 tests still pass (read-only — do not modify it).

3. Confirm working-tree scope. `git status --short` and `git diff --stat` in
   `/home/svend/DPMtF-WebUI` must show only this run's in-fence files. Report
   any in-fence file that is unexpected.

4. Confirm (read-only, do not modify) that no out-of-fence repository was
   touched by this handoff — including `/home/svend/AI-Genealogy-Research-Assistant`.

5. Remediate ONLY if a real defect in the in-scope seam is found during this
   pass. If nothing is broken, change nothing and say so explicitly.

6. `py_compile` every in-scope module.

7. Write the governed result with the real outputs.

When implementation and validation are complete, write the governed result to:
`/home/svend/flows/preferred_cloud_harness/results/004-result.md`

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 004
```

If signaling fails, report the real failure; do not fabricate completion.
</task>

<scope>
MAY modify inside `/home/svend/DPMtF-WebUI`, only if a real in-scope defect is
found and only in these four files:

- `scripts/bridgeV002/harness.py`
- `scripts/bridgeV002/harness_terminal.py`
- `scripts/bridgeV002/start_coding.py`
- `scripts/bridgeV002/dispatch.py`

MAY ADD (new test functions only — do not modify existing tests) coverage
proving any fix.

MAY READ (do not modify):

- `/home/svend/harness-allocator/` — the approved standalone package.

MUST NOT modify:

- `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`, `.env`
- governance files under `docs/governance-templates-v2/`
- `.git/` internals
- other flows' files
- the standalone package `/home/svend/harness-allocator/`
- ANY existing test function in `tests/test_preferred_cloud_harness.py`
- `/home/svend/AI-Genealogy-Research-Assistant` (any path) — strictly forbidden

Do not commit or push.
</scope>

<validation>
Run and paste the real output of all applicable checks:

1. All eight testgoals:
```bash
cd /home/svend/DPMtF-WebUI && \
python3 scripts/bridgeV002/check_testgoals.py \
  /home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md
```

2. Standalone package regression (must stay green):
```bash
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

3. Compile every in-scope module:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile \
  scripts/bridgeV002/harness.py \
  scripts/bridgeV002/harness_terminal.py \
  scripts/bridgeV002/start_coding.py \
  scripts/bridgeV002/dispatch.py
```

4. Working-tree truth (this project IS a git repository):
```bash
cd /home/svend/DPMtF-WebUI && git status --short && git diff --stat
```

5. Out-of-fence check (read-only; do not modify):
```bash
cd /home/svend/AI-Genealogy-Research-Assistant && git status --short
```

Paste real outputs in `004-result.md`.
</validation>

<constraint>
- No new runtime dependencies.
- No model resolution/substitution ownership; no silent model/harness fallback.
- No hardcoded `/home/svend/...` paths in reusable source.
- Raw tmux multiline input remains the external interaction assumption; keep the
  idle-bounded accumulation reader — no new framed DPMtF transport protocol.
- Exactly one complete submitted prompt must produce exactly one harness invocation.
- The 56 existing regression tests (41 original + 11 seam + 4 new) must stay
  green without editing them; ADD-only growth.
- Do not commit/push/stage/stash/revert.
- Do not modify the standalone package at `/home/svend/harness-allocator`.
- Do not modify `/home/svend/AI-Genealogy-Research-Assistant` or any out-of-fence path.
</constraint>

<deliverable>
`/home/svend/flows/preferred_cloud_harness/results/004-result.md` containing:

- confirmation that TG1–TG8 are all green (with real output)
- confirmation the standalone package is unchanged and its tests pass
- confirmation of working-tree scope (`git status` / `git diff`)
- any remediation applied (if any) with its tests and real output
- an explicit statement that no out-of-fence path was modified

Then signal completion exactly once as specified in `<task>`.
</deliverable>
