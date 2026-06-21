# BridgeV002 Hardening — Fase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bridge_convention_rules` table with seed data, alter `bridge_flow_steps` to add FK reference, and provide GET endpoint for conventions.

**Architecture:** New table in init_db.py + ALTER TABLE + UPDATE existing steps to link conventions. Two new functions in bridge_lib.py (list + resolve), one GET endpoint in app.py.

**Tech Stack:** Python 3, SQLite, FastAPI.

## Global Constraints

- en-US only for all code, comments, docstrings — CLAUDE.md §2
- PEP 8, parameterized SQL only (no f-string SQL) — CLAUDE.md §4
- NO hardcoded `/home/svend/...` paths — use config.py getters — CLAUDE.md §4
- `python3 -m py_compile <file>` MUST pass before signaling completion — CLAUDE.md §4
- Follow existing BridgeV002 patterns: table naming, seed data with INSERT OR IGNORE, lazy imports in app.py endpoints

---

### Task 1: Add convention rules table + alter steps + update rows

**Files:**
- Modify: `scripts/init_db.py` — add CREATE TABLE, seed data, ALTER bridge_flow_steps, UPDATE existing steps

**Interfaces:**
- Consumes: `cursor` (sqlite3 cursor, in scope)
- Produces: New `bridge_convention_rules` table with 3 rules; `bridge_flow_steps` gains optional `rule_key` FK column

- [ ] **Step 1: Find insertion point in init_db.py**

Read `/home/svend/DPMtF-WebUI/scripts/init_db.py`. Locate the Fase 2 Bridge Script Registry section (created previous phase, around line 3925) and the Spor J labels section after it. Insert new code between these two sections with header:
```python
# ── Fase 3: Bridge Convention Rules ────────────────────
```

- [ ] **Step 2: Add CREATE TABLE + seed data**

Insert in init_db.py:

```python

# ── Fase 3: Bridge Convention Rules ────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS bridge_convention_rules (
    rule_key TEXT PRIMARY KEY,
    step_type TEXT NOT NULL,
    dir_template TEXT NOT NULL,
    pattern_template TEXT NOT NULL,
    error_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_convention_rules
       (rule_key, step_type, dir_template, pattern_template, error_template)
       VALUES (?, ?, ?, ?, ?)""",
    [
        ("handoff", "Handoff",
         "reviewtoimplementor", "{ID}-handoff.md",
         "Failed to deliver handoff to {to_role}."),
        ("callback", "Callback",
         "implementertoreview", "{ID}-callback.md",
         "Failed to deliver callback to {to_role}."),
        ("verdict", "Verdict",
         "implementertoreview", "{ID}-review-verdict.md",
         "Failed to deliver verdict. Present to Human manually."),
    ],
)

# Add rule_key FK column to bridge_flow_steps (idempotent via ALTER)
cursor.execute("""
ALTER TABLE bridge_flow_steps ADD COLUMN rule_key TEXT REFERENCES bridge_convention_rules(rule_key)
""")
```

**Important:** SQLite does not support `ADD COLUMN IF NOT EXISTS`. To make this idempotent, we must catch the error. Replace the ALTER with a try/except:

```python

# Add rule_key FK column to bridge_flow_steps (idempotent — ignore if exists)
try:
    cursor.execute("""
    ALTER TABLE bridge_flow_steps ADD COLUMN rule_key TEXT REFERENCES bridge_convention_rules(rule_key)
    """)
except sqlite3.OperationalError:
    pass  # Column already exists

```

- [ ] **Step 3: UPDATE existing steps to map conventions**

After the ALTER column, add UPDATE statements that link each step to its convention rule:

```python

# Map existing steps to convention rules
cursor.executemany(
    """UPDATE bridge_flow_steps SET rule_key = ? WHERE step_key = ? AND flow_key = ?""",
    [
        # Heavy flow
        ("handoff", "architect_to_implementer", "heavy"),
        ("callback", "implementer_to_review_heavy1", "heavy"),
        ("callback", "review_heavy1_to_heavy2", "heavy"),
        ("verdict", "review_heavy2_to_human", "heavy"),
        ("callback", "review_to_architect_escalation", "heavy"),
        # Simplified flow
        ("handoff", "architect_to_implementer", "simplified"),
        ("callback", "implementer_to_reviewer_lite", "simplified"),
        ("verdict", "reviewer_lite_to_human", "simplified"),
        # Escalation flow
        ("handoff", "review_to_architect", "escalation"),
        ("callback", "architect_to_review_response", "escalation"),
    ],
)

```

