# Spor C — Accelerated WebUI Factory Design

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Build an `initialize_new_webui.py` script and skeleton file set that enables
rapid creation of new DPMtF-governed WebUI projects. When the Prompt Compiler
generates a handoff with `deployment_strategy = "accelerated"` and
`is_new_child_project = true`, the implementer runs one script and has a
working WebUI skeleton in ~2 minutes.

---

## Architecture

### Two deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | `templates/new-webui-skeleton/` | 8 skeleton files with `{PLACEHOLDER}` tokens |
| 2 | `scripts/initialize_new_webui.py` | Script that copies skeletons, replaces placeholders, initializes venv + database, verifies health endpoint |

### Skeleton files

```
templates/new-webui-skeleton/
├── app.py                  # Minimal FastAPI — health, static mount, config import, panel-structure API
├── config.py               # Identical getter functions to DPMtF-WebUI (paths resolved from dpmtf.ini)
├── dpmtf.ini               # {PROJECT_ROOT}, {PORT}, {FATHER_PROJECT} placeholders
├── .env                    # DPMTF_BRIDGE_DIR + session names (template, NOT committed)
├── requirements.txt        # fastapi, uvicorn, python-dotenv
├── scripts/
│   └── init_db.py          # Standard DPMtF schema — all tables, seed labels in da-DK + en-US
├── templates/
│   └── index.html          # 5 panel groups with headers + toggles, EMPTY panel bodies
├── static/
│   ├── js/
│   │   └── app.js          # Core infrastructure: lbl(), panel visibility, expand/collapse, language switcher
│   └── css/
│       └── theme.css       # GitHub-dark palette, panel-group/panel-subgroup/collapsed classes
```

### Placeholder system

All skeleton files use `{PLACEHOLDER}` tokens that the init script replaces:

| Placeholder | Source | Example |
|-------------|--------|---------|
| `{PROJECT_NAME}` | `--name` argument | `my-project` |
| `{PROJECT_TITLE}` | `--title` argument | `My Project` |
| `{PROJECT_ROOT}` | Derived from `--name` | `/home/svend/my-project` |
| `{PORT}` | `--port` argument | `9132` |
| `{FATHER_PROJECT}` | Fixed | `DPMtF-WebUI` |
| `{DATABASE}` | Derived from `--name` | `my-project.db` |
| `{CSS_FILE}` | Derived from `--name` | `my-project-theme.css` |
| `{JS_FILE}` | Derived from `--name` | `my-project-app.js` |

---

## index.html — Skeleton Design

### Fixed structure, empty panels

The 5 panel groups are mandatory and fixed. Each group has a header with
`data-slot` i18n attribute and a toggle arrow. Panel bodies are **empty**
— implementer adds specific panels via follow-up prompts.

```html
<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="locale" content="" />
    <title data-slot="lbl_page_title">{PROJECT_TITLE}</title>
    <link rel="stylesheet" href="/static/css/{CSS_FILE}" />
</head>
<body>
    <main class="container">
        <div class="header-row">
            <h1 data-slot="lbl_heading_main">{PROJECT_TITLE}</h1>
            <div class="lang-selector">
                <label for="lang-dropdown" class="lang-label">Language</label>
                <select id="lang-dropdown"><!-- Populated dynamically --></select>
            </div>
        </div>

        <!-- Daily -->
        <section class="panel-group" id="pg-daily">
            <div class="panel-group-header" data-group="daily">
                <h2 data-slot="pg_daily">📋 Daily</h2>
                <span class="panel-group-toggle">▼</span>
            </div>
            <div class="panel-group-body">
                <!-- Panels added here by implementer -->
            </div>
        </section>

        <!-- Journals -->
        <section class="panel-group" id="pg-journals">
            <div class="panel-group-header" data-group="journals">
                <h2 data-slot="pg_journals">📓 Journals</h2>
                <span class="panel-group-toggle">▼</span>
            </div>
            <div class="panel-group-body">
                <!-- Panels added here by implementer -->
            </div>
        </section>

        <!-- Reports -->
        <section class="panel-group" id="pg-reports">
            <div class="panel-group-header" data-group="reports">
                <h2 data-slot="pg_reports">📊 Reports</h2>
                <span class="panel-group-toggle">▼</span>
            </div>
            <div class="panel-group-body">
                <!-- Panels added here by implementer -->
            </div>
        </section>

        <!-- Periodic -->
        <section class="panel-group" id="pg-periodic">
            <div class="panel-group-header" data-group="periodic">
                <h2 data-slot="pg_periodic">🔄 Periodic</h2>
                <span class="panel-group-toggle">▼</span>
            </div>
            <div class="panel-group-body">
                <!-- Panels added here by implementer -->
            </div>
        </section>

        <!-- Setup -->
        <section class="panel-group" id="pg-setup">
            <div class="panel-group-header" data-group="setup">
                <h2 data-slot="pg_setup">⚙️ Setup</h2>
                <span class="panel-group-toggle">▼</span>
            </div>
            <div class="panel-group-body">
                <!-- Panels added here by implementer -->
            </div>
        </section>
    </main>
    <script src="/static/js/{JS_FILE}"></script>
</body>
</html>
```

