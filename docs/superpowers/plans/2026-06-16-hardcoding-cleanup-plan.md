# Hardcoding Cleanup — Implementation Plan (Spor A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate hardcoded paths and configuration values from DPMtF-WebUI and claude-bridge via a central config system (config.py + dpmtf.ini + .env), enabling PC migration without code changes.

**Architecture:** Introduce `config.py` as single source of truth for all configurable values, backed by `dpmtf.ini` (app-config) and `.env` (secrets/infrastructure). All other files import from config.py instead of hardcoding `/home/svend/...` strings. 6 sequential handoffs dispatched via bridge to local Ollama model.

**Tech Stack:** Python 3.12, configparser (stdlib), python-dotenv, FastAPI, sqlite3

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `config.py` | Central config module — .env + .ini loading, getter functions | **Create** |
| `dpmtf.ini` | App-config with defaults (port, host, db path, paths, projects) | **Create** |
| `.env` | Secrets + infrastructure env vars (extend existing) | **Modify** |
| `bridge.py` | BRIDGE_DIR + session names → env vars | **Modify** |
| `app.py` | DB_PATH, project root, validation, prompt generation → config lookups | **Modify** |
| `scripts/init_db.py` | ~75 hardcoded paths → config lookups or placeholders | **Modify** |
| `12_CODING_STANDARD.md` | Expanded "No hardcoded paths" rule + config lookup pattern | **Modify** |
| `16_FILE_ACCESS.md` | Project root resolution via config.py | **Modify** |
| `02_ARCHITECT.md` | Prompt Generation Rules: new rule 9 | **Modify** |

---

## Handoff Sequence

```
Handoff 023: config.py + dpmtf.ini (foundation)
    │
    ├─→ Handoff 024: bridge.py — BRIDGE_DIR + session names
    │
    ├─→ Handoff 025: app.py — DB_PATH + project root + validation
    │
    ├─→ Handoff 026: app.py — prompt generation (compile + internal)
    │
    ├─→ Handoff 027: init_db.py — seed data parameterization
    │
    └─→ Handoff 028: governance — 12_CODING_STANDARD + 16_FILE_ACCESS + 02_ARCHITECT
```

---

### Handoff 023: Config Foundation — config.py + dpmtf.ini

**Files:**
- Create: `/home/svend/DPMtF-WebUI/config.py`
- Create: `/home/svend/DPMtF-WebUI/dpmtf.ini`
- Modify: `/home/svend/DPMtF-WebUI/.env` (add new vars)

**Handoff file:** `/home/svend/claude-bridge/reviewtoimplementor/023-handoff.md`

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>023</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
DPMtF-WebUI and claude-bridge contain hardcoded /home/svend/... paths that
prevent moving the system to another PC. This is Handoff 1 of 6 in the
hardcoding cleanup (Spor A). It creates the config foundation: config.py
(single source of truth for all configurable values) and dpmtf.ini
(app-config with defaults). All subsequent handoffs will import from config.py.
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md

Key rules extracted:
1. Python: py_compile before signaling completion, parameterized SQL.
2. NO hardcoded /home/svend/... paths — use config.py getters.
3. DO NOT COMMIT.
</governance>

<task>
Create the config foundation for DPMtF-WebUI.

## Step 1: Create dpmtf.ini

Create `/home/svend/DPMtF-WebUI/dpmtf.ini` with these sections:

```ini
[app]
port = 9130
host = 0.0.0.0
default_locale = en-US

[database]
path = databases/dpmtf.db

[paths]
project_root = /home/svend/DPMtF-WebUI
bridge_dir = /home/svend/claude-bridge
governance_dir = docs/governance-templates-v2
log_dir = logs
exports_dir = exports

[projects]
father_project = DPMtF-WebUI
child_projects = ENO
reference_projects = ai-pc-resource-webui-v3
```

## Step 2: Create config.py

Create `/home/svend/DPMtF-WebUI/config.py`:

