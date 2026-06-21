# BridgeV002 Hardening — Fase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full CRUD API for bridge_flow_steps and frontend "Manage Steps" panel with dropdowns and auto-fill from conventions.

**Architecture:** 4 new endpoints in app.py (GET list, POST create, PUT update, DELETE soft-delete), ~7 new i18n labels in init_db.py, HTML section in index.html, ~10 JavaScript functions in dpmtf-app.js. Auto-fill logic resolves convention rules at form time.

**Tech Stack:** Python 3, SQLite, FastAPI, vanilla JS (createElement, no innerHTML).

## Global Constraints

- en-US only for all code, comments, docstrings — CLAUDE.md §2
- PEP 8, parameterized SQL only — CLAUDE.md §4
- NO `innerHTML` for dynamic content — use createElement/textContent/appendChild/replaceChildren — CLAUDE.md §4
- ALL user-facing text MUST use `lbl(key, fallback)` — no hardcoded English strings in DOM — CLAUDE.md §4
- `const` by default, `let` only when reassignment needed. Never `var`. — CLAUDE.md §4
- Dark theme (GitHub-dark palette) — CLAUDE.md §4
- `python3 -m py_compile <file>` and `node --check <file>` MUST pass before signaling completion

---

### Task 1: Steps CRUD API endpoints in app.py

**Files:**
- Modify: `app.py` — add 4 endpoints after the conventions endpoint (~line 4074)

**Interfaces:**
- Consumes: DB_PATH (module-level), bridge_lib functions via lazy import, sqlite3 parameterized SQL
- Produces: GET `/api/bridge-v2/steps/{flow_key}`, POST `/api/bridge-v2/steps/{flow_key}`, PUT `/api/bridge-v2/steps/{flow_key}/{step_id}`, DELETE `/api/bridge-v2/steps/{flow_key}/{step_id}`

- [ ] **Step 1: Read insertion point in app.py**

Read the conventions endpoint (added Fase 3, around line 4065-4075) and the Spor J CRUD section that follows. Insert new endpoints between them.

- [ ] **Step 2: Add GET `/api/bridge-v2/steps/{flow_key}`**

Insert in app.py:

```python


@app.get("/api/bridge-v2/steps/{flow_key}")
async def bridge_v2_list_steps(flow_key: str):
    """Return all steps for a flow, with available roles/conventions/scripts for dropdowns."""
    try:
        from scripts.bridgeV002.bridge_lib import list_flows_from_db, list_roles_from_db, list_scripts_from_db, list_conventions_from_db

        # Verify flow exists
        flows = list_flows_from_db(DB_PATH)
        flow_keys = [f["flow_key"] for f in flows]
        if flow_key not in flow_keys:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get steps for this flow
        steps_rows = cursor.execute(
            "SELECT * FROM bridge_flow_steps WHERE flow_key = ? ORDER BY sort_order ASC",
            (flow_key,)
        ).fetchall()
        steps = [dict(r) for r in steps_rows]

        # Get available data for frontend dropdowns
        roles_data = list_roles_from_db(DB_PATH)
        role_keys = [r["role_key"] for r in roles_data]
        conventions_data = list_conventions_from_db(DB_PATH)
        scripts_data = list_scripts_from_db(DB_PATH)

        conn.close()
        return {
            "steps": steps,
            "count": len(steps),
            "flow_key": flow_key,
            "available_roles": role_keys,
            "available_conventions": conventions_data,
            "available_scripts": scripts_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge steps: {e}")
```

- [ ] **Step 3: Add POST `/api/bridge-v2/steps/{flow_key}`**

Add after the GET endpoint:

