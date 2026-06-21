# Prompt Compiler — Accelerated WebUI Factory Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Accelerated WebUI Factory into the Prompt Compiler UI — reorder form fields, add conditional visibility for accelerated deployment strategy, add "Create New WebUI" button with 2-step backend flow.

**Architecture:** Frontend modifies `buildCompilerForm()` in `dpmtf-app.js` to reorder fields and add `onchange`-baseret conditional visibility. Two new backend endpoints in `app.py` run `initialize_new_webui.py` and start uvicorn. Ten new i18n labels seeded in `init_db.py`.

**Tech Stack:** Vanilla JavaScript (frontend), Python/FastAPI (backend), SQLite (database seed)

## Global Constraints

- NO `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`
- ALL user-facing text MUST use `lbl(key, fallback)` — no hardcoded English strings in DOM
- Python: `python3 -m py_compile app.py` MUST pass before signaling completion
- Parameterized SQL only — `?` placeholders, never f-strings in SQL
- No hardcoded `/home/svend/...` paths — use `config.py` getters
- DO NOT COMMIT — leave all changes unstaged
- `const` by default, `let` only when reassignment needed, never `var`
- Class-based CSS selectors, no inline `style=""` for layout
- `dpmtf-hidden` class for hiding elements

---

### Task 1: Seed 10 nye i18n labels i `init_db.py`

**Files:**
- Modify: `scripts/init_db.py` — tilføj labels, translations, slots, slot-label bindings

**Interfaces:**
- Produces: 10 slot_keys tilgængelige via `/api/ui-labels?domain=template_manager`:
  `lbl_compiler_new_webui_name`, `lbl_compiler_new_webui_port`, `lbl_compiler_new_webui_title`,
  `lbl_compiler_create_webui_btn`, `lbl_compiler_start_server_btn`, `lbl_compiler_webui_created`,
  `lbl_compiler_governance_reminder`, `lbl_compiler_open_webui`, `lbl_compiler_script_error`,
  `lbl_compiler_field_required`

- [ ] **Step 1: Tilføj ui_labels entries**

Find slutningen af `ui_labels_data` listen (efter LBL-1000217 omkring linje 544). Indsæt før `]`:

```python
    # ── Accelerated WebUI Factory labels (2026-06-18) ──
    ("LBL-1000218", "lbl_compiler_new_webui_name", "template_manager", "New webui", "Accelerated: new webui name field"),
    ("LBL-1000219", "lbl_compiler_new_webui_port", "template_manager", "Port", "Accelerated: port number field"),
    ("LBL-1000220", "lbl_compiler_new_webui_title", "template_manager", "Title", "Accelerated: project title field"),
    ("LBL-1000221", "lbl_compiler_create_webui_btn", "template_manager", "Create New WebUI", "Accelerated: create button"),
    ("LBL-1000222", "lbl_compiler_start_server_btn", "template_manager", "Start WebUI Server", "Accelerated: start server button"),
    ("LBL-1000223", "lbl_compiler_webui_created", "template_manager", "WebUI project created successfully", "Accelerated: success message"),
    ("LBL-1000224", "lbl_compiler_governance_reminder", "template_manager", "Governance files to create in docs/dpmtf/:", "Accelerated: governance reminder"),
    ("LBL-1000225", "lbl_compiler_open_webui", "template_manager", "Open WebUI", "Accelerated: open webui link text"),
    ("LBL-1000226", "lbl_compiler_script_error", "template_manager", "Script error", "Accelerated: script error heading"),
    ("LBL-1000227", "lbl_compiler_field_required", "template_manager", "This field is required", "Accelerated: field required message"),
```

- [ ] **Step 2: Tilføj ui_label_translations entries (en-US + da-DK)**

Find slutningen af `ui_label_translations_data` listen. Indsæt før `]`:

