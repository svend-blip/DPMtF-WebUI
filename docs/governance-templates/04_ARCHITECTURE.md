# Architecture

## High-Level Overview
[Describe the architecture in 3-5 sentences.]

## Components
| Component | Purpose | Technology |
|-----------|---------|------------|
| Backend API | REST endpoints, database access. | FastAPI + SQLite |
| Frontend | Single-page UI. | Vanilla JS + HTML + CSS |
| Database | Persistent runtime state. | SQLite |
| Governance Engine | Markdown-driven project standards. | File-based |

## Data Flow
1. Frontend calls backend API endpoints.
2. Backend reads/writes to SQLite database.
3. Governance files are read at role-handoff time, not at runtime.
4. Prompt sequences drive step-by-step implementation.

## Key Directories
- `app.py` — FastAPI application entry point.
- `templates/` — HTML templates.
- `static/js/` — Frontend JavaScript.
- `static/css/` — Stylesheets.
- `databases/` — SQLite database files.
- `docs/` — Documentation and governance templates.
