<role>You are imple-codex-minimaxM3 (Implementer) in the DPMtF preferred_cloud_harness flow.
Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>001</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
Run 001 of preferred_cloud_harness begins the carve-out: stand up
`/home/svend/harness-allocator` as a standalone, harness-neutral package that
owns the harness-generic surface extracted out of DPMtF — without breaking the
already-green flow.

Two corrections are binding for this run (Mission Contract `GOAL.md`,
§Architecture boundary and §Objective):

1. **The Model Allocator boundary.** Harness Allocator does **NOT** resolve,
   select, replace, or own the model. DPMtF resolves the model target first
   through Model Allocator and passes an already-resolved `model_target` in.
   The interface is `execute(role, harness, model_target, cwd, task)` — never
   `execute(role, harness, model, cwd, task)` — and there is no
   `resolve_model()`. `HarnessDefinition` describes harness identity and
   configuration only.
2. **Atomic semantic dispatch.** ONE complete semantic task = EXACTLY ONE
   harness invocation. Embedded newlines never define the request boundary; a
   length-delimited frame transports large multi-line tasks.

A staged reference prototype already exists under
`/home/svend/DPMtF-WebUI/harness-allocator-scaffold/harness-allocator/` and is
green (44 tests, stdlib-only, zero DPMtF coupling). This handoff materializes
the real package at the target path and proves it against the run's testgoals.
Treat the scaffold as reference material, not as the final destination: the
package must live and be proven at `/home/svend/harness-allocator`.

The Mission Contract you must read is:
`/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md`.
The product specification inside the target project (if it exists) is a
different `GOAL.md` — say which one you mean whenever you cite it.
</context>

<governance>
Key rules for this task:

1. **DO NOT COMMIT and DO NOT PUSH.** Leave every change unstaged. The Human
   reviews and commits.
2. **The package is stdlib-only.** `pytest` is the only test dependency. A
   third-party import is a park for the Human, not your call — say so in your
   result and stop.
3. **No model resolution anywhere in the package.** There is no `resolve_model`,
   no model selection, no silent model or harness substitution.
4. **No DPMtF coupling in the package.** No `bridge_roles`, no `sqlite3` against
   the bridge DB, no `scripts/bridgeV002` imports, no hardcoded machine paths in
   reusable code.
5. Python must pass `python3 -m py_compile` before you signal completion.
6. **Report only what you actually did.** Run `git status --short` and
   `git diff --stat` in the target project and let that output — not memory —
   decide what your report claims.
</governance>

<task>
Materialize the standalone `harness_allocator` package at
`/home/svend/harness-allocator` and prove it imports, is DPMtF-free, and its
suite is green.

**Step 1 — Understand the contract.**
Read the Mission Contract at
`/home/svend/flows/preferred_cloud_harness/runs/001/GOAL.md`: the Architecture
boundary, Objective items 1–8, and the ```testgoals block. Those are the WHAT
and the WHY; how you structure and implement the package is yours.

**Step 2 — Materialize the package.**
The target must end up as a stdlib-only Python package named `harness_allocator`
exposing, at minimum:

- `execute(role, harness, model_target, cwd, task)` returning a dict with at
  least `{status, output, error, elapsed, request_id, payload_chars,
  payload_lines, payload_sha256, harness, role, model_target}`.
- `HarnessDefinition` describing harness identity/configuration only — no model
  selection.
- A length-delimited framed transport: `encode_request(request_id, payload,
  retry=False)` and `extract_frame` / `FrameReader`, so a 20k+ character
  multi-line task round-trips as exactly ONE atomic frame.
- A persistent terminal loop (`run_terminal`) exposing RUNNING, HEARTBEAT,
  SUCCESS, ERROR and READY states, with PID and elapsed time where available,
  and duplicate-request protection: a completed `request_id` + payload `sha256`
  reports `DUPLICATE_REQUEST` and returns to READY without re-invoking the
  harness; only an explicit `retry` frame re-executes it.

**Step 3 — Test it.**
A pytest suite covering at minimum: the 20k+ character multi-line atomic
round-trip (one frame), request identity / payload metadata, the heartbeat and
READY lifecycle across repeated turns, handled ERROR -> READY, and
`DUPLICATE_REQUEST -> READY` with an explicit retry re-executing.

**Step 4 — Verify against the testgoals.**
Run each testgoal below and paste its real output in your result. A description
of what you did is not a measurement.

When ALL steps are complete and the testgoals are green:

1. Write your result to:
   `/home/svend/flows/preferred_cloud_harness/results/001-result.md`
2. SIGNAL completion:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
    --db-flow preferred_cloud_harness \
    --signal-complete --from-role imple-codex-minimaxM3 --id 001
```

