# CLAUDE.md — DPMtF-WebUI

> **Role-neutral project reference for Claude Code.**
> Authoritative governance: `docs/governance-templates-v2/` — this file summarizes;
> governance files rule in case of conflict.

## 1. Project Identity

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem — it owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself).

| Field | Value |
|-------|-------|
| **Port** | 9130 |
| **Repository** | `/home/svend/DPMtF-WebUI` |
| **Remote** | `https://github.com/svend-blip/DPMtF-WebUI.git` |
| **Branch** | `master` |
| **Runtime** | `/home/svend/.local/bin/uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |
| **Database** | `databases/dpmtf.db` (SQLite) |
| **Current commit** | `7ef7622` — BridgeV002 hardening (2026-06-22) |

## 2. Language Policy

- **en-US is mandatory** for all code, comments, docstrings, commit messages,
  and inter-role bridge communication.
- **Human may use Danish** — but prompts forwarded to other roles MUST be
  translated to English.
- Models perform better with English prompts — consistency matters.

## 3. Architecture Overview

```
DPMtF-WebUI/
├── app.py                  # FastAPI backend (~4000 lines)
├── config.py               # Central configuration — single source of truth
├── dpmtf.ini               # App-config defaults (committed)
├── .env                    # Secrets + infrastructure vars (NEVER commit)
├── requirements.txt        # Python dependencies
├── scripts/
│   ├── init_db.py          # Database initialization + seed data (~3300 lines)
│   ├── initialize_new_webui.py  # Accelerated WebUI Factory (Spor C)
│   └── bridgeV002/         # BridgeV002 dispatch system (replaces claude-bridge)
│       ├── dispatch.py     # Universal dispatcher — 4 signals (send/complete/escalation/answer)
│       ├── bridge_lib.py   # Database lookup, convention resolution, validation
│       ├── post-dispatch-common.py  # Convention-agnostic post-dispatch
│       ├── role_setup.py   # Ollama model pull for role preparation
│       └── role_teardown.py # Ollama model stop + VRAM cleanup
├── templates/
│   └── index.html          # Main HTML template (SPA)
├── static/
│   ├── js/dpmtf-app.js     # Frontend JavaScript (~5000 lines)
│   └── css/theme.css       # Dark theme (GitHub-dark palette)
├── docs/
│   ├── governance-templates-v2/  # Authoritative governance (all projects reference this)
│   │   ├── 01-04 + 10-27 + 99-300  # General governance files
│   │   ├── 401-405_STRICT_REVIEW_*.md  # Flow-specific role templates (BridgeV002)
│   │   └── knowledge-fragments/  # Curated .md fragments for Prompt Compiler
│   └── superpowers/              # Design specs and implementation plans
└── databases/
    └── dpmtf.db            # SQLite database (runtime state)
```

### 4-Layer i18n Architecture (Mandatory)

```
ui_text_slots (slot_key = unique position ID)
  → ui_text_slot_labels (slot → label mapping)
    → ui_labels (semantic label with default_text)
      → ui_label_translations (locale-specific text)
