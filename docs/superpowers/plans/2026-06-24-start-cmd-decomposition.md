# start_cmd Dekomponering — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dekomponer `start_cmd` på `bridge_roles` i separate felter (`tmux_session`, `target_project`, `start_cmd_suffix`) og generer aggregeret streng automatisk. Behold eksisterende `start_cmd` som fallback.

**Architecture:** Ét nyt databasefelt (`start_cmd_suffix`), `target_project` læses fra Prompt Compiler's user_preferences, aggregering sker i frontend (visning) og i `start_coding.py` (udførsel). Eksisterende `start_cmd` forbliver urørt som fallback.

**Tech Stack:** Python 3.12, SQLite3, JavaScript (vanilla), tmux send-keys

## Global Constraints

- `python3 -m py_compile <file>` MUST pass before signaling completion
- Parameterized SQL only — `?` placeholders, never f-strings/concatenation in SQL
- No hardcoded paths — use config.py getters
- Bagudkompatibel: `start_cmd` beholdes urørt, `start_cmd_suffix` er NULL som default → fallback
- Alle eksisterende tests skal stadig passere
- Felter vises i aggregeret rækkefølge top-down på role

---

## Filstruktur

| Fil | Ansvar | Ændring |
|-----|--------|---------|
| `scripts/init_db.py` | Database-skema | Tilføj migration for `start_cmd_suffix` |
| `app.py` | API endpoints | Tilføj `start_cmd_suffix` til POST/PUT |
| `scripts/bridgeV002/bridge_lib.py` | Database-opslag | Opdater docstring |
| `scripts/bridgeV002/start_coding.py` | Start code interface | Aggregeringslogik + fallback |
| `static/js/dpmtf-app.js` | Frontend | Vis felter i aggregeret rækkefølge, read-only target_project, aggregeret streng |

---

### Task 1: Database-migration for start_cmd_suffix

**Files:**
- Modify: `scripts/init_db.py` — tilføj migration efter enter_command migrationen

**Interfaces:**
- Produces: `start_cmd_suffix` kolonne i `bridge_roles` (TEXT, default NULL)

- [ ] **Step 1: Tilføj migration i init_db.py**

Indsæt efter H150 enter_command migration-blokken:

```python
# H160: start_cmd_suffix column on bridge_roles — decomposed start command
# When set, the aggregated start command is built from:
#   tmux send-keys -t {tmux_session} 'cd {target_project} {start_cmd_suffix}
# When NULL, falls back to existing start_cmd field.
try:
    cursor.execute("""
        ALTER TABLE bridge_roles ADD COLUMN start_cmd_suffix TEXT DEFAULT NULL
    """)
except sqlite3.OperationalError:
    pass
```

- [ ] **Step 2: Kør init_db.py og verificer**

```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/init_db.py
```

Forventet: "Database initialized successfully!"

```bash
sqlite3 databases/dpmtf.db "PRAGMA table_info(bridge_roles)" | grep start_cmd_suffix
```

Forventet: `16|start_cmd_suffix|TEXT|0|NULL|0`

- [ ] **Step 3: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/init_db.py && git commit -m "feat: add start_cmd_suffix column to bridge_roles

Migration H160 — enables decomposed start command configuration.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Backend API — start_cmd_suffix i POST/PUT

**Files:**
- Modify: `app.py` — POST `/api/bridge-v2/roles` (linje ~4778-4813) og PUT (linje ~4835-4840)

**Interfaces:**
- Consumes: `start_cmd_suffix` kolonne fra Task 1
- Produces: POST/PUT accepterer og gemmer `start_cmd_suffix`

- [ ] **Step 1: Tilføj start_cmd_suffix til POST INSERT**

Find INSERT INTO bridge_roles (linje ~4779):
```python
cursor.execute("""
    INSERT INTO bridge_roles
    (role_key, tmux_session, start_cmd, model_type, cloud_model, ollama_model,
     setup_script, teardown_script, deliver_error_msg, enter_command)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    ...
    data.get("enter_command", "default"),
))
```

