# DPMtF-WebUI — Father Project

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem. It owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself). It also hosts **BridgeV002** — the database-driven
dispatch system for AI role-to-role communication.

## Quick Start

```bash
pip install -r requirements.txt
python3 scripts/init_db.py      # schema + canonical defaults (idempotent)
python3 scripts/seed_bridge.py  # bridge seed data (fresh DB only)
python3 scripts/migrate.py      # apply versioned SQL migrations
uvicorn app:app --host 0.0.0.0 --port 9130 --reload
```

Open `http://localhost:9130` in a browser.

## Core Systems

### BridgeV002 — AI Role Dispatch

Database-driven dispatch system for AI role-to-role communication. Replaces
the legacy `claude-bridge` entirely.

- **Flows** — configurable step sequences (e.g., `strict_review`: architect →
  implementer → technical review → governance review → human)
- **Roles** — per-flow role definitions with tmux sessions, models, and start
  commands
- **Conventions** — content templates for handoff prompts, callback formats,
  and verdict structures
- **Signals** — `send`, `complete`, `escalation`, `answer` via `dispatch.py`

Manage flows, roles, steps, and conventions via the web UI under
**Setup → Bridge Setup**.

### Prompt Compiler

Assembles handoff prompts from knowledge fragments, scope profiles, and
governance rules. Generates BridgeV002 dispatch commands for one-click
delivery to AI roles.

### Governance Templates

`docs/governance-templates-v2/` contains the authoritative governance files
for all DPMtF projects. General templates define universal rules.
Flow-specific templates (400-series) take precedence when operating within a
BridgeV002 flow.

### Model Allocator Integration

The [model-allocator](https://github.com/svend-blip/model-allocator) is a
standalone CLI that resolves stable model aliases (e.g. `imple-fast`,
`review-cloud`) to concrete backends (Ollama, llama.cpp/TurboQuant,
OpenAI-compatible cloud APIs) and manages runtime lifecycle. The WebUI
integrates it via proxy endpoints under `/api/bridge-v2/allocator/*`:

- **Role/step editors** — `model_source` dropdown + alias picker + validate
  button (aliases, validate)
- **Runtime control** — status cards with Start/Stop/Refresh on
  allocator-managed role cards (status, start, stop)
- **Config dashboard** — full alias/role CRUD with detail forms and runtime
  status controls (config show/set/delete)

All endpoints shell out to the allocator CLI — the Father never talks to
model backends directly.

### Trade Cockpit Orchestration

The Father hosts the cronjobs that drive the trade-ui's automated flows:

| Cron | Script | Flow |
|------|--------|------|
| Weekdays 09:00 | `scripts/trade-cronjob.sh` | `trade_cockpit_simulation_v001` |
| Sunday 10:00 | `scripts/scoring-cronjob.sh` | `trade_cockpit_scoring_v001` |

Both dispatch into the trade-ui's inbox via BridgeV002. They produce research
and allocation plans — they never execute trades.

## Architecture

- **`app.py`** (~145 lines) — thin FastAPI entrypoint; all endpoints live in
  domain routers under `routers/` (bridge, governance, prompt_compiler,
  panels, sessions, git, validation, system, webui, app_profiles).
- **Database migrations** — versioned SQL migrations in `scripts/db/*.sql`
  applied by `scripts/migrate.py` (tracked in `schema_migrations`). Schema
  changes are new `00X_*.sql` files — never edits to `init_db.py`.
- **`scripts/init_db.py`** — schema + canonical defaults (i18n labels,
  conventions) only. User-configured data lives in the DB, managed via the
  frontend.
- **mcp-light** — read-only MCP context server (separate repo) exposing
  governance, panels, flows, roles, and verdicts as tools on
  `http://127.0.0.1:9135/mcp`.

## Configuration

Two files control all configurable values:

- **`dpmtf.ini`** — App-config defaults (committed to git, no secrets)
- **`.env`** — Secrets + infrastructure vars (NEVER commit)

Key environment variable:
```bash
export DPMTF_BRIDGE_DIR=/home/<you>/flows   # BridgeV002 deliverable directory
```

See `docs/governance-templates-v2/300_SETUPINSTRUCTION.md` for full setup guide.

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
