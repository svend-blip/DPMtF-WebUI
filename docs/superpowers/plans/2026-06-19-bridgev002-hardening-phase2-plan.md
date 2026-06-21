# BridgeV002 Hardening — Fase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bridge_scripts` table with seed data and a GET endpoint so the frontend can populate script dropdowns.

**Architecture:** Follow existing BridgeV002 patterns — new CREATE TABLE + INSERT in init_db.py, new list function in bridge_lib.py, new GET endpoint in app.py. No frontend changes this phase.

**Tech Stack:** Python 3, SQLite, FastAPI.

## Global Constraints

- en-US only for all code, comments, docstrings — CLAUDE.md §2
- PEP 8, parameterized SQL only (no f-string SQL) — CLAUDE.md §4
- NO hardcoded `/home/svend/...` paths — use config.py getters — CLAUDE.md §4
- `python3 -m py_compile <file>` MUST pass before signaling completion — CLAUDE.md §4
- Only Human may commit/push — ALL changes remain unstaged after implementation — CLAUDE.md §6
- Follow existing BridgeV002 patterns: table naming (`bridge_*`), seed data with `INSERT OR IGNORE`, endpoint structure with try/except + HTTPException

---

### Task 1: Add `bridge_scripts` table to init_db.py

**Files:**
- Modify: `scripts/init_db.py` — add CREATE TABLE after bridge_flow_steps (~line 3833) and INSERT seed data
- Test: Run init_db.py (idempotent), verify table + rows via SQLite CLI

**Interfaces:**
- Consumes: `cursor` (sqlite3 cursor, already in scope at this point in init_db.py)
- Produces: New `bridge_scripts` table with 3 seed rows

- [ ] **Step 1: Read the insertion point in init_db.py**

Read `/home/svend/DPMtF-WebUI/scripts/init_db.py`, starting around line 3920. Identify the end of the `bridge_flow_steps` INSERT block (after the closing `]` and `)`) and the start of the Spor J labels section (`# ── Spor J: Bridge Setup UI i18n labels`).

The CREATE TABLE + INSERT should go between these two sections, with a comment header:
```python
# ── Fase 2: Bridge Script Registry ────────────────────────
```

- [ ] **Step 2: Add CREATE TABLE statement**

Insert after the `bridge_flow_steps` seed data and before the Spor J labels section:

```python

# ── Fase 2: Bridge Script Registry ────────────────────────

cursor.execute("""
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
""")

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_scripts
       (script_key, name, description, path, stage, params_required) VALUES (?, ?, ?, ?, ?, ?)""",
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
    ],
)
```

**Important notes:**
- Use `cursor.executemany` with parameterized SQL (matching the pattern from bridge_roles/flows above)
- Script paths are relative to project root, not absolute paths
- The CHECK constraint on `stage` validates at DB level — no need for Python-side validation
- `INSERT OR IGNORE` ensures idempotency (safe to run init_db.py multiple times)

- [ ] **Step 3: Verify syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/init_db.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 4: Run init_db.py to apply schema**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/init_db.py 2>&1 | tail -5
```

Expected: Clean execution, no errors. The script is idempotent — running it again should not cause failures.

- [ ] **Step 5: Verify table exists and has seed data**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
rows = conn.execute('SELECT script_key, name, stage FROM bridge_scripts WHERE is_active=1 ORDER BY script_key').fetchall()
print(f'Total active scripts: {len(rows)}')
for r in rows:
    print(f'  {r[0]}: {r[1]} ({r[2]})')
conn.close()
"
```

Expected output:
```
Total active scripts: 3
  dispatch: Dispatcher (both)
  role_setup: Role Setup (pre)
  role_teardown: Role Teardown (post)
```

