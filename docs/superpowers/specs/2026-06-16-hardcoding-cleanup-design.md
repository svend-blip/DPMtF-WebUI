# Hardcoding Cleanup — Config System Design (Spor A)

**Date:** 2026-06-16
**Role:** Architect
**Status:** Approved — ready for implementation planning

## Purpose

Eliminate hardcoded paths, project references, and configuration values from
DPMtF-WebUI and claude-bridge so the system can be moved to another PC without
code changes. This is Spor A of a two-phase effort — Spor B (Prompt Compiler
redesign) builds on this config foundation.

## Config Architecture

### Principle (from ENVINIDATA.md)

```
Secret?        → .env / environment variable (NEVER in code, ini, or database)
Infrastructure? → Environment variable with sensible defaults
App-config?    → dpmtf.ini with fallback to hardcoded values
Content/Data?  → Database
```

### dpmtf.ini (new file — committed with defaults)

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

### .env (existing — extended)

```ini
# Existing:
DPMTF_TELEGRAM_BOT_TOKEN=...
DPMTF_TELEGRAM_CHAT_ID=...
DPMTF_CLAUDE_TMUX_SESSION=...

# New:
DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
DPMTF_REVIEW_SESSION=claude_review
DPMTF_IMPLEMENTER_SESSION=claude_implementer
DPMTF_ARCHITECT_SESSION=claude_architect
```

### config.py (new file — single source of truth)

A central config module that all other files import from:

```python
# config.py — single source of truth for all config lookups
import os
import configparser
from pathlib import Path

# .env loading
# .ini loading with fallbacks

def get_db_path(): ...
def get_bridge_dir(): ...
def get_project_root(): ...
def get_governance_dir(): ...
def get_father_project(): ...
def get_child_projects(): ...
def get_reference_projects(): ...
def get_port(): ...
def get_host(): ...
def get_default_locale(): ...
```

### Database (already database-driven — no changes)

- i18n labels/translations ✓
- Panel group states ✓
- Prompt templates ✓
- Language preferences ✓

## File-by-File Changes

### bridge.py — 3 changes (highest impact/effort ratio)

| # | Line | Change |
|---|-------|---------|
| 1 | 26-27 | `BRIDGE_DIR = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/.dpmtf/bridge"))` — ripples through 40+ references |
| 2 | 28-30 | `REVIEW_SESSION`, `IMPLEMENTER_SESSION`, `ARCHITECT_SESSION` → `os.environ.get()` with current names as defaults |
| 3 | — | `os.makedirs(BRIDGE_DIR, exist_ok=True)` + subdirectories on write |

No other changes in bridge.py — all other paths already compute from `BRIDGE_DIR`.

### app.py — 5 changes

| # | Area | Change |
|---|------|--------|
| 1 | Top | Import `config.py` + load `.env` at startup |
| 2 | Line 18 | `DB_PATH = config.get_db_path()` instead of hardcoded `"databases/dpmtf.db"` |
| 3 | Line 614 | `Project path: /home/svend/DPMtF-WebUI` → `Project path: {config.get_project_root()}` |
| 4 | Line 1722 | `/home/svend` → `os.path.expanduser("~")` in validation |
| 5 | Prompt generation (~15 places) | `/home/svend/claude-bridge/...` → `f"{config.get_bridge_dir()}/..."` and `/home/svend/{father_project}/...` → `f"{config.get_project_root()}/..."` |

### scripts/init_db.py — 2 changes

| # | Change |
|---|---------|
| 1 | Import `config.py` — replace hardcoded `/home/svend/...` paths with `config.get_*()` lookups |
| 2 | Project references (target_project_path, server_start_command) → use `{project_root}` placeholder or config lookup |

### New Files

| File | Content |
|------|---------|
| `config.py` | Central config module — `.env` + `.ini` loading, getter functions |
| `dpmtf.ini` | App-config with defaults (committed) |

### Governance Updates

| File | Change |
|------|---------|
| `12_CODING_STANDARD.md` | "No hardcoded paths" rule expanded: paths MUST come from `config.py` or environment variables. New "Config Lookup Pattern" section added. Hardcoded `/home/svend/...` becomes auto-fail. |
| `16_FILE_ACCESS.md` | Updated with reference to `config.py` for project path resolution. |
| `02_ARCHITECT.md` | Prompt Generation Rules: new rule 9 — use config getters in generated prompts. |

