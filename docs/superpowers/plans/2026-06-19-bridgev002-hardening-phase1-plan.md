# BridgeV002 Hardening — Fase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded path fallbacks in `bridge_lib.py` with `config.py` getters, add `[bridge]` section to `dpmtf.ini`, and update `.gitignore` with runtime artifact patterns.

**Architecture:** Additive-only changes — new `[bridge]` section in dpmtf.ini, new `get_bridge_base_path()` getter in config.py, then wire two fallback sites in `resolve_placeholders()` to use the new getters. No existing function signature changes.

**Tech Stack:** Python 3, configparser, SQLite (no schema change), FastAPI app.py (no change).

## Global Constraints

- **en-US only** for all code, comments, docstrings — CLAUDE.md §2
- **PEP 8**, f-strings preferred, type hints where practical — CLAUDE.md §4
- **Parameterized SQL only** — no change in this plan, but must not regress — CLAUDE.md §4
- **NO hardcoded `/home/svend/...` paths** — use `config.py` getters — CLAUDE.md §5
- **Python syntax check mandatory** — `python3 -m py_compile <file>` MUST pass before signaling completion — CLAUDE.md §4
- **Only Human may commit/push** — all changes remain unstaged after implementation — CLAUDE.md §6
- **Free write files:** `dpmtf.ini`, `.gitignore` (config artifacts). `config.py` and `bridge_lib.py` are restricted-write but covered by governance scope.

---

### Task 1: Add `[bridge]` section to dpmtf.ini + `get_bridge_base_path()` getter to config.py

**Files:**
- Modify: `dpmtf.ini` — add `[bridge] base_path` section before `[projects]`
- Modify: `config.py:50-56` — insert `get_bridge_base_path()` after `get_bridge_dir()`
- Test: N/A — verification via shell command

**Interfaces:**
- Consumes: `_config` (ConfigParser), `Path`, `get_project_root()` — all existing in config.py
- Produces: `config.get_bridge_base_path()` → returns `str` of bridge base path

- [ ] **Step 1: Read current dpmtf.ini**

Read the file at `/home/svend/DPMtF-WebUI/dpmtf.ini`. Identify that `[projects]` section starts at line 17.

- [ ] **Step 2: Add `[bridge]` section to dpmtf.ini**

Insert a new `[bridge]` section between line 15 (end of `[paths]`) and line 17 (`[projects]`):

```ini
log_dir = logs
exports_dir = exports

[bridge]
base_path = /home/svend/claude-bridge

[projects]
```

The `[bridge]` section must have exactly one key: `base_path` set to `/home/svend/claude-bridge`.

Verify by reading lines 15-18 of dpmtf.ini — they should show the transition from `[paths]` → blank line → `[bridge]` → `[projects]`.

- [ ] **Step 3: Read current config.py**

Read the file at `/home/svend/DPMtF-WebUI/config.py`. Identify that `get_bridge_dir()` ends at line 56, and `get_project_root()` starts at line 57.

- [ ] **Step 4: Add `get_bridge_base_path()` getter to config.py**

Insert the following function between `get_bridge_dir()` (ends line 56) and `get_project_root()` (starts line 57):

```python


def get_bridge_base_path() -> str:
    """Bridge base path. .ini [bridge] base_path, or fallback to project_root/claude-bridge."""
    configured = _config.get("bridge", "base_path", fallback=None)
    if configured:
        return configured
    return str(Path(get_project_root()) / "claude-bridge")
```

**Important:** Add exactly one blank line before and after the function to match PEP 8 spacing of surrounding functions. The `Path` import already exists at line 16. No new imports needed.

- [ ] **Step 5: Verify syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile config.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 6: Verify getter returns correct value**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "import config; p=config.get_bridge_base_path(); print(p); assert p == '/home/svend/claude-bridge', f'Wrong path: {p}'; print('CORRECT')"
```

Expected: `/home/svend/claude-bridge` followed by `CORRECT`.

- [ ] **Step 7: Verify existing getter still works**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "import config; print(config.get_bridge_dir()); print(config.get_project_root())"
```

Expected: Both return their previous values unchanged.

---

### Task 2: Replace hardcoded fallbacks in bridge_lib.py

**Files:**
- Modify: `scripts/bridgeV002/bridge_lib.py:19-26` — replace two hardcoded fallbacks in `resolve_placeholders()`
- Test: Run `bridge_lib.py` as standalone script, verify same output

**Interfaces:**
- Consumes: `config.get_bridge_base_path()`, `config.get_project_root()` (from Task 1), `os.environ.get()` (existing)
- Produces: `resolve_placeholders()` with config-sourced fallbacks instead of hardcoded strings

- [ ] **Step 1: Read bridge_lib.py lines 19-35**

Read the function `resolve_placeholders()` in `/home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_lib.py`. Identify the two hardcoded fallbacks:
- Line 22: `os.path.expanduser("~/.bridge")` — bridge_dir fallback
- Lines 23-25: `str(Path(__file__).resolve().parent.parent)` — project_root fallback

- [ ] **Step 2: Replace line 22 — bridge_dir fallback**

Replace:
```python
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge"))
```

With:
```python
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR") or config.get_bridge_base_path()
```

**Why `or` not second arg to `get()`:** Using `or` chains the fallback explicitly — if env-var is unset, fall back to config getter. If env-var is set to empty string, also fall through (same behavior as before with the nested default).

