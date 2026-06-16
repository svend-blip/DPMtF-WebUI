# Pattern: Create New WebUI Project

> **Fragment ID:** create-new-webui
> **Target section:** `<task>`
> **Trigger:** `task_type` = create_new_webui

## Standard Pattern for Creating a New DPMtF-Governed WebUI

### Overview

Creating a new WebUI under DPMtF governance means establishing a Child project
that follows the same architecture as DPMtF-WebUI (the Father project). The
new project will be database-driven, use the 4-layer i18n architecture, and
reference DPMtF's authoritative governance templates.

### Prerequisites

- **Project name:** Short, lowercase, hyphenated (e.g., `my-project`).
- **Port:** Next available port. DPMtF=9130, ENO=9131. Check for conflicts.
- **Database name:** Usually `{project_key}.db` (e.g., `my-project.db`).

### Step Pattern

1. **Create project directory structure.**
   ```bash
   mkdir -p /home/svend/{project_name}/{templates,static/js,static/css,scripts,databases,docs/dpmtf}
   ```

2. **Create minimal app.py.**
   Start with a FastAPI skeleton: health endpoint, static mount, config imports.
   Use `config.py` getters for all paths. No hardcoded `/home/svend/...`.

3. **Create config.py.**
   Copy the pattern from DPMtF-WebUI's config.py. The getter functions are
   identical — only `dpmtf.ini` values differ between projects.

4. **Create dpmtf.ini.**
   Set `project_root`, `bridge_dir`, `port` to the new project's values.
   Set `father_project = DPMtF-WebUI`.

5. **Create .env.**
   Set `DPMTF_BRIDGE_DIR` and session names. Add project-specific secrets.
   NEVER commit .env.

6. **Create requirements.txt.**
   ```ini
   fastapi
   uvicorn
   python-dotenv
   ```

7. **Create scripts/init_db.py.**
   Initialize the database with the standard DPMtF schema:
   - `ui_text_slots`, `ui_text_slot_labels`, `ui_labels`, `ui_label_translations`
   - `user_panel_groups`, `panel_subgroups`
   - `prompt_compiler_fields`, `prompt_templates`
   - `endpoint_registry`
   Seed essential labels in `da-DK` and `en-US` locales.

8. **Create templates/index.html.**
   Implement the 5 panel groups: Daily, Journals, Reports, Periodic, Setup.
   Use `data-slot` attributes for i18n. No hardcoded English strings.

9. **Create static/js/app.js.**
   Implement the panel system: `lbl()` helper, event delegation, panel visibility
   from database. No `innerHTML` for dynamic content.

10. **Create static/css/theme.css.**
    Dark theme using GitHub-dark palette. Class-based selectors, no inline styles.

11. **Initialize and start.**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 scripts/init_db.py
    .venv/bin/uvicorn app:app --host 0.0.0.0 --port {port} &
    ```

### Governance Files for the New Project

Create these project-specific files in `docs/dpmtf/`:
- `10_PROJECT.md` — project identity, port, repository
- `11_SCOPE.md` — current phase scope

The new project references DPMtF-WebUI for all other governance:
- `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md`
- `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/14_ARCHITECTURE.md`
- `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md`

### Verification Commands

```bash
python3 -m py_compile app.py
python3 scripts/init_db.py                    # Must run without errors
.venv/bin/uvicorn app:app --host 0.0.0.0 --port {port} &
sleep 2
curl -s http://localhost:{port}/api/health     # Must return 200
grep -RIn '"/home/svend' app.py scripts/      # Must return NO results
```
