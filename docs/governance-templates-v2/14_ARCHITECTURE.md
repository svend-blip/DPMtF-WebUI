# 14 — ARCHITECTURE

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the high-level system architecture, component structure, data flow,
and directory layout. This is the technical reference for the Architect role
when designing solutions and for the Implementor role when understanding the
system context.

## When to Use

- **Architect:** Design technical solutions within the existing architecture.
- **Implementor:** Understand component relationships before modifying code.
- **Review:** Check that changes respect architectural boundaries.

---

## Project Component Overview

{Describe the main components: backend framework, frontend framework, database,
directory structure, key modules. Adapt per project.}

## Directory Structure

```
{PROJECT_NAME}/
├── app.py                  # Backend entry point (FastAPI/Flask)
├── config.py               # Configuration
├── scripts/
│   └── init_db.py          # Database initialization and seed data
├── templates/
│   └── index.html          # Main HTML template
├── static/
│   ├── js/
│   │   └── main.js         # Frontend JavaScript
│   └── css/
│       └── theme.css       # CSS theme
├── docs/
│   ├── governance-templates-v2/  # Active governance (Father project)
│   └── dpmtf/                   # Project-specific files only (10_PROJECT.md, 11_SCOPE.md)

After Spor D (Governance Centralization): Child projects' docs/dpmtf/ contains
ONLY project-specific files (10_PROJECT.md, 11_SCOPE.md). All structural
governance files (12-24, 99, 100) are referenced from the Father project's
docs/governance-templates-v2/ (config.get_governance_dir_abs()).
└── databases/
    └── {project}.db         # SQLite database
```

## 4-Layer i18n Architecture

```
┌─────────────────────────────────────────────┐
│ Layer 1: ui_text_slots                      │
│ slot_key = unique position ID               │
│ Purpose: Stable reference for frontend      │
├─────────────────────────────────────────────┤
│ Layer 2: ui_text_slot_labels                │
│ slot_key → label_key mapping                │
│ Purpose: Many slots can share one label     │
├─────────────────────────────────────────────┤
│ Layer 3: ui_labels                          │
│ label_key → default_text                    │
│ Purpose: Semantic label definition          │
├─────────────────────────────────────────────┤
│ Layer 4: ui_label_translations              │
│ label_key + locale → translated_text        │
│ Purpose: Locale-specific text               │
└─────────────────────────────────────────────┘
```

**API contract:** `GET /api/ui-labels?domain={domain}` MUST return
`{slot_key: translated_text}` by traversing all 4 layers.

## Panel Group Architecture

```
Panel Groups (fixed)
├── Daily        — Time-sensitive information
├── Journals     — Logs and records
├── Reports      — Analysis and summaries
├── Periodic     — Scheduled/recurring items
│   └── Subgroups (optional, database-driven)
│       ├── All (implicit, if no subgroups defined)
│       ├── {Subgroup A}
│       └── {Subgroup B}
└── Setup        — Configuration and administration
```

- Panel groups are fixed: Daily, Journals, Reports, Periodic, Setup.
- Subgroups are optional and database-driven via `panel_subgroups` table.
- If no subgroups defined for a group: implicit "All" subgroup, flat display.
- Visibility controlled by `is_visible` in `user_panel_groups` and `panel_subgroups`.

## Database Architecture

{Describe the database schema: main tables, governance tables, relationship
between runtime state and governance templates.}

### Runtime State vs Governance Files

| Lives In | What |
|----------|------|
| **Database** | UI text slots, bindings, labels, translations, user preferences, panel visibility, session state, prompt templates, prompt runs, workflow runs |
| **Governance files** | Project identity, scope, coding standards, validation rules, architecture docs, decisions, changelog |
| **Git** | All code, all governance files, migration scripts |

## Component Communication

BridgeV002 is database-driven — session names, models, and step sequences are
configured per flow in `bridge_roles` and `bridge_flow_steps`. The diagram
below shows the `strict_review` flow as an example.

```
Human (01_HUMAN)
    ↓ scope definition
Architect (402_STRICT_REVIEW_ARCHI01) → archi01 tmux session
    ↓ signal_send via dispatch.py
Implementer (403_STRICT_REVIEW_IMPLE01) → imple01 tmux session
    ↓ signal_complete via dispatch.py
Review01 (404_STRICT_REVIEW_REVIEW01) → review01 tmux session
    ↓ signal_complete via dispatch.py
Review02 (405_STRICT_REVIEW_REVIEW02) → review02 tmux session
    ↓ signal_complete (human_delivery — no tmux injection)
Human (01_HUMAN)
    ↓ commit authorization
git commit + git push
```

## Related Reference Files

| File | Content |
|------|---------|
| [[12_CODING_STANDARD]] | 4-layer i18n mandatory standard. |
| [[17_DATABASE]] | Database schema and runtime state. |
| [[100_BRIDGE]] | Bridge infrastructure and tmux sessions. |

---
