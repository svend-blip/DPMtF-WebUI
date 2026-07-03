# CLAUDE.md — DPMtF-WebUI

> **Principle-based reference for Claude Code.**
> Authoritative governance: `docs/governance-templates-v2/` — this file summarizes;
> governance files rule in case of conflict.
> Script, endpoint, role, and flow details are handled by BridgeV002 and mcp-light.

## 1. Project Identity

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem — it owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself).

| Field | Value |
|------|-------|
| **Port** | 9130 |
| **Database** | `databases/dpmtf.db` (SQLite) |
| **Runtime** | `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |

## 2. Language Policy

- **en-US is mandatory** for all code, comments, docstrings, commit messages,
  and inter-role bridge communication.
- **Human may use Danish** — but prompts forwarded to other roles MUST be
  translated to English.

## 3. Config System (Mandatory)

`config.py` is the **single source of truth** for all configurable values.
Hardcoded `/home/svend/...` paths are an **auto-fail** in validation.

- Always use `config.get_*()` methods — never hardcode paths, ports, or model names.
- `.env` holds secrets and infrastructure variables (never committed).
- `dpmtf.ini` holds app-config defaults (committed).

## 4. Coding Standards

Full rules: `docs/governance-templates-v2/12_CODING_STANDARD.md`

### Python
- `python3 -m py_compile <file>` MUST pass before signaling completion.
- **Parameterized SQL only** — `?` placeholders, never f-strings/concatenation in SQL.
- **No hardcoded paths** — use `config.py` getters.
- PEP 8, f-strings preferred, type hints where practical.

### JavaScript
- **NO `innerHTML` for dynamic content** — auto-fail.
  Use `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`.
- **ALL user-facing text MUST use `lbl(key, fallback)`** — no hardcoded English strings.
- `const` by default, `let` only when reassignment needed. Never `var`.
- Event delegation on container elements, not individual listeners.

### CSS
- Class-based selectors (not ID selectors for styling).
- No inline `style=""` attributes for layout.
- Dark theme (GitHub-dark palette). No light-theme colors.

### Shell
- `bash -n <file>` MUST pass before signaling completion.
- Every script MUST start with `set -euo pipefail`.

### Auto-Fail Patterns
1. `innerHTML` for dynamic content
2. Hardcoded English strings in frontend — use `lbl()`
3. Hardcoded `/home/svend/...` paths — use `config.py`
4. Guesswork on ports, paths, model names — MUST be explicit
5. Silent failures — catch blocks MUST log or report errors
6. New dependencies without Human approval
7. More than 2 failed patching attempts — stop, document, escalate

## 5. Git Policy

Full rules: `docs/governance-templates-v2/15_GIT_POLICY.md`

- **Only the Human may commit or push.** All changes remain unstaged until
  Human approval.
- Commit messages in English, format: `[phase] description`.
- One logical change per commit. Stage selectively (`git add <files>`), not `git add -A`.
- Never commit: `__pycache__/`, `.env`, secrets, generated artifacts.
- Never amend published commits or force-push to `master`.

## 6. Validation Checklist

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

## 7. Governance Precedence

Governance files in `docs/governance-templates-v2/` are authoritative.
CLAUDE.md summarizes; in case of conflict, the governance file rules.

Flow-specific 400-series files take precedence over general 01-04 files
for that role when operating within a BridgeV002 flow.

## 8. BridgeV002 — Principles

BridgeV002 is the **database-driven dispatch system**. It replaces `claude-bridge/` entirely.

### Core Principles
1. **Fully database-driven** — zero INI dependencies, zero hardcoded paths
2. **No-kill mode** — post-dispatch `ollama stop`, no tmux kill/new-session
3. **Convention-driven** — content templates govern injected prompts per step type
4. **Human skip** — `role_type=human` → dispatch skips tmux injection

### Signals
```bash
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-send --from-role {from} --to-role {to}
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-complete --from-role {from}
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-escalation --from-role {from} --to-role {to}
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-answer --from-role {from} --to-role {to}
```

See `docs/governance-templates-v2/100_BRIDGE.md` for the full protocol.

## 9. i18n — 4-Layer Architecture

```
ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations
```

- API MUST traverse all 4 layers and return `{slot_key: text}`.
- Frontend uses `data-slot` attributes and `lbl(slot_key, fallback)`.
- Each label MUST have seed data in both `da-DK` and `en-US` locales.

## 10. File Access

Full rules: `docs/governance-templates-v2/16_FILE_ACCESS.md`

- **Free write:** `templates/`, `static/`, `docs/`
- **Human approval required:** `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`, governance role definition files
- **Forbidden:** `.git/`, `__pycache__/`, `.env`, secrets, other projects' directories
- **Append-only:** `25_DECISIONS.md`, `26_CHANGELOG.md`