```python
"""Central configuration for DPMtF-WebUI.

Single source of truth for all configurable values.
Paths, ports, model names, project references MUST come from here.
Hardcoding /home/svend/... anywhere else is an auto-fail in validation.

Sources (in priority order):
1. Environment variables (secrets, infrastructure)
2. dpmtf.ini (app-config)
3. Hardcoded fallbacks (last resort, for development only)
"""

import os
import configparser
from pathlib import Path

# ── .env loading ────────────────────────────────────────────────

def _load_env():
    """Load .env file into os.environ. Manual loader — no dependencies."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

_load_env()

# ── .ini loading ─────────────────────────────────────────────────

_ini_path = Path(__file__).resolve().parent / "dpmtf.ini"
_config = configparser.ConfigParser()
if _ini_path.exists():
    _config.read(_ini_path, encoding="utf-8")

# ── Getter functions ─────────────────────────────────────────────

def get_db_path() -> str:
    """Database path. .ini [database] path, or fallback."""
    return _config.get("database", "path", fallback="databases/dpmtf.db")

def get_bridge_dir() -> str:
    """Bridge directory. Env var DPMTF_BRIDGE_DIR, or .ini [paths] bridge_dir, or fallback."""
    env = os.environ.get("DPMTF_BRIDGE_DIR")
    if env:
        return env
    return _config.get("paths", "bridge_dir", fallback="/home/svend/claude-bridge")

def get_project_root() -> str:
    """Project root directory. .ini [paths] project_root, or derived from this file's location."""
    configured = _config.get("paths", "project_root", fallback=None)
    if configured:
        return configured
    return str(Path(__file__).resolve().parent)

def get_governance_dir() -> str:
    """Governance docs directory (relative to project root)."""
    return _config.get("paths", "governance_dir", fallback="docs/governance-templates-v2")

def get_governance_dir_abs() -> str:
    """Governance docs directory (absolute path)."""
    return str(Path(get_project_root()) / get_governance_dir())

def get_father_project() -> str:
    """Father project name."""
    return _config.get("projects", "father_project", fallback="DPMtF-WebUI")

def get_child_projects() -> list:
    """Child project names (comma-separated in .ini)."""
    raw = _config.get("projects", "child_projects", fallback="ENO")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_reference_projects() -> list:
    """Reference project names (comma-separated in .ini)."""
    raw = _config.get("projects", "reference_projects", fallback="ai-pc-resource-webui-v3")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_port() -> int:
    """Server port."""
    return _config.getint("app", "port", fallback=9130)

def get_host() -> str:
    """Server host."""
    return _config.get("app", "host", fallback="0.0.0.0")

def get_default_locale() -> str:
    """Default locale for i18n."""
    return _config.get("app", "default_locale", fallback="en-US")

def get_log_dir() -> str:
    """Log directory (relative to project root)."""
    return _config.get("paths", "log_dir", fallback="logs")

def get_exports_dir() -> str:
    """Exports directory (relative to project root)."""
    return _config.get("paths", "exports_dir", fallback="exports")

# ── Bridge session names (env vars with defaults) ────────────────

def get_review_session() -> str:
    return os.environ.get("DPMTF_REVIEW_SESSION", "claude_review")

def get_implementer_session() -> str:
    return os.environ.get("DPMTF_IMPLEMENTER_SESSION", "claude_implementer")

def get_architect_session() -> str:
    return os.environ.get("DPMTF_ARCHITECT_SESSION", "claude_architect")
```

## Step 3: Extend .env

Add these lines to `/home/svend/DPMtF-WebUI/.env` (append at end):

```ini
# Bridge infrastructure (added 2026-06-16 — Spor A hardcoding cleanup)
DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
DPMTF_REVIEW_SESSION=claude_review
DPMTF_IMPLEMENTER_SESSION=claude_implementer
DPMTF_ARCHITECT_SESSION=claude_architect
```

If the .env file does not exist, create it with these lines plus a comment header:
```ini
# DPMtF-WebUI environment variables
# Secrets and infrastructure config
```

## Step 4: Verify

Run these checks:

1. python3 -m py_compile /home/svend/DPMtF-WebUI/config.py — must pass
2. python3 -c "
import sys
sys.path.insert(0, '/home/svend/DPMtF-WebUI')
import config
print('DB_PATH:', config.get_db_path())
print('BRIDGE_DIR:', config.get_bridge_dir())
print('PROJECT_ROOT:', config.get_project_root())
print('GOVERNANCE_DIR:', config.get_governance_dir())
print('FATHER:', config.get_father_project())
print('CHILDREN:', config.get_child_projects())
print('REFERENCES:', config.get_reference_projects())
print('PORT:', config.get_port())
print('REVIEW_SESSION:', config.get_review_session())
print('IMPLEMENTER_SESSION:', config.get_implementer_session())
print('ARCHITECT_SESSION:', config.get_architect_session())
print('DEFAULT_LOCALE:', config.get_default_locale())
print('✅ All getters work')
" — must print all values without errors
3. git -C /home/svend/DPMtF-WebUI diff --stat — verify only config.py, dpmtf.ini, .env changed

When ALL steps are complete, execute the bridge signal:

1. Write result file to /home/svend/claude-bridge/implementertoreview/023-result.md
   Format per 03_IMPLEMENTOR.md — include Summary, Files Changed, Validation Results.

2. Write notification file to /home/svend/claude-bridge/implementertoreview/023-notification.md
   Format per 03_IMPLEMENTOR.md — Status, Task Summary, Files Changed, Next Action.

3. SIGNAL completion (NO /clear before this):
   python3 /home/svend/claude-bridge/bridge.py complete 023
</task>

<scope>
Files you MAY modify:
- /home/svend/DPMtF-WebUI/config.py (CREATE)
- /home/svend/DPMtF-WebUI/dpmtf.ini (CREATE)
- /home/svend/DPMtF-WebUI/.env (MODIFY — append only)