```

- API MUST traverse all 4 layers and return `{slot_key: text}`.
- Frontend uses `data-slot` attributes and `lbl(slot_key, fallback)`.
- Each label MUST have seed data in both `da-DK` and `en-US` locales.

### Panel Groups (Fixed)

Daily → Journals → Reports → Periodic → Setup

Subgroups are optional and database-driven via `panel_subgroups` table.
Visibility controlled by `is_visible` in `user_panel_groups` / `panel_subgroups`.

### Database vs Governance Files

| Lives In | What |
|----------|------|
| **Database** | UI text slots, labels, translations, user preferences, panel visibility, prompt templates, prompt runs, endpoint registry, bridge_roles, bridge_flows, bridge_flow_steps, bridge_convention_rules, bridge_scripts |
| **Governance files** | Project identity, scope, coding standards, validation rules, architecture, decisions, changelog, role definitions (general + flow-specific) |
| **Git** | All code, all governance files, migration scripts |

## 4. Coding Standards (Condensed)

Full rules: `docs/governance-templates-v2/12_CODING_STANDARD.md`

### Python
- `python3 -m py_compile <file>` MUST pass before signaling completion.
- **Parameterized SQL only** — `?` placeholders, never f-strings/concatenation in SQL.
- **No hardcoded paths** — use `config.py` getters (see §5). Auto-fail in validation.
- PEP 8, f-strings preferred, type hints where practical.

### JavaScript
- **NO `innerHTML` for dynamic content** — auto-fail. Use `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`.
- **ALL user-facing text MUST use `lbl(key, fallback)`** — no hardcoded English strings in DOM.
- `const` by default, `let` only when reassignment needed. Never `var`.
- Event delegation on container elements, not individual listeners.

### CSS
- Class-based selectors (not ID selectors for styling).
- No inline `style=""` attributes for layout.
- Dark theme (GitHub-dark palette). No light-theme colors.
- `dpmtf-hidden` class for hiding elements.

### Shell
- `bash -n <file>` MUST pass before signaling completion.
- Every script MUST start with `set -euo pipefail`.

### Prohibited Patterns (Auto-Fail)
1. `innerHTML` for dynamic content.
2. Hardcoded English strings in frontend — use `lbl()`.
3. Hardcoded `/home/svend/...` paths — use `config.py` getters.
4. Guesswork on ports/paths/model names — MUST be explicit.
5. Silent failures — catch blocks MUST log or report errors.
6. New dependencies without Human approval.
7. More than 2 failed patching attempts — stop, document, escalate.

## 5. Config System (Mandatory)

`config.py` is the **single source of truth** for all configurable values.
Hardcoded `/home/svend/...` strings anywhere are an **auto-fail** in validation.

| Value | Getter | Source |
|-------|--------|--------|
| Database path | `config.get_db_path()` | dpmtf.ini [database] |
| Bridge directory | `config.get_bridge_dir()` | .env DPMTF_BRIDGE_DIR |
| Project root | `config.get_project_root()` | dpmtf.ini [paths] |
| Governance directory | `config.get_governance_dir()` | dpmtf.ini [paths] |
| Governance dir (absolute) | `config.get_governance_dir_abs()` | Derived from project_root |
| Port | `config.get_port()` | dpmtf.ini [app] |
| Default locale | `config.get_default_locale()` | dpmtf.ini [app] |
| Father project path | `config.get_father_project()` | dpmtf.ini [projects] |
| Child projects | `config.get_child_projects()` | dpmtf.ini [projects] |
| Reference projects | `config.get_reference_projects()` | dpmtf.ini [projects] |
| Review session name | `config.get_review_session()` | .env |
| Implementer session name | `config.get_implementer_session()` | .env |
| Architect session name | `config.get_architect_session()` | .env |
| Log directory | `config.get_log_dir()` | dpmtf.ini [paths] |
| Exports directory | `config.get_exports_dir()` | dpmtf.ini [paths] |

**Correct:**
```python
import config
# BridgeV002 flow-based deliverable path:
handoff_path = f"{config.get_bridge_dir()}/handoffs/{hid}-handoff.md"
# Or use dispatch.py which resolves paths from the database:
# python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-send ...
```

**Wrong (auto-fail):**
```python
handoff_path = f"/home/svend/claude-bridge/reviewtoimplementor/{hid}-handoff.md"
```

## 6. Git Policy

Full rules: `docs/governance-templates-v2/15_GIT_POLICY.md`

- **Only the Human may commit or push.** All changes remain unstaged until
  Human approval.
- Commit messages in English, format: `[phase] description`.
- Include `Co-Authored-By: Claude <noreply@anthropic.com>` when AI-assisted.
- One logical change per commit. Stage selectively (`git add <files>`), not `git add -A`.
- Never commit: `__pycache__/`, `.env`, secrets, generated artifacts.
- Never amend published commits or force-push to `master`.

### Phase-Start Git Baseline (run these before starting work)
```bash
git status --short
git log --oneline -8
git branch --show-current
git remote -v
```

## 7. File Access

Full rules: `docs/governance-templates-v2/16_FILE_ACCESS.md`

### Free Write (within scope)
- `templates/` — HTML templates
- `static/` — JS, CSS, images
- `docs/` — documentation

### Restricted Write (Human approval required)
- `app.py` — backend entry point
- `config.py` — central configuration
- `scripts/init_db.py` — database schema and seed data
- `dpmtf.ini` — app-config defaults
- Role definition files (01-04, 401-405) — governance-critical

### Forbidden (all roles)
- `.git/` internals
- `__pycache__/`, `.pytest_cache/`
- `.env` files, credentials, API keys
- Other projects: `/home/svend/ENO/`, `/home/svend/ai-pc-resource-webui-v3/`
- Legacy bridge: `/home/svend/claude-bridge/` (read-only reference, superseded by BridgeV002)

### Append-Only Files
- `docs/governance-templates-v2/25_DECISIONS.md` — decision log
- `docs/governance-templates-v2/26_CHANGELOG.md` — change history

## 8. Validation Checklist

Full rules: `docs/governance-templates-v2/13_VALIDATION.md`

Before considering any change complete, run these 8 checks:

| # | Check | Command |
|---|-------|---------|
| 1 | Backend syntax | `python3 -m py_compile app.py` |
| 2 | Frontend syntax | `node --check static/js/*.js` |
| 3 | Shell syntax | `bash -n <file>` (if shell scripts changed) |
| 4 | Diff scope | `git diff --stat` — only expected files changed |
| 5 | Dependencies | `git diff requirements.txt` — no new deps without approval |
| 6 | Schema changes | Review diff for `ALTER TABLE` / `CREATE TABLE` |
| 7 | innerHTML | `grep -RIn "innerHTML" static/ templates/` — must be empty |
| 8 | i18n | Verify all user-facing text uses `lbl()` — no hardcoded English |

### Additional Checks
- `grep -n '"/home/svend' app.py scripts/` — must return NO results.
- `python3 scripts/init_db.py` — must run without errors (idempotent).
- `curl -s http://localhost:9130/api/health` — must return `{"status": "healthy"}`.

## 9. Governance Reference

The authoritative governance files live in `docs/governance-templates-v2/`.
This CLAUDE.md summarizes key rules; for full detail, read the source files.

### General Governance Files

| # | File | Purpose |
|---|------|---------|
| 01 | 01_HUMAN.md | Human role — scope authority, commit gate |
| 02 | 02_ARCHITECT.md | Architect role — design, prompt generation |
| 03 | 03_IMPLEMENTOR.md | Implementor role — code execution |
| 04 | 04_REVIEW.md | Review role — validation, workflow coordination |
| 10 | 10_PROJECT.md | Project identity and Father-Child relationship |
| 11 | 11_SCOPE.md | Current phase scope boundaries |
| 12 | 12_CODING_STANDARD.md | Full coding rules (this file §4 is a summary) |
| 13 | 13_VALIDATION.md | Full validation rules (this file §8 is a summary) |
| 14 | 14_ARCHITECTURE.md | System architecture and component design |
| 15 | 15_GIT_POLICY.md | Git conventions and Human-gated commits |
| 16 | 16_FILE_ACCESS.md | Role-specific file permissions |
| 17 | 17_DATABASE.md | Database schema and runtime state |
| 18 | 18_PERMISSION_MODE.md | Auto-execute boundaries and stop-and-ask rules |
| 19 | 19_OFFLINE_MODE.md | Offline operation and sync recovery |
| 20 | 20_GATES.md | Mandatory gate questions |
| 21 | 21_ALIGNMENT.md | Cross-project feature alignment |
| 22 | 22_MODEL_SELECTION.md | Model selection decision tree |
| 23 | 23_RESTART.md | Application restart and /clear reconstruction |
| 24 | 24_TESTPLAN.md | Test cases and manual verification |
| 25 | 25_DECISIONS.md | Append-only decision log |
| 26 | 26_CHANGELOG.md | Append-only change history |
| 27 | 27_NEXT_CONTEXT.md | Session handoff artifact |
| 99 | 99_ROLEINTERACTION.md | Role loop and escalation structure |
| 100 | 100_BRIDGE.md | BridgeV002 protocol and handoff formats |
| 200 | 200_HARDENING_V2.md | Design rationale for governance-templates-v2 |
| 300 | 300_SETUPINSTRUCTION.md | PC migration and fresh install guide |

### Flow-Specific Governance Files (BridgeV002)

| # | File | Role | Flow |
|---|------|------|------|
| 401 | 401_STRICT_REVIEW_HUMAN.md | Human | strict_review |
| 402 | 402_STRICT_REVIEW_ARCHI01.md | archi01 (Architect) | strict_review |
| 403 | 403_STRICT_REVIEW_IMPLE01.md | imple01 (Implementer) | strict_review |
| 404 | 404_STRICT_REVIEW_REVIEW01.md | review01 (Technical Review) | strict_review |
| 405 | 405_STRICT_REVIEW_REVIEW02.md | review02 (Governance Review) | strict_review |

> **Precedence:** When operating within a BridgeV002 flow, the flow-specific
> 400-series file takes precedence over the general 01-04 file for that role.

## 10. Knowledge Fragments

`docs/governance-templates-v2/knowledge-fragments/` contains curated `.md`
fragments used by the Prompt Compiler to assemble handoff prompts:

| Fragment | Purpose |
|----------|---------|
| `projects/dpmtf-webui.md` | DPMtF-WebUI project context |
| `projects/new-webui.md` | New Child project structure |
| `governance/python-task.md` | Python governance rules (extracted) |
| `patterns/add-endpoint.md` | Standard pattern for new API endpoints |
| `patterns/modify-backend.md` | Standard pattern for backend changes |
| `patterns/create-new-webui.md` | Accelerated + Standard paths for new WebUI |
| `scope/app.py-only.md` | Scope profile: backend-only changes |
| `scope/new-project-all.md` | Scope profile: new project creation |
| `validation/fullstack.md` | Fullstack validation commands |
| `validation/python.md` | Python-only validation commands |

## 11. Related Projects

| Project | Port | Path | Role |
|---------|------|------|------|
| **DPMtF-WebUI** | 9130 | `/home/svend/DPMtF-WebUI` | Father — governance engine + BridgeV002 |
| **ENO** | 9131 | `/home/svend/ENO` | First Child project |
| **ai-pc-resource-webui-v3** | 9123 | `/home/svend/ai-pc-resource-webui-v3` | Reference project |
| **claude-bridge** (legacy) | — | `/home/svend/claude-bridge/` | Legacy bridge — superseded by BridgeV002 |

**Rule:** Never modify files in other projects unless explicitly authorized.
DPMtF-WebUI's `docs/governance-templates-v2/` is the authoritative source for
all governance rules — other projects reference it, not the other way around.

## 12. BridgeV002 — Quick Reference

BridgeV002 is the **database-driven dispatch system** integrated into DPMtF-WebUI.
It replaces the legacy `claude-bridge/bridge.py` entirely.

### Signals (replace legacy bridge.py commands)

```bash
# Send handoff to target role:
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-send --from-role {from} --to-role {to}

# Signal completion:
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-complete --from-role {from}

# Escalate to architect:
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-escalation --from-role {from} --to-role {to}

# Answer escalation:
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-answer --from-role {from} --to-role {to}
```

### Key Principles

1. **Fully database-driven** — zero INI dependencies, zero hardcoded paths
2. **No-kill mode** — post-dispatch `ollama stop`, no tmux kill/new-session
3. **Flow-based** — `strict_review` is the primary flow; more can be added
4. **Convention-driven** — content templates govern injected prompts per step type
5. **Human skip** — `role_type=human` → dispatch skips tmux injection

### API Endpoints

```
GET  /api/bridge-v2/status, /roles, /roles/{key}, /flows, /flows/{key}
GET  /api/bridge-v2/steps/{flow_key}, /scripts, /conventions, /governance-files
POST /api/bridge-v2/roles, /flows, /steps/{flow_key}
POST /api/bridge-v2/roles/{key}/rename
POST /api/bridge-v2/flows/{key}/start-tmux, /start-coding, /stop-tmux, /attach-tmux
PUT  /api/bridge-v2/roles/{key}, /flows/{key}, /steps/{flow_key}/{id}
PATCH /api/bridge-v2/conventions/{rule_key}
DELETE /api/bridge-v2/roles/{key}, /flows/{key}, /steps/{flow_key}/{id}
```

See [[100_BRIDGE]] for the full protocol.