```python


@app.post("/api/bridge-v2/steps/{flow_key}")
async def bridge_v2_create_step(flow_key: str):
    """Create a new step for the given flow."""
    from scripts.bridgeV002.bridge_lib import resolve_convention_from_db, list_flows_from_db

    data = await request.json()
    required = ["step_key", "from_role", "to_role"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    # Verify flow exists
    flows = list_flows_from_db(DB_PATH)
    if flow_key not in [fl["flow_key"] for fl in flows]:
        raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check for duplicate step_key within same flow
    cursor.execute(
        "SELECT id FROM bridge_flow_steps WHERE flow_key = ? AND step_key = ? AND is_active = 1",
        (flow_key, data["step_key"])
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"Step '{data['step_key']}' already exists in flow '{flow_key}'")

    # Auto-fill from convention rule if rule_key is provided
    deliverable_dir = data.get("deliverable_dir", None)
    deliverable_pattern = data.get("deliverable_pattern", None)
    error_msg = data.get("error_msg", None)
    rule_key = data.get("rule_key", None)

    if rule_key:
        convention = resolve_convention_from_db(rule_key, DB_PATH)
        if convention and "rule_key" in convention:
            deliverable_dir = convention.get("dir_template", deliverable_dir)
            deliverable_pattern = convention.get("pattern_template", deliverable_pattern)
            error_msg = convention.get("error_template", error_msg)

    # Get max sort_order for this flow
    result = cursor.execute(
        "SELECT MAX(sort_order) as max_so FROM bridge_flow_steps WHERE flow_key = ?",
        (flow_key,)
    ).fetchone()
    max_so = result["max_so"] if result["max_so"] is not None else 0

    cursor.execute("""
        INSERT INTO bridge_flow_steps
            (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern,
             pre_dispatch_script, post_dispatch_script, error_msg, rule_key, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        flow_key, data["step_key"], data["from_role"], data["to_role"],
        deliverable_dir, deliverable_pattern,
        data.get("pre_dispatch_script"), data.get("post_dispatch_script"),
        error_msg, rule_key, max_so + 1,
    ))
    new_id = cursor.lastrowid
    conn.commit()

    # Return created step
    row = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ?", (new_id,)
    ).fetchone()
    conn.close()
    return {"step": dict(row), "created": True}
```

- [ ] **Step 4: Add PUT `/api/bridge-v2/steps/{flow_key}/{step_id}`**

Add after POST endpoint:

```python


@app.put("/api/bridge-v2/steps/{flow_key}/{step_id}")
async def bridge_v2_update_step(flow_key: str, step_id: int):
    """Update a step. Supports partial updates — only provided fields are changed."""
    from scripts.bridgeV002.bridge_lib import resolve_convention_from_db

    data = await request.json()
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verify step exists
    row = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ? AND flow_key = ?",
        (step_id, flow_key)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in flow '{flow_key}'")

    # Build dynamic update — only change fields that were provided
    existing = dict(row)
    updates = []
    params = []

    field_map = {
        "from_role": "from_role",
        "to_role": "to_role",
        "deliverable_dir": "deliverable_dir",
        "deliverable_pattern": "deliverable_pattern",
        "pre_dispatch_script": "pre_dispatch_script",
        "post_dispatch_script": "post_dispatch_script",
        "error_msg": "error_msg",
        "sort_order": "sort_order",
    }

    for field, column in field_map.items():
        if field in data:
            updates.append(f"{column} = ?")
            params.append(data[field])

    # Handle rule_key with optional auto-fill
    if "rule_key" in data and data["rule_key"] != existing.get("rule_key"):
        rule_key_val = data["rule_key"]
        convention = resolve_convention_from_db(rule_key_val, DB_PATH) if rule_key_val else None

        updates.append("rule_key = ?")
        params.append(rule_key_val)

        # Auto-fill from new convention if fields weren't explicitly provided
        if convention and "rule_key" in convention:
            if "deliverable_dir" not in data and convention.get("dir_template"):
                updates.append("deliverable_dir = ?")
                params.append(convention["dir_template"])
            if "deliverable_pattern" not in data and convention.get("pattern_template"):
                updates.append("deliverable_pattern = ?")
                params.append(convention["pattern_template"])
            if "error_msg" not in data and convention.get("error_template"):
                updates.append("error_msg = ?")
                params.append(convention["error_template"])

    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No valid fields to update")

    params.append(step_id)
    params.append(flow_key)
    cursor.execute(
        f"UPDATE bridge_flow_steps SET {', '.join(updates)} WHERE id = ? AND flow_key = ?",
        params,
    )
    conn.commit()

    updated = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ?", (step_id,)
    ).fetchone()
    conn.close()
    return {"step": dict(updated), "updated": True}
```