Files you MUST NOT touch:
- /home/svend/DPMtF-WebUI/app.py
- /home/svend/DPMtF-WebUI/scripts/init_db.py
- /home/svend/claude-bridge/bridge.py
- /home/svend/ENO/
- /home/svend/ai-pc-resource-webui-v3/
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile /home/svend/DPMtF-WebUI/config.py — must pass
2. python3 -c "import sys; sys.path.insert(0,'/home/svend/DPMtF-WebUI'); import config; print(config.get_db_path()); print(config.get_bridge_dir()); print(config.get_project_root())" — must print values
3. git -C /home/svend/DPMtF-WebUI diff --stat — verify only config.py, dpmtf.ini, .env changed
4. test -f /home/svend/DPMtF-WebUI/dpmtf.ini && echo "✅ dpmtf.ini exists"
5. test -f /home/svend/DPMtF-WebUI/config.py && echo "✅ config.py exists"
6. grep "DPMTF_BRIDGE_DIR" /home/svend/DPMtF-WebUI/.env || echo "⚠ .env may not have new vars"
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 4 (bridge.py complete).
Model: qwen36-27b-q4km (local).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
All text MUST be in English (en-US).
</constraint>
```

---

### Handoff 024: Bridge Config — BRIDGE_DIR + session names

**Files:**
- Modify: `/home/svend/claude-bridge/bridge.py:26-30`

**Handoff file:** `/home/svend/claude-bridge/reviewtoimplementor/024-handoff.md`

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>024</handoff_id>

<project>/home/svend/claude-bridge</project>

<context>
bridge.py has BRIDGE_DIR and tmux session names hardcoded. This is Handoff 2
of 6 in the hardcoding cleanup. It replaces 3 hardcoded constants with
environment variable lookups (with current values as defaults). This is the
highest impact/effort fix in the entire cleanup — one variable (BRIDGE_DIR)
ripples through 40+ references.
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md

Key rules extracted:
1. Python: py_compile before signaling completion.
2. NO hardcoded /home/svend/... paths — use environment variables with defaults.
3. DO NOT COMMIT.
</governance>

<task>
Replace hardcoded constants in bridge.py with environment variable lookups.

## Step 1: Add import os

Verify that `import os` exists at the top of bridge.py. If not, add it after
the existing imports (around line 8-15). Check the current imports first:

```python
# Existing imports (around lines 8-15):
import os  # ← verify this exists, add if missing
import sys
import subprocess
from datetime import datetime, timezone
```

If `import os` is already there, skip this step.

## Step 2: Replace BRIDGE_DIR (line 26-27)

Find:
```python
BRIDGE_DIR = "/home/svend/claude-bridge"
TRACE_LOG = os.path.join(BRIDGE_DIR, "trace.log")
```

Replace with:
```python
BRIDGE_DIR = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/.dpmtf/bridge"))
os.makedirs(BRIDGE_DIR, exist_ok=True)
TRACE_LOG = os.path.join(BRIDGE_DIR, "trace.log")
```

## Step 3: Replace session names (lines 28-30)

Find:
```python
REVIEW_SESSION = "claude_review"
IMPLEMENTER_SESSION = "claude_implementer"
ARCHITECT_SESSION = "claude_architect"
```

Replace with:
```python
REVIEW_SESSION = os.environ.get("DPMTF_REVIEW_SESSION", "claude_review")
IMPLEMENTER_SESSION = os.environ.get("DPMTF_IMPLEMENTER_SESSION", "claude_implementer")
ARCHITECT_SESSION = os.environ.get("DPMTF_ARCHITECT_SESSION", "claude_architect")
```

## Step 4: Add subdirectory creation in cmd_send

In `cmd_send()`, after the handoff file validation, add directory creation
for the subdirectories. Find the line after `handoff_abs = os.path.abspath(handoff_path)`
(around line 93) and add:

```python
# Ensure subdirectories exist
os.makedirs(os.path.dirname(handoff_abs), exist_ok=True)
```

Do the same in `cmd_complete()`, `cmd_ask_architect()`, and
`cmd_answer_review()` — find where each writes files and add
`os.makedirs(os.path.dirname(<path>), exist_ok=True)` before the write.

## Step 5: Verify

Run these checks:

1. python3 -m py_compile /home/svend/claude-bridge/bridge.py — must pass
2. python3 -c "
import os
os.environ['DPMTF_BRIDGE_DIR'] = '/tmp/test-bridge'
os.environ['DPMTF_REVIEW_SESSION'] = 'test_review'
import sys
sys.path.insert(0, '/home/svend/claude-bridge')
# Just verify the module can be imported without errors
import importlib.util
spec = importlib.util.spec_from_file_location('bridge', '/home/svend/claude-bridge/bridge.py')
print('✅ bridge.py imports successfully')
" — must pass
3. git -C /home/svend/claude-bridge diff --stat — verify only bridge.py changed
4. grep -n '"/home/svend' /home/svend/claude-bridge/bridge.py — must return NO results (all hardcoded paths gone)

When ALL steps are complete, execute the bridge signal:

1. Write result file to /home/svend/claude-bridge/implementertoreview/024-result.md
2. Write notification file to /home/svend/claude-bridge/implementertoreview/024-notification.md
3. SIGNAL: python3 /home/svend/claude-bridge/bridge.py complete 024
</task>

<scope>
Files you MAY modify:
- /home/svend/claude-bridge/bridge.py

Files you MUST NOT touch:
- /home/svend/DPMtF-WebUI/
- /home/svend/ENO/
- /home/svend/ai-pc-resource-webui-v3/
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile /home/svend/claude-bridge/bridge.py — must pass
2. grep -n '"/home/svend' /home/svend/claude-bridge/bridge.py — must return NO results
3. grep -n "os.environ.get" /home/svend/claude-bridge/bridge.py — must show at least 4 occurrences (BRIDGE_DIR + 3 sessions)
4. git -C /home/svend/claude-bridge diff --stat — verify only bridge.py changed
5. grep -n "os.makedirs" /home/svend/claude-bridge/bridge.py — must show at least 1 occurrence
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 5 (bridge.py complete).
Model: qwen36-27b-q4km (local).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
All text MUST be in English (en-US).
</constraint>
```

