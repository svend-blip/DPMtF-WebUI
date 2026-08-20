<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>010</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
This is the fourth governed handoff of Run 003. It implements the narrow governed
broker artifact-materialization capability that closes Objective 3 (supervisor
authoritative bridge write), authorized by a Human GOAL.md amendment that raised
the run budget from 4 to 5.

Read these artifacts before acting. They are the facts you build on:

  /home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md        (Mission Contract; the Human Amendment is at the END — read it in full)
  /home/svend/flows/preferred_cloud_harness/results/009-result.md   (the broker you are EXTENDING)
  /home/svend/flows/preferred_cloud_harness/verdicts/009-verdict.md (APPROVED; note the non-blocking follow-up on test coverage)
  /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py       (current broker, 436 lines)
  /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py               (current 15-test suite, 481 lines)

WHY THIS HANDOFF EXISTS: handoff 009 delivered the bridge/tmux broker — the
signal-transition seam (enqueue / daemon / status) that crosses the supervisor's
sandbox boundary through the writable DPMtF DB. What 009 did NOT deliver is a
file-WRITE seam. The supervisor still cannot write its own governed artifacts
(handoffs/*.md, RUN-LEDGER.md, BACKLOG.md, END-REPORT.md) to
/home/svend/flows/preferred_cloud_harness/ — its sandbox mounts that path
READ-ONLY (re-probed: touch -> Errno 30). This handoff adds a NARROW, governed
artifact-materialization action to the broker so the supervisor can write those
four artifacts to their canonical destinations without gaining unrestricted
/home/svend/flows access.

THE BINDING CONSTRAINT (from the Human amendment — do not deviate): the
materialization capability MUST NOT accept arbitrary host paths. Canonical
destinations MUST be derived from flow/run/handoff identity and an enumerated
artifact type. This is the single most important requirement of this handoff.
</context>

<governance>
1. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md and the Mission Contract GOAL.md
   (/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md) in full, including
   the Human Amendment at the end, before acting.
2. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT (GOAL.md §14). Leave changes
   unstaged for the Human.
3. This handoff authorizes ONLY the narrow broker materialization capability for
   Objective 3 / TG5. It does NOT authorize the §4 non-goals (MCP-Light, /skill,
   new Harness Allocator architecture, danger-full-access, unrelated repositories).
4. Do NOT modify /home/svend/model-allocator, config.py, dispatch.py, or any file
   not in the scope fence below. A residual defect whose only fix lives out of
   fence is a scope-fence finding — report it, do not edit it.
5. Do NOT weaken any existing assertion or production behavior merely to obtain
   green tests (GOAL.md §9).
6. Report only measured results. Never invent command output.
7. Stop after two failed patch attempts against the same problem; document the
   actual failure and return it rather than guessing.
8. Do NOT use danger-full-access or --dangerously-bypass-approvals-and-sandbox
   under any reading of this handoff (GOAL.md §4.4).
9. The materialization action MUST NOT accept arbitrary host paths. The destination
   is COMPUTED from (flow, run, handoff id, artifact type), never caller-supplied.
   Reject any caller-supplied destination path.
10. The evidence gate and scope-fence validation MUST remain active. The
    materialization action must never disable or bypass them (TG11, GOAL.md §8/§12).
11. Do NOT give any role unrestricted /home/svend/flows or host tmux access
    (GOAL.md §5). No model-allocator change. No MCP-Light. No /skill.
12. Preserve the manual recovery path: a Human must still be able to write the
    artifacts directly and run dispatch.py directly (GOAL.md §9).
</governance>

<task>
One implementation, in order. EXTEND the existing broker; do not redesign it.

PART A — CONFIRM YOUR BOUNDARY (read-only, fast). 009-result already measured
this session's boundary. Re-confirm only the two write facts you depend on, with
one command each, and record the real output:

  1. /home/svend/flows/preferred_cloud_harness/ is WRITABLE from this session:
     create then delete a temp file (.run003_tg10_probe_$$). 009-result/verdict
     already established this.
  2. The DPMtF DB (/home/svend/DPMtF-WebUI/databases/dpmtf.db) is readable AND
     writable from this session.

The DB remains the chosen content-transport seam (the supervisor can reach it
from inside its sandbox; it cannot reach /home/svend/flows). Record every
command and its real output in 010-result.md.

PART B — IMPLEMENT THE MATERIALIZATION ACTION (in-fence). Add a new `materialize`
capability to bridge_broker.py with these exact requirements:

  1. ENUMERATED ARTIFACT TYPES (exactly these four; reject anything else):
       backlog     -> create/replace   runs/<run>/BACKLOG.md
       run-ledger  -> create/append    runs/<run>/RUN-LEDGER.md
       handoff     -> create           handoffs/<id:03d>-handoff.md   (explicit id)
       end-report  -> create/replace   runs/<run>/END-REPORT.md

  2. CANONICAL DESTINATION, computed — never caller-supplied. Derive from
     (flow_key, run_id, handoff_id, artifact_type):
       backlog    -> {bridge_dir}/{flow_key}/runs/{run_id}/BACKLOG.md
       run-ledger -> {bridge_dir}/{flow_key}/runs/{run_id}/RUN-LEDGER.md
       handoff    -> {bridge_dir}/{flow_key}/handoffs/{handoff_id:03d}-handoff.md
       end-report -> {bridge_dir}/{flow_key}/runs/{run_id}/END-REPORT.md
     where {bridge_dir} is the configured bridge dir (/home/svend/flows). The
     materialization code path MUST NOT accept any arbitrary destination path.
     If a caller supplies a destination path, reject it — the destination is
     always computed from identity + type.

  3. VALIDATION before any write; reject on any failure and leave the filesystem
     untouched:
       - flow_key must be a known flow (look it up in bridge_flows), and must not
         be an arbitrary unchecked string;
       - run_id must be a positive integer and name an existing run directory
         under {bridge_dir}/{flow_key}/runs/ (for backlog/run-ledger/end-report the
         run must be the active run — no END-REPORT.md — unless the write is the
         END-REPORT itself);
       - handoff_id must be a positive integer (required for the handoff type);
       - artifact_type must be exactly one of the four enumerated values.
     Every validation failure returns a clear error and writes nothing.

  4. CONTENT TRANSPORT (sandbox-safe): the supervisor can reach only the DB and
     its own workspace, not /home/svend/flows. Carry the artifact content through
     the DB (a content column on the queue table, or a companion table), or an
     equivalent DB-bound transport. Do NOT require the caller to pass a host
     filesystem path to read content from. If a source file reference is used at
     all, its path must also be canonical/enumerated — never arbitrary.

  5. HOST-SIDE WRITE ONLY: the actual materialization write happens in the
     broker's host-side execution (daemon / process-once), exactly like the
     existing signal transitions — never in the sandbox enqueue step. The
     sandboxed supervisor enqueues a materialize request (DB-only); the host-side
     broker performs the validated write. The enqueue step must itself touch
     nothing under /home/svend/flows.

  6. APPEND vs REPLACE semantics: run-ledger appends to the existing file (create
     if absent); backlog and end-report replace; handoff creates and must refuse
     to silently overwrite an existing handoff file (a handoff that already
     exists has been dispatched or staged — do not clobber it).

  7. NO dispatch.py change. NO config.py change. NO new migration file — if a new
     table or column is needed, self-bootstrap it via the broker's existing inline
     _ensure_schema (matching how 058's schema is already duplicated inline today).

  8. Do NOT redesign the Harness Allocator (GOAL.md §4.3); do NOT touch
     model-allocator; do NOT add MCP-Light or /skill.

PART C — TESTS. Extend /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py with
at least these behaviors (use a temp dir or a test-scoped temp bridge dir — NEVER
write to the real /home/svend/flows during tests):

  1. canonical destination derivation for each of the four artifact types;
  2. rejection of an unknown/arbitrary artifact type;
  3. rejection of a caller-supplied destination path (prove it is rejected/ignored);
  4. rejection of an unknown flow_key;
  5. rejection of a non-positive or unknown run_id / handoff_id;
  6. materialize writes backlog to the canonical path (create then replace);
  7. materialize appends to run-ledger (append, not replace);
  8. materialize creates handoff at the 0-padded canonical path for an explicit id;
  9. materialize creates end-report (create then replace);
  10. materialize leaves the filesystem untouched on validation failure;
  11. the materialize enqueue step touches nothing under the bridge dir (sandbox-safe);
  12. the materialize action does not disable or bypass dispatch.py evidence-gate /
      scope-fence validation (TG11) — it re-derives and validates, never bypasses.

Document in 010-result.md how the supervisor crosses the boundary for file writes
(TG5 / TG9), and list any one-time host-side setup the Human must perform to run
the new code (e.g. restart the broker daemon with the new materialize action — a
deployment step, not a per-transition step).
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
- /home/svend/AI-Genealogy-Research-Assistant/ (any path)
- /home/svend/DPMtF-WebUI/databases/dpmtf.db (runtime writes only — do not hand-edit)

Do not commit or push.
</scope>

<validation>
Run and paste the real output of every applicable check before signalling
completion. Keep all commands POSIX (no $'...', no arrays, no [[ ]]).

TG11 — broker tests (the extended suite must be green):
```sh
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_bridge_broker.py -q
```

TG12 — relevant regression suites must stay green:
```sh
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py tests/test_supervisor_state.py -q
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

Syntax for every in-fence file you change:
```sh
python3 -m py_compile \
  /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py \
  /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py
```

Paste the real outputs into 010-result.md. Never fabricate output. If two patch
attempts fail against the same problem, stop and report the actual failure.
</validation>

<constraint>
- Extend the existing broker; do not redesign it.
- The materialization capability MUST NOT accept arbitrary host paths; canonical
  destinations are computed from flow/run/handoff identity + enumerated artifact type.
- Enumerate exactly the four artifact types; reject everything else.
- DB-bound content transport (no caller-supplied host path to read content from).
- Host-side write only (the sandbox enqueue step touches nothing under /home/svend/flows).
- No dispatch.py / config.py / migration-file change; no model-allocator change.
- No danger-full-access / --dangerously-bypass-approvals-and-sandbox (GOAL §4.4).
- No unrestricted host tmux or filesystem access for any role (GOAL §5).
- Evidence gate and scope-fence validation remain active (TG11).
- Preserve manual recovery path (a Human can still write artifacts directly and
  run dispatch.py directly) (GOAL §9).
- Do not weaken existing assertions (GOAL §9).
- No new runtime dependencies; prefer the existing DB + broker surfaces.
- Do not commit/push/stage/stash/revert.
- Report only measured results; if two patch attempts fail against the same
  problem, stop and report the actual failure.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/010-result.md containing:
- the in-scope working-tree baseline at handoff start (git status --short in
  /home/svend/DPMtF-WebUI)
- Part A: live boundary re-confirmation (bridge-dir write + DB read/write) with real output
- Part B: the materialize action (enumerated types, canonical destination derivation,
  validation, content transport, append/replace semantics, host-side write)
- Part C: the extended test suite, TG11/TG12 real output, TG5/TG9 boundary-crossing
  documentation, and any one-time host-side setup the Human must perform (e.g.
  restart the broker daemon with the new code)
- an explicit list of which testgoals are proven now (TG5 at unit/design level) vs
  deferred to 011 (TG5 live, TG6-TG8, TG13 live acceptance)

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 010
```

Read the command's output. If it reports `signal_complete_failed`, your result
is not at the path dispatch looked for — fix the path and signal again. Do not
fabricate completion.
</deliverable>