```python
    # ── Accelerated WebUI Factory (en-US) ──
    ("LBL-1000218", "en-US", "New webui"),
    ("LBL-1000219", "en-US", "Port"),
    ("LBL-1000220", "en-US", "Title"),
    ("LBL-1000221", "en-US", "Create New WebUI"),
    ("LBL-1000222", "en-US", "Start WebUI Server"),
    ("LBL-1000223", "en-US", "WebUI project created successfully"),
    ("LBL-1000224", "en-US", "Governance files to create in docs/dpmtf/:"),
    ("LBL-1000225", "en-US", "Open WebUI"),
    ("LBL-1000226", "en-US", "Script error"),
    ("LBL-1000227", "en-US", "This field is required"),
    # ── Accelerated WebUI Factory (da-DK) ──
    ("LBL-1000218", "da-DK", "Nyt webui"),
    ("LBL-1000219", "da-DK", "Port"),
    ("LBL-1000220", "da-DK", "Titel"),
    ("LBL-1000221", "da-DK", "Opret nyt WebUI"),
    ("LBL-1000222", "da-DK", "Start WebUI Server"),
    ("LBL-1000223", "da-DK", "WebUI projekt oprettet"),
    ("LBL-1000224", "da-DK", "Governance-filer der skal oprettes i docs/dpmtf/:"),
    ("LBL-1000225", "da-DK", "Åbn WebUI"),
    ("LBL-1000226", "da-DK", "Script fejl"),
    ("LBL-1000227", "da-DK", "Dette felt er påkrævet"),
```

- [ ] **Step 3: Tilføj ui_text_slots entries**

Find slutningen af `ui_text_slots_data` listen. Indsæt før `]`:

```python
    # ── Accelerated WebUI Factory slots ──
    ("lbl_compiler_new_webui_name", "Accelerated: new webui name field"),
    ("lbl_compiler_new_webui_port", "Accelerated: port number field"),
    ("lbl_compiler_new_webui_title", "Accelerated: project title field"),
    ("lbl_compiler_create_webui_btn", "Accelerated: create button"),
    ("lbl_compiler_start_server_btn", "Accelerated: start server button"),
    ("lbl_compiler_webui_created", "Accelerated: success message"),
    ("lbl_compiler_governance_reminder", "Accelerated: governance reminder"),
    ("lbl_compiler_open_webui", "Accelerated: open webui link text"),
    ("lbl_compiler_script_error", "Accelerated: script error heading"),
    ("lbl_compiler_field_required", "Accelerated: field required message"),
```

- [ ] **Step 4: Tilføj ui_text_slot_labels bindings**

Find slutningen af `ui_text_slot_labels_data` listen. Indsæt før `]`:

```python
    # ── Accelerated WebUI Factory bindings ──
    ("lbl_compiler_new_webui_name", "lbl_compiler_new_webui_name"),
    ("lbl_compiler_new_webui_port", "lbl_compiler_new_webui_port"),
    ("lbl_compiler_new_webui_title", "lbl_compiler_new_webui_title"),
    ("lbl_compiler_create_webui_btn", "lbl_compiler_create_webui_btn"),
    ("lbl_compiler_start_server_btn", "lbl_compiler_start_server_btn"),
    ("lbl_compiler_webui_created", "lbl_compiler_webui_created"),
    ("lbl_compiler_governance_reminder", "lbl_compiler_governance_reminder"),
    ("lbl_compiler_open_webui", "lbl_compiler_open_webui"),
    ("lbl_compiler_script_error", "lbl_compiler_script_error"),
    ("lbl_compiler_field_required", "lbl_compiler_field_required"),
```

- [ ] **Step 5: Kør init_db.py for at verificere idempotent seed**

```bash
python3 scripts/init_db.py
```
Expected: Ingen fejl. Scriptet kører og afslutter uden fejl.

- [ ] **Step 6: Verificer labels i databasen**

```bash
sqlite3 databases/dpmtf.db "SELECT slot_key FROM ui_text_slots WHERE slot_key LIKE 'lbl_compiler_%' ORDER BY slot_key;"
```
Expected: 10 nye `lbl_compiler_*` slots vises.

---

### Task 2: Tilføj 2 backend endpoints i `app.py`

**Files:**
- Modify: `app.py` — tilføj to nye endpoints efter eksisterende Prompt Compiler endpoints (~linje 2822)