---

### Handoff 025: App Config — Basics (DB_PATH + project root + validation)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/app.py` (lines 18, 21, 614, 1722)

**Handoff file:** `/home/svend/claude-bridge/reviewtoimplementor/025-handoff.md`

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>025</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
app.py has hardcoded DB_PATH, default locale, project path in generated
prompts, and /home/svend in validation. This is Handoff 3 of 6 in the
hardcoding cleanup. It replaces 4 hardcoded values with config.py lookups.
Handoff 026 will handle the remaining prompt generation paths.
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md

Key rules extracted:
1. Python: py_compile before signaling completion, parameterized SQL.
2. NO hardcoded /home/svend/... paths — use config.py getters.
3. DO NOT COMMIT.
</governance>

<task>
Replace 4 hardcoded values in app.py with config.py lookups.

## Step 1: Add config import

At the top of `/home/svend/DPMtF-WebUI/app.py`, find the existing imports
(after the module docstring, around lines 1-17). Add the config import:

```python
import config  # DPMtF-WebUI central config (Spor A)
```

Add it after the existing `import` statements but before any function
definitions. A good place is right after `from pathlib import Path` if it
exists, or after the last standard library import.

## Step 2: Replace DB_PATH (line 18)

Find:
```python
DB_PATH = "databases/dpmtf.db"
```

Replace with:
```python
DB_PATH = config.get_db_path()
```

## Step 3: Replace DEFAULT_LOCALE (line 21)

Find:
```python
DEFAULT_LOCALE = "en-US"
```

Replace with:
```python
DEFAULT_LOCALE = config.get_default_locale()
```

## Step 4: Replace hardcoded project path in generated prompt (line 614)

Find the line containing:
```python
generated_prompt = f"""Project path: /home/svend/DPMtF-WebUI
```

Replace the hardcoded path with config:
```python
generated_prompt = f"""Project path: {config.get_project_root()}
```

IMPORTANT: Only change the `/home/svend/DPMtF-WebUI` part. Keep the rest of
the generated_prompt string exactly as-is.

## Step 5: Replace hardcoded /home/svend in validation (line 1722)

Find:
```python
if target_folder == "/home/svend":
    raise HTTPException(status_code=400, detail="Target folder cannot be /home/svend")
```

Replace with:
```python
if target_folder == os.path.expanduser("~"):
    raise HTTPException(status_code=400, detail="Target folder cannot be home directory")
```

Verify that `import os` exists at the top of app.py. If not, add it.

## Step 6: Verify

Run these checks:

1. python3 -m py_compile /home/svend/DPMtF-WebUI/app.py — must pass
2. python3 -c "
import sys
sys.path.insert(0, '/home/svend/DPMtF-WebUI')
from app import DB_PATH, DEFAULT_LOCALE
print('DB_PATH:', DB_PATH)
print('DEFAULT_LOCALE:', DEFAULT_LOCALE)
print('✅ Config imports work')
" — must print values without errors
3. git -C /home/svend/DPMtF-WebUI diff --stat — verify only app.py changed
4. grep -n '"/home/svend' /home/svend/DPMtF-WebUI/app.py — some results will remain (prompt generation paths — these are fixed in Handoff 026). Only verify that line 18 and line 614 no longer have hardcoded paths.

When ALL steps are complete, execute the bridge signal:

1. Write result file to /home/svend/claude-bridge/implementertoreview/025-result.md
2. Write notification file to /home/svend/claude-bridge/implementertoreview/025-notification.md
3. SIGNAL: python3 /home/svend/claude-bridge/bridge.py complete 025
</task>

<scope>
Files you MAY modify:
- /home/svend/DPMtF-WebUI/app.py

Files you MUST NOT touch:
- /home/svend/DPMtF-WebUI/config.py
- /home/svend/DPMtF-WebUI/dpmtf.ini
- /home/svend/DPMtF-WebUI/scripts/init_db.py
- /home/svend/claude-bridge/
- /home/svend/ENO/
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile /home/svend/DPMtF-WebUI/app.py — must pass
2. python3 -c "import sys; sys.path.insert(0,'/home/svend/DPMtF-WebUI'); from app import DB_PATH; print(DB_PATH)" — must print database path
3. grep "config.get_db_path()" /home/svend/DPMtF-WebUI/app.py — must find at least 1 occurrence
4. grep "config.get_default_locale()" /home/svend/DPMtF-WebUI/app.py — must find at least 1 occurrence
5. grep "config.get_project_root()" /home/svend/DPMtF-WebUI/app.py — must find at least 1 occurrence
6. grep 'os.path.expanduser("~")' /home/svend/DPMtF-WebUI/app.py — must find at least 1 occurrence
7. git -C /home/svend/DPMtF-WebUI diff --stat — verify only app.py changed
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 6 (bridge.py complete).
Model: qwen36-27b-q4km (local).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
All text MUST be in English (en-US).
</constraint>
```

---

### Handoff 026: App Config — Prompt Generation Paths

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/app.py` (compile_prompt, assign_handoff_id, _compile_prompt_internal)

