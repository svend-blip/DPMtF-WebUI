# 12 — CODING STANDARD

> **en-US is the standard language for all governance-templates-v2 files.**
> All code, comments, documentation strings, and commit messages MUST be in
> English (en-US).

## Purpose

Defines coding rules for all languages used in DPMtF-governed projects. These
rules apply to all code produced by the Implementor role and are enforced by
the Review role during validation.

## When to Use

- **Implementor:** Apply these rules to every line of code produced.
- **Review:** Check all diffs against these rules.
- **Architect:** Reference these rules in implementation prompts.

---

## Python

| Rule | Description |
|------|-------------|
| **Syntax check** | `python3 -m py_compile <file>` MUST pass before signaling completion. |
| **PEP 8** | Follow PEP 8 style guide. |
| **Parameterized SQL** | All SQL queries MUST use parameterized statements — never string concatenation. |
| **No hardcoded paths** | Paths, ports, model names, project references, and bridge directories MUST come from `config.py` getter-functions or environment variables. Hardcoded `/home/svend/...` strings anywhere in Python, JavaScript, shell scripts, or seed data are an auto-fail in validation. The single source of truth for all configurable values is `config.py`. |
| **f-strings** | Prefer f-strings over `.format()` or `%` formatting. |
| **Type hints** | Use type hints for function signatures where practical. |

### Config Lookup Pattern (Mandatory)

All configurable values MUST be accessed through `config.py` getter-functions:

| Value | Getter | Source |
|-------|--------|--------|
| Database path | `config.get_db_path()` | dpmtf.ini [database] |
| Bridge directory | `config.get_bridge_dir()` | .env DPMTF_BRIDGE_DIR |
| Project root | `config.get_project_root()` | dpmtf.ini [paths] |
| Governance directory | `config.get_governance_dir()` | dpmtf.ini [paths] |
| Governance directory (absolute) | `config.get_governance_dir_abs()` | Derived from project_root |
| Tmux session names | `config.get_review_session()` etc. | .env |
| Port, host, locale | `config.get_port()` etc. | dpmtf.ini [app] |
| Father/child/reference projects | `config.get_father_project()` etc. | dpmtf.ini [projects] |
| Log directory | `config.get_log_dir()` | dpmtf.ini [paths] |
| Exports directory | `config.get_exports_dir()` | dpmtf.ini [paths] |

**Rule:** If a value could differ between two PCs, it goes through config.py.
Hardcoded strings like `/home/svend/...` are prohibited — use config getters.

**Example (correct):**
```python
import config
handoff_path = f"{config.get_bridge_dir()}/{flow_key}/handoffs/{hid}-handoff.md"
```

**Example (WRONG — auto-fail):**
```python
handoff_path = f"/home/svend/flows/strict_review/handoffs/{hid}-handoff.md"
```

## Frontend Governance

All frontend changes MUST follow [[30_FRONTEND_GOVERNANCE]] for panel registration,
subgroup mapping, and i18n requirements.

## JavaScript

| Rule | Description |
|------|-------------|
| **Syntax check** | `node --check static/js/*.js` MUST pass for each modified file. |
| **NO innerHTML** | `innerHTML` for dynamic content is an auto-fail. Use `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`. |
| **lbl() helper** | ALL user-facing text MUST use `lbl(key, fallback)`. No hardcoded English strings in DOM construction. |
| **data-slot attributes** | Frontend elements reference `slot_key` via `data-slot` attributes, not `ui_labels` directly. |
| **Event delegation** | Use event delegation on container elements, not individual listeners per item. |
| **const/let** | Use `const` by default, `let` only when reassignment is needed. Never `var`. |

## CSS

| Rule | Description |
|------|-------------|
| **Class-based selectors** | Use class selectors, not ID selectors for styling. |
| **No inline styles** | No inline `style=""` attributes for layout. Use CSS classes. |
| **Dark theme** | All projects use dark theme (GitHub-dark palette). No light-theme colors. |
| **Temporary hiding** | Use `dpmtf-hidden` class for hiding elements. `is_visible = 0` in database controls visibility. |

## Shell

| Rule | Description |
|------|-------------|
| **Syntax check** | `bash -n <file>` MUST pass before signaling completion. |
| **set -euo pipefail** | Every script MUST start with `set -euo pipefail`. |
| **No heredocs for code** | Do not use heredocs to generate code files. |

