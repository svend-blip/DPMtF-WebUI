<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>012</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
This is the sixth governed handoff of Run 003. It is a NARROW defect-fix handoff
with exactly one target: the materialize idempotency semantics in the broker.
Handoff 011's live acceptance exposed a REAL functional defect in handoff 010's
deliverable: `bridge_broker.py materialize --type run-ledger|backlog` silently
drops a SECOND write for the same run. Run 003's governed handoff budget has been
amended by the Human to 7; 012 fixes the defect, 013 is reserved for the clean
end-to-end autonomous-chain acceptance (TG5-TG8, TG13).

Read these artifacts before acting. They are the facts you build on:

  /home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md        (Mission Contract; the budget amendment is at the END — read it in full)
  /home/svend/flows/preferred_cloud_harness/runs/003/BACKLOG.md     (run plan; read the "NEW DEFECT" section)
  /home/svend/flows/preferred_cloud_harness/runs/003/RUN-LEDGER.md  (run memory; read the latest wake-up)
  /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py       (the broker; the defect is in cmd_materialize's idempotency check)
  /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py               (the test suite; one test currently codifies the defect)

THE DEFECT (read from bridge_broker.py cmd_materialize, the idempotency check):
the check skips enqueue if ANY 'completed' row exists for (flow_key, run_id,
artifact_type). Run-ledger is APPEND mode and backlog is REPLACE mode — both are
meant for MULTIPLE writes across wake-ups — yet the idempotency gate makes them
one-shot per run. Once a run has a completed run-ledger and backlog row (as run
003 now does), every subsequent append/replace is silently dropped (exit 0, no
new row). This blocks the supervisor's normal bookkeeping.
</context>

<governance>
1. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md and the Mission Contract GOAL.md
   (/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md) in full, including
   the budget amendment at the end, before acting.
2. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT (GOAL.md §14). Leave changes
   unstaged for the Human.
3. This handoff authorizes ONLY the materialize idempotency-semantics fix and its
   tests. It does NOT authorize any §4 non-goal (MCP-Light, /skill, new Harness
   Allocator architecture, danger-full-access, unrelated repositories).
4. Do NOT modify /home/svend/model-allocator, config.py, dispatch.py, or any file
   outside the scope fence below. A residual defect whose only fix lives out of
   fence is a scope-fence finding — report it, do not edit it.
5. Do NOT weaken any existing assertion or production behavior merely to obtain
   green tests (GOAL.md §9). The only behavior that changes is the idempotency
   semantics specified below.
6. Report only measured results. Never invent command output.
7. Stop after two failed patch attempts against the same problem; document the
   actual failure and return it rather than guessing.
8. Do NOT use danger-full-access or --dangerously-bypass-approvals-and-sandbox.
9. Preserve canonical destination derivation: the materialize path MUST NOT accept
   any arbitrary/caller-supplied destination path (the Human amendment binding
   constraint). Do not add a destination flag or path parameter.
10. The evidence gate and scope-fence validation MUST remain active (TG11).
11. No schema change, no migration file, no new column — compare content directly.
</governance>

<task>
One implementation, in order. Fix the idempotency semantics in bridge_broker.py
cmd_materialize and extend the test suite. No schema change is required.

PART A — CONFIRM THE DEFECT (read-only, one command).
  Run the existing broker test suite and confirm it is green (48 tests). This
  proves the CURRENT behavior, including the one-shot test that codifies the
  defect. Record the real output.
    cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_bridge_broker.py -q

PART B — FIX THE IDEMPOTENCY SEMANTICS (in-fence, bridge_broker.py only).

  Replace the idempotency check in cmd_materialize with these EXACT semantics.
  Keep everything else unchanged: canonical destination derivation, validation,
  the append/replace/create write modes, host-side-only write, and the
  sandbox-safe DB-only enqueue.

  1. handoff (create) — UNCHANGED. A request is a no-op (exit 0, no new row) if
     any 'completed' row exists for (flow_key, handoff_id, 'handoff'). The
     exclusive-create and refuse-overwrite behavior is preserved.

  2. end-report (replace, one-shot) — UNCHANGED. A request is a no-op if any
     'completed' row exists for (flow_key, run_id, 'end-report'). The
     refuse-overwrite behavior is preserved.

  3. run-ledger (append) — MULTI-WRITE. A request enqueues a NEW row unless there
     already exists a row for (flow_key, run_id, 'run-ledger') whose status is
     'pending' or 'completed' AND whose content is identical (exact string
     equality) to the requested content; in that case the request is a no-op
     (exit 0, no new row). A 'failed' row never suppresses a request (retry is
     always allowed).

  4. backlog (replace) — MULTI-WRITE. Identical semantics to run-ledger: a new row
     is enqueued unless a 'pending' or 'completed' row for
     (flow_key, run_id, 'backlog') already holds identical content.

  Net effect: a second run-ledger append with DIFFERENT content is enqueued (not
  dropped); a second backlog replace with DIFFERENT content is enqueued (not
  dropped); an immediate repeat of IDENTICAL content is dropped (no duplicate
  content); a retry after a 'failed' row is allowed.

  Update the cmd_materialize docstring and any stale comment to describe the new
  semantics. Do NOT change the _ARTIFACT_MODE mapping or the
  _write_materialize_artifact write path.

PART C — TESTS (in-fence, tests/test_bridge_broker.py only).

  1. REPLACE the existing test_materialize_is_idempotent_for_completed_rows — it
     currently asserts the DEFECTIVE one-shot behavior (a second backlog replace
     with different content is skipped). It must now assert the corrected
     multi-write semantics.

  2. ADD at least these behaviors (use the existing tmp_bridge_and_db fixture —
     NEVER write to the real /home/svend/flows during tests):
     a. run-ledger: a second append with different content produces a second
        append (the file holds both entries).
     b. backlog: a second replace with different content replaces the file.
     c. run-ledger: an immediate repeat of identical content does NOT enqueue a
        new row and does NOT duplicate content.
     d. backlog: an immediate repeat of identical content does NOT enqueue a new
        row and does NOT duplicate content.
     e. run-ledger and backlog: a request after a 'failed' row is enqueued
        (retry allowed), including retry with the SAME content that failed.
     f. handoff: remains idempotent per handoff_id (a second materialize for the
        same id is a no-op; the file is not overwritten).
     g. end-report: remains idempotent per run_id (a second materialize for the
        same run is a no-op).
     h. (preserve) the canonical-destination and no-arbitrary-path tests stay green.

  3. Keep every OTHER existing test green. Do not weaken any assertion.

PART D — WRITE THE RESULT. Write 012-result.md with the real outputs (Part A
baseline, Part B explanation, Part C test run, and the regression suites below).

PART E — COMPLETE VIA THE BROKER SEAM (TG7). Signal completion through the broker,
exactly as the injected chain_advancement block instructs (NOT via dispatch.py
--signal-complete directly):
    nohup python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py \
      enqueue --flow preferred_cloud_harness --from-role imple-codex-minimaxM3 \
      --to-role imple-codex-minimaxM3 --id 012 --action signal-complete \
      > /tmp/bridge-enqueue-preferred_cloud_harness-012.log 2>&1 &
  Then check `bridge_broker.py status --queue dispatch` and confirm the row is
  'completed'. If it is 'failed', read error_msg and report it in your result —
  do not fabricate completion.
</task>

<scope>
MAY modify — exactly these two files, and nothing else:

- /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py
- /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py

MUST NOT change any other file, including:

- /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py
- /home/svend/DPMtF-WebUI/config.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/gate-deliverable-evidence.py
- /home/svend/DPMtF-WebUI/app.py
- /home/svend/DPMtF-WebUI/scripts/init_db.py
- /home/svend/DPMtF-WebUI/dpmtf.ini
- /home/svend/DPMtF-WebUI/.env
- /home/svend/DPMtF-WebUI/scripts/db/ (any migration file)
- /home/svend/model-allocator/ (any path)
- /home/svend/harness-allocator/ (any path — this is NOT a Harness Allocator feature)
- /home/svend/AI-Genealogy-Research-Assistant/ (any path)
- /home/svend/DPMtF-WebUI/databases/dpmtf.db (runtime writes only — do not hand-edit)

Do not commit or push.
</scope>

<validation>
Run and paste the real output of every applicable check before signalling
completion. Keep all commands POSIX (no $'...', no arrays, no [[ ]]).

Broker tests (TG11):
  cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_bridge_broker.py -q

Regression (TG12):
  cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py tests/test_supervisor_state.py -q
  cd /home/svend/harness-allocator && python3 -m pytest tests -q

Syntax for every in-fence file you change:
  python3 -m py_compile \
    /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py \
    /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py

Paste the real outputs into 012-result.md. Never fabricate output. If two patch
attempts fail against the same problem, stop and report the actual failure.
</validation>

<constraint>
- Narrow idempotency-semantics fix only — no other behavior change.
- No schema change, no migration, no new column.
- Canonical destination derivation remains mandatory; no arbitrary host path.
- No dispatch.py / config.py / model-allocator / migration-file change.
- No danger-full-access / --dangerously-bypass-approvals-and-sandbox.
- Evidence gate and scope-fence validation remain active (TG11).
- Do not weaken existing assertions (GOAL §9).
- Do not commit/push/stage/stash/revert.
- Report only measured results; stop after two failed patch attempts on the same problem.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/012-result.md containing:
- the in-scope working-tree baseline at handoff start (git status --short in
  /home/svend/DPMtF-WebUI)
- Part A: baseline test run (48 tests) with real output
- Part B: the idempotency semantics change with a concise diff summary
- Part C: the new/updated tests with real test output
- Part D: TG11/TG12 real outputs, and an explicit note of which testgoals are
  affected (TG5-live/TG6-TG8/TG13 are NOT re-run here — reserved for 013)

Then signal completion exactly once via the broker seam (Part E). Read the queue
status afterward; if the row is 'failed', report the error_msg — do not fabricate
completion.
</deliverable>