**Interfaces:**
- Consumes: `config.get_project_root()` (findes allerede)
- Produces:
  - `POST /api/create-webui/initialize` — accepterer `{ name, port, title }`, returnerer `{ success, output, project_dir, port }` eller `{ success: false, error }`
  - `POST /api/create-webui/start` — accepterer `{ project_dir, port }`, returnerer `{ success, url, message }`

- [ ] **Step 1: Tjek eksisterende imports**

```bash
grep -n "^import subprocess\|^from pathlib import Path" /home/svend/DPMtF-WebUI/app.py
```
Hvis `subprocess` mangler, tilføj efter eksisterende imports (~linje 1-30):
```python
import subprocess
```

Hvis `Path` mangler:
```python
from pathlib import Path
```

- [ ] **Step 2: Tilføj `POST /api/create-webui/initialize` endpoint**

Indsæt efter `assign_handoff_id` funktionen (efter linje ~2880, før næste endpoint):

```python
# ── Accelerated WebUI Factory: Initialize (2026-06-18) ────────


@app.post("/api/create-webui/initialize")
async def create_webui_initialize(request: Request):
    """Run initialize_new_webui.py to create a new WebUI project.

    Body (JSON):
      name  — project name (lowercase, hyphenated, max 10 chars recommended)
      port  — port number (9132-9199)
      title — project title (displayed in page title and heading)
    """
    data = await request.json()

    # Validate required fields
    for field in ["name", "port", "title"]:
        if field not in data or not str(data[field]).strip():
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    name = str(data["name"]).strip()
    port = int(data["port"])
    title = str(data["title"]).strip()

    # Validate port range
    if port < 9132 or port > 9199:
        raise HTTPException(status_code=400, detail=f"Port must be in range 9132-9199")

    # Run initialize_new_webui.py
    script_path = Path(config.get_project_root()) / "scripts" / "initialize_new_webui.py"
    result = subprocess.run(
        ["python3", str(script_path), "--name", name, "--port", str(port), "--title", title],
        capture_output=True, text=True,
        cwd=config.get_project_root(),
        timeout=120,
    )

    if result.returncode != 0:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": result.stderr or result.stdout or "Unknown error",
            },
        )

    project_dir = str(Path.home() / name)

    return {
        "success": True,
        "output": result.stdout,
        "project_dir": project_dir,
        "port": port,
    }
```

- [ ] **Step 3: Tilføj `POST /api/create-webui/start` endpoint**

Indsæt umiddelbart efter initialize endpointet:

```python
@app.post("/api/create-webui/start")
async def create_webui_start(request: Request):
    """Start uvicorn for a newly created WebUI project.

    Body (JSON):
      project_dir — absolute path to the project directory
      port        — port number the project was initialized with
    """
    data = await request.json()

    for field in ["project_dir", "port"]:
        if field not in data or not str(data[field]).strip():
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    project_dir = str(data["project_dir"]).strip()
    port = int(data["port"])

    # Verify project directory exists
    if not Path(project_dir).exists():
        raise HTTPException(status_code=400, detail=f"Project directory not found: {project_dir}")

    # Verify uvicorn exists
    uvicorn_path = Path(project_dir) / ".venv" / "bin" / "uvicorn"
    if not uvicorn_path.exists():
        raise HTTPException(status_code=400, detail=f"uvicorn not found at {uvicorn_path}")

    # Start uvicorn as detached background process
    subprocess.Popen(
        [str(uvicorn_path), "app:app", "--host", "0.0.0.0", "--port", str(port)],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    url = f"http://localhost:{port}/"

    return {
        "success": True,
        "url": url,
        "message": f"Server started on port {port}",
    }
```

- [ ] **Step 4: Verificer Python syntax**

```bash
python3 -m py_compile app.py
```
Expected: Ingen output (kompilering successfuld).

---

### Task 3: Frontend — omorganisér form, conditional visibility, nye funktioner

**Files:**
- Modify: `static/js/dpmtf-app.js` — `buildCompilerForm()` (linje 839-958), tilføj `createNewWebUI()` og `startWebUIServer()` funktioner

