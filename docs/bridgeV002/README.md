# BridgeV002 — Configuration-Driven Flow System

## Overview

BridgeV002 replaces hardcoded role names and flow logic with INI-driven configuration. All roles, flows, scripts, and deliverables are defined through config files rather than Python code.

## Directory Structure

```
docs/bridgeV002/
├── bridgeV002.ini     # Global bridge configuration
├── README.md          # This file
├── flows/             # Flow definitions (INI)
│   ├── heavy.ini      # Full chain: Architect→Implementer→Review1→Review2→Human
│   ├── simplified.ini # Direct: Implementer→Review
│   └── escalation.ini # Ad-hoc escalation flows
└── roles/             # Role configurations (INI)
    └── default.ini    # All [role:NAME] sections

scripts/bridgeV002/    # Reusable Python scripts
├── dispatch.py        # Universal dispatcher for all role transitions
├── role_setup.py      # Start session with correct model/tool
├── role_teardown.py   # Kill session + unload model + free VRAM
└── bridge_lib.py      # Config reading, placeholder resolving, utilities
```

## Configuration Files

### Global Config (bridgeV002.ini)

Defines paths, defaults, and migration settings for the bridge system.

Key sections:
- `[bridge]` — bridge directory, default flow, max parallel runs (always 1), dispatch timeout
- `[paths]` — directories for flows, roles, scripts, and database
- `[migration]` — legacy bridge path and migration state

### Role Config (roles/default.ini)

Defines all available roles with their runtime parameters.

Each `[role:NAME]` section includes:
- `tmux_session` — tmux session name
- `start_cmd` — command to launch the role's environment
- `model_type` — `cloud`, `ollama`, or `hybrid`
- `cloud_model` / `ollama_model` — model identifiers per type
- `setup_script` / `teardown_script` — scripts for session lifecycle
- `deliver_error_msg` — error message on delivery failure

### Flow Definitions (flows/)

Each flow is an INI file defining a sequence of steps.

Key sections:
- `[flow]` — name, description, ordered list of steps
- `[step:NAME]` — from_role, to_role, deliverable directory/pattern, pre/post scripts

## Placeholders

INI values use placeholders resolved at runtime:

| Placeholder | Resolved To |
|-------------|------------|
| `{BRIDGE_DIR}` | Bridge data directory (from env or `~/.bridge`) |
| `{PROJECT_ROOT}` | DPMtF-WebUI project root |
| `{SCRIPTS_DIR}` | `{PROJECT_ROOT}/scripts/bridgeV002` |

## Design Principles

1. **Sequential only** — max_parallel = 1, no concurrent role sessions
2. **Config-driven** — no hardcoded role names in Python scripts
3. **Reusable scripts** — `dispatch.py`, `role_setup.py`, `role_teardown.py` work for any role/flow
4. **Database integration** — Prompt Compiler UI can define/edit flows from frontend
5. **Migration-ready** — runs parallel to legacy bridge, switches when ready

## Usage

```bash
# Dispatch handoff between roles
python3 scripts/bridgeV002/dispatch.py --from-role architect --to-role implementer --id 091 --deliverable path/to/file.md

# Setup a role session
python3 scripts/bridgeV002/role_setup.py --role implementer

# Teardown a role session
python3 scripts/bridgeV002/role_teardown.py --role implementer
```