3. **Read that command's output.** If it says `signal_complete_failed`, your
   result is not where dispatch looked — fix the path and signal again.
</task>

<scope>
Files you MAY create or modify — all inside the target project
`/home/svend/harness-allocator`:

- `harness_allocator/` — the package and every module it needs
- `tests/`
- `pyproject.toml`, `.gitignore`, `README.md`

Files you MUST NOT touch:

- Anything in `/home/svend/DPMtF-WebUI/` — the Father project, including the
  `harness-allocator-scaffold/` staging tree
- Anything under `/home/svend/flows/` except your own result file
- Governance files, `databases/dpmtf.db`, and `.git/` internals
- Any other repository or project directory

**Do not commit. Do not push. Do not create a branch.**
</scope>

<validation>
Before signaling completion, run and read (commands copied from the Mission
Contract's ```testgoals block, which is authoritative):

1. **TG2** — imports with no DPMtF coupling and no `resolve_model`:
   `cd /home/svend/harness-allocator && python3 -c "import harness_allocator as h; assert not hasattr(h,'resolve_model')"`

2. **TG3** — `execute()` returns the documented shape:
   `cd /home/svend/harness-allocator && python3 -c "from harness_allocator import execute; r=execute(role='probe', harness='codex', model_target='MiniMax-M3', cwd='.', task='x'); assert set(r) >= {'status','output','error','elapsed','request_id','payload_chars','payload_lines','payload_sha256','harness','role','model_target'}, r"`

3. **TG4** — no DPMtF coupling and no model resolution in the package:
   `grep -RInE "bridge_roles|sqlite3|DPMtF-WebUI|scripts/bridgeV002|resolve_model" /home/svend/harness-allocator/harness_allocator/ || true`
   (must print nothing)

4. **TG5** — package test suite green:
   `cd /home/svend/harness-allocator && python3 -m pytest tests -q`

5. **TG6** — a 20k+ character multi-line task round-trips as exactly ONE frame:
   `cd /home/svend/harness-allocator && python3 -c "from harness_allocator import encode_request, extract_frame; p='line\n'*5000; f,r=extract_frame(encode_request('ha-1',p)); assert r==b'' and f.payload==p and len(p)>=20000"`

6. **TG8** — a completed request_id/payload hash is not executed twice:
   `cd /home/svend/harness-allocator && python3 -c "import io; from harness_allocator import encode_request, FrameReader, run_terminal, SUCCESS, DUPLICATE_REQUEST; f=encode_request('ha-dup','same task'); r=FrameReader(io.BytesIO(f+f)); w=io.StringIO(); calls=[]; run_terminal(role='probe',harness='dsh',model_target='m',cwd='.',reader=r,writer=w,runner=lambda **k: calls.append(k) or {'status':SUCCESS,'output':'ok','error':'','elapsed':0.1,'pid':1,'request_id':k['request_id']}); out=w.getvalue(); assert len(calls)==1 and '[DUPLICATE_REQUEST]' in out and out.count('Status: READY')==3, (len(calls), out)"`

Also run `python3 -m py_compile` on every changed module, and `git status --short`
in the target project — only the files named in `<scope>`, nothing staged.
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.

- No new dependencies — stdlib plus pytest only.
- No model resolution or substitution anywhere in the package.
- No DPMtF coupling in the package.
- Stop after 2 failed attempts at the same problem — document it, do not guess.
- Execute ALL steps in `<task>`, especially the bridge signal.
</constraint>

<deliverable>
Your deliverable is an implementation report written to
`/home/svend/flows/preferred_cloud_harness/results/001-result.md` containing:

- files changed
- tests run, and their real pasted output (each of TG2, TG3, TG4, TG5, TG6, TG8)
- any deviations from the handoff
- known limitations

Then signal completion exactly as the `<task>` section instructs.
</deliverable>