**Interfaces:**
- Consumes: `lbl()` (global), `el()` (global), `clear()` (global), `compile-output` div (i DOM)
- Produces: `createNewWebUI()`, `startWebUIServer(projectDir, port)` — kaldes fra button onclick handlers

- [ ] **Step 1: Erstat `buildCompilerForm()` med ny version**

Erstat hele funktionen (linje 839-958). Den nye version flytter Deployment Strategy til toppen, tilføjer onchange handler, tilføjer accelerated felter, og tilføjer Create New WebUI knap:

```javascript
function buildCompilerForm() {
  var container = document.getElementById("template-manager-content");
  if (!container) return;
  clear(container);

  // ── 1. Deployment Strategy (øverst — styrer visibility) ──
  var depDiv = el("div", "dpmtf-form-group");
  depDiv.id = "compile-group-deployment";
  depDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_deployment_strategy", "Deployment Strategy")));
  var depSelect = el("select", null);
  depSelect.id = "compile-deployment_strategy";
  var emptyOpt = document.createElement("option");
  emptyOpt.value = "";
  emptyOpt.textContent = lbl("lbl_compiler_no_deployment", "(none)");
  depSelect.appendChild(emptyOpt);
  ["standard", "accelerated"].forEach(function (val) {
    var opt = document.createElement("option");
    opt.value = val;
    opt.textContent = val;
    depSelect.appendChild(opt);
  });
  depDiv.appendChild(depSelect);
  container.appendChild(depDiv);

  // ── 2. Target Session (skjules ved accelerated) ──
  var sessionDiv = el("div", "dpmtf-form-group");
  sessionDiv.id = "compile-group-session";
  sessionDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_session", "Target Session")));
  var sessionSelect = el("select", null);
  sessionSelect.id = "compile-target_session";
  [
    ["claude_implementer", lbl("lbl_session_implementer", "Implementer")],
    ["claude_review", lbl("lbl_session_review", "Review")],
    ["claude_architect", lbl("lbl_session_architect", "Architect")]
  ].forEach(function (pair) {
    var opt = document.createElement("option");
    opt.value = pair[0];
    opt.textContent = pair[1];
    sessionSelect.appendChild(opt);
  });
  sessionDiv.appendChild(sessionSelect);
  container.appendChild(sessionDiv);

  // ── 3. Target Project (auto-sættes ved accelerated) ──
  var projDiv = el("div", "dpmtf-form-group");
  projDiv.id = "compile-group-project";
  projDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_project", "Target Project")));
  var projInput = el("input", null);
  projInput.type = "text";
  projInput.id = "compile-target_project";
  projInput.placeholder = lbl("lbl_compiler_project_placeholder", "/home/svend/DPMtF-WebUI");
  projDiv.appendChild(projInput);
  container.appendChild(projDiv);

  // ── 4. Phase Key (skjules ved accelerated) ──
  var phaseDiv = el("div", "dpmtf-form-group");
  phaseDiv.id = "compile-group-phase";
  phaseDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_phase_key", "Phase Key")));
  var phaseInput = el("input", null);
  phaseInput.type = "text";
  phaseInput.id = "compile-phase_key";
  phaseInput.placeholder = lbl("lbl_compiler_phase_placeholder", "spor-g-test");
  phaseDiv.appendChild(phaseInput);
  container.appendChild(phaseDiv);

  // ── 5. Goal (skjules ved accelerated) ──
  var goalDiv = el("div", "dpmtf-form-group");
  goalDiv.id = "compile-group-goal";
  goalDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_goal", "Goal")));
  var goalTextarea = el("textarea", null);
  goalTextarea.id = "compile-goal";
  goalTextarea.rows = 4;
  goalTextarea.placeholder = lbl("lbl_compiler_goal_placeholder", "Describe the implementation task...");
  goalDiv.appendChild(goalTextarea);
  container.appendChild(goalDiv);

  // ── 6. Accelerated felter (KUN synlige ved accelerated) ──
  // New webui name
  var nameDiv = el("div", "dpmtf-form-group");
  nameDiv.id = "compile-group-accel-name";
  nameDiv.style.display = "none";
  nameDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_new_webui_name", "New webui")));
  var nameInput = el("input", null);
  nameInput.type = "text";
  nameInput.id = "compile-accel-name";
  nameInput.maxLength = 10;
  nameInput.placeholder = "mywebui";
  nameDiv.appendChild(nameInput);
  container.appendChild(nameDiv);

  // Port
  var portDiv = el("div", "dpmtf-form-group");
  portDiv.id = "compile-group-accel-port";
  portDiv.style.display = "none";
  portDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_new_webui_port", "Port")));
  var portInput = el("input", null);
  portInput.type = "number";
  portInput.id = "compile-accel-port";
  portInput.min = 9132;
  portInput.max = 9199;
  portInput.placeholder = "9136";
  portDiv.appendChild(portInput);
  container.appendChild(portDiv);

  // Title
  var titleDiv = el("div", "dpmtf-form-group");
  titleDiv.id = "compile-group-accel-title";
  titleDiv.style.display = "none";
  titleDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_new_webui_title", "Title")));
  var titleInput = el("input", null);
  titleInput.type = "text";
  titleInput.id = "compile-accel-title";
  titleInput.placeholder = "My Project";
  titleDiv.appendChild(titleInput);
  container.appendChild(titleDiv);

  // ── 7. Scope & Gate confirmation (skjules ved accelerated) ──
  var scopeDiv = el("div", "dpmtf-form-group");
  scopeDiv.id = "compile-group-scope";
  var scopeLabel = el("label", "dpmtf-label", null);
  var scopeCheckbox = el("input", null);
  scopeCheckbox.type = "checkbox";
  scopeCheckbox.id = "compile-scope_gate_confirmed";
  scopeLabel.appendChild(scopeCheckbox);
  scopeLabel.appendChild(document.createTextNode(lbl("lbl_compiler_scope_gate", " Have you considered scope and gate scope?")));
  scopeDiv.appendChild(scopeLabel);
  container.appendChild(scopeDiv);

  // ── 8. Allowed files (skjules ved accelerated) ──
  var allowedDiv = el("div", "dpmtf-form-group");
  allowedDiv.id = "compile-group-allowed";
  allowedDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_allowed_files", "Allowed files (optional, one per line)")));
  var allowedTextarea = el("textarea", null);
  allowedTextarea.id = "compile-allowed_files";
  allowedTextarea.rows = 3;
  allowedTextarea.placeholder = lbl("lbl_compiler_allowed_placeholder", "(blank = Review verifies)");
  allowedDiv.appendChild(allowedTextarea);
  container.appendChild(allowedDiv);

  // ── 9. Forbidden files (skjules ved accelerated) ──
  var forbiddenDiv = el("div", "dpmtf-form-group");
  forbiddenDiv.id = "compile-group-forbidden";
  forbiddenDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_forbidden_files", "Forbidden files (optional, one per line)")));
  var forbiddenTextarea = el("textarea", null);
  forbiddenTextarea.id = "compile-forbidden_files";
  forbiddenTextarea.rows = 3;
  forbiddenTextarea.placeholder = lbl("lbl_compiler_forbidden_placeholder", "(blank = none specified)");
  forbiddenDiv.appendChild(forbiddenTextarea);
  container.appendChild(forbiddenDiv);

  // ── Output area (genbruges til både compile og accelerated) ──
  var outputDiv = el("div", null);
  outputDiv.id = "compile-output";
  outputDiv.style.display = "none";
  container.appendChild(outputDiv);

  // ── Warning area ──
  var warningDiv = el("div", null);
  warningDiv.id = "compile-warning";
  warningDiv.style.display = "none";
  container.appendChild(warningDiv);

  // ── Compile Prompt button (skjules ved accelerated) ──
  var compileBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  compileBtn.id = "compile-btn-submit";
  compileBtn.textContent = lbl("lbl_tpl_compile_prompt", "Compile Prompt");
  compileBtn.onclick = compilePromptV2;
  container.appendChild(compileBtn);

  // ── Create New WebUI button (KUN synlig ved accelerated) ──
  var createBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  createBtn.id = "compile-btn-create-webui";
  createBtn.style.display = "none";
  createBtn.textContent = lbl("lbl_compiler_create_webui_btn", "Create New WebUI");
  createBtn.onclick = createNewWebUI;
  container.appendChild(createBtn);

  // ── Start WebUI Server button (erstatter Create efter success) ──
  var startBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  startBtn.id = "compile-btn-start-server";
  startBtn.style.display = "none";
  startBtn.textContent = lbl("lbl_compiler_start_server_btn", "Start WebUI Server");
  container.appendChild(startBtn);

  // ── Deployment Strategy onchange handler ──
  depSelect.onchange = function () {
    var isAccelerated = depSelect.value === "accelerated";

    // Standard felter: skjul ved accelerated
    var standardIds = [
      "compile-group-session", "compile-group-phase", "compile-group-goal",
      "compile-group-scope", "compile-group-allowed", "compile-group-forbidden"
    ];
    standardIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = isAccelerated ? "none" : "";
    });

    // Accelerated felter: vis kun ved accelerated
    var accelIds = [
      "compile-group-accel-name", "compile-group-accel-port", "compile-group-accel-title"
    ];
    accelIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = isAccelerated ? "" : "none";
    });

    // Knapper
    var compileBtnEl = document.getElementById("compile-btn-submit");
    var createBtnEl = document.getElementById("compile-btn-create-webui");
    var startBtnEl = document.getElementById("compile-btn-start-server");
    if (compileBtnEl) compileBtnEl.style.display = isAccelerated ? "none" : "";
    if (createBtnEl) createBtnEl.style.display = isAccelerated ? "" : "none";
    if (startBtnEl) startBtnEl.style.display = "none"; // altid skjul ved skift

    // Target Project: auto-sæt til Father project ved accelerated
    var projEl = document.getElementById("compile-target_project");
    if (isAccelerated && projEl) {
      projEl.value = "/home/svend/DPMtF-WebUI";
      projEl.readOnly = true;
    } else if (projEl) {
      projEl.readOnly = false;
    }

    // Nulstil skjulte felter
    if (isAccelerated) {
      // Nulstil standard felter
      var sessionEl = document.getElementById("compile-target_session");
      if (sessionEl) sessionEl.value = "claude_implementer";
      var phaseEl = document.getElementById("compile-phase_key");
      if (phaseEl) phaseEl.value = "";
      var goalEl = document.getElementById("compile-goal");
      if (goalEl) goalEl.value = "";
      var scopeEl = document.getElementById("compile-scope_gate_confirmed");
      if (scopeEl) scopeEl.checked = false;
      var allowedEl = document.getElementById("compile-allowed_files");
      if (allowedEl) allowedEl.value = "";
      var forbiddenEl = document.getElementById("compile-forbidden_files");
      if (forbiddenEl) forbiddenEl.value = "";
    } else {
      // Nulstil accelerated felter
      var nameEl = document.getElementById("compile-accel-name");
      if (nameEl) nameEl.value = "";
      var portEl = document.getElementById("compile-accel-port");
      if (portEl) portEl.value = "";
      var titleEl = document.getElementById("compile-accel-title");
      if (titleEl) titleEl.value = "";
    }

    // Skjul output/warning ved skift
    var outEl = document.getElementById("compile-output");
    if (outEl) { outEl.style.display = "none"; clear(outEl); }
    var warnEl = document.getElementById("compile-warning");
    if (warnEl) { warnEl.style.display = "none"; clear(warnEl); }
  };
}
```