- [ ] **Step 5: Add DELETE `/api/bridge-v2/steps/{flow_key}/{step_id}`**

Add after PUT endpoint:

```python


@app.delete("/api/bridge-v2/steps/{flow_key}/{step_id}")
async def bridge_v2_delete_step(flow_key: str, step_id: int):
    """Soft-delete a step (set is_active = 0)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verify step exists
    row = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ? AND flow_key = ?",
        (step_id, flow_key)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in flow '{flow_key}'")

    deleted = dict(row)
    cursor.execute(
        "UPDATE bridge_flow_steps SET is_active = 0 WHERE id = ? AND flow_key = ?",
        (step_id, flow_key)
    )
    conn.commit()
    conn.close()
    return {"deleted": True, "step": deleted}
```

- [ ] **Step 6: Verify app.py syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile app.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

---

### Task 2: i18n labels for Steps UI in init_db.py

**Files:**
- Modify: `scripts/init_db.py` — add step-UI labels to existing bridge_setup_labels lists

**Interfaces:**
- Consumes: cursor (sqlite3), existing _bridge_setup_labels list pattern
- Produces: 7 new i18n labels (da-DK + en-US each) for Steps UI section

- [ ] **Step 1: Find the bridge labels insertion point in init_db.py**

Read `scripts/init_db.py` and locate the `_bridge_setup_labels` list (layer 3 ui_text_slots). This was added in Spor J with ~48 labels. Find where the last bridge label ends.

- [ ] **Step 2: Append new labels to _bridge_setup_labels**

Add these entries to the existing `_bridge_setup_labels` list (append before the closing bracket):

```python
    ("LBL-1000276", "lbl_bridge_steps_title", "main", "Steps", "Steps section title"),
    ("LBL-1000277", "lbl_bridge_select_flow", "main", "Select Flow", "Flow selector label"),
    ("lbl_bridge_step_form_title", "main", "Add/Edit Step", "Step form modal title"),
    ("LBL-1000280", "lbl_bridge_rule_key", "main", "Convention Rule", "Rule key dropdown label"),
    ("LBL-1000281", "lbl_bridge_script_pre", "main", "Pre-Dispatch Script", "Pre-dispatch script dropdown"),
    ("LBL-1000282", "lbl_bridge_script_post", "main", "Post-Dispatch Script", "Post-dispatch script dropdown"),
    ("LBL-1000283", "lbl_bridge_auto_filled", "main", "(auto-filled)", "Indicator: field auto-filled from convention"),
]
```

**NOTE:** Also add the corresponding da-DK translations. The seed data follows the pattern:
`("LBL-ID", "label_key", "domain", "en-US text", "description")`

da-DK translations are added in a separate loop further down in init_db.py. Find where da-DK bridge labels end and append:

```python
    ("lbl_bridge_steps_title", "Trin"),
    ("lbl_bridge_select_flow", "Vælg Flow"),
    ("lbl_bridge_step_form_title", "Tilføj/Redigér Trin"),
    ("lbl_bridge_rule_key", "Konvention Regel"),
    ("lbl_bridge_script_pre", "Forud-script"),
    ("lbl_bridge_script_post", "Efter-script"),
    ("lbl_bridge_auto_filled", "(auto-udfyldt)"),
```