**Handoff file:** `/home/svend/claude-bridge/reviewtoimplementor/026-handoff.md`

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>026</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
app.py's compile_prompt(), assign_handoff_id(), and _compile_prompt_internal()
functions contain ~15 hardcoded /home/svend/... paths in generated prompt
strings. This is Handoff 4 of 6. It replaces all remaining hardcoded paths
with config.py getters. After this handoff, app.py will have ZERO hardcoded
/home/svend/ strings outside of config imports.
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md

Key rules extracted:
1. Python: py_compile before signaling completion, parameterized SQL.
2. NO hardcoded /home/svend/... paths — use config.py getters.
3. DO NOT COMMIT.
</governance>

<task>
Replace all hardcoded /home/svend/... paths in prompt generation functions
with config.py getters.

## Step 1: Identify all hardcoded paths

Run this command to see all remaining hardcoded paths:
```bash
grep -n '"/home/svend' /home/svend/DPMtF-WebUI/app.py
```

You should see results in these functions:
- `compile_prompt()` — around lines 2738, 2753, 2807, 2849, 2893, 2904, 2915, 2941, 2967, 2994, 2996, 3105, 3124, 3136
- `_compile_prompt_internal()` — around line 3856

## Step 2: Replace bridge paths in compile_prompt()

### 2a: Bridge signal paths (lines ~2738, ~2753)

Find lines like:
```python
signal = f"python3 /home/svend/claude-bridge/bridge.py complete {handoff_id}"
```

Replace with:
```python
signal = f"python3 {config.get_bridge_dir()}/bridge.py complete {handoff_id}"
```

There are TWO occurrences (one in the initial derivation, one in the else
fallback). Replace both.

### 2b: Role definition path (line ~2807)

Find:
```python
f"in /home/svend/{father_project}"
f"/docs/governance-templates-v2/{governance_role_file}."
```

Replace with:
```python
f"in {config.get_project_root()}"
f"/{config.get_governance_dir()}/{governance_role_file}."
```

### 2c: Governance file paths (lines ~2849-2850)

Find:
```python
f"- /home/svend/{father_project}"
"/docs/governance-templates-v2/12_CODING_STANDARD.md"
```

Replace with:
```python
f"- {config.get_project_root()}"
f"/{config.get_governance_dir()}/12_CODING_STANDARD.md"
```

Do the same for the 16_FILE_ACCESS.md and 21_ALIGNMENT.md references
on the following lines.

### 2d: Result/notification file paths (lines ~2893, ~2904)

Find:
```python
f"/home/svend/claude-bridge/implementertoreview/"
f"{handoff_id}-result.md"
```

Replace with:
```python
f"{config.get_bridge_dir()}/implementertoreview/"
f"{handoff_id}-result.md"
```

Do the same for the notification file path on the next line.

### 2e: Bridge complete command in task (line ~2915)

Find:
```python
f"   python3 /home/svend/claude-bridge/bridge.py "
f"complete {handoff_id}"
```

Replace with:
```python
f"   python3 {config.get_bridge_dir()}/bridge.py "
f"complete {handoff_id}"
```

### 2f: Architect response path (line ~2941)

Find:
```python
f"/home/svend/claude-bridge/architecttoreview/"
f"{handoff_id}-response.md"
```

Replace with:
```python
f"{config.get_bridge_dir()}/architecttoreview/"
f"{handoff_id}-response.md"
```

### 2g: Review verdict path (line ~2967)

Find:
```python
f"/home/svend/claude-bridge/implementertoreview/"
f"{handoff_id}-review-verdict.md"
```

Replace with:
```python
f"{config.get_bridge_dir()}/implementertoreview/"
f"{handoff_id}-review-verdict.md"
```

### 2h: Forbidden paths (lines ~2994, ~2996)

Find:
```python
lines.append("- /home/svend/ENO/ (other Child project)")
lines.append(
    "- /home/svend/ai-pc-resource-webui-v3/"
    " (reference project)"
)
```

Replace with dynamic generation from config. Add this BEFORE the forbidden
files loop (around line 2993):

```python
# Add standard forbidden projects from config
for child in config.get_child_projects():
    lines.append(f"- /home/svend/{child}/ (other Child project)")
for ref in config.get_reference_projects():
    lines.append(f"- /home/svend/{ref}/ (reference project)")
```

And REMOVE the two hardcoded lines that list ENO and ai-pc-resource-webui-v3
specifically.

NOTE: The `/home/svend/` prefix in these generated lines is intentional —
it's the standard location for projects on this system. The project NAMES
come from config, but the `/home/svend/` prefix is a system convention.
If full portability is needed later, the prefix can also come from config.

## Step 3: Replace paths in assign_handoff_id()

### 3a: bridge.py next-id call (line ~3105)

Find:
```python
["python3", "/home/svend/claude-bridge/bridge.py", "next-id"],
```

Replace with:
```python
["python3", f"{config.get_bridge_dir()}/bridge.py", "next-id"],
```

### 3b: Handoff directory (line ~3124)

Find:
```python
handoff_dir: str = "/home/svend/claude-bridge/reviewtoimplementor"
```

Replace with:
```python
handoff_dir: str = f"{config.get_bridge_dir()}/reviewtoimplementor"
```

### 3c: Dispatch command (line ~3136)

Find:
```python
f"python3 /home/svend/claude-bridge/bridge.py send {handoff_id}"
```

Replace with:
```python
f"python3 {config.get_bridge_dir()}/bridge.py send {handoff_id}"
```

## Step 4: Replace paths in _compile_prompt_internal()

