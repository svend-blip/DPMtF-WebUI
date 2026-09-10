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

## Model Allocator, Harness Allocator, and Configuration Locus

A role's execution is resolved through three cooperating layers, each with one
non-overlapping responsibility. DPMtF references **aliases and role keys only**;
the allocators resolve them.

| Layer | Owns | Config lives in | Edited via |
|-------|------|-----------------|------------|
| **BridgeV002** (DPMtF) | Which role runs which step and in what order; the role's binding to a model alias and a harness | `bridge_roles`, `bridge_flow_steps` (dpmtf.db) | The WebUI frontend (Default Model Source/Alias, Harness) |
| **Model Allocator** | Resolving a model alias → runtime profile → real model + endpoint; starting/stopping/validating model runtimes | Committed config in the model-allocator repo (`models.yaml`, `runtime_profiles.yaml`, `roles.yaml`) | The model-allocator web UI |
| **Harness Allocator** | Resolving how the coding interface is launched for ANY interface (the LaunchSpec/StopSpec: which harness, permissions, terminal-wrapped vs one-shot) | The harness-allocator's own committed config | Its own surface |

`start_coding.py` builds a role's launch line by asking the Model Allocator to
resolve the role's endpoint + model and the Harness Allocator to resolve the
interface — neither value is hand-set on the role.

### The configuration-locus rule (mandatory)

Every value a role depends on at runtime — which model, which endpoint, which
harness, which permissions — **MUST be database-driven so it survives the next
chain start, and MUST be visible and editable in the frontend.** It must never
live only where a person cannot see and change it from the UI:

- **Not** `.env` as the home for a routable value. A remote endpoint's URL is
  committed config — a runtime profile's `default_api_base`, like every cloud
  profile — so it resolves at every start with nothing to set by hand. Do
  **not** point `default_api_base` at a placeholder and defer the real value to
  an `api_base_env` that reads `.env`.
- **Never** a runtime hack: a `tmux setenv`, an exported shell variable, a
  hand-edited file the frontend does not surface. If a fresh boot with an empty
  shell environment would break the chain, the config is in the wrong place.
- The role → model/harness binding is `bridge_roles` (dpmtf.db), shown and
  edited in the frontend. When you move a role to a new model, change it in
  **both** `bridge_roles` AND the allocator's committed config — or the two
  layers drift (the chain runs one model while the frontend shows another).

**The one exception — secrets.** API keys are deliberately never in the DB,
never in committed config, never literal on the command line. They live in
`.env` and reach the pane through the environment, referenced by the launch as
`${KEY_ENV:?...}`. A node with **no** auth carries **no** `api_key_env` at all,
so the launch emits no key guard and depends on no environment variable.

> **Why this rule exists (2026-09-10).** A role's remote endpoint was placed in
> `.env` and injected with a manual `tmux setenv -g`. It ran — until a
> tmux-server restart would have silently stranded it, and it was invisible and
> uneditable in the frontend. (New tmux sessions inherit the tmux *server's*
> environment, fixed at server start, so neither `.env` nor a uvicorn restart
> reached the pane.) The fix was to move the endpoint into committed allocator
> config (`default_api_base`) and the role→alias into `bridge_roles`. Config a
> person cannot see and change in the frontend, or that a fresh boot loses, is a
> defect — not a workaround.

## Related Reference Files

| File | Content |
|------|---------|
| [[12_CODING_STANDARD]] | 4-layer i18n mandatory standard. |
| [[17_DATABASE]] | Database schema and runtime state. |
| [[100_BRIDGE]] | Bridge infrastructure and tmux sessions. |
| [[22_MODEL_SELECTION]] | Role-to-model mapping and the two-layer binding. |

---