Also add to `ui_text_slot_labels` mapping:
```python
    ("lbl_bridge_steps_title", "lbl_bridge_steps_title"),
    ("lbl_bridge_select_flow", "lbl_bridge_select_flow"),
    ("lbl_bridge_step_form_title", "lbl_bridge_step_form_title"),
    ("lbl_bridge_rule_key", "lbl_bridge_rule_key"),
    ("lbl_bridge_script_pre", "lbl_bridge_script_pre"),
    ("lbl_bridge_script_post", "lbl_bridge_script_post"),
    ("lbl_bridge_auto_filled", "lbl_bridge_auto_filled"),
```

- [ ] **Step 3: Verify syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/init_db.py && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

- [ ] **Step 4: Run init_db.py**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/init_db.py 2>&1 | tail -3
```

Expected: Clean execution, no errors.

---

### Task 3: Frontend — HTML panel + JavaScript functions

**Files:**
- Modify: `templates/index.html` — add Steps section after Flows section (~line 100)
- Modify: `static/js/dpmtf-app.js` — add ~10 JS functions for Steps CRUD UI

**Interfaces:**
- Consumes: `lbl(key, fallback)` function (existing), `apiBase`, fetch pattern from existing bridge functions
- Produces: HTML section with flow selector + steps grid; 10 JS functions for render/create/edit/delete

- [ ] **Step 1: Add Steps HTML section**

Insert in index.html after the Flows section (after line ~101, before the Export section):

```html
                    <!-- Steps -->
                    <section id="bridge-steps-section">
                        <h3 data-slot="lbl_bridge_steps_title">Steps</h3>
                        <div class="bridge-btn-row">
                            <select id="bridge-steps-flow-select" data-slot="lbl_bridge_select_flow"></select>
                            <button id="bridge-add-step-btn" type="button" data-slot="lbl_bridge_step_add">Add Step</button>
                        </div>
                        <div id="bridge-steps-list-container" class="dpmtf-card-grid"></div>
                    </section>
```

- [ ] **Step 2: Add JavaScript functions — part A: Load + Render**

Add to dpmtf-app.js at the end of the BridgeV002 section. Read existing bridge functions first (added Fase J) to match coding style.

Functions to add (all use `lbl()` for text, `createElement` for DOM):

```javascript
// ── Bridge Steps: Load Flow Selector ────────────────────────────

function loadBridgeStepsFlowSelector() {
    const select = document.getElementById('bridge-steps-flow-select');
    if (!select) return;
    fetch(apiBase + '/bridge-v2/flows')
        .then(r => r.json())
        .then(data => {
            select.innerHTML = '';
            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = lbl('lbl_bridge_select_flow', 'Select Flow');
            select.appendChild(defaultOpt);
            if (data.flows) {
                data.flows.forEach(function(fl) {
                    const opt = document.createElement('option');
                    opt.value = fl.flow_key;
                    opt.textContent = fl.name + ' (' + fl.flow_key + ')';
                    select.appendChild(opt);
                });
            }
        })
        .catch(function() {});
}

function fetchBridgeSteps(flowKey) {
    if (!flowKey) return;
    const container = document.getElementById('bridge-steps-list-container');
    if (!container) return;
    fetch(apiBase + '/bridge-v2/steps/' + flowKey)
        .then(r => r.json())
        .then(data => renderBridgeStepsList(data))
        .catch(function() {});
}

