# Database Runtime State

## Purpose

This governance document defines what data lives in the SQLite database versus what lives in governance documents (Markdown files). It clarifies the separation between runtime state and process definitions, and establishes the rules for schema changes. The database stores operational data; governance documents store process rules.

## When to Use

- **Solution Architect**: Reference before designing new database tables or columns.
- **Implementer**: Read to know what belongs in the database vs. governance files.
- **Validator**: Check that no runtime-state data was accidentally put into governance files (or vice versa).
- **After `/clear`**: Reconstruct the data model without querying the live database.

## Required Inputs

| Input | Description |
|-------|-------------|
| Current database schema | This document, updated for each phase. |
| Proposed changes | From Solution Architect design. |

## Required Outputs

- Updated table list if new tables or columns were added.
- Schema change policy followed and documented in `DECISIONS.md`.
- Clear separation maintained between runtime data and governance documents.

---

## Overview

The SQLite database stores runtime state, configuration, registry data, and execution history. Governance documents are file-based (Markdown) and live in `docs/governance-templates/`, not in the database. This separation ensures that process rules are always readable without a running application.

## What Lives in the Database

| Table | Purpose |
|-------|---------|
| `phase_status` | Phase tracking: completed, next phase, planned phases. |
| `frontend_panels` | Registered UI panels with metadata (name, label, visibility). |
| `panel_classifications` | Classification per panel (category, type). |
| `app_profiles` | Named collections of panels for different application modes. |
| `prompt_sequences` | Prompt execution plans: phase, role sequence, status. |
| `prompt_sequence_steps` | Individual steps within a prompt sequence. |
| `generated_prompts` | Archive of generated prompts from Prompt Engineer steps. |
| `ui_text_slots` | Stable frontend-facing text placement IDs (page title, panel heading, button label, tooltip, etc.). Frontend references this layer, not labels directly. |
| `ui_text_slot_labels` | UI Text Binding table: maps `ui_text_slots` → `ui_labels`. Many slots may bind to the same label for reuse. Changing a binding in the database does not require editing frontend code. |
| `ui_labels` | Reusable semantic UI labels / text concepts (e.g., "Start", "Stop", "Validation failed"). Not hardcoded as frontend placement IDs. Labels do not control layout, endpoints, permissions, actions, or visibility. |
| `ui_label_translations` | Locale-specific translated text per label using BCP 47 locale tags (da-DK, en-US, en-GB). |
| `endpoint_registry` | Registered API endpoints with metadata (method, path, description). |
| `layout_slots` | Layout slot definitions for the frontend grid system. |
| `layout_panels` | Panel placement within layout slots. |
| `project_plans` | New project planning records created by the governance engine. |

### UI Text Slot / i18n Table Relationships

```
ui_text_slots (Layer 1 — frontend placement)
       │
       │  1:N relationship (many slots → one label)
       │
       ▼
ui_text_slot_labels (Layer 2 — binding table)
       │
       │  N:1 relationship (many slots can share one label)
       │
       ▼
ui_labels (Layer 3 — reusable semantic labels)
       │
       │  1:N relationship (one label → many translations)
       │
       ▼
ui_label_translations (Layer 4 — locale text via BCP 47 tags)
```

**Key rules:**

- **Many-to-one reuse**: Multiple `ui_text_slots` may bind to the same `ui_label_id`. For example, two different buttons on two different panels can both display "Start" by binding to the same label.
- **Binding is database-only**: Changing which label a slot points to is done entirely in `ui_text_slot_labels`. No frontend code changes are required for re-binding.
- **Safe fallback**: If a `ui_text_slot` has no binding, or a `ui_label` has no translation for the active locale, the frontend must render safely (display the slot key or a generic placeholder) — missing labels must not break rendering.
- **Separation from layout and endpoints**: UI Labels are purely text/translation concerns. Layout is managed by `layout_slots` and `layout_panels`. Endpoints are managed by `endpoint_registry`. These registries do not overlap.

### Migration Policy for Text Slot Architecture

When the four-layer slot/binding architecture is implemented:

1. Migrate **one panel at a time** — do not migrate all panels in a single phase.
2. Each migrated panel introduces its own `ui_text_slot` entries and bindings.
3. Unmigrated panels continue using the legacy direct-label pattern until their migration phase.
4. Document each panel's migration status in `DECISIONS.md`.

## What Does NOT Live in the Database

- Governance templates (Markdown files in `docs/governance-templates/`).
- Role definitions, scope boundaries, coding standards, or file access policies.
- Architecture decisions beyond ADR table entries recorded in `DECISIONS.md`.
- Prompt-run reports and validation reports (stored in `docs/prompt-runs/`).

## Schema Change Policy

1. **Schema changes require explicit Human Approval Gate approval** and must be backward compatible.
2. **Prefer adding new columns with defaults** over altering existing columns — this avoids breaking existing data.
3. **Document all schema changes in `DECISIONS.md`** using the decision format.
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
