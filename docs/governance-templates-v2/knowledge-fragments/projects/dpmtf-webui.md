# DPMtF-WebUI — Project Knowledge Fragment

> **Fragment ID:** dpmtf-webui
> **Target section:** `<context>`
> **Trigger:** `target_project` = DPMtF-WebUI

## Project Identity

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem. It owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself).

- **Port:** 9130 (configurable via `config.get_port()`)
- **Repository:** the DPMtF-WebUI checkout (`config.get_project_root()`)
- **Runtime:** `.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130`

## Directory Structure

```
DPMtF-WebUI/
├── app.py                  # Backend entry point (FastAPI, ~4000 lines)
├── config.py               # Central configuration — single source of truth (Spor A)
├── dpmtf.ini               # App-config defaults (committed)
├── .env                    # Secrets + infrastructure vars (NEVER commit)
├── requirements.txt        # Python dependencies
├── scripts/
│   └── init_db.py          # Database initialization + seed data (~3300 lines)
├── templates/
│   └── index.html          # Main HTML template (SPA)
├── static/
│   ├── js/
│   │   └── dpmtf-app.js    # Frontend JavaScript (~5000 lines)
│   └── css/
│       └── theme.css       # Dark theme (GitHub-dark palette)
├── docs/
│   ├── governance-templates-v2/  # Authoritative governance (all projects reference this)
│   │   └── knowledge-fragments/  # Curated .md fragments for Prompt Compiler (Spor B)
│   └── superpowers/              # Design specs and implementation plans
└── databases/
    └── dpmtf.db            # SQLite database (runtime state)
```

## Key Conventions

- **Config:** All paths, ports, project names MUST come from `config.py` getters.
  Hardcoded `/home/svend/...` is an auto-fail (12_CODING_STANDARD.md).
- **i18n:** All user-facing text uses the 4-layer i18n architecture.
  Frontend: `lbl(slot_key, fallback)`. No hardcoded English strings.
- **Database:** Parameterized SQL only. `CREATE TABLE IF NOT EXISTS` /
  `INSERT OR IGNORE` for idempotent seed data.
- **Frontend:** No `innerHTML` for dynamic content. Use `createElement()` /
  `textContent` / `appendChild()`. Event delegation on containers.
- **Panels:** Database-driven via `user_panel_groups` and `panel_subgroups`.
  Panel groups: Daily, Journals, Reports, Periodic, Setup.

## Common Modification Points

| Task | Primary File(s) | Also Check |
|------|----------------|------------|
| Add API endpoint | app.py | init_db.py (endpoint_registry seed) |
| Modify frontend panel | static/js/dpmtf-app.js | templates/index.html |
| Add database table | scripts/init_db.py | app.py (new routes for the table) |
| Change styling | static/css/theme.css | — |
| Add i18n labels | scripts/init_db.py (seed data) | — |
| Update governance | docs/governance-templates-v2/ | — |