## Markdown

| Rule | Description |
|------|-------------|
| **ATX headings** | Use `#` style headings, not underline style. |
| **Consistent tables** | Align table columns for readability. |
| **Append-only logs** | [[25_DECISIONS]] and [[26_CHANGELOG]] are append-only — add new entries at the bottom. |

## Test Selection Policy (Mandatory where a policy file exists)

The repository's regression testing is governed by
`.dpmtf/test-policy.json`, consumed by the test-impact engine
(`scripts/testing/`, spec: `docs/specs/TEST-IMPACT-ARCHITECTURE.md`).

| Rule | Description |
|------|-------------|
| **Selection, not skipping** | A change runs the policy-resolved selection for its changed files. The selection may only ever be *escalated* (component → broad → full) — never narrowed below what the engine resolves. |
| **Fallback, not floor** | Uncertainty escalates: an unmapped file, an unresolved symbol, or an empty/absent policy resolves to a broader scope, ultimately the full suite. |
| **Smoke tests are unconditional** | `mandatory_smoke_tests` run at every scope, including the narrowest. |
| **The engine never vouches for itself** | Any change under `scripts/testing/` triggers the full suite (`full_regression_triggers`). So does a change to the policy file itself. |
| **Reviewers verify, never trust** | The reviewer re-runs the resolved selection (or the full suite) — never the implementer's pasted summary, never the impact artifact's recorded status. See TECHNICAL_REVIEW check 9. |
| **Frontend changes escalate** | No JavaScript test suite exists (Run 012 parked), so JS/CSS/template changes resolve broad — honest escalation, not a gap to patch around. |

## 4-Layer i18n Architecture (Mandatory)

The four-layer internationalization architecture is mandatory across all projects:

```
ui_text_slots (slot_key = unique position ID)
  → ui_text_slot_labels (slot → label mapping)
    → ui_labels (semantic label with default_text)
      → ui_label_translations (locale-specific text)
```

**Mandatory locales (all four, every label):**

| Locale | Language |
|--------|----------|
| `en-US` | English |
| `da-DK` | Danish |
| `de-DE` | German |
| `es-ES` | Spanish |

**Rules:**
- API MUST traverse all 4 layers and return `{slot_key: text}`.
- Multiple slots CAN map to the same label.
- Frontend `data-slot` attributes and `lbl()` calls use `slot_key` as the key.
- Each label MUST have seed data in **all four mandatory locales** —
  `en-US`, `da-DK`, `de-DE`, `es-ES`. (Until 2026-08-08 the requirement was
  da-DK + en-US; existing projects carrying extra locales such as `sv-SE` or
  `el-GR` may keep them as optional, but they never substitute for a
  mandatory one.)
- New labels require `ui_labels` + `ui_label_translations` entries in all
  four mandatory locales — this is routine, not optional.
- A label missing one of the four mandatory locales is a validation
  finding: the Review role reports it, and the fix is adding the
  translation, never deleting the label.

**Find-or-create — never create-per-slot.** Slot keys are unique, but
labels are shared: when several slots present the same text and help text,
they map to ONE label. Before creating any label:

1. Check for an existing label with identical `default_text` +
   `description` — mcp-light's `find_reusable_label` tool does this and
   answers `reuse` (with the slot-mapping SQL) or `create` (with the
   4-locale template).
2. On `reuse`: map the slot to the existing label. Creating a duplicate
   anyway is a validation finding.
3. In Python seeds/migrations, use `scripts/i18n_lib.py` —
   `find_or_create_label()` performs the check-and-reuse automatically and
   refuses labels missing any mandatory locale; `map_slot()` registers the
   slot idempotently.
4. mcp-light's `find_duplicate_labels` reports existing duplicates; the
   merge is: keep one, repoint the slots, deactivate (`is_active = 0`,
   never DELETE) the rest.

## Frontend Structure Standard (Mandatory where a UI exists)

Every DPMtF-governed project that has a web UI follows the same overarching
structure — the one produced by deployment strategy `accelerated` and the
"Create New WebUI" button. The canonical reference implementation is
`templates/new-webui-skeleton/` in the Father project; when this standard and
the skeleton disagree, fix the skeleton or this file — do not fork a third
variant.

