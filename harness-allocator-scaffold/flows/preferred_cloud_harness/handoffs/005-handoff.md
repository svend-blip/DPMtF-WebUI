<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>005</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
This is the first handoff of Run 002 — "Harness Terminal Runtime Hardening".
The authoritative Mission Contract is:
/home/svend/flows/preferred_cloud_harness/runs/002/GOAL.md — read it in full
before proceeding. (That is the run's Mission Contract; the product
specification is a separate /home/svend/harness-allocator/GOAL.md — do not
confuse the two.)

Run 001 established the standalone, stdlib-only `harness_allocator` package at
/home/svend/harness-allocator and rewired the DPMtF seam so
/home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py consumes that
package. It proved raw multiline terminal input is accumulated and delivered to
DeepSeek Harness as exactly one task / one invocation, and implemented request
identity, SHA-256 reporting, heartbeat/lifecycle visibility and
duplicate-request protection. Run 002 hardens that interactive runtime WITHOUT
expanding the architecture.

This handoff spans TWO repositories, both in-scope:
- /home/svend/harness-allocator (the standalone package — this flow's target
  project and your working directory), and
- /home/svend/DPMtF-WebUI (Father — the seam file harness_terminal.py and its
  test file only).

Four objectives, none of which may be dropped:
1. Safe Ctrl+C semantics (GOAL.md §2 Obj 1, §7).
2. Runtime status visibility (GOAL.md §2 Obj 2, §8).
3. Preserve raw multiline input (GOAL.md §2 Obj 3).
4. Preserve Run 001 lifecycle behavior (GOAL.md §2 Obj 4).

This is intentionally small. Do not overengineer, do not introduce a
process-supervisor framework, and do not expand scope.
</context>

<governance>
1. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md and the Mission Contract
   GOAL.md in full before acting.
2. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT. Leave changes unstaged for the
   Human (GOAL.md §14).
3. No new runtime dependencies, no new background daemons, no new databases, no
   new protocols.
4. Harness Allocator never resolves, selects, replaces or owns the model. There
   is no `resolve_model()` in Harness Allocator, and no silent model or harness
   substitution (GOAL.md §4).
5. Model Allocator is the sole model/runtime authority; `model_target` is
   already resolved before Harness Allocator receives it.
6. Record the in-scope working-tree baseline at handoff start (git status/diff
   in BOTH repositories) so pre-existing dirty files are not attributed to this
   handoff (GOAL.md §5).
7. Report only measured results. Never invent command output. If a validation
   step cannot run in your environment, say so plainly and move on (512).
8. Stop after two failed attempts against the same problem; document the actual
   failure and return it to the Supervisor rather than guessing (GOAL.md §10).
9. Do not modify dispatch.py unless a proven blocker requires it — and even then
   do not modify it: report the blocker instead (GOAL.md §10).
</governance>

<task>
Implement the four Run 002 objectives inside the scope fence. Read the Mission
Contract GOAL.md sections 2, 7 and 8 before and while you work.

Step 1 — Understand current state.
Read the current code you will change:
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py
- /home/svend/harness-allocator/harness_allocator/terminal.py
- /home/svend/harness-allocator/harness_allocator/status.py
- /home/svend/harness-allocator/harness_allocator/invoke.py
- both test files named in <scope>.

Objective 1 — Safe Ctrl+C semantics (GOAL.md §2 Obj 1, §7).
Before changing anything, investigate and DOCUMENT the current runtime
behavior, distinguishing at least (GOAL.md §7):
1. Ctrl+C while Harness Terminal is READY.
2. Ctrl+C while DeepSeek Harness is RUNNING.
3. Whether SIGINT reaches the terminal, the harness child, both, or the tmux
   shell/process group.
4. Whether a cancelled child remains running.
5. Whether the terminal can safely return to READY.
Then implement so that:
- READY + Ctrl+C -> deterministic, documented behavior, and no stale harness
  child process left behind.
- RUNNING + Ctrl+C -> cancels/terminates ONLY the currently active harness child
  execution; does NOT terminate unrelated tmux sessions or processes; the
  terminal stays alive and returns to a known state (READY is the intended
  post-cancel state).
- If graceful-to-forced escalation is required, it is bounded and documented.
- No orphan harness process remains after a successful cancellation.
Use normal process/signal semantics. Do NOT introduce a process-supervisor
framework merely to implement cancellation (GOAL.md §7).

Objective 2 — Runtime status visibility (GOAL.md §2 Obj 2, §8).
Expose, when the information is available: flow, role, harness, model target,
cwd, terminal mode, current lifecycle state, sandbox mode, approval policy,
workspace access mode, the configured bridge-dir access state (the configured
bridge directory, not a hardcoded literal), and MCP-Light state as one of
connected | available | unavailable | not configured.
- Unknown information MUST be shown honestly as "unknown" / "not configured",
  never guessed.
- The display MUST NOT expose API keys, credentials, tokens or secrets.
- Values MUST come from real configuration/runtime information where available;
  do NOT infer workspace-write or full-access merely because a write happened to
  succeed (GOAL.md §8).
- Keep it compact (the layout in GOAL.md §8 is illustrative, not a byte-for-byte
  requirement).
- MCP-Light here is a read-only state LABEL, not integration — integration is an
  explicit non-goal (GOAL.md §3), so the field will honestly report "not
  configured" (or the actual state) without implementing connectivity.