### 4a: Role definition path (line ~3778)

Find:
```python
f"in /home/svend/{father_project}"
f"/docs/governance-templates-v2/{governance_role_file}."
```

Replace with:
```python
f"in {config.get_project_root()}"
f"/{config.get_governance_dir()}/{governance_role_file}."
```

### 4b: Governance file paths (lines ~3799-3805)

Find:
```python
f"- /home/svend/{father_project}"
"/docs/governance-templates-v2/12_CODING_STANDARD.md"
```

Replace with:
```python
f"- {config.get_project_root()}"
f"/{config.get_governance_dir()}/12_CODING_STANDARD.md"
```

Do the same for 16_FILE_ACCESS.md on the following line.

### 4c: Result file path (line ~3856)

Find:
```python
f"/home/svend/claude-bridge/implementertoreview/"
f"{handoff_id}-result.md"
```

Replace with:
```python
f"{config.get_bridge_dir()}/implementertoreview/"
f"{handoff_id}-result.md"
```

## Step 5: Final verification

Run these checks:

1. python3 -m py_compile /home/svend/DPMtF-WebUI/app.py — must pass
2. grep -n '"/home/svend' /home/svend/DPMtF-WebUI/app.py — should show ONLY:
   - Lines with `config.get_child_projects()` or `config.get_reference_projects()` (the /home/svend/ prefix in generated forbidden paths)
   - Any comment lines
   - NO hardcoded paths to claude-bridge, DPMtF-WebUI, ENO, or ai-pc-resource-webui-v3
3. grep -c "config.get_bridge_dir()" /home/svend/DPMtF-WebUI/app.py — must show at least 8 occurrences
4. grep -c "config.get_project_root()" /home/svend/DPMtF-WebUI/app.py — must show at least 4 occurrences
5. git -C /home/svend/DPMtF-WebUI diff --stat — verify only app.py changed

When ALL steps are complete, execute the bridge signal:

1. Write result file to /home/svend/claude-bridge/implementertoreview/026-result.md
2. Write notification file to /home/svend/claude-bridge/implementertoreview/026-notification.md
3. SIGNAL: python3 /home/svend/claude-bridge/bridge.py complete 026
</task>

<scope>
Files you MAY modify:
- /home/svend/DPMtF-WebUI/app.py

Files you MUST NOT touch:
- /home/svend/DPMtF-WebUI/config.py
- /home/svend/DPMtF-WebUI/dpmtf.ini
- /home/svend/DPMtF-WebUI/scripts/init_db.py
- /home/svend/claude-bridge/
- /home/svend/ENO/
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile /home/svend/DPMtF-WebUI/app.py — must pass
2. grep -n '"/home/svend/claude-bridge' /home/svend/DPMtF-WebUI/app.py — must return NO results (all bridge paths use config)
3. grep -n '"/home/svend/DPMtF-WebUI' /home/svend/DPMtF-WebUI/app.py — must return NO results (all project paths use config)
4. grep -c "config.get_bridge_dir()" /home/svend/DPMtF-WebUI/app.py — must show at least 8
5. grep -c "config.get_project_root()" /home/svend/DPMtF-WebUI/app.py — must show at least 4
6. git -C /home/svend/DPMtF-WebUI diff --stat — verify only app.py changed
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 5 (bridge.py complete).
Model: qwen36-27b-q4km (local).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
All text MUST be in English (en-US).
</constraint>
```

---

### Handoff 027: Seed Data Parameterization

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/init_db.py`

**Handoff file:** `/home/svend/claude-bridge/reviewtoimplementor/027-handoff.md`

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>027</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
scripts/init_db.py contains ~75 hardcoded /home/svend/... paths in seed data
(project paths, server start commands, panel data). This is Handoff 5 of 6.
It replaces hardcoded paths with config.py lookups. The seed data must remain
functional — projects referenced in seed data should resolve correctly.
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/17_DATABASE.md

Key rules extracted:
1. Python: py_compile before signaling completion, parameterized SQL.
2. NO hardcoded /home/svend/... paths — use config.py getters.
3. CREATE TABLE IF NOT EXISTS / INSERT OR IGNORE for idempotent changes.
4. DO NOT COMMIT.
</governance>

<task>
Replace hardcoded /home/svend/... paths in seed data with config.py lookups.

## Step 1: Add config import

At the top of `/home/svend/DPMtF-WebUI/scripts/init_db.py`, add:

```python
import sys
sys.path.insert(0, '/home/svend/DPMtF-WebUI')
import config
```

Add this after the existing imports but before any database operations.

## Step 2: Find all hardcoded paths

Run this command to see all hardcoded paths:
```bash
grep -n '/home/svend' /home/svend/DPMtF-WebUI/scripts/init_db.py | head -40
```

You will see paths in:
- `target_project_path` values (e.g., `/home/svend/ai-pc-resource-webui-v2`)
- `server_start_command` values (e.g., `cd /home/svend/... && ...`)
- Panel seed data with ComfyUI paths, disk paths
- Project skeleton paths

## Step 3: Replace project paths with config lookups

For each hardcoded `/home/svend/...` path, determine the appropriate
replacement:

### 3a: Project root references

If the path refers to DPMtF-WebUI itself:
```python
# Before:
"/home/svend/DPMtF-WebUI"
# After:
config.get_project_root()
```

