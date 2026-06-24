# Scope Profile: app.py Only

> **Fragment ID:** app.py-only
> **Target section:** `<scope>`
> **Trigger:** `scope_profile` = app.py-only

## Allowed Files

- `{project_root}/app.py`

## Forbidden Files

- `{project_root}/config.py` — Central configuration, requires Human approval
- `{project_root}/dpmtf.ini` — App-config defaults
- `{project_root}/.env` — Secrets, NEVER modify programmatically
- `{project_root}/scripts/init_db.py` — Database initialization and seed data
- `{project_root}/templates/index.html` — Main HTML template
- `{project_root}/static/` — All frontend assets (JS, CSS)
- `{project_root}/docs/` — All documentation and governance
- `/home/svend/flows/` — Bridge infrastructure
- `/home/svend/ENO/` — Other Child project
- `/home/svend/ai-pc-resource-webui-v3/` — Reference project

## Notes

This profile is for backend-only changes that do not touch the database schema
or seed data. If the task requires init_db.py changes (new endpoint registration,
schema changes, seed data), use a broader scope profile.