Tilføj `start_cmd_suffix` til kolonne-listen og VALUES:
```python
cursor.execute("""
    INSERT INTO bridge_roles
    (role_key, tmux_session, start_cmd, model_type, cloud_model, ollama_model,
     setup_script, teardown_script, deliver_error_msg, enter_command, start_cmd_suffix)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    data["role_key"],
    data["tmux_session"],
    data.get("start_cmd"),
    model_type,
    data.get("cloud_model"),
    data.get("ollama_model"),
    data.get("setup_script"),
    data.get("teardown_script"),
    data.get("deliver_error_msg"),
    data.get("enter_command", "default"),
    data.get("start_cmd_suffix"),
))
```

- [ ] **Step 2: Tilføj start_cmd_suffix til POST UPDATE fields**

Find UPDATE fields listen (linje ~4800):
```python
for field in ["tmux_session", "start_cmd", "model_type", "cloud_model",
              "ollama_model", "setup_script", "teardown_script",
              "deliver_error_msg", "enter_command"]:
```

Tilføj `"start_cmd_suffix"` til listen:
```python
for field in ["tmux_session", "start_cmd", "model_type", "cloud_model",
              "ollama_model", "setup_script", "teardown_script",
              "deliver_error_msg", "enter_command", "start_cmd_suffix"]:
```

- [ ] **Step 3: Tilføj start_cmd_suffix til PUT updatable**

Find `updatable` listen (linje ~4835):
```python
updatable = [
    "tmux_session", "start_cmd", "model_type", "cloud_model", "ollama_model",
    "setup_script", "teardown_script", "deliver_error_msg", "is_active",
    "governance_file",
    "role_type",
    "enter_command",
]
```

Tilføj `"start_cmd_suffix"`:
```python
updatable = [
    "tmux_session", "start_cmd", "model_type", "cloud_model", "ollama_model",
    "setup_script", "teardown_script", "deliver_error_msg", "is_active",
    "governance_file",
    "role_type",
    "enter_command",
    "start_cmd_suffix",  # H160: decomposed start command suffix
]
```

