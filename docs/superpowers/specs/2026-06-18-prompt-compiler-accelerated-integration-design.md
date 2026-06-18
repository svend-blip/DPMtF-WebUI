# Prompt Compiler — Accelerated WebUI Factory Integration

> **Status:** Approved design, awaiting implementation plan
> **Date:** 2026-06-18
> **Scope:** Frontend (dpmtf-app.js) + Backend (app.py) + Database seed (init_db.py)

## 1. Purpose

Integrate the Accelerated WebUI Factory (`initialize_new_webui.py`) into the
Prompt Compiler UI under the Daily panel. When Deployment Strategy "accelerated"
is selected, the standard prompt-compilation form is replaced with a dedicated
"Create New WebUI" flow that runs the factory script and starts the new server.

## 2. Frontend Changes (`static/js/dpmtf-app.js`)

### 2.1 Field Reorder in `buildCompilerForm()`

New field order (top to bottom):

| # | Field | Visibility |
|---|-------|------------|
| 1 | Deployment Strategy | Always visible |
| 2 | Target Session | Hidden when accelerated |
| 3 | Target Project | Always visible; auto-set to DPMtF-WebUI path when accelerated |
| 4 | Phase Key | Hidden when accelerated |
| 5 | Goal | Hidden when accelerated |
| 6 | **New webui** (name) | Only when accelerated |
| 6 | **Port** | Only when accelerated |
| 6 | **Title** | Only when accelerated |
| 7 | Scope & Gate checkbox | Hidden when accelerated |
| 8 | Allowed files | Hidden when accelerated |
| 9 | Forbidden files | Hidden when accelerated |

Buttons:
- **Compile Prompt** — visible only when deployment strategy ≠ "accelerated"
- **Create New WebUI** — visible only when deployment strategy = "accelerated"
- **Start WebUI Server** — replaces Create New WebUI after successful initialize

### 2.2 Conditional Visibility Logic

`onchange` handler on Deployment Strategy `<select>`:

- **"accelerated" selected:**
  - Hide: Target Session, Phase Key, Goal, Scope Gate, Allowed files, Forbidden files, Compile Prompt button
  - Show: New webui, Port, Title fields, Create New WebUI button
  - Auto-set Target Project to Father project path (read-only display)
  - Reset hidden fields to default/empty values

- **"standard" or "" selected:**
  - Show all standard fields + Compile Prompt button
  - Hide accelerated fields + Create New WebUI / Start Server buttons
  - Reset accelerated fields to empty values

### 2.3 New Accelerated Fields

| Field | Type | Constraints |
|-------|------|-------------|
| New webui | `<input type="text">` | `maxlength="10"` (visual hint only; script validates) |
| Port | `<input type="number">` | `min="9132" max="9199"` |
| Title | `<input type="text">` | Required |

### 2.4 New Functions

- `createNewWebUI()` — validates all 3 accelerated fields are non-empty, calls
  `POST /api/create-webui/initialize`, displays output/errors in `compile-output` div.
  On success, replaces button with "Start WebUI Server".

- `startWebUIServer(projectDir, port)` — calls `POST /api/create-webui/start`,
  displays clickable link to new WebUI, shows governance reminder.

### 2.5 Output Display

Reuses existing `#compile-output` div. Content:
- Script stdout (success case) — monospace preformatted
- Script stderr (error case) — red styling (`dpmtf-error`)
- Clickable link: `<a href="http://localhost:{port}/" target="_blank">Open WebUI</a>`
- Governance reminder text (from i18n labels)

## 3. Backend Changes (`app.py`)

### 3.1 `POST /api/create-webui/initialize`

**Request body:**
```json
{ "name": "webuitest003", "port": 9133, "title": "Test3" }
```

**Handler logic:**
1. Validate all 3 fields present and non-empty → 400 if missing
2. Validate port in range 9132–9199 → 400 if invalid
3. Run: `python3 scripts/initialize_new_webui.py --name <name> --port <port> --title "<title>"`
   via `subprocess.run(capture_output=True, text=True, cwd=config.get_project_root())`
4. Return response based on `returncode`

**Success response (200):**
```json
{
  "success": true,
  "output": "<full stdout from script>",
  "project_dir": "/home/svend/<name>",
  "port": 9133
}
```

**Error response (400):**
```json
{
  "success": false,
  "error": "<stderr from script>"
}
```

### 3.2 `POST /api/create-webui/start`

**Request body:**
```json
{ "project_dir": "/home/svend/webuitest003", "port": 9133 }
```