- [ ] **Step 2: Tilføj `createNewWebUI()` funktion**

Indsæt efter `buildCompilerForm()` (før `compilePromptV2`):

```javascript
function createNewWebUI() {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  outputDiv.style.display = "block";
  clear(outputDiv);

  // Clear previous error highlights
  document.querySelectorAll(".dpmtf-field-error").forEach(function (errEl) {
    errEl.style.borderColor = "";
    errEl.classList.remove("dpmtf-field-error");
  });
  document.querySelectorAll(".dpmtf-error-text").forEach(function (msgEl) {
    msgEl.remove();
  });

  // Validate all 3 accelerated fields are filled
  var nameEl = document.getElementById("compile-accel-name");
  var portEl = document.getElementById("compile-accel-port");
  var titleEl = document.getElementById("compile-accel-title");

  var errors = [];
  [nameEl, portEl, titleEl].forEach(function (el) {
    if (!el || !el.value || el.value.trim() === "") {
      if (el) {
        el.style.borderColor = "#f85149";
        el.classList.add("dpmtf-field-error");
        var msg = document.createElement("span");
        msg.className = "dpmtf-error-text";
        msg.textContent = lbl("lbl_compiler_field_required", "This field is required");
        el.parentNode.appendChild(msg);
      }
      errors.push(true);
    }
  });

  if (errors.length > 0) {
    outputDiv.appendChild(
      el("p", "dpmtf-error", lbl("lbl_compiler_field_required", "Please fill in all required fields."))
    );
    return;
  }

  outputDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_compiling", "Creating WebUI project..."))
  );

  var body = {
    name: nameEl.value.trim(),
    port: parseInt(portEl.value, 10),
    title: titleEl.value.trim(),
  };

  fetch("/api/create-webui/initialize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
    .then(function (resp) { return resp.json().then(function (data) { return { status: resp.status, data: data }; }); })
    .then(function (result) {
      clear(outputDiv);
      outputDiv.style.display = "block";

      if (!result.data.success) {
        var errHeading = el("h4", "dpmtf-error", lbl("lbl_compiler_script_error", "Script error"));
        outputDiv.appendChild(errHeading);
        var errPre = el("pre", "dpmtf-error");
        errPre.textContent = result.data.error || "Unknown error";
        outputDiv.appendChild(errPre);
        return;
      }

      // Success — vis output
      var successHeading = el("h4", null);
      successHeading.textContent = lbl("lbl_compiler_webui_created", "WebUI project created successfully");
      outputDiv.appendChild(successHeading);

      var outPre = el("pre", null);
      outPre.textContent = result.data.output;
      outputDiv.appendChild(outPre);

      // Skjul Create button, vis Start Server button
      var createBtn = document.getElementById("compile-btn-create-webui");
      var startBtn = document.getElementById("compile-btn-start-server");
      if (createBtn) createBtn.style.display = "none";
      if (startBtn) {
        startBtn.style.display = "";
        startBtn.onclick = function () {
          startWebUIServer(result.data.project_dir, result.data.port);
        };
      }
    })
    .catch(function (err) {
      clear(outputDiv);
      outputDiv.style.display = "block";
      outputDiv.appendChild(
        el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + err.message)
      );
    });
}
```