### 3b: Bridge references

If the path refers to claude-bridge:
```python
# Before:
"/home/svend/claude-bridge"
# After:
config.get_bridge_dir()
```

### 3c: Child/reference project paths

If the path refers to ENO or ai-pc-resource-webui-v3, use the standard
Linux home directory convention with config-derived project names:
```python
# Before:
"/home/svend/ENO"
# After:
f"/home/svend/{config.get_child_projects()[0]}"
```

For reference projects:
```python
# Before:
"/home/svend/ai-pc-resource-webui-v3"
# After:
f"/home/svend/{config.get_reference_projects()[0]}"
```

### 3d: Server start commands

For server_start_command values containing full paths, replace the path
portion:
```python
# Before:
"cd /home/svend/DPMtF-WebUI && /home/svend/DPMtF-WebUI/venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 9130"
# After:
f"cd {config.get_project_root()} && {config.get_project_root()}/venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port {config.get_port()}"
```

### 3e: Paths that are NOT /home/svend

Paths like `/ComfyUI`, `/media/disk2/...` etc. are external resources —
they are NOT DPMtF project paths. Leave them as-is. They refer to the
user's external storage and applications, not to DPMtF itself.

## Step 4: Strategy for large seed data blocks

For seed data tuples that contain paths, you have two options:

**Option A (preferred):** Replace the hardcoded string in the tuple with
an f-string that uses config getters. Example:

```python
# Before:
("/home/svend/ENO", "/home/svend/ENO", 9131, ...),
# After:
(f"/home/svend/{config.get_child_projects()[0]}",
 f"/home/svend/{config.get_child_projects()[0]}", 9131, ...),
```

**Option B:** If a tuple is complex, extract it to a variable before the
INSERT loop and build it with config getters.

## Step 5: Verify

Run these checks:

1. python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py — must pass
2. python3 /home/svend/DPMtF-WebUI/scripts/init_db.py — must run without errors (idempotent)
3. grep -c '/home/svend' /home/svend/DPMtF-WebUI/scripts/init_db.py — count before and after. The count should decrease significantly. Remaining /home/svend/ references should only be:
   - In comments
   - In the sys.path.insert line (which is a bootstrap necessity)
   - In f-strings using config getters (e.g., `f"/home/svend/{config.get_...()}"`)
4. git -C /home/svend/DPMtF-WebUI diff --stat — verify only init_db.py changed

When ALL steps are complete, execute the bridge signal:

1. Write result file to /home/svend/claude-bridge/implementertoreview/027-result.md
2. Write notification file to /home/svend/claude-bridge/implementertoreview/027-notification.md
3. SIGNAL: python3 /home/svend/claude-bridge/bridge.py complete 027
</task>

<scope>
Files you MAY modify:
- /home/svend/DPMtF-WebUI/scripts/init_db.py

Files you MUST NOT touch:
- /home/svend/DPMtF-WebUI/config.py
- /home/svend/DPMtF-WebUI/dpmtf.ini
- /home/svend/DPMtF-WebUI/app.py
- /home/svend/claude-bridge/
- /home/svend/ENO/
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py — must pass
2. python3 /home/svend/DPMtF-WebUI/scripts/init_db.py — must run without errors
3. grep -c "config.get" /home/svend/DPMtF-WebUI/scripts/init_db.py — must show at least 5 occurrences
4. git -C /home/svend/DPMtF-WebUI diff --stat — verify only init_db.py changed
5. grep '"/home/svend/DPMtF-WebUI"' /home/svend/DPMtF-WebUI/scripts/init_db.py — must return NO results (use config.get_project_root() instead)
6. grep '"/home/svend/claude-bridge"' /home/svend/DPMtF-WebUI/scripts/init_db.py — must return NO results (use config.get_bridge_dir() instead)
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 5 (bridge.py complete).
Model: qwen36-27b-q4km (local).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
All text MUST be in English (en-US).
</constraint>
```

---

### Handoff 028: Governance Updates

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md`
- Modify: `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md`
- Modify: `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md`

**Handoff file:** `/home/svend/claude-bridge/reviewtoimplementor/028-handoff.md`

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>028</handoff_id>

<project>/home/svend/DPMtF-WebUI</project>

<context>
The governance documents must be updated to enforce the new config system.
This is Handoff 6 of 6 — the final step in Spor A. It updates three
governance files to mandate config.py usage and prohibit hardcoded paths.
After this, the coding standard will auto-fail any hardcoded /home/svend/
string in validation.
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md

Key rules extracted:
1. Markdown: ATX headings, consistent tables.
2. Append-only for CHANGELOG and DECISIONS — but these are standard docs, OK to modify.
3. DO NOT COMMIT.
</governance>

<task>
Update three governance files to enforce the config system.

## Step 1: Update 12_CODING_STANDARD.md

### 1a: Expand "No hardcoded paths" rule

Find the Python rules table (around lines 23-30). Find the row:
```
| **No hardcoded paths** | Ports, paths, model names MUST come from explicit arguments or configuration. |
```

Replace with:
```
| **No hardcoded paths** | Paths, ports, model names, project references, and bridge directories MUST come from `config.py` getter-functions or environment variables. Hardcoded `/home/svend/...` strings anywhere in Python, JavaScript, shell scripts, or seed data are an auto-fail in validation. The single source of truth for all configurable values is `config.py`. |
```