- [ ] **Step 4: Verify syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/init_db.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 5: Run init_db.py to apply schema**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/init_db.py 2>&1 | tail -5
```

Expected: Clean execution, no errors. The try/except on ALTER handles the case where column already exists.

- [ ] **Step 6: Verify convention rules table**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
rules = conn.execute('SELECT rule_key, step_type, dir_template FROM bridge_convention_rules ORDER BY rule_key').fetchall()
print(f'Convention rules: {len(rules)}')
for r in rules:
    print(f'  {r[0]}: {r[1]} -> {r[2]}')
conn.close()
"
```

Expected output:
```
Convention rules: 3
  callback: Callback -> implementertoreview
  handoff: Handoff -> reviewtoimplementor
  verdict: Verdict -> implementertoreview
```

- [ ] **Step 7: Verify steps now have rule_key**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
steps = conn.execute('SELECT step_key, flow_key, rule_key FROM bridge_flow_steps ORDER BY flow_key, sort_order').fetchall()
print(f'Steps with rule_key: {len(steps)}')
for s in steps:
    print(f'  {s[0]} ({s[1]}): {s[2]}')
conn.close()
"
```

Expected: All 11 steps should have a non-NULL `rule_key` value.

---

### Task 2: Add list + resolve functions to bridge_lib.py + GET endpoint

**Files:**
- Modify: `scripts/bridgeV002/bridge_lib.py` — add `list_conventions_from_db()` and `resolve_convention_from_db()`
- Modify: `app.py` — add GET `/api/bridge-v2/conventions` endpoint

**Interfaces:**
- Consumes: `config.get_db_path()` (Fase 1)
- Produces: `list_conventions_from_db(db_path)` returns list of dicts; `resolve_convention_from_db(rule_key, db_path)` returns single convention dict

- [ ] **Step 1: Add `list_conventions_from_db()` function**

Add to bridge_lib.py after the `list_scripts_from_db()` function (which was added Fase 2):

```python


def list_conventions_from_db(db_path=None):
    """List all convention rules from bridge_convention_rules table.

    Returns:
        list of dicts, one per rule, ordered by rule_key.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM bridge_convention_rules ORDER BY rule_key"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def resolve_convention_from_db(rule_key, db_path=None):
    """Resolve a single convention rule by key.

    Args:
        rule_key: The convention key (e.g. 'handoff', 'callback', 'verdict')
        db_path: Optional path to SQLite database. Uses config.get_db_path() if not given.

    Returns:
        dict with keys: rule_key, step_type, dir_template, pattern_template, error_template

    Raises:
        ValueError: If rule_key not found.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM bridge_convention_rules WHERE rule_key = ?",
            (rule_key,)
        ).fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Convention rule '{rule_key}' not found in bridge_convention_rules")
        result = dict(row)
        conn.close()
        return result
    except sqlite3.OperationalError:
        return {}
```

**Design notes:**
- `list_conventions_from_db` catches OperationalError and returns empty list (same pattern as scripts/flows)
- `resolve_convention_from_db` raises ValueError for missing rules (caller can handle), but returns empty dict if table doesn't exist yet
- Both use parameterized SQL

- [ ] **Step 2: Verify bridge_lib.py syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/bridge_lib.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 3: Add GET `/api/bridge-v2/conventions` endpoint**

Add to app.py after the scripts endpoint (Fase 2):

```python


@app.get("/api/bridge-v2/conventions")
async def bridge_v2_list_conventions():
    """Return all convention rules from database."""
    try:
        from scripts.bridgeV002.bridge_lib import list_conventions_from_db
        conventions = list_conventions_from_db(DB_PATH)
        return {"conventions": conventions, "count": len(conventions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge conventions: {e}")

```

- [ ] **Step 4: Verify app.py syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile app.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 5: Test functions directly**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import sys; sys.path.insert(0, 'scripts/bridgeV002')
from bridge_lib import list_conventions_from_db, resolve_convention_from_db

rules = list_conventions_from_db()
print(f'Listed {len(rules)} conventions')
for r in rules:
    print(f'  {r[\"rule_key\"]}: dir={r[\"dir_template\"]}, pattern={r[\"pattern_template\"]}')

resolved = resolve_convention_from_db('handoff')
print(f'Resolved handoff: dir={resolved[\"dir_template\"]}, pattern={resolved[\"pattern_template\"]}')
"
```

Expected: 3 conventions listed, handoff resolution shows correct dir/pattern.

- [ ] **Step 6: Verify bridge_lib.py standalone**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/bridge_lib.py 2>&1 | tail -5
```

Expected: Clean execution, no errors.