- [ ] **Step 3: Tilføj `startWebUIServer()` funktion**

Indsæt efter `createNewWebUI()`:

```javascript
function startWebUIServer(projectDir, port) {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  clear(outputDiv);
  outputDiv.style.display = "block";

  outputDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_compiling", "Starting server..."))
  );

  fetch("/api/create-webui/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_dir: projectDir, port: port }),
  })
    .then(function (resp) { return resp.json().then(function (data) { return { status: resp.status, data: data }; }); })
    .then(function (result) {
      clear(outputDiv);
      outputDiv.style.display = "block";

      if (!result.data.success) {
        outputDiv.appendChild(
          el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + (result.data.detail || "Failed to start server"))
        );
        return;
      }

      // Vis klikbart link
      var linkP = el("p", null);
      var linkLabel = document.createTextNode(lbl("lbl_compiler_open_webui", "Open WebUI") + ": ");
      linkP.appendChild(linkLabel);
      var link = el("a", null);
      link.href = result.data.url;
      link.target = "_blank";
      link.textContent = result.data.url;
      linkP.appendChild(link);
      outputDiv.appendChild(linkP);

      // Vis governance reminder
      var govHeading = el("p", "dpmtf-muted");
      govHeading.textContent = lbl("lbl_compiler_governance_reminder", "Governance files to create in docs/dpmtf/:");
      outputDiv.appendChild(govHeading);
      var govList = el("ul", null);
      var item1 = el("li", null);
      item1.textContent = "10_PROJECT.md (project identity)";
      govList.appendChild(item1);
      var item2 = el("li", null);
      item2.textContent = "11_SCOPE.md (current phase scope)";
      govList.appendChild(item2);
      outputDiv.appendChild(govList);

      // Skjul Start Server button
      var startBtn = document.getElementById("compile-btn-start-server");
      if (startBtn) startBtn.style.display = "none";
    })
    .catch(function (err) {
      clear(outputDiv);
      outputDiv.style.display = "block";
      outputDiv.appendChild(
        el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + err.message)
      );
    });
}
```

