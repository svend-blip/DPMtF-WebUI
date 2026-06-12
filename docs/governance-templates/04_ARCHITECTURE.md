# Architecture

## Purpose

This governance document describes the target project's architecture, its components, data flow, and directory structure. It provides context for all roles — especially Solution Architect and Implementer — so that changes align with the existing design instead of introducing uncoordinated drift.

## When to Use

- **Solution Architect step**: Reference this file before designing new components or data flows.
- **Implementer step**: Read to understand where code belongs and how it connects to other components.
- **After `/clear`**: Reconstruct the project structure without exploring the filesystem blindly.

---

## Current State — v3 Skeleton

As of phase 3C-3, AI PC Resource WebUI v3 is an initial skeleton with no functional panels, no database schema, and no implemented features beyond a basic FastAPI entry point.

### Current Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `app.py` | FastAPI application entry point — minimal skeleton. | FastAPI |
| `config.py` | Configuration module — minimal skeleton. | Python |
| `templates/index.html` | Base HTML template — placeholder shell. | Jinja2 / HTML |
| `static/css/app.css` | Stylesheet — minimal base styles. | CSS |
| `static/js/app.js` | Frontend JavaScript — placeholder script. | Vanilla JS |
| `.venv` | Python virtual environment for uvicorn. | Python venv |
| `databases/` | Database directory with `.gitkeep`. Empty — no schema yet. | — |
| `scripts/actions/` | Action script directory. Empty in v3. | — |

### Current Directory Structure

```
ai-pc-resource-webui-v3/
  app.py              # FastAPI skeleton
  config.py           # Configuration skeleton
  templates/
    index.html        # Base template placeholder
  static/
    css/
      app.css         # Minimal styles
    js/
      app.js          # Placeholder script
  databases/
    .gitkeep          # No database schema yet
  docs/
    dpmtf/            # Governance documents (this directory)
  scripts/
    actions/          # Empty in v3
  tests/
    .gitkeep
  .venv/              # Python virtual environment
  requirements.txt
  README.md
```

### Current Characteristics

- Runs on **port 9123**.
- Served via `.venv/bin/uvicorn app:app`.
- **No database schema** — the `databases/` directory exists but contains only `.gitkeep`.
- **No real panels** — `index.html` is a placeholder shell.
- **No API endpoints** beyond basic health check in the skeleton.
- Clean slate — no legacy code from v2.

---

## Planned Architecture — Intended v3 Direction

The following describes the **future target architecture** for AI PC Resource WebUI v3. None of these components are implemented yet as of phase 3C-3. Schema creation belongs to phase 3C-4 and later.

### Intended Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| Backend API | REST endpoints for database access, service cards, Ollama integration, and UI configuration. | FastAPI + SQLite |
| Frontend | Single-page UI with panel rendering, layout management, and i18n label display — data-driven from the database. | Vanilla JS + HTML + CSS |
| Database | Persistent runtime state: labels, endpoints, roles, service cards, pipelines, actions, Ollama state, audit log. | SQLite |
| Governance Engine | DPMtF governance documents govern development process. File-based (Markdown). | Markdown in `docs/dpmtf/` |

### Planned Database Table Groups

1. **UI Text Slots / i18n** — Four-layer text architecture: `ui_text_slots` → `ui_text_slot_labels` → `ui_labels` → `ui_label_translations`. Database-driven UI labels so frontend text is fully configurable without code changes.
2. **Endpoint Registry** — Registered API endpoints with metadata (method, path, description, permission requirements).
3. **Roles / Permissions / Users** — Role-based access control model for authenticating and authorizing users.
4. **Service Cards** — Service card definitions with configuration, status tracking, and Ollama integration points.
5. **Pipeline Registry** — Pipeline definitions for orchestrating multi-step service operations.
6. **Service Actions** — Action definitions bound to service cards or pipelines.
7. **Ollama Model Defaults / State per Card** — Persistent Ollama model selection and state tracking per service card.
8. **Audit / Action Log** — Audit trail of all system actions for traceability.

### Planned Data Flow

1. Frontend calls backend API endpoints for data and configuration.
2. Backend reads/writes to SQLite database for all runtime state (labels, endpoints, panels, permissions, service cards).
3. UI text is fully database-driven: frontend slot IDs → label bindings → labels → locale translations.
4. Governance files are read at role-handoff time by the active role (Analyst, Architect, etc.), not by the running application.

### Key Architectural Differences from v2

- **Database-first UI**: All UI text driven from database tables, not hardcoded in HTML.
- **No v2 migration**: v3 is built from scratch; no legacy panels or code to migrate.
- **Clean separation**: Endpoint registry, permission model, and service action registries designed in from the start, not retrofitted.
- **Ollama state persistence**: Model defaults and runtime state tracked per service card in the database.

---

## Architecture Change Rules

- New components must be added to the component table above.
- Data flow changes must be documented in the data flow section.
- New directories must be added to the directory structure.
- Architecture changes require Solution Architect design + Human Approval Gate sign-off before implementation.
- Distinguish clearly between **current skeleton** and **planned architecture** — do not conflate what exists with what is planned.

---
