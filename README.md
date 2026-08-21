# DPMtF-WebUI — Father Project

**DPMtF — Deterministic Process Management to Finalisation.**

DPMtF is a deterministic multi-agent process orchestration framework for
taking defined work from intent to verified finalisation through governed
flows, steps, roles, harnesses, models, gates, and artifacts.

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem. It owns the
authoritative governance templates, hosts the **BridgeV002** dispatch system
for AI role-to-role communication, and provides a **Job Queue** for fully
automated chain execution with durable state management.

## Place in the DPMtF Ecosystem

Four components, one machine boundary:

```
   model-allocator                  model-allocator
   (Father's copy)                  (worker's copy)
         │ resolves role→model            │
         ▼                                ▼
   DPMtF-WebUI ("Father") ◄──────── DPMtF-LightWorker
   flows · dispatch · evidence      polls Father over Tailscale,
   gates · SQLite · port 9130       executes one role at a time in
         │                          disposable worktrees
         └── mcp-light (port 9135)
             read-only context: loopback for Father's own
             roles, a second tailnet instance for workers
```

| Component | Depends on | Provides |
|-----------|-----------|----------|
| model-allocator | its own machine's `models.yaml`/`roles.yaml` | role→model resolution, runtime lifecycle, client configs |
| DPMtF-WebUI | model-allocator (same machine), SQLite | flows, dispatch, evidence gates, LightWorker endpoints, watchdog |
| mcp-light | read access to DPMtF-WebUI's files and database | governance/flow/verdict lookup over MCP |
| DPMtF-LightWorker | model-allocator (worker machine), Father reachable over Tailscale | remote role execution |
| harness-allocator | nothing (stdlib-only Python) | harness identity and adapters (dsh, codex, claude-code), one-shot execution, the persistent Harness Terminal for harness-backed roles |

**Install order — each step's preflight checks the one before it:**

1. **model-allocator** — on every machine that runs models (Father and
   each worker), with that machine's own config files.
2. **DPMtF-WebUI** — on Father: `init_db` → `migrate` → uvicorn on 9130.
3. **mcp-light** — on Father (optional but standard): loopback unit, plus
   the tailnet unit if remote workers should reach it.
4. **DPMtF-LightWorker** — on each worker: venv → `worker.yaml` → auth
   token → base client config → `preflight.sh` 16/16 → daemon.
5. **harness-allocator** — on Father (optional, required only for
   harness-backed roles such as dsh/codex chains): clone next to
   DPMtF-WebUI; `scripts/bridgeV002/harness.py` finds it via
   `config.get_project_path` or `HARNESS_ALLOCATOR_PATH`.

Each repository's own Installation section covers its steps in detail.

## Quick Start

For the full installation guide — including system requirements (Python 3.12, CUDA, tmux), repository layout, virtual environment setup, `.env` configuration, and local runtime installations — see [SETUP.md](SETUP.md).

The commands below assume the prerequisites from SETUP.md are already in place:

```bash
pip install -r requirements.txt
python3 scripts/init_db.py      # schema + canonical defaults (idempotent)
python3 scripts/migrate.py      # apply versioned SQL migrations, incl. bridge seed data
uvicorn app:app --host 0.0.0.0 --port 9130 --reload
```

Open `http://localhost:9130` in a browser.

## LLM-Assisted Installation — a Runbook for AI Assistants

This section is written to be executed by an LLM assistant (Claude
Fable 5, DeepSeek, or similar) that has been pointed at this repository
and asked to install the DPMtF ecosystem and bring the first flow to
life. A human can follow it too, but every step is phrased so an
assistant can verify it mechanically: each phase ends with a **gate** —
a command and the output that proves the phase is done. Do not proceed
past a failed gate; diagnose it.

### The Assistant's Contract

Read these eight rules before running anything. They override any
default behavior.

1. **Never guess ports, paths, or model names.** Every configurable
   value has a source: `dpmtf.ini`, `.env`, the database, or the Human.
   If a value is not in one of those, ask — guesswork is an auto-fail
   in this project's validation standard.
2. **Ask the Human before choosing.** The decision points are marked
   `DECISION` below: which models to serve, which flow to start first,
   which code frontend each role uses. These are the Human's calls.
3. **Secrets never touch git.** `.env` is never committed. Tokens are
   shown once and stored outside the repository. If you find yourself
   about to `git add .env`, stop.
4. **Only the Human commits.** During installation you will edit config
   files; leave them unstaged and tell the Human what changed and why.
5. **`app.py`, `config.py`, `scripts/init_db.py`, and `dpmtf.ini`
   require explicit Human approval before editing.** Everything the
   installation needs is possible without touching the first three.
6. **Verify placement rather than assuming it.** After every service
   start, run the gate command. "The command exited 0" is not the same
   as "the service works".
7. **All code, comments, and commit messages in en-US.** The Human may
   speak Danish to you; translate before anything reaches a file.