### Why empty panels?

Each new WebUI has its own domain logic. The skeleton provides the fixed
5-group structure so prompts can target specific groups precisely:
- "Add a status panel to the Daily group"
- "Create a chart panel in Reports"
- "Add a settings form to Setup"

The `data-slot` attributes and `id="pg-{group}"` naming give prompts
unambiguous anchors to reference.

---

## app.js — Core Infrastructure

The skeleton `app.js` includes ONLY the infrastructure that every WebUI
needs. No domain-specific panel loading functions.

### Included functions

| Function | Purpose |
|----------|---------|
| `lbl(key, fallback)` | i18n lookup — reads `data-slot` elements, fetches translations from `/api/ui-labels` |
| `el(tag, className, text)` | Safe DOM creation — no innerHTML |
| `escapeHtml(str)` | XSS prevention |
| `currentLocale` | Language state tracking |
| `switchLanguage(locale)` | Fetches translations, updates all `data-slot` elements, re-renders panels |
| `loadPanelStructure()` | Fetches `/api/panel-structure` for group visibility + collapse state |
| `buildPanelStructure()` | Renders 5 groups: visibility, collapse state, subgroups |
| `buildSubgroups(body, groupName, subgroups)` | Creates subgroup sections with collapse toggles, slot-based panel placement |
| `initPanelGroupToggles()` | Click handlers on group headers — toggles collapse, persists state |
| `init()` | Boot sequence: load labels → load panel structure → init toggles → load language dropdown |

### NOT included (added by implementer per project)

- Domain-specific panel loading (e.g. `loadCurrentProjects()`, `loadNightrun()`)
- Form handlers
- Project-specific API calls

---

## app.py — Minimal Backend

The skeleton `app.py` provides the minimum endpoints every WebUI needs:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check — returns `{"status":"ok","project":"{PROJECT_NAME}"}` |
| `GET /api/ui-labels` | i18n — returns labels for requested locale from database |
| `GET /api/available-languages` | Returns list of available locales |
| `GET /api/panel-structure` | Returns group visibility + collapse state + subgroups from database |
| `POST /api/panel-structure/subgroup-state` | Persists subgroup collapse state |
| Static mount | Serves `static/` directory |

---

## init_db.py — Standard Schema

Creates all tables from the DPMtF standard schema:

- `ui_text_slots`, `ui_text_slot_labels`, `ui_labels`, `ui_label_translations`
- `user_panel_groups`, `panel_subgroups`
- `prompt_compiler_fields`, `prompt_compiler_field_options`, `prompt_templates`
- `endpoint_registry`

Seeds essential labels in `da-DK` and `en-US`:
- Page title, main heading
- 5 panel group names (Daily, Journals, Reports, Periodic, Setup)
- Standard UI labels (Language, Loading, Error, etc.)

---

## initialize_new_webui.py — Script Flow

### Arguments

```
python3 /home/svend/DPMtF-WebUI/scripts/initialize_new_webui.py \
  --name my-project \
  --port 9132 \
  --title "My Project Title"
```

### Steps