- [ ] **Step 6: Verify CHECK constraint works**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
try:
    conn.execute(\"INSERT INTO bridge_scripts (script_key, name, path, stage) VALUES ('x', 'Test', 'path.py', 'invalid')\")
    print('FAIL: CHECK constraint did not reject invalid stage')
except sqlite3.IntegrityError as e:
    print(f'PASS: CHECK constraint works ({e})')
conn.close()
"
```

Expected: `PASS: CHECK constraint works (CHECK constraint failed: stage)`

---

### Task 2: Add list function to bridge_lib.py + GET endpoint to app.py

**Files:**
- Modify: `scripts/bridgeV002/bridge_lib.py` — add `list_scripts_from_db()` function
- Modify: `app.py` — add GET `/api/bridge-v2/scripts` endpoint after the flows section (~line 4040)
- Test: Verify syntax, test endpoint with curl (if server running)

**Interfaces:**
- Consumes: `config.get_db_path()` (Fase 1), sqlite3 connection pattern from existing bridge_lib functions
- Produces: `list_scripts_from_db(db_path)` returns list of dicts for active scripts; GET endpoint at `/api/bridge-v2/scripts`

- [ ] **Step 1: Read the insertion point in bridge_lib.py**

Read the end of `scripts/bridgeV002/bridge_lib.py`. Identify where `list_flows_from_db()` ends (around line 402). The new function should be inserted after `list_flows_from_db()`.

- [ ] **Step 2: Add `list_scripts_from_db()` function**

Add after the `list_flows_from_db()` function in `scripts/bridgeV002/bridge_lib.py`:

```python


def list_scripts_from_db(db_path=None):
    """List all active scripts from bridge_scripts table.

    Returns:
        list of dicts, one per active script, ordered by script_key.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM bridge_scripts WHERE is_active = 1 ORDER BY script_key"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
```

**Design notes:**
- Catches `sqlite3.OperationalError` and returns empty list (same pattern as `_bridgev002_tables_exist` check — table may not exist on fresh installs)
- Uses parameterized SQL only
- Ordered by script_key for deterministic output
- Two blank lines before function to match PEP 8 spacing

- [ ] **Step 3: Verify bridge_lib.py syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/bridge_lib.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 4: Read the insertion point in app.py**

Read `/home/svend/DPMtF-WebUI/app.py`, lines around 4038-4056. Identify the section after the flows GET endpoint and before the Spor J CRUD section comment (`# ── Spor J: BridgeV002 CRUD API`).

The new scripts endpoint should be inserted between the `@app.get("/api/bridge-v2/flows/{flow_key}")` endpoint (which ends with the except block) and the Spor J comment.

- [ ] **Step 5: Add GET `/api/bridge-v2/scripts` endpoint**

Insert in app.py after the `bridge_v2_get_flow` function (after line ~4052):

```python


@app.get("/api/bridge-v2/scripts")
async def bridge_v2_list_scripts():
    """Return all active BridgeV002 scripts from database."""
    try:
        from scripts.bridgeV002.bridge_lib import list_scripts_from_db
        scripts = list_scripts_from_db(DB_PATH)
        return {"scripts": scripts, "count": len(scripts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge scripts: {e}")
```

**Design notes:**
- Uses lazy import (`from scripts.bridgeV002.bridge_lib import list_scripts_from_db`) matching the existing pattern in other BridgeV002 endpoints
- Response format matches `/roles` and `/flows`: `{key: list, "count": int}` — here key is `"scripts"`
- Two blank lines before decorator to match PEP 8 spacing between top-level functions
- DB_PATH is already imported at module level

- [ ] **Step 6: Verify app.py syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile app.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 7: Test endpoint (if server is running)**

Run:
```bash
curl -s http://localhost:9130/api/bridge-v2/scripts | python3 -m json.tool || echo "(server not running — skip)"
```

If the server is running and has been restarted since init_db.py ran, expected output should show a JSON object with `"count": 3` and 3 script entries.

- [ ] **Step 8: Verify bridge_lib.py standalone still works**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/bridge_lib.py 2>&1 | tail -3
```

Expected: Clean execution, no errors. The `__main__` block should still work correctly.