- [ ] **Step 4: Kør py_compile**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/app.py
```

Forventet: Ingen output (kompilering succes).

- [ ] **Step 5: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add app.py && git commit -m "feat: add start_cmd_suffix to role API endpoints

POST and PUT now accept and store start_cmd_suffix.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Frontend — rolle-kort visning i aggregeret rækkefølge

**Files:**
- Modify: `static/js/dpmtf-app.js` — `buildRoleCard()` funktionen (omkring linje 1869-1879)

**Interfaces:**
- Consumes: `role.start_cmd_suffix` fra API (Task 2), `target_project` fra user_preferences
- Produces: Rolle-kort viser felter i aggregeret rækkefølge med read-only aggregeret streng

- [ ] **Step 1: Læs target_project fra user_preferences**

Tilføj en hjælpefunktion til at hente target_project. Indsæt før `buildRoleCard`:

```javascript
function getTargetProject() {
  // Read from the compile form's target_project input (most current value)
  var input = document.getElementById("compile-target_project");
  if (input && input.value.trim()) {
    return input.value.trim();
  }
  // Fallback: DPMTF_PROJECT_ROOT from page context
  var meta = document.querySelector("meta[name='project-root']");
  if (meta) return meta.getAttribute("content");
  return "";
}
```

- [ ] **Step 2: Omstrukturer rolle-kort felter i aggregeret rækkefølge**

Erstat den eksisterende `fields` array (linje 1870-1879) med aggregeret rækkefølge:

```javascript
// Fields in aggregated order (top-down = how the command is built)
var targetProject = getTargetProject();
var fields = [
  // 1. tmux_session — first part of aggregated command
  [lbl("lbl_bridge_tmux_session", "Tmux Session"), role.tmux_session],
  // 2. target_project — read-only, from Prompt Compiler
  [lbl("lbl_compiler_target_project", "Target Project"), targetProject || "(not set)"],
  // 3. start_cmd_suffix — editable part after cd {project}
  [lbl("lbl_bridge_start_cmd_suffix", "Start Cmd Suffix"), role.start_cmd_suffix || null],
  // 4. Aggregeret streng (read-only, genereret)
  [lbl("lbl_bridge_aggregated_cmd", "Aggregated Command"), buildAggregatedCmd(role, targetProject)],
  // Existing fields below
  [lbl("lbl_bridge_start_cmd", "Start Command (fallback)"), role.start_cmd],
  [lbl("lbl_bridge_model_type", "Model Type"), role.model_type],
  [lbl("lbl_bridge_cloud_model", "Cloud Model"), role.cloud_model],
  [lbl("lbl_bridge_ollama_model", "Ollama Model"), role.ollama_model],
  [lbl("lbl_bridge_governance_file", "Governance File"), role.governance_file],
  [lbl("lbl_bridge_role_type", "Role Type"), role.role_type && role.role_type !== "agent" ? role.role_type : null],
  [lbl("lbl_bridge_enter_command", "Enter Command"), role.enter_command || "default"],
];
```

- [ ] **Step 3: Tilføj buildAggregatedCmd() funktion**

Indsæt før `buildRoleCard`:

```javascript
function buildAggregatedCmd(role, targetProject) {
  if (!role.start_cmd_suffix) return null; // Not configured — use fallback
  if (!targetProject) return null; // Missing project — can't build
  return "tmux send-keys -t " + role.tmux_session +
         " 'cd " + targetProject + " " + role.start_cmd_suffix;
}
```

- [ ] **Step 4: Vis aggregeret streng med monospace styling**

I felt-loopen, giv aggregeret streng særlig visning. Tilføj efter `fields.forEach`:

```javascript
// Style the aggregated command row with monospace font
var aggRow = card.querySelector("[data-field='aggregated_cmd']");
if (aggRow) {
  aggRow.style.fontFamily = "monospace";
  aggRow.style.fontSize = "11px";
  aggRow.style.wordBreak = "break-all";
  aggRow.style.background = "#161b22";
  aggRow.style.padding = "4px 8px";
  aggRow.style.borderRadius = "4px";
  aggRow.style.marginTop = "4px";
}
```

Mere præcist: tilføj et `data-field` attribut i felt-loopen så vi kan style det. Opdater felt-loopen:

```javascript
fields.forEach(function (pair) {
  if (!pair[1]) return;
  var row = el("div", null);
  var label = pair[0];
  // Set data-field for styling hooks
  if (label === lbl("lbl_bridge_aggregated_cmd", "Aggregated Command")) {
    row.setAttribute("data-field", "aggregated_cmd");
  }
  row.appendChild(el("span", "dpmtf-small", escapeHtml(label) + ": "));
  var valSpan = el("span", null, escapeHtml(String(pair[1])));
  if (label === lbl("lbl_bridge_aggregated_cmd", "Aggregated Command")) {
    valSpan.style.fontFamily = "monospace";
    valSpan.style.fontSize = "11px";
    valSpan.style.wordBreak = "break-all";
  }
  row.appendChild(valSpan);
  card.appendChild(row);
});
```

- [ ] **Step 5: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add static/js/dpmtf-app.js && git commit -m "feat: show role fields in aggregated order with generated command

Fields now displayed top-down matching the aggregated command structure.
target_project shown read-only from Prompt Compiler.
Aggregated command generated and displayed in monospace.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Frontend — edit/create forms med start_cmd_suffix

**Files:**
- Modify: `static/js/dpmtf-app.js` — create-form (omkring linje 2203) og edit-form (omkring linje 2551)

**Interfaces:**
- Consumes: Rolle-kort visning fra Task 3
- Produces: Edit/create forms har `start_cmd_suffix` input, gemmer via API (Task 2)

- [ ] **Step 1: Tilføj start_cmd_suffix input til create-form**

Efter enter_command select i create-formen, tilføj:

```javascript
// H160: start_cmd_suffix input
var scsDiv = el("div", "dpmtf-form-group");
scsDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_start_cmd_suffix", "Start Cmd Suffix")));
var scsInput = el("input", null);
scsInput.id = "bridge-input-start_cmd_suffix";
scsInput.type = "text";
scsInput.placeholder = "&& OPENCODE_CONFIG_DIR=... opencode --model ollama/...' Enter";
scsDiv.appendChild(scsInput);
form.appendChild(scsDiv);
```

- [ ] **Step 2: Tilføj start_cmd_suffix til create save-logik**

Find saveBtn.onclick for create (omkring linje 2139). Efter `enter_command` linjen, tilføj:

```javascript
var scs = document.getElementById("bridge-input-start_cmd_suffix");
if (scs && scs.value.trim()) body.start_cmd_suffix = scs.value.trim();
```

- [ ] **Step 3: Tilføj start_cmd_suffix input til edit-form**

Efter enter_command select i edit-formen (omkring linje 2551), tilføj:

```javascript
// H160: start_cmd_suffix input
var scsDiv2 = el("div", "dpmtf-form-group");
scsDiv2.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_start_cmd_suffix", "Start Cmd Suffix")));
var scsInput2 = el("input", null);
scsInput2.id = "bridge-edit-input-start_cmd_suffix";
scsInput2.type = "text";
scsInput2.value = role.start_cmd_suffix || "";
scsInput2.placeholder = "&& OPENCODE_CONFIG_DIR=... opencode --model ollama/...' Enter";
scsDiv2.appendChild(scsInput2);
form.appendChild(scsDiv2);
```

- [ ] **Step 4: Tilføj start_cmd_suffix til edit save-logik**

Find saveBtn.onclick for edit (omkring linje 2414). Efter enter_command linjen, tilføj:

```javascript
// H160: start_cmd_suffix
var scs = document.getElementById("bridge-edit-input-start_cmd_suffix");
if (scs) body.start_cmd_suffix = scs.value.trim();
```

- [ ] **Step 5: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add static/js/dpmtf-app.js && git commit -m "feat: add start_cmd_suffix to role create/edit forms

Create and edit forms now include start_cmd_suffix input field.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: start_coding.py — aggregeringslogik og fallback

**Files:**
- Modify: `scripts/bridgeV002/start_coding.py` — `get_flow_roles()` og `run_cmd_in_session()`

**Interfaces:**
- Consumes: `start_cmd_suffix` fra database (Task 1), `target_project` fra config
- Produces: Aggregeret streng genereres og udføres; fallback til `start_cmd`

- [ ] **Step 1: Opdater get_flow_roles() til at hente start_cmd_suffix**

Find SQL query (linje 38-47). Tilføj `r.start_cmd_suffix` til SELECT:

```python
rows = conn.execute(
    """
    SELECT r.role_key, r.tmux_session, r.start_cmd, r.start_cmd_suffix
    FROM bridge_flow_steps s
    JOIN bridge_roles r ON s.from_role = r.role_key
    WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
    ORDER BY s.sort_order
    """,
    (flow_key,),
).fetchall()
```

Og opdater result-dict:

```python
result.append({
    "role_key": row["role_key"],
    "tmux_session": row["tmux_session"],
    "start_cmd": row["start_cmd"],
    "start_cmd_suffix": row["start_cmd_suffix"],
})
```

- [ ] **Step 2: Tilføj build_aggregated_cmd() funktion**

Indsæt før `main()`:

```python
def build_aggregated_cmd(tmux_session, target_project, start_cmd_suffix):
    """Build the aggregated start command from decomposed fields.

    Returns the full tmux send-keys command string, or None if missing fields.
    """
    if not start_cmd_suffix:
        return None
    if not target_project:
        return None
    return (
        f"tmux send-keys -t {tmux_session} "
        f"'cd {target_project} {start_cmd_suffix}"
    )
