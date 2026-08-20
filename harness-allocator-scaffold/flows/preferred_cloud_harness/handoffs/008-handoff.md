<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>008</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
This is the second governed handoff of Run 003. Handoff 007 (investigation +
Codex/Claude permission/auth) was APPROVED. Read its two artifacts before
acting — they are the facts you build on:

  /home/svend/flows/preferred_cloud_harness/results/007-result.md
  /home/svend/flows/preferred_cloud_harness/verdicts/007-verdict.md

The authoritative Mission Contract is:

  /home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md — read it in full
  before proceeding. (That is the run's Mission Contract. The product
  specification is a separate /home/svend/harness-allocator/GOAL.md — do not
  confuse the two.)

007's key conclusion (Part C.2): the single root cause of the supervisor's
read-only /home/svend/flows AND its invisible host tmux socket is the OUTER
sandbox mount the DeepSeek Harness supervisor runs inside — workspace-write
rooted at /home/svend/DPMtF-WebUI, with no add-dirs. No DPMtF config seam can
fix that from inside the sandbox; the fix is a host-side bridge broker the
supervisor invokes across its boundary through one narrow seam.

The Codex permission profile (Objective 1, TG1/TG2) and the Claude
subscription auth (Objective 2, TG3/TG4 static layer) are already GREEN — do
NOT redo them. This handoff implements Objectives 3/4/5/6 (supervisor
bridge-write, role-to-role dispatch, tmux visibility, trace.log writes) and
proves the governance-preservation + regression testgoals (TG9-TG12).
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
   <scope>. A residual defect whose only fix lives out of fence is a
   scope-fence finding — report it, do not edit it.
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
</governance>

<task>
Three parts, in order. Part A gates Part B and Part C: measure before changing.

PART A — MEASURE YOUR OWN BOUNDARY (read-only). This handoff's seam depends on
what THIS session can and cannot reach, and on the supervisor's already-measured
boundary. Determine and document each with live command output (file:line where a
code claim is made):

 1. Write access under /home/svend/flows/preferred_cloud_harness/: create then
    delete a temp file (e.g. .run003_tg10_probe_$$) — do NOT append to or edit
    trace.log; probing the directory is sufficient, and 007 already showed
    /home/svend/flows is writable from this role. Report the result.
 2. Host tmux socket visibility: `tmux ls` and `tmux has-session -t
    super-deep-deep4`, `-t imple-codex-minimaxM3`, `-t review-claude-sonnet5`.
    Report which sessions are visible and reachable from THIS session.
 3. DPMtF database: read `bridge_id_counters` and `bridge_flows` from
    /home/svend/DPMtF-WebUI/databases/dpmtf.db (read-only query).
 4. DPMtF WebUI reachability: `curl -s http://localhost:9130/api/health`.
 5. Restate the SUPERVISOR's boundary (you cannot run as the supervisor; rely on
    007-result A.6/A.7/A.8 and the run's RUN-LEDGER.md, which measured it live):
    read-only /home/svend/flows, invisible /tmp/tmux-1000, writable
    /home/svend/DPMtF-WebUI and the DB. Name the seam surfaces the supervisor
    CAN reach from inside its sandbox (workspace files, the DB, and localhost
    network if Part A.4 confirms a host endpoint exists).

The outcome of Part A decides the concrete seam in Part B. Record every command
and its real output in 008-result.md.

PART B — IMPLEMENT THE BRIDGE BROKER (in-fence). Implement the smallest robust
host-side bridge broker per 007-result Part C.2, which recommends:

 1. A narrow `bridge-broker` command — a thin wrapper around
    `dispatch.py --signal-send` / `--signal-complete` — that owns exactly the
    TWO host capabilities the supervisor sandbox lacks:
      (a) authoritative bridge-dir write: append /home/svend/flows/trace.log and
          write handoffs/NNN-handoff.md, results/NNN-result.md,
          verdicts/NNN-verdict.md under /home/svend/flows/preferred_cloud_harness/;
      (b) tmux injection against the host tmux server (has-session / send-keys /
          paste-buffer / load-buffer), for the governed role sessions only.
    Nothing else host-wide is writable or reachable from the broker's own
    surface.
 2. A single narrow seam for the supervisor to invoke the broker from inside its
    workspace-write sandbox. The supervisor can write /home/svend/DPMtF-WebUI
    and the DPMtF database, and (per Part A) reach the WebUI — choose the
    SMALLEST deterministic seam consistent with the existing database-driven
    dispatch (CLAUDE.md §8): e.g. a DB-backed dispatch request the WebUI or a
    host-side broker process observes, or a localhost HTTP call to the WebUI
    that performs the host-side write + tmux injection on the role's behalf.
    Document exactly how the supervisor crosses the boundary, and prove the
    supervisor never gains unrestricted host access.
 3. Keep dispatch.py's existing manual/Human recovery path intact (GOAL.md §9 —
    manual bridge commands remain recovery tools). The broker is additive.
 4. Preserve the evidence gate and scope-fence validation: whatever executes the
    transition (broker or seam) must re-run the same scope-fence and
    evidence-gate checks with the same inputs. Never disable them (TG11).
 5. Do NOT redesign the Harness Allocator (GOAL.md §4.3); do NOT touch
    model-allocator (its subscription-auth path is already correct, 007 A.4).