- [ ] **Step 3: Replace lines 23-25 — project_root fallback**

Replace:
```python
        project_root = os.environ.get(
            "DPMTF_PROJECT_ROOT"
        ) or str(Path(__file__).resolve().parent.parent)
```

With:
```python
        project_root = os.environ.get(
            "DPMTF_PROJECT_ROOT"
        ) or config.get_project_root()
```

- [ ] **Step 4: Verify the function looks correct**

The full `resolve_placeholders()` should now read:

```python
def resolve_placeholders(text, bridge_dir=None, project_root=None):
    """Replace {BRIDGE_DIR}, {PROJECT_ROOT}, {SCRIPTS_DIR} in config values."""
    if bridge_dir is None:
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR") or config.get_bridge_base_path()
    if project_root is None:
        project_root = os.environ.get(
            "DPMTF_PROJECT_ROOT"
        ) or config.get_project_root()

    replacements = {
        "{BRIDGE_DIR}": bridge_dir,
        "{PROJECT_ROOT}": project_root,
        "{SCRIPTS_DIR}": f"{project_root}/scripts/bridgeV002",
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text
```

Verify line-by-line that the function body matches. The `replacements` dict and replacement loop must be unchanged from before.

- [ ] **Step 5: Verify syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/bridge_lib.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 6: Run bridge_lib.py standalone**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/bridge_lib.py
```

Expected output pattern:
- `BridgeV002 core library` printed
- Config sections listed
- Role lookups succeed for `architect` and `implementer`
- Next handoff ID computed
- Database-backed lookup section appears (if tables exist)
- NO import errors, NO AttributeError on `get_bridge_base_path()`

- [ ] **Step 7: Verify no hardcoded home-paths remain in resolve_placeholders scope**

Run:
```bash
cd /home/svend/DPMtF-WebUI && grep -n 'expanduser.*~/.bridge' scripts/bridgeV002/bridge_lib.py | wc -l
```

Expected: `0` — no matches (the hardcoded fallback is gone).

---

### Task 3: Update .gitignore with runtime artifact patterns

**Files:**
- Modify: `.gitignore` — append bridge/runtime artifact patterns
- Test: Verify untracked files disappear from git status

**Interfaces:**
- Consumes: N/A
- Produces: Updated `.gitignore` that excludes H99 backups, playwright-mcp, screenshots

- [ ] **Step 1: Read current .gitignore**

Read `/home/svend/DPMtF-WebUI/.gitignore`. Current content is 6 lines covering `venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.env`.

- [ ] **Step 2: Append runtime artifact patterns**

Append these lines at the end of the file (after the trailing newline of line 7):

```
# Bridge runtime artifacts
databases/*.bak.*
databases/*.preh99.*
.playwright-mcp/
screenshot-*.png
```

**Important:** Add exactly one blank line between existing content and new section comment. The final `.gitignore` should look like:

```
venv/
__pycache__/
*/__pycache__/
*.pyc
.pytest_cache/
.env

# Bridge runtime artifacts
databases/*.bak.*
databases/*.preh99.*
.playwright-mcp/
screenshot-*.png
```

- [ ] **Step 3: Verify git status reflects change**

Run:
```bash
cd /home/svend/DPMtF-WebUI && git status --short | grep -E "bak\.(h99|preh99)|playwright-mcp|screenshot-" | wc -l
```

Expected: `0` — the files are now ignored and should not appear as untracked. If they still appear, it means the glob patterns need adjustment — re-check spelling against actual filenames from `ls databases/*.bak.*`.

---

### Task 4: Full verification suite

**Files:** N/A — verification only
**Interfaces:** Consumes all outputs from Tasks 1-3

- [ ] **Step 1: Compile all modified Python files**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile config.py && python3 -m py_compile scripts/bridgeV002/bridge_lib.py && echo "ALL PASS" || echo "SYNTAX FAIL"
```

Expected: `ALL PASS`

- [ ] **Step 2: Check diff scope**

Run:
```bash
cd /home/svend/DPMtF-WebUI && git diff --stat
```

Expected: Exactly 4 files changed: `dpmtf.ini`, `config.py`, `.gitignore`, `scripts/bridgeV002/bridge_lib.py`. If any other file appears, investigate and revert it.

- [ ] **Step 3: Check no hardcoded home-paths in bridge_lib.py (in scope)**

Run:
```bash
cd /home/svend/DPMtF-WebUI && grep -n "'/home/svend" scripts/bridgeV002/bridge_lib.py | wc -l
```

Expected: `0` — no hardcoded home-paths in the resolve_placeholders function scope. (Note: `_find_project_root()` at line 45 still has `Path.home() / "DPMtF-WebUI"` — this is OUT of scope per spec Decision 3.)

- [ ] **Step 4: Verify bridge_lib.py still works end-to-end**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/bridge_lib.py 2>&1
```

Expected: Clean execution with role lookups and database-backed lookup output. Exit code 0.

- [ ] **Step 5: Final governance check — innerHTML scan**

Run:
```bash
cd /home/svend/DPMtF-WebUI && grep -RIn "innerHTML" static/js/dpmtf-app.js | wc -l
```

Expected: `0` — no regression, we didn't touch frontend.

- [ ] **Step 6: Confirm all changes remain unstaged**

Run:
```bash
cd /home/svend/DPMtF-WebUI && git status --short
```

Expected: Modified files appear as ` M` (unstaged). NO files in index. The Human commits and pushes per Git Policy.
