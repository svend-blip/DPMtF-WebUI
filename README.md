# DPMtF-WebUI — Father Project

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
  `:9141`/`:9142` (see `[integration]` in `dpmtf.ini`).

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
  `[paths]`, `[projects]`, `[integration]` (companion web-UI URLs).
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
