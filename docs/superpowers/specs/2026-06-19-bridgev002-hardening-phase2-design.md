---
name: bridgev002-hardening-phase2-script-registry
date: 2026-06-19
handoff: 103
status: approved
---

# BridgeV002 Hardening — Fase 2: Script Registry

## Problem Statement

`bridge_flow_steps` has `pre_dispatch_script` and `post_dispatch_script` columns that are NULL for all rows. There is no way to select scripts via the UI — only manual string entry. A script registry enables dropdown-based selection, making pre/post hooks discoverable and configurable through the frontend.

## Scope

| File | Change | Lines (est.) |
|------|--------|-------------|
| `scripts/init_db.py` | Add `bridge_scripts` table + seed data | ~40 |
| `app.py` | Add GET endpoint for scripts | ~25 |
| `docs/superpowers/specs/2026-06-19-bridgev002-hardening-phase2-design.md` | This file | — |

**Total:** ~65 lines across 2 files + design doc.

## Schema Design

```sql
CREATE TABLE IF NOT EXISTS bridge_scripts (
    script_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    path TEXT NOT NULL,
    stage TEXT CHECK(stage IN ('pre', 'post', 'both')),
    params_required TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

| Column | Type | Purpose |
|--------|------|---------|
| `script_key` | TEXT PK | Unique identifier: `"role_setup"`, `"role_teardown"`, `"dispatch"` |
| `name` | TEXT NOT NULL | Display name for dropdowns: "Role Setup", "Dispatcher" |
| `description` | TEXT | Tooltip/tooltip text explaining what the script does |
| `path` | TEXT NOT NULL | Path relative to project root: `"scripts/bridgeV002/role_setup.py"` |
| `stage` | TEXT (CHECK) | When this script can be used: `'pre'`, `'post'`, or `'both'` |
| `params_required` | TEXT | Comma-separated list of argparse params the script expects |
| `is_active` | INTEGER DEFAULT 1 | Soft-delete support |

### Why not JSON for params_required?

Fase 5 (parameterized script calls) will iterate over these at runtime. A comma-separated string is easier to split in both SQL and Python than parsing JSON from a TEXT column. The stage CHECK constraint prevents invalid values at DB level.

## Seed Data

```python
[
    ("role_setup", "Role Setup",
     "Start role session with fresh context, load correct model/tool",
     "scripts/bridgeV002/role_setup.py",
     "pre",
     "--role"),
    ("role_teardown", "Role Teardown",
     "Stop role session, unload Ollama model, free VRAM",
     "scripts/bridgeV002/role_teardown.py",
     "post",
     "--role,--force"),
    ("dispatch", "Dispatcher",
     "Universal role-to-role transition dispatcher",
     "scripts/bridgeV002/dispatch.py",
     "both",
     "--from-role,--to-role,--id,--flow,--step,--deliverable"),
]
```

These are the 3 existing scripts. When new scripts are added to `scripts/bridgeV002/`, they get registered here.

## API Endpoint

Add GET endpoint following existing BridgeV002 pattern:

```python
@app.get("/api/bridge-v2/scripts")
async def api_bridge_scripts():
    """List all active scripts from bridge_scripts table."""
```

Response format (matches existing `/roles` and `/flows` patterns):

```json
{
    "count": 3,
    "scripts": [
        {
            "script_key": "role_setup",
            "name": "Role Setup",
            "description": "Start role session with fresh context...",
            "path": "scripts/bridgeV002/role_setup.py",
            "stage": "pre",
            "params_required": "--role"
        },
        ...
    ]
}
```

### Why GET-only for Fase 2?

Scripts are registered via `init_db.py` seed data, not through the UI. The frontend needs to read them for dropdowns. POST/PUT/DELETE for scripts can be added in Fase 4 when we build the full Steps CRUD with script selection.

## Integration Points

- **Fase 4 (Steps CRUD):** Step-form will have a dropdown populated from this endpoint
- **Fase 5 (Parameterized calls):** `dispatch.py` will read `params_required` to construct argparse args
- **Status endpoint:** `/api/bridge-v2/status` should report the new table count

## Out of Scope

- POST/PUT/DELETE endpoints for scripts (deferred to Fase 4 if needed)
- Frontend dropdown implementation (Fase 4 task)
- Parameterized script execution (Fase 5 task)
- Status endpoint update — optional, can be added later