Objective 3 — Preserve raw multiline input (GOAL.md §2 Obj 3).
Prove the binding invariant still holds: one Human submission produces exactly
ONE request, ONE request_id, ONE task payload and ONE harness invocation;
embedded newlines preserved; never line-by-line tmux dispatch. Retain the
existing idle-bounded accumulation reader unless a strictly smaller or safer
correction is necessary (GOAL.md §2 Obj 3).

Objective 4 — Preserve Run 001 lifecycle (GOAL.md §2 Obj 4).
Keep READY -> DISPATCH -> RUNNING -> SUCCESS | ERROR -> READY functional, along
with request identity, SHA-256 reporting, heartbeat/lifecycle visibility and
duplicate-request protection. A CANCELLED state/token may be added if required,
but existing status semantics must stay backward compatible unless a test proves
a correction is necessary.

Then write the governed result (real outputs only) and signal completion exactly
once as specified in <deliverable>.
</task>

<scope>
MAY modify (only when necessary, and only these files):
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py
- /home/svend/harness-allocator/harness_allocator/terminal.py
- /home/svend/harness-allocator/harness_allocator/status.py
- /home/svend/harness-allocator/harness_allocator/invoke.py

MAY ADD tests (new test functions only — do NOT modify existing test functions):
- /home/svend/DPMtF-WebUI/tests/test_preferred_cloud_harness.py
- /home/svend/harness-allocator/tests/test_harness_allocator.py

MAY update documentation directly associated with changed behavior:
- /home/svend/harness-allocator/README.md

MAY READ (do not modify):
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness.py (for the TG8
  resolve_harness regression check)
- any other file needed to implement safely.

MUST NOT modify:
- app.py, config.py, scripts/init_db.py, dpmtf.ini, .env
- governance files under docs/governance-templates-v2/
- .git/ internals
- scripts/bridgeV002/dispatch.py, scripts/bridgeV002/harness.py,
  scripts/bridgeV002/start_coding.py, scripts/bridgeV002/start_tmuxflow.py
- ANY existing test function in either in-scope test file (ADD-only growth)
- /home/svend/AI-Genealogy-Research-Assistant (any path) — forbidden
- any path outside the fence

Do not commit or push.
</scope>

<validation>
Run and paste the real output of all applicable checks before signaling
completion. TG1–TG9 are the implementer's automated checks; TG10 is
Human-observed live acceptance and is NOT yours to claim — state explicitly in
your result that TG10 remains for the Human.

TG1 — DPMtF regression suite stays green:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q
```

TG2 — standalone harness_allocator regression suite stays green:
```bash
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

TG3 — multiline atomicity: an automated test MUST prove a 20k+ character task
containing many embedded newlines produces exactly one logical request and
exactly one harness runner invocation with the complete payload preserved.

TG4 — Ctrl+C during RUNNING: an automated test with a controllable long-running
child (or equivalent deterministic runner) MUST prove it cancels only the active
harness execution, returns the terminal to READY, and leaves no orphan child.

TG5 — Ctrl+C while READY: an automated test where practical, plus documentation
evidence, proving the behavior is deterministic and documented.

TG6 — runtime status: an automated output test MUST prove the status display
exposes flow, role, harness, model target, cwd, lifecycle state and the
available sandbox/access metadata WITHOUT exposing secrets.

TG7 — lifecycle: automated tests MUST prove READY -> DISPATCH -> RUNNING ->
SUCCESS | ERROR -> READY, and preserve request identity and duplicate-request
behavior.

TG8 — backward-compatible harness resolution:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "from scripts.bridgeV002 import harness; assert harness.resolve_harness({'allocator_client':'dsh'}) == 'dsh'"
```

TG9 — compile every changed Python module:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/harness_terminal.py
cd /home/svend/harness-allocator && python3 -m py_compile harness_allocator/terminal.py harness_allocator/status.py harness_allocator/invoke.py
```
If a listed module is not part of the final implementation or was not changed,
report that honestly rather than inventing validation output (GOAL.md §6 TG9).

Paste the real outputs into 005-result.md. Never fabricate output.
</validation>

<constraint>
- No new runtime dependencies.
- No model resolution/substitution ownership; no silent model or harness
  fallback; no resolve_model() in Harness Allocator.
- No hardcoded /home/svend/... paths in reusable source — locate the standalone
  package and the bridge directory through configuration (config getters or env),
  not literals. (Absolute paths in this handoff and in the Mission Contract are
  instructions, not a license to hardcode them in source.)
- Raw tmux multiline input remains the external interaction assumption; keep the
  idle-bounded accumulation reader — no new framed DPMtF transport protocol.
- Exactly one complete submitted prompt must produce exactly one harness
  invocation.
- Existing tests in both suites must stay green WITHOUT editing them; ADD-only
  growth. Do not weaken existing assertions (GOAL.md §9).
- No process-supervisor framework, no new daemons, no new databases.
- Do not commit/push/stage/stash/revert.
- Do not modify dispatch.py (report a blocker instead).
- Do not modify /home/svend/AI-Genealogy-Research-Assistant or any out-of-fence
  path.
- Report only measured results; if two patch attempts fail against the same
  problem, stop and report the actual failure.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/005-result.md containing:
- the in-scope working-tree baseline you recorded at handoff start (both repos)
- the Ctrl+C investigation findings (GOAL.md §7, itemised)
- files changed (only what `git status --short` / `git diff --stat` shows)
- tests run with their real output (TG1–TG9)
- any deviations from this handoff, and known limitations
- an explicit statement that TG10 remains for the Human

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 005
```

Read the command's output. If it reports `signal_complete_failed`, your result
is not at the path dispatch looked for — fix the path and signal again. Do not
fabricate completion.
</deliverable>
