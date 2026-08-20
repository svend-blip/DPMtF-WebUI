<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>006</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
This is a Human-authorized, narrowly bounded Run 002 scope expansion. Its only
purpose is to make TG1 truthfully green. It does NOT redesign handoff 005 —
that implementation is APPROVED and stays exactly as delivered.

The authoritative Mission Contract is:
/home/svend/flows/preferred_cloud_harness/runs/002/GOAL.md — read it in full
before proceeding. (That is the run's Mission Contract; the product
specification is a separate /home/svend/harness-allocator/GOAL.md — do not
confuse the two.)

Background: handoff 005's reviewer verdict is APPROVED, but TG1 is red as
literally specified (no --deselect) for two test-file-only reasons:
1. test_seam_idle_reader_handles_eintr uses a fake stream that re-serves the
   same bytes forever and never idles/EOFs, so it cannot model a real
   terminal. It is a broken fixture, not a seam defect.
2. The five new seam tests added in 005 were accidentally defined twice; the
   first copy is shadowed by the second (module-level redefinition), so pytest
   collects 5, not 10 — dead duplicate code.

The Human has authorized a scope expansion confined to ONE file to repair both.
</context>

<governance>
1. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md and the Mission Contract
   GOAL.md in full before acting.
2. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT. Leave changes unstaged for the
   Human (GOAL.md §14).
3. This handoff authorizes modification of EXACTLY ONE file:
   /home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py
   Nothing else.
4. Do NOT modify production source. If you discover a genuine production
   defect that would force a production change, STOP and PARK for Human
   approval — do not edit production code.
5. Do NOT weaken any existing assertion or production behavior merely to
   obtain green tests.
6. Do NOT modify /home/svend/AI-Genealogy-Research-Assistant or any other
   repository.
7. Report only measured results. Never invent command output.
8. Stop after two failed patch attempts against the same problem; document the
   actual failure and return it rather than guessing (GOAL.md §10).
</governance>

<task>
Two changes, both inside /home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py:

1. Repair test_seam_idle_reader_handles_eintr so it models a FINITE, realistic
   EINTR + idle-input condition. The fake stream MUST NOT re-serve the same
   bytes forever: it must raise EINTR exactly once, then serve the data
   exactly once, then go idle/EOF. Preserve the test's original intent:
   EINTR -> IDLE_READ_INTERRUPTED sentinel; clear() discards the interrupted
   state; a subsequent read returns the single real frame.

2. Verify the two "Run 002 ADD-only growth" blocks are genuinely identical and
   shadowed (the first copy is dead because module-level redefinition means
   only the second copy is collected), then remove the FIRST (shadowed) copy
   and keep the superseding copy. After removal, each of the five seam test
   functions and the two helper functions must appear exactly once.

Do not change anything else in the file, and do not change any other file.
</task>

<scope>
MAY modify (only this one file):
- /home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py

MUST NOT modify:
- any production source (including scripts/bridgeV002/harness_terminal.py and
  /home/svend/harness-allocator/harness_allocator/*)
- any other test file
- app.py, config.py, scripts/init_db.py, dpmtf.ini, .env
- governance files under docs/governance-templates-v2/
- .git/ internals
- scripts/bridgeV002/dispatch.py, scripts/bridgeV002/harness.py,
  scripts/bridgeV002/start_coding.py, scripts/bridgeV002/start_tmuxflow.py
- /home/svend/AI-Genealogy-Research-Assistant (any path) — forbidden
- any path outside the fence

Do not commit or push.
</scope>

<validation>
Run and paste the real output of every applicable check before signalling
completion.

TG1 (literal, NO --deselect):
```bash
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q
```
Must be fully green (no failure, no deselection).

Then re-run the relevant coverage subsets to prove the repair did not weaken
coverage (Ctrl+C, multiline, lifecycle, status, duplicate-protection):

```bash
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -v -k "eintr or cancel or sigint or multiline or atomicity or collect_runtime_status or render_banner or duplicate" --no-header
```

And the standalone suite (unchanged, must stay green):
```bash
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

Paste the real outputs into 006-result.md. Never fabricate output.
</validation>

<constraint>
- Exactly one in-scope file; no production changes.
- Do not weaken existing assertions (GOAL.md §9).
- No new runtime dependencies, daemons, databases or protocols.
- Do not commit/push/stage/stash/revert.
- Do not modify dispatch.py (report a blocker instead).
- Do not modify /home/svend/AI-Genealogy-Research-Assistant or any out-of-fence
  path.
- Report only measured results; if two patch attempts fail against the same
  problem, stop and report the actual failure.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/006-result.md containing:
- the in-scope working-tree baseline you recorded at handoff start
  (git status --short in /home/svend/DPMtF-WebUI)
- the two changes, described precisely
- tests run with their real output (TG1 + relevant subsets + standalone)
- an explicit statement that TG10 remains Human-observed (already obtained in
  Run 002) and that this handoff does NOT fabricate any additional Human
  observation

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 006
```

Read the command's output. If it reports `signal_complete_failed`, your result
is not at the path dispatch looked for — fix the path and signal again. Do not
fabricate completion.
</deliverable>