- [ ] **Step 4: Verificer JavaScript syntax**

```bash
node --check static/js/dpmtf-app.js
```
Expected: Ingen output (syntax OK).

- [ ] **Step 5: Verificer ingen innerHTML i ændringer**

```bash
grep -n "innerHTML" static/js/dpmtf-app.js
```
Expected: Ingen matches (eller kun i kommentarer).

---

### Task 4: Validering — kør alle governance checks

- [ ] **Step 1: Backend syntax**

```bash
python3 -m py_compile app.py
```
Expected: Ingen output.

- [ ] **Step 2: Frontend syntax**

```bash
node --check static/js/dpmtf-app.js
```
Expected: Ingen output.

- [ ] **Step 3: Diff scope**

```bash
git diff --stat
```
Expected: Kun `app.py`, `static/js/dpmtf-app.js`, `scripts/init_db.py`.

- [ ] **Step 4: Dependencies**

```bash
git diff requirements.txt
```
Expected: Ingen ændringer.

- [ ] **Step 5: Schema changes**

```bash
git diff scripts/init_db.py | grep -E "CREATE TABLE|ALTER TABLE"
```
Expected: Ingen matches.

- [ ] **Step 6: innerHTML check**

```bash
grep -RIn "innerHTML" static/ templates/
```
Expected: Ingen matches.

