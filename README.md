# DPMtF-WebUI — Father Project

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem. It owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself). It also hosts **BridgeV002** — the database-driven
dispatch system for AI role-to-role communication.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database (idempotent — safe to run multiple times)
python3 scripts/init_db.py

# Start the application
uvicorn app:app --host 0.0.0.0 --port 9130 --reload

# Health check
curl http://localhost:9130/api/health
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
for all DPMtF projects. General templates (01-300) define universal rules.
Flow-specific templates (401-405) take precedence when operating within a
BridgeV002 flow.

## Project Structure

```
DPMtF-WebUI/
├── app.py                  # FastAPI backend (~4000 lines)
├── config.py               # Central configuration — single source of truth
├── dpmtf.ini               # App-config defaults (committed)
├── .env                    # Secrets + infrastructure vars (NEVER commit)
├── requirements.txt        # Python dependencies
├── CLAUDE.md               # Project reference for Claude Code
├── README.md               # This file
├── templates/
│   └── index.html          # Single-page application HTML
├── static/
│   ├── js/dpmtf-app.js     # Frontend JavaScript (~5000 lines)
│   └── css/dpmtf-theme.css # Dark theme (GitHub-dark palette)
├── scripts/
│   ├── init_db.py          # Database initialization + seed data
│   ├── initialize_new_webui.py  # Accelerated WebUI Factory
│   └── bridgeV002/         # BridgeV002 dispatch system
│       ├── dispatch.py     # Universal dispatcher (4 signals)
│       ├── bridge_lib.py   # Database lookup, convention resolution
│       ├── post-dispatch-common.py  # Post-dispatch: validate + ollama stop
│       ├── start_tmuxflow.py    # Create tmux sessions for a flow
│       ├── start_coding.py      # Launch AI tools in tmux sessions
│       ├── stop_tmuxflow.py     # Kill tmux sessions for a flow
│       └── attach_tmux.py       # Build viewer session for a flow
├── docs/
│   ├── governance-templates-v2/ # Authoritative governance (all projects)
│   │   ├── 01-04 + 10-29 + 99-300  # General governance files
│   │   ├── 401-405_STRICT_REVIEW_*.md  # Flow-specific role templates
│   │   └── knowledge-fragments/  # Curated .md fragments for Prompt Compiler
│   └── superpowers/              # Design specs and implementation plans
├── databases/
│   └── dpmtf.db            # SQLite database (runtime state)
└── .claude/
    └── skills/STRICTREVIEW/ # Architect cold-start skill
```

## Configuration

Two files control all configurable values:

- **`dpmtf.ini`** — App-config defaults (committed to git, no secrets)
- **`.env`** — Secrets + infrastructure vars (NEVER commit)

Key environment variable:
```bash
export DPMTF_BRIDGE_DIR=/home/<you>/flows   # BridgeV002 deliverable directory
```

See `docs/governance-templates-v2/300_SETUPINSTRUCTION.md` for full setup guide.

## Governance

All roles MUST read their governance file before acting:

- **Human:** `01_HUMAN.md`
- **Architect (strict_review):** `402_STRICT_REVIEW_ARCHI01.md`
- **Implementer (strict_review):** `403_STRICT_REVIEW_IMPLE01.md`
- **Technical Review (strict_review):** `404_STRICT_REVIEW_REVIEW01.md`
- **Governance Review (strict_review):** `405_STRICT_REVIEW_REVIEW02.md`

General coding standards, validation rules, and git policy are in the
01-99 series. The 400-series takes precedence when operating within a
BridgeV002 flow.

## Language Policy

- **en-US** is mandatory for all code, comments, docstrings, commit messages,
  and inter-role bridge communication.
- Human may use Danish — but prompts forwarded to other roles MUST be
  translated to English.