PART C — TESTS. Add or adjust automated tests proving:
 - the broker/seam preserves scope-fence and evidence-gate validation (TG11);
 - the broker's trace.log write no longer hits Errno 30 for an authorized
   transition (TG10) — tested from the broker's own boundary;
 - relevant existing suites stay green (TG12).
Document in 008-result.md how session delivery crosses the sandbox boundary
(TG9), and list any one-time host-side setup the Human must perform to run the
broker (that setup is a deployment step, not a per-transition step).
</task>

<scope>
MAY modify (only these, and only the smallest change that satisfies Part B):
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py
  (broker seam — in scope for this handoff)
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness_terminal.py
  (each only if the seam strictly requires it)
- /home/svend/DPMtF-WebUI/config.py
  (only if strictly necessary for broker config; prefer ini/env — CLAUDE.md §10)
- NEW: a broker module/script under /home/svend/DPMtF-WebUI/scripts/bridgeV002/
  (e.g. bridge_broker.py) and any small DB migration under
  /home/svend/DPMtF-WebUI/scripts/db/ genuinely required by the seam
- directly related flow-start / launcher / test files required to establish the
  boundary
- tests added/modified to prove TG9/TG10/TG11/TG12

MUST NOT modify:
- /home/svend/model-allocator (any path) — read-only investigation only
- app.py, scripts/init_db.py, dpmtf.ini, .env
- databases/dpmtf.db (do not hand-edit the DB file; runtime writes only)
- governance files under docs/governance-templates-v2/
- scripts/bridgeV002/gate-deliverable-evidence.py
- .git/ internals
- /home/svend/AI-Genealogy-Research-Assistant (any path) — forbidden
- any other repository or any path outside the fence

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

TG11 — automated test that runtime permission expansion does NOT disable or
bypass scope-fence/evidence validation. Run whatever test you added and paste
the output.

TG12 — relevant regression suites must stay green:
```sh
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

Syntax for every in-fence file you change:
```sh
python3 -m py_compile <changed file>
```

Paste the real outputs into 008-result.md. Never fabricate output. If two patch
attempts fail against the same problem, stop and report the actual failure.
</validation>

<constraint>
- Measure (Part A) before modification (Part B); no symptom patching before the
  seam is identified.
- Only the smallest in-fence broker/seam; no redesign, no full live-chain
  orchestration in this handoff (TG5-TG8, TG13 live acceptance is handoff 009).
- No model-allocator modification; report out-of-fence findings instead.
- No danger-full-access / --dangerously-bypass-approvals-and-sandbox (GOAL §4.4).
- No unrestricted host tmux or filesystem access for any role (GOAL §5).
- Evidence gate and scope-fence validation remain active (TG11).
- Do not weaken existing assertions (GOAL §9); preserve manual recovery path.
- No new runtime dependencies, daemons, databases or protocols without Human
  approval; prefer the existing DB + WebUI + tmux surfaces.
- Do not commit/push/stage/stash/revert.
- Report only measured results; if two patch attempts fail against the same
  problem, stop and report the actual failure.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/008-result.md containing:
- the in-scope working-tree baseline you recorded at handoff start
  (git status --short in /home/svend/DPMtF-WebUI and /home/svend/harness-allocator)
- Part A: your live boundary measurements (write/tmux/DB/WebUI) + the restated
  supervisor boundary, each with real output
- Part B: the implementation (files changed, the seam, how the supervisor
  crosses the boundary, how the broker preserves scope-fence + evidence gate)
- Part C: TG10/TG11/TG12 real output, the TG9 boundary-crossing documentation,
  and any one-time host-side setup the Human must perform to run the broker
- an explicit list of which testgoals are proven now vs deferred to 009
  (TG5-TG8, TG13 are live-chain acceptance and are deferred)

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 008
```

Read the command's output. If it reports `signal_complete_failed`, your result
is not at the path dispatch looked for — fix the path and signal again. Do not
fabricate completion.
</deliverable>
