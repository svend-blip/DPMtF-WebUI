# New WebUI — Project Knowledge Fragment

> **Fragment ID:** new-webui
> **Target section:** `<context>`
> **Trigger:** `target_project` is a new/child project (not DPMtF-WebUI)

## Standard WebUI Structure

All WebUIs built under DPMtF governance follow the same architecture as
DPMtF-WebUI (the Father project). A new WebUI is a **Child project**.

## Required Components

Every DPMtF-governed WebUI MUST have:

```
{project_name}/
├── app.py                  # FastAPI backend (minimal at start)
├── config.py               # Central configuration (copy from DPMtF-WebUI template)
├── dpmtf.ini               # App-config with project-specific paths/port
├── .env                    # Secrets (NEVER commit)
├── requirements.txt        # Python dependencies
├── scripts/
│   └── init_db.py          # Database initialization
├── templates/
│   └── index.html          # SPA with panel group structure
├── static/
│   ├── js/
│   │   └── app.js          # Frontend with panel system
│   └── css/
│       └── theme.css       # Dark theme (GitHub-dark palette)
├── docs/
│   └── dpmtf/              # Project-specific governance (11_SCOPE, 10_PROJECT, etc.)
└── databases/
    └── {project}.db        # SQLite database
```

## Panel Group Structure (Mandatory)

The index.html MUST implement these panel groups:

| Group | Purpose | Example Panels |
|-------|---------|---------------|
| **Daily** | Time-sensitive information | Status cards, today's metrics |
| **Journals** | Logs and records | Activity logs, audit trails |
| **Reports** | Analysis and summaries | Charts, aggregated views |
| **Periodic** | Scheduled/recurring items | Cron jobs, recurring tasks |
| **Setup** | Configuration and administration | Settings, management panels |

Panel groups are fixed. Subgroups are optional and database-driven via
`panel_subgroups` table. If no subgroups defined: implicit "All" subgroup.

## Database-Driven Architecture

- Panel visibility: `user_panel_groups.is_visible`, `panel_subgroups.is_visible`
- i18n: 4-layer architecture (ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations)
- Prompt Compiler: `prompt_compiler_fields` + `prompt_templates`
- All runtime state in database, not hardcoded

## Governance Reference

All projects reference DPMtF-WebUI's authoritative governance:
In the Father's governance directory (`config.get_governance_dir_abs()`):

- `12_CODING_STANDARD.md`
- `16_FILE_ACCESS.md`
- `14_ARCHITECTURE.md`

Project-specific files (10_PROJECT, 11_SCOPE) live in the project's own
`docs/dpmtf/` directory. After Spor D centralization, this directory contains
ONLY these project-specific files. All structural governance comes from Father.

## Port Assignment

- DPMtF-WebUI: 9130 (Father)
- ENO: 9131 (first Child)
- New projects: assign next available port (9132, 9133, ...)
