# Architecture

## Purpose

This governance document describes the target project's architecture, its components, data flow, and directory structure. It provides context for all roles — especially Solution Architect and Implementer — so that changes align with the existing design instead of introducing uncoordinated drift.

## When to Use

- **Solution Architect step**: Reference this file before designing new components or data flows.
- **Implementer step**: Read to understand where code belongs and how it connects to other components.
- **After `/clear`**: Reconstruct the project structure without exploring the filesystem blindly.

## Required Inputs

| Input | Description |
|-------|-------------|
| Current architecture state | This document, updated for each phase. |
| Proposed changes | From Solution Architect design or Prompt Engineer prompts. |

## Required Outputs

- Architecture description stays current with the implemented state.
- New components added to the component table after implementation.
- Data flow updated if the change introduces new endpoints or data paths.

---

## High-Level Overview

DPMtF WebUI is a governance-first orchestration engine for local AI-driven project development. The backend (FastAPI + SQLite) provides API endpoints for runtime state management. The frontend (vanilla JS + HTML + CSS) renders panels driven by the endpoint registry. Governance documents (Markdown files in `docs/`) control process, roles, scope, and standards — they are read during role handoffs, not at application runtime.

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| Backend API | REST endpoints for database access, prompt sequencing, phase tracking, and UI configuration. | FastAPI + SQLite |
| Frontend | Single-page UI with panel rendering, layout management, and i18n label display. | Vanilla JS + HTML + CSS |
| Database | Persistent runtime state: panels, prompts, phases, labels, endpoints, projects. | SQLite |
| Governance Engine | Markdown-driven project standards read during role-based prompt loop transitions. | File-based (Markdown) |
| Prompt System | Sequence generation, prompt archiving, and execution tracking. | Python backend + Markdown templates |

## Data Flow

1. Frontend calls backend API endpoints for data and configuration.
2. Backend reads/writes to SQLite database for runtime state.
3. Governance files are read at role-handoff time by the active role (Analyst, Architect, etc.), not by the running application.
4. Prompt sequences drive step-by-step implementation: Prompt Engineer generates → Implementer executes → Validator verifies.
5. After verification, Release Operator commits and optionally syncs to remote git.

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `app.py` | FastAPI application entry point. Restricted write. |
| `templates/` | HTML templates for Jinja2 rendering. Free write within scope. |
| `static/js/` | Frontend JavaScript logic. Free write within scope. |
| `static/css/` | Stylesheets. Free write within scope. |
| `databases/` | SQLite database files. Read-only — modify via backend, not directly. |
| `docs/` | Documentation and governance templates. Governed by file access policy. |
| `docs/governance-templates/` | Governance documents controlling the role-based prompt loop. |
| `docs/prompt-runs/` | Prompt-run history with reports and metadata per run. |

## UI Text Slot / i18n Architecture

DPMtF WebUI uses a four-layer text architecture so that frontend rendering, reusable labels, and locale translations are cleanly separated. This prevents hardcoded label IDs in frontend code and allows all text changes and re-bindings to be managed through the database without touching `index.html` or frontend JavaScript.

### Layer Diagram

```
Frontend (HTML/JS)
      │ references stable slot ID
      ▼
┌─────────────────┐
│  ui_text_slots   │  Layer 1 — stable, globally unique text placement IDs
│                  │  Represents WHERE text appears in the UI:
│  Examples:       │    page title, panel heading, button label, tooltip,
│    slot_id:      │    warning message, status text.
│    "panel_3a_heading"
│    type:         │  Frontend references ONLY this layer for text display.
│    "heading"     │
└────────┬────────┘
         │ bound via ui_text_slot_labels (Layer 2)
         ▼
┌─────────────────┐
│ ui_text_slot_labels │ Layer 2 — UI Text Binding table
│                    │  Binds ui_text_slots → ui_labels.
│  Purpose:          │  Many slots may bind to the same label (reuse).
│    - 1:N slot→label │  Changing a binding in the database does NOT
│    - N:1 reuse      │  require editing index.html or frontend JS.
└────────┬────────┘
         │ references label ID
         ▼
┌─────────────────┐
│   ui_labels      │  Layer 3 — Reusable UI Label registry
│                  │  Semantic text concepts that can be shared across
│  Examples:       │  multiple frontend positions.
│    "Start"       │  Labels do NOT control layout, endpoints,
│    "Stop"        │  permissions, actions, or visibility.
│    "Next Planned Phases"     │  Those are separate registries.
│    "Validation failed"       │
└────────┬────────┘
         │ translated per BCP 47 locale tag
         ▼
┌─────────────────┐
│ ui_label_translations │ Layer 4 — Locale-specific text
│                       │  Uses BCP 47 locale tags: da-DK, en-US, en-GB.
│  Examples:            │  One label may have many translations.
│    "Start" → da-DK:   │
│      "Start"          │
│    "Start" → en-US:   │
│      "Start"          │
└─────────────────────┘
```

### Separation Rules

1. **Frontend references stable UI text slot IDs/keys**, never reusable label IDs directly.
2. **Reusable labels are not hardcoded as frontend placement identifiers.** They exist at a higher abstraction than individual UI positions.
3. **Text changes and label re-binding happen in the database** — no edits to `index.html` or frontend JavaScript are required to change displayed text.
4. **Labels do not control layout, endpoints, permissions, actions, or visibility.** Layout registry, endpoint registry, permission registry, and action registry are separate concerns with their own tables.
5. **Migration is one panel at a time** — when the slot/binding layer is implemented later, migrate panels individually, not all at once.
6. **Missing labels must not break frontend rendering** — frontend must have safe fallback behavior (e.g., display the slot key itself or a generic placeholder) when a label or translation is missing.

### Terminology Summary

| Term | Meaning |
|------|---------|
| **UI Text Slot** | A stable, globally unique text placement in the frontend. Represents *where* text appears. Table: `ui_text_slots`. |
| **UI Text Binding** | The relationship between a text slot and a reusable label. Table: `ui_text_slot_labels`. |
| **Reusable UI Label** | A semantic text concept that may be shared across multiple slots. Table: `ui_labels`. |
| **BCP 47 locale tag** | Locale identifier for translations (e.g., `da-DK`, `en-US`, `en-GB`). Used in `ui_label_translations`. |

## Architecture Change Rules

- New components must be added to the component table above.
- Data flow changes must be documented in the data flow section.
- New directories must be added to the key directories table.
- Architecture changes require Solution Architect design + Human Approval Gate sign-off before implementation.

---