```

- [ ] **Step 3: Opdater run_cmd_in_session() til at bruge aggregeret eller fallback**

Erstat funktionen (linje 79-93):

```python
def run_cmd_in_session(session_name, start_cmd, bridge_dir, project_root,
                       start_cmd_suffix=None, target_project=None):
    """Run a start command in an existing tmux session via send-keys.

    If start_cmd_suffix is set, builds aggregated command from:
      tmux send-keys -t {session} 'cd {target_project} {suffix}
    Otherwise falls back to the existing start_cmd field.

    Returns True on success, False on failure.
    """
    if start_cmd_suffix and target_project:
        # New decomposed mode: build aggregated command
        resolved_suffix = resolve_placeholders(
            start_cmd_suffix, bridge_dir=bridge_dir, project_root=project_root
        )
        resolved_target = resolve_placeholders(
            target_project, bridge_dir=bridge_dir, project_root=project_root
        )
        cmd_str = build_aggregated_cmd(session_name, resolved_target, resolved_suffix)
        print(f"  Aggregated: {cmd_str}")
        # Split into tmux send-keys arguments
        cmd = ["tmux", "send-keys", "-t", session_name, cmd_str]
    elif start_cmd:
        # Fallback: use existing start_cmd as before
        resolved = resolve_placeholders(
            start_cmd, bridge_dir=bridge_dir, project_root=project_root
        )
        print(f"  Command: {resolved}")
        cmd = ["tmux", "send-keys", "-t", session_name, resolved, "Enter"]
    else:
        print(f"  ERROR: No start_cmd or start_cmd_suffix configured")
        return False

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
```

- [ ] **Step 4: Opdater main() til at sende nye felter med**

Find kaldet til `run_cmd_in_session` (linje 151). Erstat:

```python
ok = run_cmd_in_session(session_name, start_cmd, bridge_dir, project_root)
```

Med:

```python
ok = run_cmd_in_session(
    session_name,
    role["start_cmd"],
    bridge_dir,
    project_root,
    start_cmd_suffix=role.get("start_cmd_suffix"),
    target_project=project_root,  # target_project = DPMtF project root
)
```

- [ ] **Step 5: Kør py_compile**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
```