8. **When something fails twice, stop and report** the exact command,
   the exact output, and your hypothesis — do not loop on retries.

### What to Ask the Human Before Starting

Collect these answers first; they parameterize everything below:

| Question | Why it matters | Default if the Human has no preference |
|---|---|---|
| Which machine(s)? One box, or Father + remote workers? | Decides whether Phase 6 (LightWorker) applies | One box, no LightWorker |
| Which GPU / how much VRAM? | Decides which local models are feasible (see SETUP.md's model table) | Cloud/hosted models only, no local runtimes |
| Which first flow? | Decides which roles, models, and frontends must exist | `strict_review` (simplest fully-automated chain) |
| Which code frontend for the roles? | Must match `bridge_roles.allocator_client`; the frontend must be installed | Whatever the seeded roles already declare — read it from the DB, do not assume |
| Local model runtimes wanted (Ollama / llama.cpp / SGLang)? | Each needs its own install + `.env` paths | None — skip Local Runtime Installations |

### Phase Map

| Phase | Installs | Required? |
|---|---|---|
| 1 | Prerequisites + clone all repositories | Yes |
| 2 | model-allocator (Father's copy) | Yes |
| 3 | DPMtF-WebUI itself (DB, migrations, server) | Yes |
| 4 | mcp-light (context server, both instances) | Standard — skip only if the Human says so |
| 5 | First flow end-to-end | Yes — this is the goal |
| 6 | DPMtF-LightWorker on a remote worker | Only for multi-machine setups |

The dependency order is load-bearing: each phase's preflight checks the
one before it. Do not reorder.

### Phase 1 — Prerequisites and Clone

System requirements: Python 3.12+, git, tmux, SQLite 3. GPU/CUDA only
if local models were chosen (see `SETUP.md` for the hardware table).

```bash
cd $HOME
git clone https://github.com/svend-blip/model-allocator.git
git clone https://github.com/svend-blip/DPMtF-WebUI.git
git clone https://github.com/svend-blip/mcp-light.git
# Only for multi-machine setups, on the WORKER machine:
git clone https://github.com/svend-blip/DPMtF-LightWorker.git
```

The four directories must be siblings under one base directory
(default `$HOME`) — cross-repo paths are resolved relative to it.

**GATE 1:** `ls $HOME` shows `DPMtF-WebUI model-allocator mcp-light`,
and `python3 --version` reports 3.12 or newer, and `tmux -V` answers.

### Phase 2 — model-allocator

```bash
cd $HOME/model-allocator
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                      # pyyaml is the only dependency
cp models.example.yaml models.yaml
cp runtime_profiles.example.yaml runtime_profiles.yaml
cp roles.example.yaml roles.yaml
```

`DECISION` — edit the three YAML files with the Human: which aliases
exist, which backend serves each (`ollama`, `llama_cpp`,
`openai_compatible`, `anthropic`, `sglang`, `onyx`), and which role
uses which alias. The allocator's own README documents every adapter;
its "Full installation guide" covers local runtimes. Keys in
`roles.yaml` must match `bridge_roles.role_key` in Father's database
EXACTLY — a mismatch resolves to nothing, not to a default.

If local runtimes were chosen, install them now (Ollama / llama.cpp /
SGLang — see `SETUP.md` "Local Runtime Installations") and pull the
models the YAML names.

**GATE 2:** from the allocator directory:
```bash
python3 -m model_allocator list            # lists the configured aliases
python3 -m model_allocator validate --alias <one-alias> --client <frontend>
```
`validate` must end `OK` or `WARNING` (a WARNING names exactly what to
fix — read it). `ERROR` means the alias/backend/client triple is wrong;
fix the YAML before proceeding.

### Phase 3 — DPMtF-WebUI (Father)

```bash
cd $HOME/DPMtF-WebUI
python3 -m venv venv && source venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
cp .env.example .env       # then edit — see below
python3 scripts/init_db.py # schema + canonical defaults (idempotent)
python3 scripts/migrate.py # versioned migrations incl. bridge seed data
```

`.env` minimum for a single-machine install: set `DPMTF_BRIDGE_DIR` to
the directory where flow deliverables will live (a directory OUTSIDE
the repo, e.g. `$HOME/flows` — dispatch creates subdirectories itself),
plus the model-runtime paths from Phase 2 if local runtimes exist.
Every variable is documented inline in `.env.example`; leave the rest
at their defaults on a first install.

Start the server:

```bash
uvicorn app:app --host 0.0.0.0 --port 9130
```

**GATE 3:** all four checks pass:
```bash
curl -s http://localhost:9130/api/health
# → {"status":"healthy","app":"DPMtF WebUI",...}
curl -s http://localhost:9130/api/bridge-v2/status
# → {"available":true,...}
curl -s http://localhost:9130/api/bridge-v2/flows | python3 -c \
  "import json,sys; print(len(json.load(sys.stdin)['flows']), 'flows')"
# → 12 flows   (the seeded flow definitions arrived via migrations)
curl -s http://localhost:9130/api/bridge-v2/roles | python3 -c \
  "import json,sys; print(len(json.load(sys.stdin)['roles']), 'roles')"
# → 43 roles
```
If flows/roles come back empty, `migrate.py` did not run or ran against
a different database — check `dpmtf.ini` `[paths]` before anything else.

### Phase 4 — mcp-light

```bash
cd $HOME/mcp-light
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp mcp-light.service ~/.config/systemd/user/
# EDIT the copied unit first: ExecStart must use THIS venv's python
# (…/mcp-light/venv/bin/python server.py), not /usr/bin/python3.
systemctl --user daemon-reload
systemctl --user enable --now mcp-light
loginctl enable-linger $USER    # start at boot without a login
```

The tailnet instance (`mcp-light-tailnet.service`) is only needed when
remote LightWorkers exist — defer it to Phase 6.

**GATE 4:** `curl -s http://127.0.0.1:9135/mcp` returns MCP transport
data (an event-stream/JSON-RPC response — any HTTP answer from the
port proves the server is up; connection refused fails the gate).

### Phase 5 — The First Flow

`DECISION` — confirm the flow with the Human. The default recommendation
is **`strict_review`**: four automated roles in a straight line, no
supervisor logic, no remote execution.

```
archi01 → imple01 → review01 → review02 → human
handoffs   results    reviews     verdicts
```

Step 1 — read what the seeded roles expect, never assume it:

```bash
sqlite3 -readonly databases/dpmtf.db "SELECT role_key, allocator_client, \
  default_model_alias, tmux_session FROM bridge_roles WHERE role_key IN \
  ('archi01','imple01','review01','review02');"
```

Every `allocator_client` named there must be an installed frontend
(`opencode`, `claude-code`, or `pi`), and every `default_model_alias`
must validate in Phase 2's gate. If the Human wants different
models/frontends, change them via the web UI (Setup → Bridge Setup →
Roles) — not by hand-editing the database.

Step 2 — start the role sessions and their frontends. Use the web UI
(Setup → Bridge Setup, the flow's Start buttons) or the same endpoints
the buttons call:

```bash
curl -s -X POST http://localhost:9130/api/bridge-v2/flows/strict_review/start-tmux
curl -s -X POST http://localhost:9130/api/bridge-v2/flows/strict_review/start-coding
curl -s -X POST http://localhost:9130/api/bridge-v2/flows/strict_review/attach-tmux
```

`tmux ls` must now show a session per role plus the `flow-strict_review`
viewer. Look at the panes (`tmux attach -t flow-strict_review`): each
role's frontend must be at its prompt, not at an error or a login
screen. A frontend asking for authentication is a Human task — report
it and wait.

Step 3 — dispatch the first handoff. Write a small, real task as the
handoff content (the Human provides the task; a good smoke task is
"add a comment header to file X"), then either use the web UI's
**Flow Control** panel (Setup → Flow Control: pick flow, pick step,
Send dispatch) or the CLI:

```bash
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review \
    --signal-send --from-role archi01 --to-role imple01
```

**GATE 5:** delivery is proven by the trace log, nothing else:

```bash
tail -5 $DPMTF_BRIDGE_DIR/trace.log
# must show: <timestamp> | archi01->imple01 | <ID> | dispatched | ...
```

A dispatch lands in five steps (file written, counter advanced, model
swapped, prompt injected, trace line recorded) — **only the trace line
means delivered**. If the trace line exists, watch the chain run:
deliverables appear under `$DPMTF_BRIDGE_DIR/strict_review/` in the
order handoffs → results → reviews → verdicts, and the chain ends with
a `signal_complete_to_human` line. The `chain-watchdog` service (see
Operations below) nudges a stalled step automatically — install it once
the first manual run has succeeded.

### Phase 6 — Remote Worker (optional)

Only for multi-machine setups. On the worker machine, in this order:
model-allocator (Phase 2, with THAT machine's YAML), then
DPMtF-LightWorker per its own README: venv → `config/worker.yaml` →
auth token (minted on Father with
`scripts/bridgeV002/mint_worker_token.py --worker-id <id>`, shown
once) → base client config → `bash scripts/preflight.sh` must report
16/16 → daemon as a systemd user unit. On Father, start
`mcp-light-tailnet` so the worker's roles can reach context over the
tailnet.

**GATE 6:** the worker's `preflight.sh` reports 16/16, and Father's
`/api/bridge-v2/status` still answers while
`journalctl --user -u lightworker-daemon -f` on the worker shows it
polling.

### Troubleshooting for Assistants — Measured Failure Modes

These are failures this project has actually logged, with the check
that distinguishes them:

| Symptom | Reality | Check |
|---|---|---|
| Dispatch printed "injected into <session>" but nothing happens | Printing is not delivery | `tmux capture-pane -p -t <session> \| tail -20` — is the prompt actually in the pane? Then `trace.log` |
| OpenCode role's pane shows "100% context used" | Cosmetic on cloud-model sessions — not a blocker | Does the role still produce output? Then ignore |
| A role "reset" with `/clear` under OpenCode keeps degrading | OpenCode's `/clear` is a prompt, not a reset — OpenCode roles use `/new` | `bridge_roles.fresh_session_command` is authoritative |
| Ollama-served model emits tool calls as prose (no tool runs) | Wrong endpoint shape for that model | Serve via the OpenAI-compatible `/v1` path (allocator: `opencode_ollama_mode=openai_compatible`) |
| `ConnectionRefused` on a local model port right after a signal | The dispatcher stopped that model as part of the signal — routine | Do not restart anything; the next dispatch starts it |
| A running frontend ignores a config change | No frontend hot-reloads config | Restart the role's tmux session |
| Gate blames a role for a file the role never touched | An outside edit landed in the working tree during a run | Never touch Father's working tree while a flow run is active (`databases/dpmtf.db` is the one exception) |

When the first flow has completed once, hand the Human the Operations
section below (watchdog service, viewer, stop buttons) — that is the
day-2 material.

## Core Systems

### BridgeV002 — AI Role Dispatch

Database-driven dispatch system for AI role-to-role communication. All flow
configuration — roles, steps, conventions, deliverable paths — is stored in
the database and resolved at runtime. No flow-specific hardcoding in dispatch
code.

- **Flows** — configurable step sequences stored in `bridge_flows` +
  `bridge_flow_steps`. 12 active flows:
  - `strict_review` — architect → implementer → technical review → governance
    review → human (5 steps, fully automated)
  - `cloud_llm` — cloud LLM variant using Freebuff frontends
  - `cloud_pay` — cloud LLM variant using Anthropic API proxy
  - `trade_cockpit_simulation_v001` — daily research-to-simulation chain
    (7 steps: trend → market → analyst → risk → review → sim → portfolio)
  - `trade_cockpit_scoring_v001` — periodic scoring and learning
  - `supervised_review` / `llama_SG` / `preferred_cloud` / `reveng` —
    autonomous supervisor-driven chains (supervisor → implementer →
    review(s) → supervisor), differing in which models are local vs hosted
  - `lightworker` — chain whose implementer executes on a remote
    LightWorker over Tailscale
  - `supervisor` — legacy run-directory root; new runs open per-flow
  - `pi_test` — frontend-comparison experiment (same model, different
    code frontends); also the Deterministic Patcher pilot — the only
    flow opted into `implementation_mode = deterministic_patch`. Its
    two handoff steps are manual-dispatch only (`auto_dispatch = 0`)

**Auto-chain** — the strict_review flow now auto-advances via chain_advancement
blocks in content templates, with _advance_chain as fallback. Only the initial
signal_send is needed from the Human.
- **Advance chain guards:** the fallback only nudges a step whose
  deliverable exists but was never signaled — it checks trace.log recency,
  target pane activity, and deliverable age, and stops after
  `max_nudges_per_step` attempts (machine profile `[watchdog]` section).
- **Fast nudge path:** when the writer's pane has been idle on
  `idle_confirmations` consecutive ticks and the deliverable is older than
  `fast_nudge_minutes`, the nudge fires within ~2-3 minutes instead of
  waiting out `stall_minutes`. Safe because `signal_complete` itself is
  idempotent: a transition already delivered within
  `delivery_grace_minutes` is suppressed (override with `--force`).
- **Roles** — per-role definitions in `bridge_roles` with tmux sessions,
  model aliases, governance files, and enter commands. 43 active roles across
  all flows.
- **Conventions** — `bridge_convention_rules` with `content_template` and
  `validation_schema` for handoff, callback, technical_review, verdict,
  human_delivery, escalation, and json_output rule keys.
- **Signals** — `signal_send` (initial dispatch), `signal_complete` (chain
  advancement), `signal_escalation` (review → architect question),
  `signal_answer` (architect → review response). All via `dispatch.py`.
- **Manual-dispatch-only steps** — `bridge_flow_steps.auto_dispatch = 0`
  (migration 054) marks a step Human-initiated only: `signal_complete`
  refuses it before any session or deliverable check (trace event
  `signal_complete_refused`); `--signal-send` is the only way in.
  Guards cyclic flows against a model improvising a stray signal that
  would re-inject the same handoff id into a parallel role — measured
  live on pi_test handoffs 008-010, where the duplicate would have
  re-run a repository-mutating task.

**Key dispatch features:**

- **Tool-aware injection** — detects opencode vs Claude Code in target tmux
  session and adapts injection method (send-keys for short prompts, paste-buffer
  for long)
- **XML tag stripping** — opencode models hallucinate XML function calls when
  they see XML tags; `_strip_xml_tags()` converts KNOWN XML section headers to
  plain text before injection and deletes the rest. Any NEW tag used in an
  injected prompt must be added to its whitelist, or opencode/pi roles
  receive the tag's inner text as an orphaned bare line (measured live:
  `<implementation_mode>` before it was whitelisted)
- **Auto-prepend** — `auto_prepend_xml_sections()` adds missing XML headers to
  deliverable files before validation, using `content_template` from DB
- **nohup background execution** — signal-complete commands run via `nohup ... &`
  to prevent opencode's 120s shell timeout from killing the dispatch process
- **Model lifecycle** — allocator warm-up before injection, reference-counted
  model leases, VRAM cleanup after dispatch
- **Checkpoint integration** — structured checkpoints written after each
  signal-complete for fresh-context continuation

Manage flows, roles, steps, and conventions via the web UI under
**Setup → Bridge Setup**.

### Deterministic Patcher — LLM-Planned, Machine-Applied Edits

Infrastructure (not a role, no model, no LLM calls) that turns an
implementer's machine-readable **PatchRequest** into a repository
mutation: `structural_python` operations via LibCST, `unified_diff` via
`git apply`, with verification, audit trail, and the exact resulting
diff captured for review. Same repo state + same PatchRequest + same
tool versions = same transformation. Package: `patcher/` (+ CLI);
spec: `docs/specs/DETERMINISTIC_PATCHER_SPEC.md`; usage guide:
`docs/specs/DETERMINISTIC_PATCHER_USAGE.md`.

**Opt-in via `implementation_mode`** — database-driven, precedence
**role > step > flow > global default `direct`** (migration 052 on
`bridge_roles`, `bridge_flow_steps`, `bridge_flows`; resolver in
`scripts/bridgeV002/patch_mode.py`). Nothing behaves differently until
a Human opts a flow in — flow level via the web UI dropdown (Bridge
Flows edit form), step/role level via SQL.

When a dispatch target resolves to `deterministic_patch`, the injected
prompt carries the section-26 instruction block (rules in the shared
governance file `102_DETERMINISTIC_PATCH_MODE.md` — role files are not
rewritten) at **all three composition sites**: `run_flow_step_db`,
`signal_complete`, and `signal_send`. With `direct`/unset the prompt is
byte-identical to pre-patcher behavior, proven by test. Roles can fetch
the governance and the PatchRequest format on demand through mcp-light
(`get_governance_file`, `get_patcher_usage`) and verify their own
resolved mode against the database (`get_implementation_mode`).

Pilot flow: `pi_test` (live-proven 2026-08-16 — the dispatched
implementer quoted the full block verbatim from its own prompt, and
the first real patch task shipped the same day: a role-authored
`replace_method` PatchRequest applied end-to-end with the full
allocator suite as its verification command).

**Authoring contract** (USAGE.md §1, learned by the first live tasks):
`replacement`/`code` fragments are parsed as top-level statements —
`def` at column 0, the engine re-indents on insertion; string-literal
interiors are NOT re-indented, so docstring continuation lines are
written at target depth; leading blank lines are inherited from the
replaced node unless the fragment supplies its own (the engine
preserves PEP8 separation at all three replacement operations).

Measured trade-off (same task, same role, A/B): direct edit was ~5×
faster and ~40% cheaper on a trivial one-file change — the patcher's
value is its guarantees (reproducible mutation, path fence,
base-revision lock, verbatim verification, audit with diff hash), not
speed. Opt flows in where the review side must trust what actually
happened over what the role reports.

### Job Queue — Automated Chain Execution

Durable job abstraction with a state machine that drives flows from job
creation through full chain completion — no manual intervention required.

**State machine:** `DRAFT → AWAITING_APPROVAL → APPROVED → QUEUED → RUNNING → VERIFYING → COMPLETED`
(with `CANCELLED`, `FAILED`, `BLOCKED` as terminal states)

**Components:**

| File | Purpose |
|------|---------|
| `scripts/job_queue/models.py` | `JobRepository` — atomic claims, 15-min leases, heartbeat, retry with max_retries |
| `scripts/job_queue/scheduler.py` | `Scheduler` — claims APPROVED jobs, compiles handoff, dispatches, checks completion |
| `scripts/job_queue/cron_tick.py` | Single-pass entry point — run via cron every minute |
| `scripts/job_queue/model_lease.py` | `LeaseRegistry` — reference-counted model load/unload |
| `scripts/job_queue/checkpoint_integration.py` | Checkpoint creation for dispatch steps |
| `scripts/job_queue/handoff_compiler.py` | Context-fit splitting for oversized goals |

**Chain automation:**

1. **Cron-tick** (every minute) claims oldest APPROVED job → transitions to
   RUNNING → compiles handoff file → injects short prompt into role's tmux
   session
2. **Model** reads handoff file, executes task, writes deliverable, runs
   `nohup signal-complete &` (background, no timeout)
3. **signal_complete** validates deliverable, resolves content_template from
   DB, injects callback prompt into next role's tmux session (with deliverable
   path, output path, and signal command)
4. **_advance_chain** (fallback) — if a model forgets signal-complete,
   cron-tick scans deliverable files, reads `<source_role>` or `Source Role:`
   from each, and runs signal-complete for the last completed role
5. **_check_completion** — when the final step's deliverable exists, job is
   marked COMPLETED

**Job records created automatically at signal_send time** (state machine:
DRAFT→AWAITING_APPROVAL→APPROVED→QUEUED→RUNNING)

**LeaseRegistry for reference-counted model lifecycle** (models only stop
when all leases are released)

**Chain advancement fallback** (_advance_chain) that auto-advances if a
model forgets to signal completion

**Cron-based scheduler** (cron_tick.py) for fully automated flows

**Lease recovery:** expired leases (15 min) are recovered back to APPROVED,
re-claimed, and the handoff_id is reused so deliverable files don't need to
be renamed.

### Prompt Compiler

Assembles handoff prompts from knowledge fragments, scope profiles, and
governance rules. The scheduler's `_compile_handoff()` generates handoff
files with task description, deliverable path, signal-complete command, and
required XML sections — all dynamically resolved from DB flow/step config.

### Governance Templates

`docs/governance-templates-v2/` contains 50+ authoritative governance files:

- **100-series** — bridge, project, scope, coding standard, validation
- **200-series** — hardening, gates, alignment, model selection, frontend
- **300-series** — setup instructions
- **400-series** — flow-specific role definitions (strict_review, cloud_llm,
  cloud_pay, trade)

Governance files are the **single source of truth** for role identity,
responsibilities, and boundaries. No role descriptions are hardcoded in
dispatch or scheduler code — the prompt simply says "Read your role
definition at {gov_path}".

### Model Allocator Integration

The [model-allocator](https://github.com/svend-blip/model-allocator) is a
standalone CLI + web UI that resolves stable model aliases (e.g.
`archi-local`, `imple01-local`) to concrete backends (Ollama,
llama.cpp/TurboQuant, OpenAI-compatible cloud APIs) and manages runtime
lifecycle.

**Separation of concerns:**
- **Model-allocator UI** (port 9140) — full CRUD for allocation models,
  runtime profiles, validation, doctor diagnostics. This is where models
  are created, configured, and tested.
- **DPMtF-WebUI** (port 9130) — role editor has a simple `model_alias`
  text field + "Test OK" button + link to allocator UI. No allocator
  dashboard, no config management.

DPMtF calls the allocator CLI during dispatch (`start`/`stop`/`validate`)
but does not manage model configuration — that lives entirely in the
allocator repo.

**Model and frontend are separate choices.** The allocator resolves a role
to a model; `bridge_roles.allocator_client` decides which code frontend
drives it. Three are supported — `claude-code`, `opencode` and `pi` — and a
role can move between them without its model, runtime or governance
changing. That is what makes a same-model comparison of two frontends
possible, which is what the `pi_test` flow exists to do.

Swapping a frontend is a migration plus a session restart, and it must not
require rewriting the flow's procedures. The rule, the placement
requirements and the per-frontend differences that do exist are in
`docs/governance-templates-v2/101_CODE_FRONTENDS.md`.

### Trade Cockpit Orchestration

The Father hosts the cronjobs that drive the trade-ui's automated flows:

| Cron | Script | Flow |
|------|--------|------|
| Weekdays 09:00 | `scripts/trade-cronjob.sh` | `trade_cockpit_simulation_v001` |
| Sunday 10:00 | `scripts/scoring-cronjob.sh` | `trade_cockpit_scoring_v001` |

Both dispatch into the trade-ui's inbox via BridgeV002. They produce research
and allocation plans — they never execute trades.

### Python Runtime

`scripts/python-runtime/` provides an alternative execution backend for
roles that use `model_source = "python_runtime"` instead of tmux injection.
Supports checkpoint schema, file tools, context-fit spike testing, and
prompt parsing.

## Architecture

### Backend

- **`app.py`** (149 lines) — thin FastAPI entrypoint; all endpoints live in
  11 domain routers under `routers/`:
  - `bridge.py` (38 endpoints) — flows, roles, steps, conventions, dispatch,
    tmux session management, job queue, allocator proxy
  - `system.py` (14) — health, config, system info
  - `panels.py` (10) — frontend panel CRUD, layout slots
  - `lightworkers.py` (9) — the LightWorker protocol (see below)
  - `sessions.py` (7) — Claude session management
  - `prompt_compiler.py` (4) — handoff prompt compilation
  - `git.py` (4) — git operations
  - `validation.py` (4) — deliverable validation
  - `webui.py` (4) — webui migration targets
  - `app_profiles.py` (2) — user profile panels
  - `governance.py` (1) — governance file access
- **97 API endpoints** total

### LightWorker API

`routers/lightworkers.py` exposes the nine endpoints a remote
DPMtF-LightWorker polls over Tailscale: register, worker heartbeat, offer,
offer-next, claim (atomic), execution heartbeat, record-event, complete and
fail — backed by the durable `SqliteLightWorkerStore`
(`routers/lightworker_store.py`, schema in
`scripts/db/030_lightworker_executions.sql`). Per-worker bearer tokens are
minted with `scripts/bridgeV002/mint_worker_token.py` and stored as sha256;
the token both authenticates and identifies its worker.

### Database

- **SQLite** (`databases/dpmtf.db`) with 48 tables
- **Versioned migrations** — `scripts/db/*.sql` applied by `scripts/migrate.py`
  (tracked in `schema_migrations`). 49 migrations to date. Schema changes are
  new `00X_*.sql` files — never edits to `init_db.py`.
- **`scripts/init_db.py`** — schema + canonical defaults (i18n labels,
  conventions) only. User-configured data lives in the DB, managed via the
  frontend.

### Frontend

- **`static/js/dpmtf-app.js`** — main application shell, panel groups,
  expand/collapse tracking, theme switching, role editor with "Test OK"
  button for allocator alias validation
- **`static/js/job-queue.js`** — job queue panel with status filters,
  scheduler tick trigger, job creation/approval
- **`static/css/dpmtf-theme.css`** — themed styling

### External Integrations

- **mcp-light** — required MCP context server providing real-time access to
  governance, panels, flows, roles, and verdicts via tools on
  `http://127.0.0.1:9135/mcp`. Must be running before any flow starts; roles
  depend on it for cold-start initialization and will degrade without it.
  Runs as a systemd **user** unit (`systemctl --user status mcp-light`), with
  `loginctl enable-linger` so it starts at boot without a login.
  A second instance, `mcp-light-tailnet`, binds this host's Tailscale address
  so roles executing on a remote LightWorker can reach it — the server is
  read-only, so the two cannot conflict. It has no authentication, so the
  tailnet is the boundary; see the mcp-light repository's README.
- **model-allocator** — standalone CLI + web UI (port 9140) for model
  lifecycle management and allocation model CRUD
- **opencode** — AI coding frontend running in tmux sessions, configured per
  role via `~/.config/opencode-roles/{role}/opencode.json` with permissions
  (`external_directory: allow`, `bash: allow`, `edit: allow`)

### Cold-Start Skills

`.claude/skills/` holds the cold-start procedures. Despite the directory
name they are **not** Claude Code-specific: one skill per flow, written so
that Claude Code, OpenCode and Pi all read the same file. Swapping a flow's
code frontend must never mean rewriting its procedures — see
`docs/governance-templates-v2/101_CODE_FRONTENDS.md` for the rule.

| Skill | Covers |
|---|---|
| `dpmtf-cold-start` | any dispatched worker, any flow — orientation, fencing, verification, signalling |
| `REVENG` | `reveng` supervisor |
| `LLAMASG` | `llama_SG` supervisor |
| `PRECLOUD` | `preferred_cloud` supervisor |
| `SUPERVISEDREVIEW` | `supervised_review` supervisor |
| `STRICTREVIEW` | `strict_review` architect |
| `CLOUDLLM` / `CLOUDPAY` | `cloud_llm` / `cloud_pay` architects |

A worker's working directory is the **target project**, not Father, so a
skill stored only in this repository is invisible to it. Skills meant for
workers are published by symlink into `~/.agents/skills/` (Pi, OpenCode) and
`~/.claude/skills/` (Claude Code, OpenCode); the source stays here under
git. Verify from a target project, never from Father:

```bash
cd <target_project>
opencode debug skill | grep <name>
pi --print "List the names of the skills available to you. Names only."
```

## Testing

```bash
python3 -m pytest tests/ -q    # 807 tests, all passing
```

65 test files covering:
- Job queue models, scheduler, integration, spikes
- Bridge endpoints, dispatch, convention rules
- Chain watchdog and supervisor state
- LightWorker store, endpoints, artifacts, patch application
- Checkpoint schema and integration
- Migration tests
- Runtime modules, safe resolve, action schema
- E2E pipeline and full cycle workflow
- Handoff compiler, context fit
- Allocator config endpoints, model lease
- Validation-rule command guard
- Deterministic Patcher: engines, policy, CLI, implementation_mode
  resolution, dispatch injection wiring (ast-pinned at all three
  composition sites), flow integration, WebUI mode endpoint
- Evidence gate: claim extraction, scope fences (incl. glob entries),
  per-step clock

## Configuration

Two files control all configurable values:

- **`dpmtf.ini`** — App-config defaults (committed to git, no secrets):
  port, host, database path, governance dir, log dir, project paths
- **`.env`** — Secrets + infrastructure vars (NEVER commit)

For the complete list of environment variables (~20 documented entries), see
[`.env.example`](.env.example). Notable examples:

```bash
export DPMTF_BRIDGE_DIR=/home/<you>/flows   # BridgeV002 deliverable directory
```

Note: `DPMTF_PROJECT_ROOT` is read by bridge and shell scripts (e.g.
`scripts/bridgeV002/dispatch.py`, `trade-cronjob.sh`), not by
`config.get_project_root()` — which resolves the project path from
`dpmtf.ini` `[paths]` section instead.

See `SETUP.md` for full setup guide.

## Operations

**Always-on services** (systemd user units, `loginctl enable-linger` set,
so they start at boot without a login):

| Unit | What it does |
|------|-------------|
| `chain-watchdog` | watches EVERY flow permanently (`--all-flows --forever`): produced-nothing fast path (3 consecutive idle passes → nudge, budget 2/step), remote-role liveness via execution heartbeats (never auto-nudged), chains older than 6h ignored as history |
| `mcp-light` | read-only context server on loopback for Father's own roles |
| `mcp-light-tailnet` | second instance on the Tailscale address for remote LightWorkers |

The watchdog does NOT start with a chain and needs no arming — per-run
manual arming was the failure mode it replaced: it existed through every
produced-nothing incident this project logged and was armed for none of
them.

**Following a run:** `tmux attach -t flow-<key>` shows every role in chain
order, remote roles mirrored over ssh. The viewer is rebuilt automatically
by `start_tmuxflow.py` and the start-coding endpoint; after any manual
session surgery, run `python3 scripts/bridgeV002/attach_tmux.py <flow>`.

**LightWorker capabilities (completed 2026-08-07):**

- **Per-worker credentials** — tokens minted with
  `scripts/bridgeV002/mint_worker_token.py --worker-id <id>`, stored as
  sha256 (Father never persists a usable secret). The token authenticates
  AND identifies: a body asserting another worker's id is 403. While no
  token is minted the shared `LIGHTWORKER_AUTH_TOKEN` still works; the
  first minted token retires it. Rollout order: mint → install → restart.
- **Artifact transfer** — `POST /api/lightworkers/artifacts` stores blobs
  content-addressed under their sha256 (filesystem, not the git-committed
  database). Results reference `artifact_sha256`; Father re-hashes on
  redemption. Workers switch to references above 256 KiB.
- **Patch mode** — `patch_and_deliverable` results carry a binary-safe
  git patch. Father validates (checksum, base_commit cross-checked
  against the dispatched envelope) and applies it in a throwaway worktree
  at that exact base; only the branch `lightworker/<flow>-<handoff>`
  survives. No existing ref moves — review and merge stay human-gated.
- **Claim expiry** — a claimed execution whose heartbeats stop is failed
  by Father when its worker next polls (300s silence with heartbeats,
  900s grace before the first — model load is legitimately silent), so
  the queue heals itself.

**Stop buttons:** *Stop tmux* kills the flow's local sessions, its viewer,
and — for roles with an `execution_target` — the worker's `dpmtf-*`
execution sessions and daemon over ssh. *Stop servers* stops local
allocator runtimes, and for remote roles resolves the alias ON the worker
(its own `roles.yaml`; Father's stored value can be stale) and stops it
there. Both live-verified against svend3060 2026-08-07.

## Tmux Session Management

The web UI provides four tmux management actions per flow (accessible via
bridge endpoints):

| Action | Endpoint | Script |
|--------|----------|--------|
| Start sessions | `POST /api/bridge-v2/flows/{flow}/start-tmux` | `start_tmuxflow.py` |
| Stop sessions | `POST /api/bridge-v2/flows/{flow}/stop-tmux` | `stop_tmuxflow.py` |
| Start coding | `POST /api/bridge-v2/flows/{flow}/start-coding` | `start_coding.py` |
| Attach viewer | `POST /api/bridge-v2/flows/{flow}/attach-tmux` | `attach_tmux.py` |

Sessions are named by role key (e.g., `archi01`, `imple01`). The attach
action creates a viewer session (`flow-<flow_key>`) that links all role
sessions as windows for easy monitoring.

## Platform Support

| Platform | Status |
|----------|--------|
| **Linux** | Native — fully supported (Ubuntu 24.04+, Debian 12+) |
| **macOS** | Supported via Homebrew (python, tmux, ollama) |
| **Windows** | **WSL2 required** — tmux has no native Windows port. Install WSL2 with Ubuntu, then follow Linux setup. Native Windows is not supported. |

## Language Policy

- **en-US** is mandatory for all code, comments, docstrings, commit messages,
  and inter-role bridge communication.
- Human may use Danish — but prompts forwarded to other roles MUST be
  translated to English.
