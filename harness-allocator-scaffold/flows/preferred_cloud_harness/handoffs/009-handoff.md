<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>009</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
This is the third governed handoff of Run 003. It RE-ISSUES handoff 008's
bridge/tmux broker implementation, which was honestly declined by the
implementer for a handoff-authoring defect — not for any fault in the work.

Read these artifacts before acting. They are the facts you build on:

  /home/svend/flows/preferred_cloud_harness/results/007-result.md   (investigation, APPROVED)
  /home/svend/flows/preferred_cloud_harness/results/008-result.md   (the decline + the broker design you are to IMPLEMENT)
  /home/svend/flows/preferred_cloud_harness/results/008-gate-rejection.md
  /home/svend/flows/preferred_cloud_harness/verdicts/007-verdict.md
  /home/svend/flows/preferred_cloud_harness/verdicts/008-verdict.md (REJECTED — one narrow A.4 correction; see below)

The authoritative Mission Contract is:

  /home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md — read it in full
  before proceeding. (That is the run's Mission Contract. The product
  specification is a separate /home/svend/harness-allocator/GOAL.md — do not
  confuse the two.)

WHY 008 WAS DECLINED, AND WHY 009 WILL PASS: the 008 handoff's scope block
authorized the NEW broker files in prose form ("NEW: a broker module/script
under ..."), which the evidence gate's scope parser cannot read. The
implementer created the three NEW files, the gate rejected them as outside the
fence, and the implementer correctly deleted them and reverted rather than
force the deliverable through with gate-ignore paths. This handoff lists every
file by exact absolute path, which the gate CAN parse (verified by the
supervisor against gate-deliverable-evidence.py before authoring this handoff).

VERDICT 008 (REJECTED) — ONE NARROW CORRECTION: the reviewer verified the
decline and its revert byte-for-byte, then rejected 008-result for ONE factual
overclaim: its Part A.4 asserted "no uvicorn process is listening on port 9130"
as host fact. That is FALSE — a uvicorn (pid 1509795) has been bound to
0.0.0.0:9130 for the entire run, and the supervisor independently re-verified
reachability from its own sandbox this wake-up (curl -> HTTP 200,
{"status":"healthy"}). The correct claim is that curl failed FROM THE
IMPLEMENTER'S SANDBOX due to network-namespace isolation — the same class of
restriction as A.2 (tmux) and A.5 (out-of-fence paths) — not that no host
endpoint exists. This handoff carries that correction into Part A item 4 and
the boundary table; do NOT repeat the overclaim in 009-result.

DO NOT redesign the broker. Handoff 008's result already measured the boundary
(Part A), built the broker end-to-end (Part B.3), ran 15 green unit tests, and
documented the exact architecture. Your job is to re-implement that same
architecture faithfully inside this handoff's explicit file fence.
</context>

<governance>
1. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md and the Mission Contract
   GOAL.md (/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md) in full
   before acting.
2. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT (GOAL.md §14). Leave changes
   unstaged for the Human.
3. This handoff authorizes implementation of the bridge/tmux broker for
   Objectives 3/4/5/6 + regression tests. It does NOT authorize the §4
   non-goals (MCP-Light, /skill, new Harness Allocator architecture,
   danger-full-access, unrelated repositories).
4. Do NOT modify /home/svend/model-allocator or any repository not listed in
   the scope fence below. A residual defect whose only fix lives out of fence
   is a scope-fence finding — report it, do not edit it.
5. Do NOT weaken any existing assertion or production behavior merely to obtain
   green tests (GOAL.md §9).
6. Report only measured results. Never invent command output.
7. Stop after two failed patch attempts against the same problem; document the
   actual failure and return it rather than guessing.
8. Do NOT use danger-full-access or --dangerously-bypass-approvals-and-sandbox
   under any reading of this handoff (GOAL.md §4.4).
9. The evidence gate and scope-fence validation MUST remain active. The broker
   re-runs them with the same inputs; it must never disable or bypass them
   (TG11, GOAL.md §8/§12).
10. Do NOT give the supervisor — or any role — unrestricted host filesystem or
    host tmux access. The broker is a narrow capability, not a sandbox-mode
    flag (GOAL.md §5, Objective 8).
11. DO NOT set DPMTF_GATE_IGNORE_PATHS or any gate-ignore path to make the gate
    pass. The scope in this handoff is parseable on its own; the 3 NEW files
    are listed by absolute path and will be in the gate's allowed set.
12. Do NOT repeat 008-result's A.4 overclaim ("no uvicorn process is listening
    on port 9130"). Verdict 008 established a uvicorn IS listening on
    0.0.0.0:9130. A curl failure from your sandbox is network-namespace
    isolation, not host-endpoint absence. Record the corrected claim.
</governance>

<task>
One implementation, in order. Adopt 008-result Part B.3 as the binding spec —
do not redesign it.

PART A — CONFIRM YOUR BOUNDARY (read-only, fast). 008-result Part A already
measured this session's boundary live. Re-confirm the four facts below with
one command each (do not re-investigate; the answers are already documented in
008-result A.1-A.6):

  1. Write access under /home/svend/flows/preferred_cloud_harness/: create then
     delete a temp file (.run003_tg10_probe_$$). 008-result A.1 reported
     WRITABLE.
  2. Host tmux socket: `tmux has-session -t super-deep-deep4` (and the other
     two roles). 008-result A.2 reported the socket EXISTS but is not
     permitted/invisible from this session.
  3. DPMtF database read+write: read bridge_id_counters and bridge_flows from
     /home/svend/DPMtF-WebUI/databases/dpmtf.db. 008-result A.3 reported
     readable AND writable.
  4. DPMtF WebUI: `curl -s --max-time 3 http://localhost:9130/api/health`.
     NOTE — verdict 008 REJECTED 008-result for a factual overclaim in its A.4:
     it asserted "no uvicorn process is listening on port 9130". That is FALSE.
     A uvicorn (pid 1509795) is bound to 0.0.0.0:9130 and has been up for the
     entire run; the supervisor re-verified reachability from its own sandbox
     (curl -> HTTP 200). If YOUR curl fails from THIS session, that is
     network-namespace isolation — the same class of restriction as A.2 (tmux)
     and A.5 (out-of-fence paths). Do NOT conclude "no host endpoint exists".
     Record your real curl output and state the claim correctly.

The DB remains the chosen seam (the smallest deterministic surface the
supervisor can reach from inside its sandbox: workspace files + DB + localhost
WebUI). The WebUI endpoint IS running on the host and IS reachable from the
supervisor's sandbox; the DB seam is chosen for determinism, NOT because the
WebUI is absent. Record every command and its real output in 009-result.md.

PART B — IMPLEMENT THE BRIDGE BROKER (in-fence), exactly per 008-result B.3:

  1. NEW migration `/home/svend/DPMtF-WebUI/scripts/db/058_bridge_dispatch_queue.sql`
     creating a narrow queue table `bridge_dispatch_queue` in the DPMtF DB with
     the columns the broker needs for FIFO dispatch: a row id, flow key, from
     role, to role, handoff id, action (signal-send or signal-complete),
     status (pending/completed/failed), created timestamp, processed timestamp.
     Only this table; no other schema change.

  2. NEW `/home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py` — a thin
     wrapper around dispatch.py owning EXACTLY the two host capabilities the
     supervisor sandbox lacks, and nothing else:
       - `enqueue`   — DB-only: INSERT a pending row. NO tmux, NO
                      /home/svend/flows, NO /tmp. This is what the supervisor
                      (and the rewritten chain_advancement commands) run.
       - `daemon`    — host-side: poll for pending rows, and for each run
                      dispatch.py --signal-send/--signal-complete as a
                      subprocess (the subprocess owns the authoritative
                      bridge-dir write + tmux injection). Mark the row
                      completed/failed from the subprocess result.
       - `status`    — print the queue.
     The broker self-bootstraps the queue schema if migration 058 has not been
     applied (matching 008-result B.3's test). The broker does NOT itself touch
     bridge_dir or tmux — it delegates to dispatch.py, which keeps the evidence
     gate and scope fence active (TG11).

  3. MODIFY `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py` — rewrite
     the three chain_advancement command strings so a role that would have run
     `dispatch.py --signal-complete ...` now runs
     `bridge_broker.py enqueue --flow ... --from-role ... --to-role ... --id ... --action signal-complete`.
     The three sites (grep for `--signal-complete` in dispatch.py) are:
       (a) the gate-rejection recovery command in _handle_gate_rejection
           (~line 1370);
       (b) the next_signal_cmd in signal_complete (~line 2388);
       (c) the "## Signal Completion" block in signal_send (~line 3334).
     The manual/Human recovery path (running dispatch.py directly) must remain
     intact — the broker is additive, not a replacement (GOAL.md §9).

  4. Preserve the evidence gate and scope-fence validation: whatever executes
     the transition re-runs the same scope-fence and evidence-gate checks with
     the same inputs. Never disable them (TG11).

  5. Do NOT redesign the Harness Allocator (GOAL.md §4.3); do NOT touch
     model-allocator (its subscription-auth path is already correct, 007 A.4);
     do NOT add MCP-Light or /skill.

PART C — TESTS. Add NEW `/home/svend/DPMtF-WebUI/tests/test_bridge_broker.py`
covering at least the 15 behaviors 008-result B.3 listed: enqueue writes a row;
enqueue with missing handoff fails; enqueue with present handoff succeeds;
enqueue is idempotent for completed rows; enqueue allows re-dispatch for failed
rows; enqueue action must be valid; process updates status to completed;
process updates status to failed; process does not touch completed rows;
process preserves FIFO order; broker does not disable dispatch.py validation;
broker self-bootstraps schema when migration not run; broker status prints
queue; broker detects dispatch.py error in output; broker does not touch
bridge_dir or tmux. Document in 009-result.md how session delivery crosses the
sandbox boundary (TG9), and list any one-time host-side setup the Human must
perform to run the broker (deployment step, not a per-transition step).
</task>

<scope>
MAY modify — exactly these four files, and nothing else:

- /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py
- /home/svend/DPMtF-WebUI/scripts/db/058_bridge_dispatch_queue.sql
- /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py

MUST NOT change any other file, including:

- /home/svend/DPMtF-WebUI/config.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/gate-deliverable-evidence.py
- /home/svend/DPMtF-WebUI/app.py
- /home/svend/DPMtF-WebUI/scripts/init_db.py
- /home/svend/DPMtF-WebUI/dpmtf.ini
- /home/svend/DPMtF-WebUI/.env
- /home/svend/model-allocator/ (any path)
- /home/svend/AI-Genealogy-Research-Assistant/ (any path)
- /home/svend/DPMtF-WebUI/databases/dpmtf.db (runtime writes only — do not hand-edit)

Do not commit or push.
</scope>

<validation>
Run and paste the real output of every applicable check before signalling
completion. Keep all commands POSIX (no $'...', no arrays, no [[ ]]).

TG10 — bridge-dir write probe (create+delete, no residue):
```sh
f=/home/svend/flows/preferred_cloud_harness/.run003_tg10_probe_$$
if (umask 077 && : > "$f" 2>/dev/null); then echo "WRITABLE /home/svend/flows/preferred_cloud_harness"; python3 -c "import os,sys; os.path.exists(sys.argv[1]) and os.unlink(sys.argv[1])" "$f"; else echo "BLOCKED /home/svend/flows/preferred_cloud_harness"; fi
```

TG11 — broker governance tests (the new suite must be green):
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
  /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  /home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_broker.py \
  /home/svend/DPMtF-WebUI/tests/test_bridge_broker.py
```

Paste the real outputs into 009-result.md. Never fabricate output. If two patch
attempts fail against the same problem, stop and report the actual failure.
</validation>

<constraint>
- Measure (Part A) before modification (Part B); no symptom patching before the
  seam is confirmed.
- Adopt 008-result Part B.3 as the binding spec — do NOT redesign the broker.
- Only the smallest in-fence broker/seam; no full live-chain orchestration in
  this handoff (TG5-TG8, TG13 live acceptance is handoff 010).
- No model-allocator modification; report out-of-fence findings instead.
- No danger-full-access / --dangerously-bypass-approvals-and-sandbox (GOAL §4.4).
- No unrestricted host tmux or filesystem access for any role (GOAL §5).
- Evidence gate and scope-fence validation remain active (TG11).
- Do not weaken existing assertions (GOAL §9); preserve manual recovery path.
- No new runtime dependencies, daemons, databases or protocols beyond the
  queue table and broker module this handoff scopes; prefer the existing DB +
  dispatch.py + tmux surfaces.
- Do not commit/push/stage/stash/revert.
- Report only measured results; if two patch attempts fail against the same
  problem, stop and report the actual failure.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/009-result.md containing:
- the in-scope working-tree baseline you recorded at handoff start
  (git status --short in /home/svend/DPMtF-WebUI and /home/svend/harness-allocator)
- Part A: your live boundary re-confirmation (write/tmux/DB/WebUI) with real output,
  including the CORRECTED A.4 claim (a curl failure from your sandbox = network
  isolation; a host uvicorn IS listening on 0.0.0.0:9130 — do not repeat
  008-result's "no listener" overclaim)
- Part B: the implementation (files changed, the queue schema, the enqueue/daemon/
  status seam, how the supervisor crosses the boundary, how the broker preserves
  scope-fence + evidence gate, the three dispatch.py chain_advancement sites)
- Part C: TG10/TG11/TG12 real output, the TG9 boundary-crossing documentation,
  and any one-time host-side setup the Human must perform to run the broker
- an explicit list of which testgoals are proven now vs deferred to 010
  (TG5-TG8, TG13 are live-chain acceptance and are deferred)

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 009
```

Read the command's output. If it reports `signal_complete_failed`, your result
is not at the path dispatch looked for — fix the path and signal again. Do not
fabricate completion.
</deliverable>