Forventet: Ingen output.

- [ ] **Step 6: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/bridgeV002/start_coding.py && git commit -m "feat: add aggregated command support to start_coding.py

Uses start_cmd_suffix + target_project when available, falls back to
existing start_cmd for backward compatibility.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Opdater bridge_lib.py docstring

**Files:**
- Modify: `scripts/bridgeV002/bridge_lib.py` — `load_role_from_db()` docstring (linje 325-329)

- [ ] **Step 1: Tilføj start_cmd_suffix til docstring**

Find:
```python
Keys: role_key, tmux_session, start_cmd, model_type, cloud_model,
      ollama_model, setup_script, teardown_script, deliver_error_msg,
      is_active, created_at, updated_at, restart_policy,
      governance_file, role_type, enter_command
```

Tilføj `start_cmd_suffix`:
```python
Keys: role_key, tmux_session, start_cmd, model_type, cloud_model,
      ollama_model, setup_script, teardown_script, deliver_error_msg,
      is_active, created_at, updated_at, restart_policy,
      governance_file, role_type, enter_command, start_cmd_suffix
```

- [ ] **Step 2: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/bridgeV002/bridge_lib.py && git commit -m "docs: add start_cmd_suffix to load_role_from_db docstring

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Integrationstest

**Files:**
- Ingen nye filer — manuel test

- [ ] **Step 1: Sæt start_cmd_suffix på en test-role**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "UPDATE bridge_roles SET start_cmd_suffix = '&& echo test_aggregated' Enter' WHERE role_key = 'imple01'"
```

- [ ] **Step 2: Verificer at rolle-kort viser aggregeret streng**

Åbn WebUI → Bridge Setup → Roles → se imple01 kortet.
Forventet: Viser "Aggregated Command: tmux send-keys -t imple01 'cd /home/svend/DPMtF-WebUI && echo test_aggregated' Enter"

- [ ] **Step 3: Test start_coding.py med aggregeret kommando**

```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/start_coding.py strict_review 2>&1
```

Forventet: imple01 viser "Aggregated: ..." og kommandoen køres.

- [ ] **Step 4: Nulstil test-data**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "UPDATE bridge_roles SET start_cmd_suffix = NULL WHERE role_key = 'imple01'"
```

- [ ] **Step 5: Verificer fallback virker**

```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/start_coding.py strict_review 2>&1
```

Forventet: imple01 bruger eksisterende `start_cmd` (fallback).
