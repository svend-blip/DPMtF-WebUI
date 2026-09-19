# DPMtF-WebUI — Father Project

## DPMtF — The right model, the right harness, the right role

**DPMtF (Deterministic Process Management to Finalisation)** is an open-source framework for coordinating multiple AI agents, models, and coding tools through a controlled process from defined intent to verified completion.

Instead of using the same — and often most expensive — LLM for every task, DPMtF is designed around assigning **the model that best fits each role**.

A powerful premium model can be used for architecture, planning, supervision, or difficult decisions, while lower-cost cloud models or local models can handle implementation, routine work, decomposition, or parts of the review process. The Model Allocator keeps model selection separate from the workflow itself, allowing roles to move between local and cloud-based models without redesigning the process.

The same principle applies to the tools surrounding the model.

DPMtF supports multiple **coding harnesses**, including Codex, Claude Code, OpenCode, DeepSeek Harness, Whip, Simple Harness, and others. The Harness Allocator keeps harness selection separate from model selection, because the best harness is not necessarily the same for every model or every role.

A powerful cloud agent may benefit from a feature-rich coding harness, while a local model may perform better through a lighter harness with less overhead. DPMtF therefore treats the model and the harness as separate parts of the execution configuration rather than forcing every agent through the same toolchain.

At the center, **[DPMtF-WebUI](https://github.com/svend-blip/DPMtF-WebUI)** coordinates flows, roles, governance, dispatch, gates, and verification. **[Model Allocator](https://github.com/svend-blip/model-allocator)** resolves and manages the models. **[Harness Allocator](https://github.com/svend-blip/harness-allocator)** provides the appropriate coding environment. **[mcp-light](https://github.com/svend-blip/mcp-light)** gives agents controlled, read-only access to governance and project context. **[DPMtF-LightWorker](https://github.com/svend-blip/DPMtF-LightWorker)** allows execution to be distributed to other machines while the central DPMtF system remains in control.

The result is an AI workflow that can be optimized per role for **capability, cost, speed, local hardware, privacy, and tooling** instead of using premium models and heavyweight tools everywhere.

DPMtF is not about finding one AI agent that can do everything.

It is about building a governed AI team where different agents can do what they are best suited for — and where their work is moved through a deterministic process toward a verified result.

**The right model, the right harness, the right role — premium resources only where they add value.**

**The DPMtF ecosystem:** [DPMtF-WebUI](https://github.com/svend-blip/DPMtF-WebUI) · [model-allocator](https://github.com/svend-blip/model-allocator) · [harness-allocator](https://github.com/svend-blip/harness-allocator) · [mcp-light](https://github.com/svend-blip/mcp-light) · [DPMtF-LightWorker](https://github.com/svend-blip/DPMtF-LightWorker) · [simple-harness](https://github.com/svend-blip/simple-harness)

---

**DPMtF — Deterministic Process Management to Finalisation.**

DPMtF is a deterministic multi-agent process orchestration framework for
taking defined work from intent to verified finalisation through governed
flows, steps, roles, harnesses, models, gates, and artifacts.

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem. It owns the
authoritative governance templates under
`docs/governance-templates-v2/`, runs the **BridgeV002** dispatch system
for AI role-to-role communication, and acts as the **Prompt Compiler**
for every project — including itself.

## Overview

### Place in the DPMtF Ecosystem

Five components, one machine boundary:

| Component | Role | Depends on / Provides |
|---|---|---|
| **DPMtF-WebUI** (this repo, `:9130`) | Father — owns governance templates, BridgeV002 dispatch, web UI, and the SQLite production DB (`databases/dpmtf.db`). The Prompt Compiler for every project. | Provides governance; consumes the broker seam. |
| **model-allocator** (`~/model-allocator`) | Resolves role→model on the local GPU; cold-start and stop a model on demand. | Provides GPU-resident inference; depends on DPMtF-WebUI's broker signal path. |
| **mcp-light** (`~/mcp-light`, `:9135`) | Read-only context server. Loopback for Father's own roles; a second Tailscale instance for workers. | Provides loopback MCP context. |
| **DPMtF-LightWorker** (`~/DPMtF-LightWorker`) | Polls Father over Tailscale; executes one role at a time in a disposable worktree. | Provides remote role execution; depends on the broker and the mcp-light tailnet instance. |
| **harness-allocator** (`~/harness-allocator`) | Allocates coding harnesses (Codex CLI / Claude Code / DeepSeek Harness / OpenCode) for harness-backed roles. | Provides harness residency; the bridge daemon writes token leases into `lightworker_worker_tokens`. |
| **harness-allocator** (cross-reference) | The bridge resolves `harness_source` per role (column `bridge_roles.default_harness_source`); `scripts/bridgeV002/start_coding.py` launches the matching harness client. | Depends on the role-level harness-source column. |

`harness-allocator` is named twice — once in the table above as the
allocation service, and once as the integration surface the bridge talks
to (TG5 ≥ 2 lines).

## Architecture

### The Three-Layer Bridge

BridgeV002 is the dispatch protocol every flow uses. A flow type may
leave a layer thinner, never different.

| Layer | What it does | Live surface |
|---|---|---|
| **Delivery** | How a prompt reaches a role. | `tmux` injection with `verify_injection_submitted`; the persistent Harness Terminal (`scripts/bridgeV002/harness_terminal.py`) for harness-backed roles. |
| **Advancement** | How the chain moves from one role to the next. | The broker's two DB queues — `bridge_dispatch_queue` and `bridge_materialize_queue` — are the ONLY role-facing signal path. Every `chain_advancement` block in a handoff template enqueues via `scripts/bridgeV002/bridge_broker.py enqueue`; no role invokes `dispatch.py` directly in normal flow. |
| **Recovery** | What acts when the chain does not move. | `scripts/bridgeV002/chain_watchdog.py` polls each flow and nudges with the correct normalized `--id`; `bridge_flows.supervisor_role` names the wake-up target for stall escalation (migration 065 seeded it for the five autonomous flows); `scripts/bridgeV002/supervisor_state.py --flow {flow_key}` reports the active run; the evidence gate (`scripts/bridgeV002/gate-deliverable-evidence.py`) blocks review dispatch when a deliverable's claims do not survive contact with the working tree. |

The systemd user units (live in the tree):

- `scripts/bridgeV002/bridge-broker.service` — the broker daemon. REQUIRED for any flow with sandboxed roles; without `active`, queued signal rows pile up and the chain silently stalls.
- `scripts/bridgeV002/chain-watchdog.service` — the stall watchdog.

Full three-layer model — including the Harness Source column, the
`callback` convention rule, the lease sweep, and the generalized stall
wake-up: `docs/governance-templates-v2/100_BRIDGE.md`.

### Flow Types

A new BridgeV002 flow is wired by copying its type's row. The columns
are non-overlapping — a flow belongs to exactly one type, classified
by **who authors the start artifact** and **who drives the first
dispatch**.

| Type | Flows | Start artifact | First dispatch | Verification |
|---|---|---|---|---|
| **Supervisor-driven** | `llama_SG`, `preferred_cloud`, `preferred_cloud_harness`, `reveng` (and `supervised_review` with the autonomous `supervisor_auto`) | `runs/NNN/GOAL.md` + `BACKLOG.md` + `RUN-LEDGER.md`; Human approves by renaming `GOAL-DRAFT.md` → `GOAL.md` | Wake-up to `bridge_flows.supervisor_role` (broker `enqueue --action signal-send`) | `python3 scripts/bridgeV002/supervisor_state.py --flow {flow_key}` |
| **Architect-driven** | `strict_review`, `cloud_llm`, `cloud_pay` | A handoff file in `{flow}/handoffs/{NNN}-handoff.md`; the contract lives in the handoff | `python3 scripts/bridgeV002/dispatch.py --signal-send --from-role <architect>` (or broker seam) | The first role's cold-start skill |
| **Bare / other** | `supervisor`, `pi_test`, `lightworker` | Per-flow minimal contract | Manual | n/a |

Bring-up sequence (any flow):

```bash
python3 scripts/bridgeV002/start_tmuxflow.py {flow_key}
python3 scripts/bridgeV002/start_coding.py {flow_key}
# For harness-backed roles, the persistent Harness Terminal:
python3 scripts/bridgeV002/harness_terminal.py \
  --role {role_key} --harness {harness_key} --model {model_alias} \
  --flow {flow_key} --cwd {path}
systemctl --user is-active bridge-broker.service   # MUST print 'active'
```

Full binding contract (cold-start, supervisor wake-up, broker daemon
precondition, the seven Binding Rules): `docs/governance-templates-v2/103_FLOW_STARTUP.md`.

## Requirements

- Python 3.10+ with the pinned dependencies in `requirements.txt`
  (FastAPI, uvicorn, pytest — no new dependency without Human approval).
- SQLite (bundled with Python), tmux, git.
- Companion services as configured: model-allocator (CLI), mcp-light
  (`:9135`), harness-allocator (imported package), and their web UIs on
  `:9141`/`:9142` (see `[integration]` in `dpmtf.ini`); knowledge-service
  (`:9140`) when `[knowledge]` is enabled — without it retrieval answers
  empty and nothing else is affected.

### Ecosystem dependencies and installation order

**This repository is row 4.** It owns the governance templates, BridgeV002 and the database that mcp-light reads; it is a client of knowledge-service over HTTP (`[knowledge]` in `dpmtf.ini`, service mode) and keeps no retrieval provider of its own.

The same table is in the README of each of the six repositories; it was
written from the code on 2026-09-19 and follows it. Install top to bottom: each row
needs only rows above it.

| # | Repository | Needs | Serves | Needed by |
|---|---|---|---|---|
| 0 | a model runtime (Ollama, FreeToken, llama.cpp, a cloud endpoint) | — | an OpenAI-compatible `/v1` endpoint | every harness |
| 1 | [simple-harness](https://github.com/svend-blip/simple-harness) | Go 1.27 to build; row 0 to run | the `simple-harness` command on `PATH` | FlowRunner steps that name it, DPMtF-WebUI roles launched through harness-allocator |
| 2 | [scope-mcp](https://github.com/svend-blip/scope-mcp) | Node >= 22.5 (built-in `node:sqlite`) | a stdio MCP server; state in `<workspace>/.scope-mcp/state.db` | any harness that declares it (row 6) |
| 3 | [knowledge-service](https://github.com/svend-blip/knowledge-service) | Python >= 3.11; provider `leann`: a CUDA GPU with ~2.5 GB free VRAM; provider `portable`: CPU only | `http://127.0.0.1:9140/v1` — retrieval over LEANN indexes | mcp-light (four `knowledge_*` tools), DPMtF-WebUI (service mode) |
| 4 | [DPMtF-WebUI](https://github.com/svend-blip/DPMtF-WebUI) | Python 3.10+, tmux, git; [model-allocator](https://github.com/svend-blip/model-allocator) and [harness-allocator](https://github.com/svend-blip/harness-allocator) beside it; a harness on `PATH` (row 1); row 3 optional | `:9130`, the governance templates, BridgeV002, `DPMtF-WebUI/databases/dpmtf.db` | mcp-light (reads its files and database) |
| 5 | [mcp-light](https://github.com/svend-blip/mcp-light) | Python 3.8+, `mcp[cli]`; read access to the DPMtF-WebUI checkout and database (row 4) and to `model-allocator/allocator.db`; row 3 for the knowledge tools | `http://127.0.0.1:9135/mcp` — read-only MCP context server | any harness that declares it (row 6) |
| 6 | harness wiring | rows 1, 2, 5 | `~/.simple-harness/config.json` with an `mcp_servers` entry per server | every simple-harness run on the machine, whoever launched it |
| 7 | [FlowRunner](https://github.com/svend-blip/FlowRunner) | Go 1.27 to build; at run time, every harness a FlowApp's steps name, on `PATH` (row 1 for `simple-harness`) | the `flowrunner` command and desktop app | — |

Rows 1, 2 and 3 depend on nothing else in the table and can be installed
in any order. knowledge-service's one-time `import-registry` step reads
the DPMtF-WebUI database, so run that step after row 4; the service itself
does not need DPMtF-WebUI at run time.

#### Row 6: what wires a harness to the servers

simple-harness takes its MCP servers from its own configuration:
`~/.simple-harness/config.json`, then the nearest
`.simple-harness/config.json` at or above its working directory, then the
file `SIMPLE_HARNESS_CONFIG_FILE` names. A later file replaces an earlier
one's `mcp_servers` whole. FlowRunner writes that last file for a FlowApp
that declares `mcp_servers` (see below); DPMtF-WebUI's BridgeV002 writes
none, so its roles get what the machine's own files declare:

```json
{
  "mcp_servers": [
    { "name": "mcp-light", "transport": "http",
      "endpoint": "http://127.0.0.1:9135/mcp", "permission": "read_only",
      "allowlist": ["get_governance_index", "get_governance_file",
                    "knowledge_search", "knowledge_scopes",
                    "knowledge_learning", "knowledge_retrievals"] },
    { "name": "scope-mcp", "transport": "stdio",
      "command": ["node", "/abs/path/to/scope-mcp/src/server.js"],
      "permission": "workspace_write" }
  ]
}
```

Without the `knowledge_*` names in the allowlist an agent has no
retrieval. Without the scope-mcp entry it has no durable project state:
no simple-harness configuration declares scope-mcp unless you add it. A
stdio server is started in the workspace, so scope-mcp keeps its state
with the project.

#### How LEANN retrieval reaches an agent

```text
model in a harness
  -> the harness's MCP client              (mcp_servers, row 6)
  -> mcp-light          :9135/mcp          knowledge_search / _scopes / _learning / _retrievals
  -> knowledge-service  :9140/v1           /v1/search, /v1/scopes, /v1/learning, /v1/retrievals
  -> LEANN (hnsw, CUDA)  or the portable CPU provider
```

LEANN lives in knowledge-service and nowhere else. mcp-light is its only
MCP face. scope-mcp has no retrieval of any kind, and simple-harness has
none of its own: it is a generic MCP client that also fills in `run_id`,
`handoff_id` and `flow_key` on MCP calls from `SIMPLE_HARNESS_RUN_ID`,
`SIMPLE_HARNESS_HANDOFF_ID` and `SIMPLE_HARNESS_FLOW_KEY`, so that a
retrieval can be attributed to the run that made it.

#### What is and is not automatic

- FlowRunner has no default harness: every step of a FlowApp names one,
  and an empty `harness:` fails validation. A step that names
  `simple-harness` gets whatever `simple-harness` resolves to on `PATH`
  at dispatch — so a rebuilt simple-harness is used by the next run with
  no change to FlowRunner. The Windows bundle carries its own
  `simple-harness.exe`; FlowRunner's `build-windows-bundle.sh` script
  builds the three programs together and stamps the commits into
  `BUILD-INFO.txt`.
- A FlowApp declares its MCP servers (`mcp_servers:` in `app.yaml`:
  `endpoint_env` for an http server, a `command` with `${VAR}` references
  for a stdio one). FlowRunner's preflight connects to each — a real MCP
  handshake and tool listing — and the run is handed exactly those servers
  through `SIMPLE_HARNESS_CONFIG_FILE`, written under FlowRunner's runtime
  root, never into the workspace. `flowrunner mcp <flowapp-id>` and the
  desktop's green pills show which declared servers FlowRunner is
  connected to. A FlowApp that declares none leaves simple-harness with
  the machine's `~/.simple-harness/config.json`, as before: on a machine
  without that file such a FlowApp runs with no MCP server at all.
- A FlowApp's `knowledge:` block reaches a harness as
  `KNOWLEDGE_PROVIDERS` and `KNOWLEDGE_<NAME>_URL`. simple-harness does not
  read them: for a simple-harness step retrieval comes through an MCP
  server that offers `knowledge_search` (mcp-light does), and FlowRunner's
  preflight refuses a FlowApp that enables knowledge, runs simple-harness
  steps and declares no such server, instead of letting it run and
  retrieve nothing.
- Both launchers hand simple-harness the model's context window, as its
  configured limit (`SIMPLE_HARNESS_CONTEXT_MODEL_LIMIT`). The harness
  bounds a run — pruning, compaction — only when it knows the window; it
  asks the runtime, and a cloud API does not answer, so without this a
  cloud run is unbounded. FlowRunner takes the value from `context_window`
  in the FlowApp's model binding (DPMtF-WebUI's exporter fills it in) and
  shows it per profile in preflight; BridgeV002 takes it from the
  model-allocator alias's `context`. The harness still takes the smaller of
  this and what a local runtime reports.
- A window says what the model can hold; a **context budget** says what a
  role may use. On a 1,000,000-token window the window bounds nothing a run
  will reach, and every turn resends the whole history. DPMtF-WebUI's role
  editor has a Context Budget per role (`bridge_roles.context_budget`); the
  smaller of window and budget goes to the harness, from BridgeV002 directly
  and from FlowRunner through the binding's `context_budget`, which the
  exporter fills in. Empty means the window.
- Both launchers set the three position variables. FlowRunner sets them
  from the family run number, the handoff cycle and the FlowApp id.
  BridgeV002's role terminal sets them per delivered prompt — a pane
  outlives its handoffs — from the flow key, the run the chain is
  executing and the handoff id field of the prompt; what it does not know
  it does not set.
## Installation

### Install manually

```bash
git clone https://github.com/svend-blip/DPMtF-WebUI.git
cd DPMtF-WebUI
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env            # secrets and machine paths — never committed
venv/bin/python scripts/init_db.py    # runs migrations, seeds, idempotent
```

### Install using an Agent

Point your coding agent at this repository; `CLAUDE.md` and
`docs/governance-templates-v2/` are the binding instructions it must read
first. The manual steps above are the whole install; the judgement calls
live in `.env` and `dpmtf.ini`.

### Verify installation

```bash
venv/bin/python -m pytest tests/ -q
venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130 &
curl -s http://localhost:9130/api/health    # {"status": "healthy", ...}
```

## Configuration

`config.py` is the single source of truth for every configurable value —
hardcoded `/home/svend/...`-style paths are an auto-fail:

- `.env` — secrets and infrastructure variables (never committed).
- `dpmtf.ini` — committed app-config defaults: `[app]` port/host/locale,
  `[paths]`, `[projects]`, `[integration]` (companion web-UI URLs),
  `[knowledge]` (retrieval through the standalone knowledge-service at
  `http://127.0.0.1:9140`, service mode; enabled in the committed
  `dpmtf.ini`; the client is in `knowledge/`).
- `databases/dpmtf.db` — the production DB; schema changes are numbered
  migrations under `scripts/db/` applied by `scripts/migrate.py`.

## Running

```bash
venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130   # the web UI (no --reload)
```

Two always-on systemd user units accompany it (broker + watchdog, below),
and flows are started from the web UI (Flows panel → Start tmux / Start
code interface) or the equivalent scripts.

## Testing

```bash
venv/bin/python -m pytest tests/ -q
```

Regression testing is governed by the test selection policy in
`.dpmtf/test-policy.json`, consumed by the test-impact engine
(`scripts/testing/`, spec `docs/specs/TEST-IMPACT-ARCHITECTURE.md`): a
change runs the policy-resolved selection for its changed files, and
uncertainty escalates toward the full suite — never past it. Changes to
the engine itself or to the policy file always run everything. The
`gate-test-impact` pre-dispatch gate applies the same selection inside
BridgeV002 flows and records an impact artifact per handoff. Delivery
stalls are measured with `scripts/trace_delivery_stats.py` (per-day
DELIVERED/ATTEMPTS plus three failure classes from the trace log).

The mechanical validation checklist every change must pass is summarized
in the Validation section below; `13_VALIDATION.md` is authoritative.

## Runtime Services

Two always-on systemd user units:

- `scripts/bridgeV002/bridge-broker.service` — the broker daemon. Installed at `~/.config/systemd/user/bridge-broker.service`. Materialize and dispatch queues; the only role-facing signal path.
- `scripts/bridgeV002/chain-watchdog.service` — the stall watchdog. Polls each flow, nudges stalled chains, escalates to `bridge_flows.supervisor_role` when the nudge budget is exhausted.

Sandbox-safe status commands (run from any working tree):

```bash
python3 scripts/bridgeV002/bridge_broker.py status --queue both
python3 scripts/bridgeV002/supervisor_state.py --flow preferred_cloud_harness
```

Step-key execution resolution. Every step resolves governance, model,
harness, and `implementation_mode` through a single deterministic
precedence walk:

```
STEP → ROLE → SYSTEM   (governance, model, harness)
role > step > flow > 'direct'   (implementation_mode, delegated to patch_mode)
```

The resolver lives in `scripts/bridgeV002/execution_config.py`
(`resolve_execution_config(flow_key, step_key)` — returns 13 keys
including each dimension's `*_source_level`). The RUNTIME CONTEXT block
injected at the top of every role's prompt is rendered from that dict
(`render_runtime_context`); the generic behavioral governance files
(`IMPLEMENTOR.md`, `REVIEW.md`, `SUPERVISOR_AUTONOMOUS.md`, `ARCHITECT.md`,
`HUMAN.md`, plus the addendum files) bind on that block rather than
naming flows or roles.

The resolver is exposed over HTTP for operator inspection
(`routers/bridge.py`):

```
GET /api/bridge-v2/flows/{flow_key}/steps/{step_key}/execution-config
```

returns the resolver dict verbatim — `flow_key`, `step_key`,
`from_role`, `to_role`, `governance_file`, `governance_source_level`,
`model_source`, `model_alias`, `model_source_level`, `harness_source`,
`harness_profile`, `harness_source_level`, `implementation_mode`. 404
when the flow or step is unknown.

### Model residency at role transitions

`dispatch.py` decides what happens to the sender's allocator-managed model
when the chain moves to the next role (`_from_model_disposition`):

| Receiver | Sender's local model |
|---|---|
| binds no GPU (cloud alias, human role) | **kept resident** — lease released without stop |
| local (needs the GPU) | stopped before the receiver is warmed (VRAM-first swap) |
| same alias / no allocator sender | untouched |

The discriminator is the allocator's `resolved_gpu`, never the backend
name; an unreadable allocator fails closed to "stop". Session context is
fresh regardless: every dispatch opens a new harness session, and a local
server's prefix cache is only a cache. Before this rule a flow with one
local model paid a ~2 min reload on every return to it and the stop cut
the sender's post-signal narration (a benign exit 3).

### Per-role ceilings and the verdict wake-up

- `bridge_roles.max_turns` (per role) and `bridge_roles.max_output_tokens`
  reach simple-harness as `SIMPLE_HARNESS_MAX_TURNS` /
  `SIMPLE_HARNESS_MAX_OUTPUT_TOKENS` at pane launch. An output ceiling
  that is too small truncates a large `write_file` call mid-JSON and the
  harness reports exit 3 with no text — the last usage line then shows
  `completion_tokens == ceiling`.
- The kickoff prompt and every handoff start from deterministic scripts:
  `scripts/bridgeV002/kickoff_packet.py --flow <eloop> --run <NNN>` (the
  predecessor is the highest lower run; `databases/dpmtf.db` never counts
  as dirt) and `scripts/bridgeV002/handoff_skeleton.py --flow <eloop> --id <N> --to <role>`.
  A skeleton whose `<task>` still carries the placeholder is not a delivery.
- A verdict callback carries `<verdict_summary>`, `<next_action>` and
  `<stop>` blocks rendered from the verdict file (migration 100), so the
  decomposer reads the status and the next action before opening the file.
- A result file must carry a section headed exactly `## README Impact`
  with `README impact: yes|no` and `Reason:`; the two lines alone are
  refused as `README_IMPACT_BLOCK_MISSING`.
- The test-impact gate (`scripts/bridgeV002/gate-test-impact.py`) runs the
  planner's selection with an interpreter that has pytest (repo `venv`
  first, then `sys.executable`, never a bare `python3`); an environment
  failure is `ERROR` with its message, not `FAIL`, and the timeout comes
  from `.dpmtf/test-policy.json` (`test_timeout_seconds`).

## Validation

The validation standard is bound at `docs/governance-templates-v2/13_VALIDATION.md`.
Every change set MUST pass the pre-commit checks before a reviewer
signs off. The mechanical subset, summarized:

| Check | Command | Pass |
|---|---|---|
| Backend syntax | `python3 -m py_compile <file>` | rc=0 |
| Frontend syntax | `node --check static/js/*.js` | rc=0 each |
| Shell syntax | `bash -n <file>` | rc=0 |
| Diff scope | `git diff --stat` | changes within phase scope |
| innerHTML | `grep -RIn "innerHTML" static/js/ --exclude-dir=__pycache__ \\|\\| echo "no_innerHTML"` | prints `no_innerHTML` |
| i18n | every user-facing string uses `lbl(key, fallback)` | bare English in `static/js/` is a fail |
| Dependencies | `git diff requirements.txt` is empty | no new deps |
| Schema | `git diff` contains no `ALTER TABLE` / `CREATE TABLE` | no schema change without phase authorization |

The full test suite:

```bash
python3 -m pytest tests/ -q
```

A regression green baseline (tests/test_execution_config.py +
tests/test_preferred_cloud_harness.py) runs in under 15 seconds; the
reviewer is expected to keep it green across every handoff.

## TROUBLESHOOTING

A role pane whose harness has exited shows a bare shell prompt — the
harness process is gone and the pane is no longer running an active role.

Relaunch every coding frontend for a flow with:

```bash
python3 scripts/bridgeV002/start_coding.py <flow_key>
```

This restarts the matching coding client for each role whose
`harness_source` resolves to a coding harness in that flow.

Launch-only environment keys. DeepSeek Harness (`dsh`) refuses to boot when a
project `.env` sets `DSH_V4_PRO_PATCH` ("only the launching environment may
set"). Keep that key out of every `.env` under a flow target; export it in
the environment that launches the process instead (`~/.bashrc`,
`Environment=` in `bridge-broker.service`, the shell that starts the 9130
app) and in `harness-allocator.ini` `[harness] dsh_v4_pro_patch`.

Session attribution. `~/.simple-harness/sessions/` is shared by every role
of every flow family; a session belongs to a role only by its
`session.json` `config.workspace`, never by id or recency.

Local model dies right after loading under the broker but starts fine from
a shell: the systemd unit has no CUDA toolkit on `PATH`, so a runtime that
JIT-builds kernels picks the apt `nvcc` and refuses the version mismatch.
Set `Environment=CUDA_HOME=/usr/local/cuda-<ver>` on the unit; the
FreeToken adapter prepends `$CUDA_HOME/bin` to the server's `PATH`.
