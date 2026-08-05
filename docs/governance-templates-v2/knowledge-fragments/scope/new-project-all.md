# Scope Profile: New Project (All Files)

> **Fragment ID:** new-project-all
> **Target section:** `<scope>`
> **Trigger:** `scope_profile` = new-project-all

## Allowed Files

All files within the new project directory:

- `{project_root}/app.py` — Backend entry point (CREATE)
- `{project_root}/config.py` — Central configuration (CREATE)
- `{project_root}/dpmtf.ini` — App-config defaults (CREATE)
- `{project_root}/.env` — Secrets and infrastructure (CREATE)
- `{project_root}/requirements.txt` — Python dependencies (CREATE)
- `{project_root}/scripts/init_db.py` — Database initialization (CREATE)
- `{project_root}/templates/index.html` — Main HTML template (CREATE)
- `{project_root}/static/js/app.js` — Frontend JavaScript (CREATE)
- `{project_root}/static/css/theme.css` — Dark theme CSS (CREATE)
- `{project_root}/docs/dpmtf/10_PROJECT.md` — Project identity (CREATE)
- `{project_root}/docs/dpmtf/11_SCOPE.md` — Phase scope (CREATE)
- `{project_root}/databases/{project}.db` — SQLite database (CREATE via init_db.py)

## Forbidden Files

- the Father project checkout — READ-ONLY reference
- the Father's `config.py` and `dpmtf.ini` — DO NOT MODIFY
- `$DPMTF_BRIDGE_DIR/` — Bridge infrastructure (DO NOT MODIFY)
- every other Child project checkout (DO NOT MODIFY)
- every reference project checkout (DO NOT MODIFY)

## Notes

This profile is for creating a NEW project from scratch. All files within the
new project root are allowed. Existing projects (Father, other Children,
bridge infrastructure) are strictly read-only. Structural governance files
(12-24, 99, 100) are referenced from Father's docs/governance-templates-v2/,
not duplicated in child projects.