function renderBridgeStepsList(data) {
    var container = document.getElementById('bridge-steps-list-container');
    if (!container) return;
    container.replaceChildren();
    if (!data.steps || data.steps.length === 0) {
        var msg = document.createElement('p');
        msg.textContent = lbl('lbl_bridge_steps_empty', 'No steps for this flow');
        container.appendChild(msg);
        return;
    }
    // Store metadata globally for form use
    window.bridgeStepsMeta = {
        roles: data.available_roles || [],
        conventions: data.available_conventions || [],
        scripts: data.available_scripts || [],
    };
    data.steps.forEach(function(step) {
        var card = document.createElement('div');
        card.className = 'dpmtf-card';
        // Build content using createElement
        var header = document.createElement('h4');
        header.textContent = step.step_key + ' (order: ' + step.sort_order + ')';
        card.appendChild(header);
        var detail = document.createElement('p');
        detail.textContent = step.from_role + ' → ' + step.to_role;
        card.appendChild(detail);
        if (step.rule_key) {
            var rule = document.createElement('span');
            rule.className = 'dpmtf-badge';
            rule.textContent = step.rule_key;
            card.appendChild(rule);
        }
        // Action buttons
        var btnRow = document.createElement('div');
        btnRow.className = 'bridge-btn-row';
        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.textContent = lbl('lbl_bridge_edit', 'Edit');
        editBtn.onclick = function() { editBridgeStep(step.id, data.flow_key); };
        btnRow.appendChild(editBtn);
        var delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.textContent = lbl('lbl_bridge_delete', 'Delete');
        delBtn.style.marginLeft = '0.5rem';
        delBtn.onclick = function() { deleteBridgeStep(step.id, data.flow_key); };
        btnRow.appendChild(delBtn);
        card.appendChild(btnRow);
        container.appendChild(card);
    });
}
```

- [ ] **Step 3: Add JavaScript functions — part B: Create / Edit Form**

```javascript
function showCreateStepForm(flowKey) {
    if (!flowKey) { alert('Select a flow first'); return; }
    var formContainer = document.getElementById('bridge-steps-form-container');
    if (!formContainer) return;
    formContainer.innerHTML = '';
    // Build form with createElement
    var form = document.createElement('form');
    form.id = 'bridge-step-form';
    form.action = '#';
    form.onsubmit = function(e) { e.preventDefault(); submitBridgeStep(flowKey, form); };
    // Fields: step_key, from_role, to_role, rule_key, deliverable_dir, deliverable_pattern,
    //         pre_dispatch_script, post_dispatch_script, error_msg, sort_order
    // ... (use createElement for each field, matching existing bridge form style)
    // Populate dropdowns from window.bridgeStepsMeta
    formContainer.appendChild(form);
}

function autoFillFromConvention(ruleKey, form) {
    if (!ruleKey || !window.bridgeStepsMeta) return;
    var conv = (window.bridgeStepsMeta.conventions || []).find(function(c) { return c.rule_key === ruleKey; });
    if (!conv) return;
    var dirField = form.querySelector('[name="deliverable_dir"]');
    var patternField = form.querySelector('[name="deliverable_pattern"]');
    var errorField = form.querySelector('[name="error_msg"]');
    if (dirField) dirField.value = conv.dir_template || '';
    if (patternField) patternField.value = conv.pattern_template || '';
    if (errorField) errorField.value = conv.error_template || '';
}

function submitBridgeStep(flowKey, formOrId) {
    // Collect form data, send POST or PUT
    var formData = {};
    // Read from form fields
    var existingId = formOrId.id ? formOrId.querySelector('#bridge-step-id') : null;
    var isEdit = !!existingId;
    var url = apiBase + '/bridge-v2/steps/' + flowKey;
    var method = isEdit ? 'PUT' : 'POST';
    if (isEdit) {
        url = apiBase + '/bridge-v2/steps/' + flowKey + '/' + existingId.value;
    }
    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData),
    })
    .then(r => r.json())
    .then(function(data) {
        if (data.step || data.created || data.updated) {
            fetchBridgeSteps(flowKey); // Re-render list
        }
    })
    .catch(function() {});
}
```

- [ ] **Step 4: Add JavaScript functions — part C: Edit + Delete**

```javascript
function editBridgeStep(stepId, flowKey) {
    // Fetch steps again to get full data for this step
    fetch(apiBase + '/bridge-v2/steps/' + flowKey)
        .then(r => r.json())
        .then(function(data) {
            var step = (data.steps || []).find(function(s) { return s.id === stepId; });
            if (!step) return;
            showCreateStepForm(flowKey);
            // Pre-populate form with step data
            var form = document.getElementById('bridge-step-form');
            if (!form) return;
            // Set hidden id field
            var idField = form.querySelector('#bridge-step-id');
            if (idField) idField.value = stepId;
            // Fill all fields...
        });
}

