# Database Runtime State

## Purpose

This governance document defines what data lives in the SQLite database versus what lives in governance documents (Markdown files). It clarifies the separation between runtime state and process definitions, and establishes the rules for schema changes. The database stores operational data; governance documents store process rules.

## When to Use

- **Solution Architect**: Reference before designing new database tables or columns.
- **Implementer**: Read to know what belongs in the database vs. governance files.
- **Validator**: Check that no runtime-state data was accidentally put into governance files (or vice versa).
- **After `/clear`**: Reconstruct the data model without querying the live database.

---

## Current State — No Database Schema Yet

**As of phase 3C-3, AI PC Resource WebUI v3 has no database schema.** The `databases/` directory exists and contains only a `.gitkeep` file. No SQLite database file exists. No tables are defined. The current skeleton in `app.py` does not connect to any database.

Database schema creation belongs to **phase 3C-4** and later.

---

## Planned Database Table Groups (Future Architecture)

The following table groups describe the **intended future architecture** for AI PC Resource WebUI v3. None of these tables exist yet. They are documented here to establish the architectural direction before implementation begins in phase 3C-4 or later.

### 1. UI Text Slots / i18n

Database-driven UI labels and translations so all frontend text is configurable without code changes.

| Planned Table | Purpose |
|---------------|---------|
| `ui_text_slots` | Stable frontend-facing text placement IDs (page title, panel heading, button label, tooltip, etc.). Layer 1 — where text appears. |
| `ui_text_slot_labels` | Binding table mapping `ui_text_slots` → `ui_labels`. Layer 2 — allows reuse (many slots can share one label). |
| `ui_labels` | Reusable semantic UI labels / text concepts (e.g., "Start", "Stop", "Validation failed"). Layer 3 — not hardcoded as frontend placement IDs. |
| `ui_label_translations` | Locale-specific translated text per label using BCP 47 locale tags (da-DK, en-US, en-GB). Layer 4. |

### 2. Endpoint Registry

Registered API endpoints with metadata for frontend-driven panel rendering.

| Planned Table | Purpose |
|---------------|---------|
| `endpoint_registry` | Registered API endpoints with method, path, description, and permission requirements. |

### 3. Roles / Permissions / Users

Role-based access control model.

| Planned Table | Purpose |
|---------------|---------|
| `roles` | Role definitions (e.g., admin, operator, viewer). |
| `permissions` | Permission definitions bound to roles. |
| `users` | User accounts with role assignments. |

### 4. Service Cards

Service card definitions for resource management and Ollama integration.

| Planned Table | Purpose |
|---------------|---------|
| `service_cards` | Service card definitions with configuration, status, and metadata. |

### 5. Pipeline Registry

Pipeline definitions for multi-step orchestration.

| Planned Table | Purpose |
|---------------|---------|
| `pipelines` | Pipeline definitions for orchestrating service operations. |
| `pipeline_steps` | Individual steps within a pipeline. |

### 6. Service Actions

Action definitions bound to service cards or pipelines.

| Planned Table | Purpose |
|---------------|---------|
| `service_actions` | Action definitions (start, stop, restart, configure) bound to service cards. |

### 7. Ollama Model Defaults / State per Card

Persistent Ollama model selection and runtime state tracking.

| Planned Table | Purpose |
|---------------|---------|
| `ollama_model_defaults` | Default model configuration per service card. |
| `ollama_card_state` | Runtime state tracking per service card (current model, temperature, last used, etc.). |

### 8. Audit / Action Log

Audit trail of all system actions for traceability.

| Planned Table | Purpose |
|---------------|---------|
| `audit_log` | Timestamped record of all significant system actions with user/context attribution. |

---

## What Lives in the Database (Future)

When schema is created in phase 3C-4 and later:

- All runtime state for the application.
- UI labels, translations, and text bindings.
- Endpoint registry data.
- Role, permission, and user data.
- Service card definitions and state.
- Pipeline and action definitions.
- Ollama model defaults and per-card state.
- Audit/action log entries.

## What Does NOT Live in the Database

- Governance templates (Markdown files in `docs/dpmtf/`).
- Role definitions, scope boundaries, coding standards, or file access policies.
- Architecture decisions beyond ADR table entries recorded in `09_DECISIONS.md`.
- Prompt-run reports and validation reports (stored in `docs/prompt-runs/` when applicable).

## Schema Change Policy

1. **Schema changes require explicit Human Approval Gate approval** and must be backward compatible.
2. **Prefer adding new columns with defaults** over altering existing columns — this avoids breaking existing data.
3. **Document all schema changes in `09_DECISIONS.md`** using the decision format.
4. **Test schema changes locally** before committing — verify the application starts and reads old data correctly.
5. **Do not drop columns or tables** unless the phase explicitly authorizes destructive changes AND a backup exists.

## Schema Change Template

When proposing a schema change, Solution Architect must fill in:

```markdown
### Proposed Schema Change
**Table:** [existing table name or "new table"]
**Change:** [ADD COLUMN, CREATE TABLE, ALTER COLUMN, etc.]
**Default value:** [default for new columns]
**Backward compatible:** Yes / No — explanation if No.
**Backup plan:** [How to revert if the change breaks something.]
```

---