### 1b: Add "Config Lookup Pattern" section

After the "No hardcoded paths" row in the Python table, add a new subsection
before the JavaScript section. Insert after the Python table (after line 30)
and before "## JavaScript" (around line 32):

```markdown
### Config Lookup Pattern (Mandatory)

All configurable values MUST be accessed through `config.py` getter-functions:

| Value | Getter | Source |
|-------|--------|--------|
| Database path | `config.get_db_path()` | dpmtf.ini [database] |
| Bridge directory | `config.get_bridge_dir()` | .env DPMTF_BRIDGE_DIR |
| Project root | `config.get_project_root()` | dpmtf.ini [paths] |
| Governance directory | `config.get_governance_dir()` | dpmtf.ini [paths] |
| Tmux session names | `config.get_review_session()` etc. | .env |
| Port, host, locale | `config.get_port()` etc. | dpmtf.ini [app] |
| Father/child/reference projects | `config.get_father_project()` etc. | dpmtf.ini [projects] |

**Rule:** If a value could differ between two PCs, it goes through config.py.
Hardcoded strings like `/home/svend/...` are prohibited — use config getters.

**Example (correct):**
```python
import config
handoff_path = f"{config.get_bridge_dir()}/reviewtoimplementor/{hid}-handoff.md"
```

**Example (WRONG — auto-fail):**
```python
handoff_path = f"/home/svend/claude-bridge/reviewtoimplementor/{hid}-handoff.md"
```
```

### 1c: Update "Prohibited Patterns" section

Find the "Prohibited Patterns" section (around lines 87-96). Add a new item
after item 2:

```markdown
2.5. **Hardcoded /home/svend or user-specific paths** — auto-fail. Use `config.py` getters. The only allowed hardcoded path is `sys.path.insert(0, ...)` for bootstrap in scripts that need to import config before it's on PYTHONPATH.
```

Renumber items 3-6 to 3-7 accordingly (or keep as-is, just insert at position 2.5).

## Step 2: Update 16_FILE_ACCESS.md

### 2a: Add "Project Root Resolution" section

Find a good location in 16_FILE_ACCESS.md — after the existing content,
before the closing `---`. Add:

```markdown
## Project Root Resolution

All project paths are resolved via `config.py`:

| Path | Getter | Example Value |
|------|--------|---------------|
| Project root | `config.get_project_root()` | `/home/svend/DPMtF-WebUI` |
| Bridge directory | `config.get_bridge_dir()` | `/home/svend/claude-bridge` |
| Governance docs | `config.get_governance_dir_abs()` | `/home/svend/DPMtF-WebUI/docs/governance-templates-v2` |

When writing handoff prompts, validation scripts, or scope definitions,
use config getters instead of hardcoding `/home/svend/...`.

**Example (correct — in a handoff prompt):**
```
<project>{config.get_project_root()}</project>
<governance>
- {config.get_project_root()}/{config.get_governance_dir()}/12_CODING_STANDARD.md
</governance>
```

**Example (WRONG — auto-fail in review):**
```
<project>/home/svend/DPMtF-WebUI</project>
<governance>
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
</governance>
```
```

## Step 3: Update 02_ARCHITECT.md

### 3a: Add rule 9 to "Prompt Generation Rules"

Find the "Prompt Generation Rules" section (around lines 70-105). After rule 8
("All prompt text MUST be in English"), add:

```markdown
9. **Use config getters in generated prompts** — paths in `<role>`, `<governance>`,
   `<task>`, and `<scope>` sections MUST use `config.get_project_root()`,
   `config.get_bridge_dir()`, and `config.get_governance_dir()` instead of
   hardcoded `/home/svend/...` strings. This ensures prompts work when the
   project is moved to another PC.
```

## Step 4: Verify

Run these checks:

1. git -C /home/svend/DPMtF-WebUI diff --stat — verify only the three .md files changed
2. grep "config.py" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md — must find at least 3 occurrences
3. grep "config.py" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md — must find at least 2 occurrences
4. grep "config getters" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md — must find at least 1 occurrence

When ALL steps are complete, execute the bridge signal:

1. Write result file to /home/svend/claude-bridge/implementertoreview/028-result.md
2. Write notification file to /home/svend/claude-bridge/implementertoreview/028-notification.md
3. SIGNAL: python3 /home/svend/claude-bridge/bridge.py complete 028
</task>

<scope>
Files you MAY modify:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md

Files you MUST NOT touch:
- /home/svend/DPMtF-WebUI/config.py
- /home/svend/DPMtF-WebUI/dpmtf.ini
- /home/svend/DPMtF-WebUI/app.py
- /home/svend/DPMtF-WebUI/scripts/init_db.py
- /home/svend/claude-bridge/
- /home/svend/ENO/
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. git -C /home/svend/DPMtF-WebUI diff --stat — verify only 12_CODING_STANDARD.md, 16_FILE_ACCESS.md, 02_ARCHITECT.md changed
2. grep -c "config.py" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md — must be >= 3
3. grep -c "config.py" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md — must be >= 2
4. grep "config getters" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md — must find at least 1
5. grep "auto-fail" /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md — must find at least 1 (the new hardcoded paths prohibition)
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 4 (bridge.py complete).
Model: qwen36-27b-q4km (local).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
All text MUST be in English (en-US).
</constraint>
```
