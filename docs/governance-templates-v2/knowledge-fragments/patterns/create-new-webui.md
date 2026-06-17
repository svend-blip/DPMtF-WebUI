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

### Accelerated Path (deployment_strategy = "accelerated")

When the Prompt Compiler generates a handoff with `deployment_strategy = "accelerated"`
and `is_new_child_project = true`, the implementer uses the init script instead of
following the manual 11-step pattern below.

1. **Run the init script:**
   ```bash
   python3 /home/svend/DPMtF-WebUI/scripts/initialize_new_webui.py \
     --name {project_name} \
     --port {port} \
     --title "{project_title}"
   ```
   This creates the complete project skeleton in ~2 minutes:
   - Directory structure with all subdirectories
   - Minimal app.py with health, i18n, panel-structure endpoints
   - config.py with all standard getter functions
   - dpmtf.ini with project-specific paths and port
   - .env with DPMTF_BRIDGE_DIR and session names
   - requirements.txt with fastapi, uvicorn, python-dotenv
   - scripts/init_db.py with 6 essential tables + seed labels
   - templates/index.html with 5 empty panel groups
   - static/js/app.js with lbl(), panel structure, expand/collapse
   - static/css/theme.css with GitHub-dark palette
   - .venv with installed dependencies
   - Initialized database with seed labels in da-DK, en-US, de-DE, sv-SE

2. **Verify:**
   ```bash
   curl http://localhost:{port}/api/health  # Must return {"status":"healthy"}
   curl http://localhost:{port}/  # Must return HTML with 5 panel groups
   ```

3. **Start the app persistently:**
   ```bash
   cd /home/svend/{project_name}
   .venv/bin/uvicorn app:app --host 0.0.0.0 --port {port} --reload &
   ```

4. **Create governance files:**
   - `docs/dpmtf/10_PROJECT.md` — project identity, port, repository
   - `docs/dpmtf/11_SCOPE.md` — current phase scope

The project is now ready for domain-specific panels and endpoints
via follow-up prompts targeting specific panel groups.

---

### Standard Path (deployment_strategy = "standard")

The manual 11-step pattern below is used when `deployment_strategy = "standard"`.

#### Prerequisites

- **Project name:** Short, lowercase, hyphenated (e.g., `my-project`).
- **Port:** Next available port. DPMtF=9130, ENO=9131. Check for conflicts.
- **Database name:** Usually `{project_key}.db` (e.g., `my-project.db`).

#### Step Pattern

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

#### Governance Files for the New Project

Create these project-specific files in `docs/dpmtf/`:
- `10_PROJECT.md` — project identity, port, repository
- `11_SCOPE.md` — current phase scope

This directory contains ONLY project-specific files (10_PROJECT.md, 11_SCOPE.md).
All structural governance rules (coding standards, validation, architecture,
file access) are defined in the Father project at docs/governance-templates-v2/.

The new project references DPMtF-WebUI for all other governance:
- `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md`
- `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/14_ARCHITECTURE.md`
- `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md`

#### Verification Commands

```bash
python3 -m py_compile app.py
python3 scripts/init_db.py                    # Must run without errors
.venv/bin/uvicorn app:app --host 0.0.0.0 --port {port} &
sleep 2
curl -s http://localhost:{port}/api/health     # Must return 200
grep -RIn '"/home/svend' app.py scripts/      # Must return NO results
```