## Implementation Order — Handoff Sequence

Each handoff is designed for execution by the local Ollama model (qwen36-27b-q4km)
via the bridge. Small, focused, with concrete validation commands.

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
    └─→ Handoff 028: governance — 12_CODING_STANDARD + 16_FILE_ACCESS
```

| ID | Title | Files | Key Change | Est. Complexity |
|----|-------|-------|-------------|-------------------|
| **023** | Config foundation | `config.py` (new), `dpmtf.ini` (new) | Central config module with `.env` + `.ini` loading | Low |
| **024** | Bridge config | `bridge.py` | 3-line change — BRIDGE_DIR + sessions → environment variables | Low |
| **025** | App config — basics | `app.py` | DB_PATH, project root, validation → config lookups | Low |
| **026** | App config — prompts | `app.py` | 15+ hardcoded `/home/svend/...` in prompt generation → config lookups | Medium |
| **027** | Seed data | `scripts/init_db.py` | ~75 hardcoded paths → config lookups or placeholders | Medium |
| **028** | Governance | `12_CODING_STANDARD.md`, `16_FILE_ACCESS.md`, `02_ARCHITECT.md` | "No hardcoded paths" rule + config lookup pattern | Low |

**Total: 6 handoffs, estimated 2-3 hours on local model.**

Each handoff validates with `py_compile`, `node --check` (if relevant),
`git diff --stat`, and a specific check (e.g. "grep '/home/svend' app.py —
only config.py imports remain").

## Prompt Compiler Impact (Spor B Preview)

### What Spor A Fixes in the Prompt Compiler

| Problem | Solution |
|---------|----------|
| `/home/svend/claude-bridge/...` in result/notification paths | `config.get_bridge_dir()` |
| `/home/svend/{father_project}/...` in governance paths | `config.get_project_root()` |
| `/home/svend/ENO/` and `/home/svend/ai-pc-resource-webui-v3/` in forbidden paths | `config.get_child_projects()` / `config.get_reference_projects()` |
| `python3 /home/svend/claude-bridge/bridge.py` in signal | `config.get_bridge_dir()` |

### What Spor B Must Handle (Next Phase)

| Problem | Current | Spor B Direction |
|---------|---------|------------------|
| `11_SCOPE.md` reference | Hardcoded in `<context>` | Database-driven: scope filename from `prompt_compiler_fields` or template |
| `12_CODING_STANDARD.md` + `16_FILE_ACCESS.md` | Hardcoded in `<governance>` | Database-driven: governance files as template parameters |
| `20_GATES.md` reference | Hardcoded in gate field names | Database-driven: gate definitions in `prompt_compiler_fields` |
| Entire XML structure | Hardcoded Python string concatenation (~100 lines) | Template-driven: `prompt_templates` table with `{variable}` substitution |
| "Father project:" | Hardcoded text | Template variable |
| Role-specific sections | Hardcoded if/elif | Template-driven: role → section mapping in database |
| Allowed/forbidden files structure | Hardcoded `<scope>` format | Template-driven with database-driven defaults |

### Spor B Design Direction (Preview)

Prompt Compiler moves from:

```
Python string concatenation → Database template with {variable} substitution
```

Principle: `prompt_templates.structure_json` already defines a structure.
It should be extended to contain the entire prompt layout, not just metadata.
The compile function becomes a template engine: load template from DB,
substitute `{variables}`, output finished prompt.

## Success Criteria

- [ ] `config.py` exists and is the single source of truth for all configurable values
- [ ] `dpmtf.ini` exists with all sections populated with defaults
- [ ] `bridge.py` has zero hardcoded `/home/svend/` strings (only env var lookups)
- [ ] `app.py` has zero hardcoded `/home/svend/` strings outside of config imports
- [ ] `scripts/init_db.py` has zero hardcoded `/home/svend/` strings outside of config imports
- [ ] `12_CODING_STANDARD.md` has expanded "No hardcoded paths" rule with config lookup pattern
- [ ] All 6 handoffs pass their validation checks
- [ ] System starts and runs correctly after all changes
- [ ] `.env` and `dpmtf.ini` can be edited to point to different paths and the system still works
