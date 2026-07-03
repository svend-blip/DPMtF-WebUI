# DPMtF-WebUI — Father Project

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem. It owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself). It also hosts **BridgeV002** — the database-driven
dispatch system for AI role-to-role communication.

## Quick Start

```bash
pip install -r requirements.txt
python3 scripts/init_db.py
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