**Fixed panel-group structure.** `index.html` contains exactly these five
panel groups, in this order, with these element ids:

```
pg-daily      — day-to-day operational panels
pg-journals   — logs, journals, run histories
pg-reports    — reports and analyses
pg-periodic   — recurring/periodic tasks
pg-setup      — configuration and administration
```

Rules:

| Rule | Description |
|------|-------------|
| **Group ids are fixed** | `pg-daily`, `pg-journals`, `pg-reports`, `pg-periodic`, `pg-setup`. New top-level groups require a governance change here first. |
| **Empty groups stay** | A project with nothing to show in a group keeps the group and hides it via `is_visible = 0` in the database — never by deleting it from `index.html`. |
| **Panels register in a group** | Every panel lives inside one of the five groups; panel/subgroup registration follows [[30_FRONTEND_GOVERNANCE]]. |
| **Group titles are slots** | Group headers use `data-slot` (`pg_daily`, `pg_journals`, …) and are translated through the 4-layer i18n architecture like any other label. |

**Language switcher.** The UI has a language selector in the upper-right
corner (as in DPMtF-WebUI): populated from `/api/available-languages`
(database-driven — never a hardcoded list in JS), switching locale re-renders
labels via the i18n API without a page reload, and the chosen locale is
persisted per user.

**Expand/collapse is database-driven per user.** Panel-group and subgroup
open/closed state is stored per user in the database (`user_panel_groups`:
`user_id`, `group_name`, `state`, `is_visible`) and saved through an API
endpoint when the user toggles. The frontend renders from the saved state on
load — no locally-hardcoded defaults that fight the database.

**Scope.** This section binds projects that HAVE a web UI (currently
DPMtF-WebUI and model-allocator). Components without a UI (workers, MCP
servers) are exempt until the day they grow one — and then they start from
the skeleton, not from scratch.

## Prohibited Patterns

These patterns are prohibited based on project history:

1. **innerHTML for dynamic content** — auto-fail in validation.
2. **Hardcoded English strings in frontend** — auto-fail. Use `lbl()`.
2.5. **Hardcoded /home/svend or user-specific paths** — auto-fail. Use `config.py` getters. The only allowed hardcoded path is `sys.path.insert(0, ...)` for bootstrap in scripts that need to import config before it's on PYTHONPATH.
3. **Guesswork on operational targets** — ports, paths, model names MUST be explicit.
4. **Silent failures** — catch blocks MUST log or report errors.
5. **New dependencies without Human approval** — auto-fail.
6. **More than 2 failed patching attempts** — stop, document, escalate.
7. **Destructive database operations on production data** — auto-fail. This
   includes `DROP TABLE`, `DELETE FROM <table>` (without a WHERE on a temp
   table), `rm` on any path containing `databases/` or a production `.db`
   file, and `CREATE TABLE` that recreates a production table from memory.
   **Production DB = `databases/dpmtf.db` (Father) and
   `databases/trade-ui.db` (trade-ui).** Rules:
   - Never `rm` a production `.db` path — even inside a multi-path `rm -f`.
     Only `rm` paths under `/tmp/` or an explicit test-fixture dir.
   - If a production DB is corrupted/deleted: **restore from backup** (see
     `docs/bridgeV002/BACKUP-STRATEGY.md`) or escalate to Human. NEVER
     recreate tables from memory — hallucinated schemas (e.g. `last_id` vs
     `next_id`) silently corrupt the bridge and break dispatch.
   - Test against a **temp DB** (`/tmp/test_*.db` or `tmp_path`), never the
     production DB. If a test must touch production schema, copy first:
     `cp databases/dpmtf.db /tmp/test.db`.
   - `signal-complete` / dispatch failures are NOT a reason to mutate the
     production DB. Investigate the cause; do not INSERT minimal rows to
     make the command succeed.
   - Added 2026-07-04 after handoff 43 (B-4): imple01pay ran
     `rm -f /tmp/test_b4_father.db databases/dpmtf.db` (deleted the Father
     DB by mistake), then recreated bridge tables from memory with a
     hallucinated `last_id` schema, losing 4 flows / 22 roles / all counters.

---