**Handler logic:**
1. Verify `project_dir` exists on disk → 400 if not
2. Verify `.venv/bin/uvicorn` exists in project_dir → 400 if not
3. Start uvicorn as detached background process:
   `subprocess.Popen([uvicorn_path, "app:app", "--host", "0.0.0.0", "--port", str(port)], cwd=project_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)`
4. `start_new_session=True` ensures the process survives the web server restart

**Success response (200):**
```json
{
  "success": true,
  "url": "http://localhost:9133/",
  "message": "Server started on port 9133"
}
```

### 3.3 Security Constraints

- Port validated against `VALID_PORT_RANGE` (9132–9199) in both endpoints
- `project_dir` must exist before server start (prevents path traversal)
- `subprocess.run` with explicit `cwd` — no shell injection (args passed as list, not string)
- These endpoints are NOT gated behind authentication (matches existing DPMtF pattern)

## 4. Database Seed Data (`scripts/init_db.py`)

### 4.1 New UI Labels

All labels follow the 4-layer i18n architecture (ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations).

| slot_key | label_key | en-US default | da-DK translation |
|----------|-----------|---------------|-------------------|
| `lbl_compiler_new_webui_name` | `compiler_new_webui_name` | New webui | Nyt webui |
| `lbl_compiler_new_webui_port` | `compiler_new_webui_port` | Port | Port |
| `lbl_compiler_new_webui_title` | `compiler_new_webui_title` | Title | Titel |
| `lbl_compiler_create_webui_btn` | `compiler_create_webui_btn` | Create New WebUI | Opret nyt WebUI |
| `lbl_compiler_start_server_btn` | `compiler_start_server_btn` | Start WebUI Server | Start WebUI Server |
| `lbl_compiler_webui_created` | `compiler_webui_created` | WebUI project created successfully | WebUI projekt oprettet |
| `lbl_compiler_governance_reminder` | `compiler_governance_reminder` | Governance files to create in docs/dpmtf/: | Governance-filer der skal oprettes i docs/dpmtf/: |
| `lbl_compiler_open_webui` | `compiler_open_webui` | Open WebUI | Åbn WebUI |
| `lbl_compiler_script_error` | `compiler_script_error` | Script error | Script fejl |
| `lbl_compiler_field_required` | `compiler_field_required` | This field is required | Dette felt er påkrævet |

### 4.2 Existing Labels Reused

- `lbl_compiler_deployment_strategy` — already exists
- `lbl_compiler_target_project` — already exists
- `lbl_compiler_no_deployment` — already exists
- `lbl_compiler_project_placeholder` — already exists

## 5. Error Handling Matrix

| Scenario | Detection | Response |
|----------|-----------|----------|
| Missing accelerated fields | Frontend check before API call | Inline `dpmtf-field-error` on empty fields |
| Script validation fails (bad name, port in use, dir exists) | `returncode != 0` | Display stderr in output div with `dpmtf-error` styling |
| Port becomes occupied between init and start | Start endpoint fails | Error message, user can retry with different port |
| Network error (fetch fails) | `catch` in frontend | Generic error in output div |
| Uvicorn fails to start | `Popen` exception | Backend returns 500, frontend shows error |
| Script produces unexpected output | Always capture both stdout+stderr | Display both; user can diagnose |

## 6. Validation Checklist (Pre-Completion)

Per governance 13_VALIDATION.md:

| # | Check | Applies |
|---|-------|---------|
| 1 | `python3 -m py_compile app.py` | Yes |
| 2 | `node --check static/js/dpmtf-app.js` | Yes |
| 3 | `bash -n scripts/init_db.py` | Yes (seed data changes) |
| 4 | `git diff --stat` — only expected files | Yes |
| 5 | No new dependencies in requirements.txt | Yes |
| 6 | No schema changes (only seed data) | Verify |
| 7 | `grep -RIn "innerHTML" static/ templates/` — empty | Yes |
| 8 | All user-facing text uses `lbl()` | Yes |
| + | `grep -n '"/home/svend' app.py scripts/` — empty | Yes |
| + | `python3 scripts/init_db.py` — idempotent | Yes |
| + | `curl -s http://localhost:9130/api/health` — healthy | Yes |

## 7. Files Modified

| File | Change Type | Scope |
|------|-------------|-------|
| `static/js/dpmtf-app.js` | Modify `buildCompilerForm()`, add 2 functions | ~80 lines |
| `app.py` | Add 2 endpoints | ~60 lines |
| `scripts/init_db.py` | Add 10 label seed data entries | ~40 lines |

No new files. No new dependencies. No schema changes.
