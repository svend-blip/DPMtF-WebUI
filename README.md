# DPMtF-WebUI — Father Project

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

**Install order — each step's preflight checks the one before it:**

1. **model-allocator** — on every machine that runs models (Father and
   each worker), with that machine's own config files.
2. **DPMtF-WebUI** — on Father: `init_db` → `migrate` → uvicorn on 9130.
3. **mcp-light** — on Father (optional but standard): loopback unit, plus
   the tailnet unit if remote workers should reach it.
4. **DPMtF-LightWorker** — on each worker: venv → `worker.yaml` → auth
   token → base client config → `preflight.sh` 16/16 → daemon.

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

## Core Systems

### BridgeV002 — AI Role Dispatch

Database-driven dispatch system for AI role-to-role communication. All flow
configuration — roles, steps, conventions, deliverable paths — is stored in
the database and resolved at runtime. No flow-specific hardcoding in dispatch
code.

- **Flows** — configurable step sequences stored in `bridge_flows` +
  `bridge_flow_steps`. Active flows:
  - `strict_review` — architect → implementer → technical review → governance
    review → human (5 steps, fully automated)
  - `cloud_llm` — cloud LLM variant using Freebuff frontends
  - `cloud_pay` — cloud LLM variant using Anthropic API proxy
  - `trade_cockpit_simulation_v001` — daily research-to-simulation chain
    (7 steps: trend → market → analyst → risk → review → sim → portfolio)
  - `trade_cockpit_scoring_v001` — periodic scoring and learning

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
  model aliases, governance files, and enter commands. 25 active roles across
  all flows.
- **Conventions** — `bridge_convention_rules` with `content_template` and
  `validation_schema` for handoff, callback, technical_review, verdict,
  human_delivery, escalation, and json_output rule keys.
- **Signals** — `signal_send` (initial dispatch), `signal_complete` (chain
  advancement), `signal_escalation` (review → architect question),
  `signal_answer` (architect → review response). All via `dispatch.py`.

**Key dispatch features:**

- **Tool-aware injection** — detects opencode vs Claude Code in target tmux
  session and adapts injection method (send-keys for short prompts, paste-buffer
  for long)
- **XML tag stripping** — opencode models hallucinate XML function calls when
  they see XML tags; `_strip_xml_tags()` converts XML section headers to plain
  text before injection
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

- **`app.py`** (145 lines) — thin FastAPI entrypoint; all endpoints live in
  10 domain routers under `routers/`:
  - `bridge.py` (45 endpoints) — flows, roles, steps, conventions, dispatch,
    tmux session management, allocator proxy
  - `system.py` (15) — health, config, system info
  - `panels.py` (11) — frontend panel CRUD, layout slots
  - `sessions.py` (8) — Claude session management
  - `prompt_compiler.py` (5) — handoff prompt compilation
  - `git.py` (5) — git operations
  - `validation.py` (5) — deliverable validation
  - `webui.py` (5) — webui migration targets
  - `app_profiles.py` (3) — user profile panels
  - `governance.py` (2) — governance file access
- **94 API endpoints** total

### Database

- **SQLite** (`databases/dpmtf.db`) with 39 tables
- **Versioned migrations** — `scripts/db/*.sql` applied by `scripts/migrate.py`
  (tracked in `schema_migrations`). 8 migrations to date. Schema changes are
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

### Claude Code Skills

`.claude/skills/` contains role-specific skill definitions:
- `STRICTREVIEW` — strict_review flow monitoring and chain advancement
- `CLOUDLLM` — cloud LLM flow configuration
- `CLOUDPAY` — cloud pay flow configuration

## Testing

```bash
python3 -m pytest tests/ -q    # 159 tests, all passing
```

26 test files covering:
- Job queue models, scheduler, integration, spikes
- Bridge endpoints, dispatch, convention rules
- Checkpoint schema and integration
- Migration tests (005, 007)
- Runtime modules, safe resolve, action schema
- E2E pipeline and full cycle workflow
- Handoff compiler, context fit
- Allocator config endpoints
- Model lease

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