1. **Validate inputs** — name: lowercase-hyphenated, port: 9132-9199 range, title: non-empty
2. **Check for conflicts** — port not in use, directory doesn't already exist
3. **Create directory structure** — `mkdir -p` all directories
4. **Copy skeleton files** — from `templates/new-webui-skeleton/` to target
5. **Replace placeholders** — `{PROJECT_NAME}`, `{PORT}`, `{TITLE}`, etc. in all copied files
6. **Rename files** — `{CSS_FILE}` → `my-project-theme.css`, `{JS_FILE}` → `my-project-app.js`
7. **Create venv** — `python3 -m venv .venv`
8. **Install dependencies** — `.venv/bin/pip install -r requirements.txt`
9. **Initialize database** — `.venv/bin/python3 scripts/init_db.py`
10. **Verify** — start app briefly, `curl /api/health`, stop app
11. **Print summary** — project path, port, health status, next steps

### Error handling

- Pre-flight checks before any disk writes (port conflict, directory exists)
- Each step has rollback on failure (remove created directory)
- All output to stdout — implementer sees progress

---

## Prompt Compiler Integration

### What already works (no changes needed)

- `deployment_strategy = "accelerated"` triggers the ACCELERATED STRATEGY note in `<context>` (app.py:2908-2913)
- `is_new_child_project = true` triggers the new-child context line (app.py:2922-2927)
- Both together load `patterns/create-new-webui.md` fragment into `<task>` (app.py:2865-2866)

### What needs updating

The knowledge fragment `patterns/create-new-webui.md` currently describes 11
manual steps. After Spor C, it should reference the init script:

```markdown
### Accelerated Path (deployment_strategy = accelerated)

1. Run the init script:
   python3 /home/svend/DPMtF-WebUI/scripts/initialize_new_webui.py \
     --name {project_name} --port {port} --title "{project_title}"

2. Verify:
   curl http://localhost:{port}/api/health  # Must return 200

3. Start the app persistently:
   .venv/bin/uvicorn app:app --host 0.0.0.0 --port {port} --reload &
```

The manual 11-step pattern remains in the fragment for `deployment_strategy = "standard"`.

### Backend reference fix

`app.py:2912` references `DPMtF-WebUI/templates/new-webui-skeleton/` — this
directory will now actually exist.

---

## Files to Create

| File | Type | Description |
|------|------|-------------|
| `templates/new-webui-skeleton/app.py` | New | Minimal FastAPI backend |
| `templates/new-webui-skeleton/config.py` | New | Config getters (copy of DPMtF-WebUI's) |
| `templates/new-webui-skeleton/dpmtf.ini` | New | Project config with placeholders |
| `templates/new-webui-skeleton/.env` | New | Secrets template |
| `templates/new-webui-skeleton/requirements.txt` | New | Python dependencies |
| `templates/new-webui-skeleton/scripts/init_db.py` | New | Standard schema + seed data |
| `templates/new-webui-skeleton/templates/index.html` | New | 5 empty panel groups |
| `templates/new-webui-skeleton/static/js/app.js` | New | Core frontend infrastructure |
| `templates/new-webui-skeleton/static/css/theme.css` | New | Dark theme |
| `scripts/initialize_new_webui.py` | New | Init script |

## Files to Modify

| File | Change |
|------|--------|
| `docs/governance-templates-v2/knowledge-fragments/patterns/create-new-webui.md` | Add accelerated path section |
| `app.py:2912` | Verify skeleton path reference (already correct, just verify) |

## Files NOT Touched

- `static/js/dpmtf-app.js` — DPMtF's own frontend
- `config.py` — no new getters needed
- `scripts/init_db.py` (DPMtF's) — unchanged
- `databases/dpmtf.db` — no schema changes

---

## Validation

After implementation, verify:

```bash
# 1. Init script runs end-to-end
python3 scripts/initialize_new_webui.py --name test-webui --port 9132 --title "Test WebUI"
# Must complete all 11 steps without errors

# 2. Health endpoint works
curl http://localhost:9132/api/health
# Must return {"status":"ok","project":"test-webui"}

# 3. Panel structure API works
curl http://localhost:9132/api/panel-structure
# Must return 5 groups with is_visible=true, state=expanded

# 4. UI loads
curl http://localhost:9132/
# Must return HTML with 5 panel groups

# 5. No hardcoded paths
grep -RIn '"/home/svend' /home/svend/test-webui/app.py /home/svend/test-webui/scripts/
# Must return NO results

# 6. Cleanup
rm -rf /home/svend/test-webui
```