- [ ] **Step 7: i18n check**

```bash
grep -n "lbl(" static/js/dpmtf-app.js | grep -v "^\s*//"
```
Expected: Alle nye user-facing strings bruger `lbl()` — verificer manuelt.

- [ ] **Step 8: Hardcoded paths check**

```bash
grep -n '"/home/svend' app.py
```
Expected: Ingen matches.

- [ ] **Step 9: Database seed idempotent**

```bash
python3 scripts/init_db.py
```
Expected: Kører uden fejl.

- [ ] **Step 10: Health endpoint**

```bash
curl -s http://localhost:9130/api/health
```
Expected: `{"status": "healthy"}`

---

### Task 5: Manuel browser-test

- [ ] **Step 1: Åbn DPMtF WebUI** → `http://localhost:9130/`

- [ ] **Step 2: Vælg "accelerated" i Deployment Strategy**
  - Verificer: standard felter skjules, accelerated felter vises, Compile knap skjules, Create New WebUI vises, Target Project auto-sættes og er read-only

- [ ] **Step 3: Klik "Create New WebUI" uden at udfylde felter**
  - Verificer: røde fejl-markeringer + fejlbesked

- [ ] **Step 4: Udfyld felter og klik "Create New WebUI"**
  - Brug: name=`testwui`, port=`9136`, title=`Test WebUI`
  - Verificer: script output vises, Create knap erstattes af Start Server knap

- [ ] **Step 5: Klik "Start WebUI Server"**
  - Verificer: klikbart link + governance reminder vises

- [ ] **Step 6: Klik link og verificer ny WebUI loader**

- [ ] **Step 7: Skift tilbage til "standard"**
  - Verificer: standard felter vises, accelerated skjules, felter nulstilles

- [ ] **Step 8: Ryd op**
  ```bash
  kill $(lsof -t -i:9136) 2>/dev/null; rm -rf /home/svend/testwui
  ```

