# Database Runtime State

## Overview
The SQLite database stores runtime state, configuration, and registry data. Governance documents are file-based (Markdown) and live in `docs/`, not in the database.

## What Lives in the Database
| Table | Purpose |
|-------|---------|
| `phase_status` | Phase tracking (completed, next, planned). |
| `frontend_panels` | Registered UI panels with metadata. |
| `panel_classifications` | Classification per panel. |
| `app_profiles` | Named collections of panels. |
| `prompt_sequences` | Prompt execution plans. |
| `prompt_sequence_steps` | Individual steps in a sequence. |
| `generated_prompts` | Archive of generated prompts. |
| `ui_labels` | i18n label registry. |
| `ui_label_translations` | Translated label text per locale. |
| `endpoint_registry` | Registered API endpoints. |
| `layout_slots` | Layout slot definitions. |
| `layout_panels` | Panel placement in layout slots. |
| `project_plans` | New project planning records. |

## What Does NOT Live in the Database
- Governance templates (Markdown files in `docs/governance-templates/`).
- Architecture decisions beyond ADR table entries.
- Scope definitions, coding standards, or file access policies.

## Schema Change Policy
- Schema changes require explicit approval and must be backward compatible.
- Prefer adding new columns with defaults over altering existing ones.
- Document all schema changes in `DECISIONS.md`.