function deleteBridgeStep(stepId, flowKey) {
    if (!confirm('Delete this step?')) return;
    fetch(apiBase + '/bridge-v2/steps/' + flowKey + '/' + stepId, { method: 'DELETE' })
        .then(r => r.json())
        .then(function(data) {
            if (data.deleted) {
                fetchBridgeSteps(flowKey); // Re-render list
            }
        })
        .catch(function() {});
}
```

- [ ] **Step 5: Wire up event listeners**

Add to the existing initBridgeSetup section or create a new function called from there:

```javascript
function initBridgeStepsSection() {
    var flowSelect = document.getElementById('bridge-steps-flow-select');
    if (flowSelect) {
        flowSelect.addEventListener('change', function() {
            fetchBridgeSteps(this.value);
        });
    }
    var addBtn = document.getElementById('bridge-add-step-btn');
    if (addBtn) {
        addBtn.addEventListener('click', function() {
            var flowKey = document.getElementById('bridge-steps-flow-select').value;
            showCreateStepForm(flowKey);
        });
    }
}
```

Call `initBridgeStepsSection()` from the existing initialization flow (same place where `initBridgeRoles()` and `initBridgeFlows()` are called).

- [ ] **Step 6: Verify JavaScript syntax**

Run:
```bash
cd /home/svend/DPMtF-WebUI && node --check static/js/dpmtf-app.js && echo "PASS" || echo "FAIL"
```

Expected: `PASS`

---

### Task 4: Verification suite

**Files:** N/A — verification only

- [ ] **Step 1: Compile all modified files**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile app.py && python3 -m py_compile scripts/init_db.py && node --check static/js/dpmtf-app.js && echo "ALL PASS" || echo "FAIL"
```

Expected: `ALL PASS`

- [ ] **Step 2: Check diff scope**

Run:
```bash
cd /home/svend/DPMtF-WebUI && git diff --stat
```

Expected: app.py, init_db.py, index.html, dpmtf-app.js, databases/dpmtf.db — only these files changed.

- [ ] **Step 3: Check innerHTML compliance**

Run:
```bash
cd /home/svend/DPMtF-WebUI && git diff static/js/dpmtf-app.js | grep -c "innerHTML" || true
```

If any innerHTML found in the diff, it must be for form container reset (`formContainer.innerHTML = ''`) which is acceptable when no user content is rendered. Dynamic content MUST use createElement.

- [ ] **Step 4: Verify i18n labels seeded correctly**

Run:
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
for label in ['lbl_bridge_steps_title', 'lbl_bridge_select_flow', 'lbl_bridge_rule_key']:
    en = conn.execute('SELECT default_text FROM ui_labels WHERE label_key=?', (label,)).fetchone()
    da = conn.execute('SELECT text FROM ui_label_translations WHERE label_key=? AND locale=?', (label, 'da-DK')).fetchone()
    print(f'{label}: EN={en}, DA={da}')
conn.close()
"
```

Expected: All labels found with both en-US and da-DK translations.

- [ ] **Step 5: Test endpoints after server restart**

Run (requires server running with new code):
```bash
curl -s http://localhost:9130/api/bridge-v2/steps/heavy | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Steps for heavy: {d.get(\"count\", 0)}, roles: {len(d.get(\"available_roles\", []))}, conventions: {len(d.get(\"available_conventions\", []))}')" || echo "(server not running — skip)"
```

Expected (if server is running and restarted): Steps count matches DB, dropdowns populated.

- [ ] **Step 6: Verify all changes unstaged**

Run:
```bash
cd /home/svend/DPMtF-WebUI && git status --short | head -10
```

Expected: Modified files appear as ` M` (unstaged before Human review, then staged and committed per permission).
