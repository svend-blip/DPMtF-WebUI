# Panel Subgroups — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Indfør "Design subpatterns" som nestede expand/collapse panel-subgroup containere inden for de 5 faste panel-groups. Database-drevet synlighed. DPMtF først, ENO alignment herefter.

**Architecture:** 2 nye databasetabeller (panel_subgroups, panel_subgroup_mappings) + udvidelse af user_panel_groups. Nyt GET /api/panel-structure endpoint returnerer fuld hierarki. JS buildPanelStructure() bygger subgroups dynamisk i DOM'en. CSS panel-subgroup klasser baseret på eksisterende panel-group mønster.

**Tech Stack:** Python/FastAPI, SQLite, vanilla JS, CSS. Bridge (bridge.py) til lokal model execution.

**Bridge-strategi:**
- Database + API + CSS + i18n → claude_implementer (lokal, qwen36-27b-q4km)
- JS buildPanelStructure() → claude_architect (cloud, deepseek-v4-pro) — ny kompleks logik
- ENO alignment → claude_implementer (lokal)
- Review → claude_review (lokal)

---

## File Structure

| Fil | Ansvar |
|---|---|
| `scripts/init_db.py` | ALTER user_panel_groups, CREATE panel_subgroups + panel_subgroup_mappings, seed data, i18n labels, endpoint registry, bootstrap registry, phase status |
| `app.py` | GET /api/panel-structure, POST /api/panel-structure/subgroup-state, udvid GET/POST /api/user-panel-groups |
| `static/css/dpmtf-theme.css` | Nye .panel-subgroup-* klasser |
| `static/js/dpmtf-app.js` | buildPanelStructure() — erstatter applyPanelGroupStates(), bygger subgroups dynamisk |
| `docs/governance-templates/superpowertemplates/superpowers.md` | Nye scope-regler for subgroups |
| `docs/governance-templates/11_NEXT_CONTEXT.md` | Opdatering efter implementation |

---

### Task 1: Database — ALTER + CREATE tabeller + seed data (LOKAL)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/init_db.py`

**Sendes via bridge til claude_implementer.**

- [ ] **Step 1: ALTER user_panel_groups — tilføj is_visible**

Efter `CREATE TABLE IF NOT EXISTS user_panel_groups` (omkring linje 2802), tilføj:

```sql
-- Tilføj is_visible kolonne (idempotent via IF NOT EXISTS pattern)
-- SQLite understøtter ikke ALTER TABLE ADD COLUMN IF NOT EXISTS,
-- så vi bruger en try/except i Python eller tjekker kolonnen først.
```

Python-mønster (efter conn.commit for user_panel_groups CREATE):

```python
# Tilføj is_visible kolonne hvis den ikke findes
cursor.execute("PRAGMA table_info(user_panel_groups)")
columns = [col[1] for col in cursor.fetchall()]
if "is_visible" not in columns:
    cursor.execute("ALTER TABLE user_panel_groups ADD COLUMN is_visible INTEGER DEFAULT 1")
```

- [ ] **Step 2: CREATE TABLE panel_subgroups**

Efter user_panel_groups sektionen:

```sql
cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroups (
    subgroup_key  TEXT PRIMARY KEY NOT NULL,
    group_name    TEXT NOT NULL,
    title_da      TEXT NOT NULL,
    title_en      TEXT NOT NULL,
    sort_order    INTEGER DEFAULT 0,
    is_visible    INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
```

- [ ] **Step 3: CREATE TABLE panel_subgroup_mappings**

```sql
cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroup_mappings (
    slot_key      TEXT NOT NULL,
    subgroup_key  TEXT NOT NULL,
    PRIMARY KEY (slot_key, subgroup_key)
)
""")
```

- [ ] **Step 4: Seed data — DPMtF subgroups**

```python
panel_subgroups_seed = [
    ("sg_periodic_phase", "periodic", "Fase", "Phase", 1, 1),
    ("sg_periodic_planning", "periodic", "Planlægning", "Planning", 2, 1),
    ("sg_periodic_existing", "periodic", "Eksisterende Projekter", "Existing Projects", 3, 1),
]
for sg in panel_subgroups_seed:
    cursor.execute("""
        INSERT OR REPLACE INTO panel_subgroups
        (subgroup_key, group_name, title_da, title_en, sort_order, is_visible)
        VALUES (?, ?, ?, ?, ?, ?)
    """, sg)
```

- [ ] **Step 5: Seed data — DPMtF mappings**

```python
panel_subgroup_mappings_seed = [
    ("lbl_panel_phase_status", "sg_periodic_phase"),
    ("lbl_panel_project_planning", "sg_periodic_planning"),
]
for slot, sg in panel_subgroup_mappings_seed:
    cursor.execute("""
        INSERT OR REPLACE INTO panel_subgroup_mappings (slot_key, subgroup_key)
        VALUES (?, ?)
    """, (slot, sg))
```

- [ ] **Step 6: Sæt Journals is_visible = 0**

```python
cursor.execute("""
    INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
    VALUES ('default', 'journals', 'expanded', 0, datetime('now'))
""")
```

- [ ] **Step 7: i18n labels — subgroup titles**

Tilføj til `ui_labels_data` (brug næste ledige LBL-ID'er):

```python
("LBL-1000116", "sg_periodic_phase_title", "main", "Fase", "Subgroup: Phase"),
("LBL-1000117", "sg_periodic_planning_title", "main", "Planlægning", "Subgroup: Planning"),
("LBL-1000118", "sg_periodic_existing_title", "main", "Eksisterende Projekter", "Subgroup: Existing Projects"),
```

Tilføj til `ui_label_translations_data` (da-DK + en-US):

```python
("sg_periodic_phase_title", "Fase"), ("sg_periodic_phase_title", "Phase"),
("sg_periodic_planning_title", "Planlægning"), ("sg_periodic_planning_title", "Planning"),
("sg_periodic_existing_title", "Eksisterende Projekter"), ("sg_periodic_existing_title", "Existing Projects"),
```

Tilføj slots + bindings:

```python
("sg_periodic_phase_title", "Subgroup: Phase"),
("sg_periodic_planning_title", "Subgroup: Planning"),
("sg_periodic_existing_title", "Subgroup: Existing Projects"),
```

```python
("sg_periodic_phase_title", "sg_periodic_phase_title"),
("sg_periodic_planning_title", "sg_periodic_planning_title"),
("sg_periodic_existing_title", "sg_periodic_existing_title"),
```

- [ ] **Step 8: Endpoint registry + bootstrap + phase status**

```python
endpoint_registry_subgroups = [
    ("ENDP-4000036", "panel_structure", "/api/panel-structure", "GET", "Get full panel hierarchy with subgroups, visibility, and collapse states", "panel structure JSON", "panel_groups"),
    ("ENDP-4000037", "subgroup_state", "/api/panel-structure/subgroup-state", "POST", "Save collapse state for a panel subgroup", "state JSON", "panel_groups"),
]
for ep in endpoint_registry_subgroups:
    cursor.execute("""
        INSERT OR REPLACE INTO endpoint_registry
        (endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose, response_shape, frontend_consumer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ep)

cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000024", "panel_subgroups", "panel_subgroups", "Panel subgroup definitions for nested expand/collapse", "scripts/init_db.py", 3, 0, 1))

cursor.execute("""
    INSERT OR REPLACE INTO bootstrap_dataset_registry
    (dataset_id, dataset_key, table_name, dataset_purpose, source_script, min_expected_count, is_required, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("BDS-5000025", "panel_subgroup_mappings", "panel_subgroup_mappings", "Slot-to-subgroup mappings", "scripts/init_db.py", 2, 0, 1))

# Phase status: 2O-b → completed, 3A → next
cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("2O-b", "Comparison Panel", "Comparison Runs panel in System Setup drawer.", "completed", 39))

cursor.execute("""
    INSERT OR REPLACE INTO phase_status
    (phase_key, phase_title, phase_description, phase_state, sort_order)
    VALUES (?, ?, ?, ?, ?)
""", ("3A", "Panel Subgroups", "Design subpatterns: nested expand/collapse subgroups within panel groups. Database-driven visibility.", "next", 40))
```

- [ ] **Step 9: Validering**

```bash
python3 -m py_compile scripts/init_db.py
# Expected: PASS
```

- [ ] **Step 10: Commit (af architect efter review)**

---

### Task 2: API — GET /api/panel-structure + POST subgroup-state (LOKAL)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/app.py`

**Sendes via bridge til claude_implementer.**

- [ ] **Step 1: GET /api/panel-structure**

Indsæt før `if __name__ == "__main__"`:

```python
@app.get("/api/panel-structure")
async def get_panel_structure(locale: str = "en-US"):
    """Return full panel hierarchy with subgroups, visibility, and collapse states."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Hent panel group states
    cursor.execute(
        "SELECT group_name, state, is_visible FROM user_panel_groups WHERE user_id = 'default'"
    )
    group_rows = {r["group_name"]: r for r in cursor.fetchall()}

    # Hent subgroups
    cursor.execute(
        "SELECT * FROM panel_subgroups WHERE is_visible = 1 ORDER BY sort_order"
    )
    subgroups = [dict(r) for r in cursor.fetchall()]

    # Hent mappings
    cursor.execute("SELECT * FROM panel_subgroup_mappings")
    mappings = {}
    for r in cursor.fetchall():
        sg = r["subgroup_key"]
        if sg not in mappings:
            mappings[sg] = []
        mappings[sg].append(r["slot_key"])

    # Hent subgroup states
    cursor.execute(
        "SELECT subgroup_key, state FROM user_panel_groups WHERE user_id = 'default' AND subgroup_key IS NOT NULL"
    )
    subgroup_states = {r["subgroup_key"]: r["state"] for r in cursor.fetchall()}

    # Byg struktur
    group_names = ["daily", "journals", "reports", "periodic", "setup"]
    result = {}
    title_field = "title_da" if locale == "da-DK" else "title_en"

    for gn in group_names:
        gr = group_rows.get(gn, {})
        is_visible = gr.get("is_visible", 1) if gr else 1
        state = gr.get("state", "expanded") if gr else "expanded"

        # Find subgroups for this group
        group_subgroups = [sg for sg in subgroups if sg["group_name"] == gn]

        if group_subgroups:
            subgroup_list = []
            for sg in group_subgroups:
                subgroup_list.append({
                    "key": sg["subgroup_key"],
                    "title": sg[title_field],
                    "is_visible": bool(sg["is_visible"]),
                    "state": subgroup_states.get(sg["subgroup_key"], "expanded"),
                    "slots": mappings.get(sg["subgroup_key"], []),
                })
        else:
            # Implicit "All" subgroup
            subgroup_list = [{
                "key": f"sg_{gn}_all",
                "title": "",
                "is_visible": True,
                "state": "expanded",
                "slots": [],  # Alle slots i gruppen
            }]

        result[gn] = {
            "is_visible": bool(is_visible),
            "state": state,
            "subgroups": subgroup_list,
        }

    conn.close()
    return {"groups": result}
```

- [ ] **Step 2: POST /api/panel-structure/subgroup-state**

```python
@app.post("/api/panel-structure/subgroup-state")
async def save_subgroup_state(request: Request):
    """Save collapse state for a panel subgroup."""
    data = await request.json()
    subgroup_key = data.get("subgroup_key")
    state = data.get("state", "expanded")

    if not subgroup_key:
        raise HTTPException(status_code=400, detail="subgroup_key required")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
        VALUES ('default', ?, ?, 1, datetime('now'))
    """, (subgroup_key, state))
    conn.commit()
    conn.close()
    return {"status": "saved", "subgroup_key": subgroup_key, "state": state}
```

- [ ] **Step 3: Udvid GET /api/user-panel-groups**

Eksisterende endpoint (omkring linje 846) — tilføj `is_visible` til SELECT:

```python
# FØR:
cursor.execute(
    "SELECT group_name, state FROM user_panel_groups WHERE user_id = ?",
    (user_id,)
)

# EFTER:
cursor.execute(
    "SELECT group_name, state, is_visible FROM user_panel_groups WHERE user_id = ?",
    (user_id,)
)
```

Og inkluder `is_visible` i response:

```python
groups[group_name] = {
    "state": row["state"],
    "is_visible": bool(row["is_visible"]),
}
```

- [ ] **Step 4: Udvid POST /api/user-panel-groups**

Accepter `is_visible` i request body (optional, default 1):

```python
is_visible = data.get("is_visible", 1)
# ...
cursor.execute("""
    INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
    VALUES (?, ?, ?, ?, datetime('now'))
""", (user_id, group_name, state, is_visible))
```

- [ ] **Step 5: Validering**

```bash
python3 -m py_compile app.py
# Expected: PASS
```

- [ ] **Step 6: Commit (af architect efter review)**

---

### Task 3: CSS — panel-subgroup klasser (LOKAL)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/static/css/dpmtf-theme.css`

**Sendes via bridge til claude_implementer.**

- [ ] **Step 1: Tilføj panel-subgroup CSS**

Efter `.panel-group.collapsed .panel-group-body` sektionen (omkring linje 400):

```css
/* ── Panel Subgroups (collapse/expand) ──────────────── */
.panel-subgroup {
    margin-bottom: 12px;
    border: 1px solid #21262d;
    border-radius: 6px;
    overflow: hidden;
}

.panel-subgroup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    user-select: none;
    background: #161b22;
}

.panel-subgroup-header:hover {
    background: #1c2129;
}

.panel-subgroup-header h3 {
    font-size: 0.95rem;
    margin: 0;
    color: #c9d1d9;
}

.panel-subgroup-toggle {
    font-size: 0.75rem;
    color: #8b949e;
}

.panel-subgroup-body {
    padding: 8px 12px;
    border-top: 1px solid #21262d;
    background: #0d1117;
}

.panel-subgroup.collapsed .panel-subgroup-body {
    display: none;
}

/* Skjul implicit "All" subgroup header */
.panel-subgroup-all .panel-subgroup-header {
    display: none;
}

/* Skjul tomme grupper */
.panel-group.dpmtf-hidden {
    display: none;
}
```

- [ ] **Step 2: Validering**

```bash
# CSS har ingen syntaks-check — visuel verifikation efter deployment
grep "panel-subgroup" static/css/dpmtf-theme.css | wc -l
# Expected: >= 8
```

- [ ] **Step 3: Commit (af architect efter review)**

---

### Task 4: JS — buildPanelStructure() (CLOUD — claude_architect)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/static/js/dpmtf-app.js`

**Udføres af claude_architect (denne session).** Kompleks ny logik — cloud model bedre egnet.

- [ ] **Step 1: Erstat applyPanelGroupStates() med buildPanelStructure()**

Erstat funktionerne `loadPanelGroupStates()`, `applyPanelGroupStates()`, `initPanelGroupToggles()` (linje 83-142) med:

```javascript
/* ── 1b. Panel structure (groups + subgroups) ────────── */
var panelStructure = {};

function loadPanelStructure() {
  fetch("/api/panel-structure?locale=" + encodeURIComponent(currentLocale))
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      panelStructure = data.groups || {};
      buildPanelStructure();
    })
    .catch(function () {
      // Fallback: vis alle grupper uden subgroups
      buildPanelStructure();
    });
}

function buildPanelStructure() {
  var groupNames = ["daily", "journals", "reports", "periodic", "setup"];
  for (var i = 0; i < groupNames.length; i++) {
    var gn = groupNames[i];
    var pg = document.getElementById("pg-" + gn);
    if (!pg) continue;
    var info = panelStructure[gn] || { is_visible: true, state: "expanded", subgroups: [] };

    // Skjul tomme grupper
    if (!info.is_visible) {
      pg.classList.add("dpmtf-hidden");
      continue;
    }
    pg.classList.remove("dpmtf-hidden");

    // Sæt group collapse state
    var toggle = pg.querySelector(".panel-group-toggle");
    var body = pg.querySelector(".panel-group-body");
    if (info.state === "collapsed") {
      pg.classList.add("collapsed");
      if (body) body.style.display = "none";
      if (toggle) toggle.textContent = "▶";
    } else {
      pg.classList.remove("collapsed");
      if (body) body.style.display = "";
      if (toggle) toggle.textContent = "▼";
    }

    // Byg subgroups inde i body
    if (body) buildSubgroups(body, gn, info.subgroups);
  }
}

function buildSubgroups(body, groupName, subgroups) {
  // Fjern eksisterende subgroups (hvis nogen)
  var existing = body.querySelectorAll(".panel-subgroup");
  for (var i = 0; i < existing.length; i++) {
    existing[i].remove();
  }

  if (!subgroups || !subgroups.length) {
    // Ingen subgroups defineret — "All" implicit: paneler forbliver direkte i body
    // Find paneler der blev flyttet til subgroups og flyt dem tilbage
    return;
  }

  for (var s = 0; s < subgroups.length; s++) {
    var sg = subgroups[s];
    if (!sg.is_visible) continue;

    var sgEl = document.createElement("section");
    sgEl.className = "panel-subgroup";
    if (sg.key && sg.key.endsWith("_all")) {
      sgEl.classList.add("panel-subgroup-all");
    }
    sgEl.setAttribute("data-subgroup", sg.key);

    // Header
    var header = document.createElement("div");
    header.className = "panel-subgroup-header";
    var title = document.createElement("h3");
    title.textContent = sg.title || "";
    header.appendChild(title);
    var sgToggle = document.createElement("span");
    sgToggle.className = "panel-subgroup-toggle";
    sgToggle.textContent = sg.state === "collapsed" ? "▶" : "▼";
    header.appendChild(sgToggle);
    sgEl.appendChild(header);

    // Body
    var sgBody = document.createElement("div");
    sgBody.className = "panel-subgroup-body";
    if (sg.state === "collapsed") {
      sgEl.classList.add("collapsed");
      sgBody.style.display = "none";
    }

    // Flyt paneler ind i subgroup baseret på slot mapping
    if (sg.slots && sg.slots.length) {
      for (var k = 0; k < sg.slots.length; k++) {
        var slotKey = sg.slots[k];
        var panel = body.querySelector('[data-slot="' + slotKey + '"]');
        if (panel) {
          // Find panelens nærmeste section/parent og flyt den
          var section = panel.closest("section") || panel.parentElement;
          if (section && section !== body) {
            sgBody.appendChild(section);
          }
        }
      }
    }

    sgEl.appendChild(sgBody);
    body.appendChild(sgEl);

    // Click handler for collapse
    header.addEventListener("click", function (subgroupKey, el, bodyEl, toggleEl) {
      return function () {
        var isCollapsed = el.classList.contains("collapsed");
        var newState = isCollapsed ? "expanded" : "collapsed";
        if (newState === "collapsed") {
          el.classList.add("collapsed");
          if (bodyEl) bodyEl.style.display = "none";
          if (toggleEl) toggleEl.textContent = "▶";
        } else {
          el.classList.remove("collapsed");
          if (bodyEl) bodyEl.style.display = "";
          if (toggleEl) toggleEl.textContent = "▼";
        }
        fetch("/api/panel-structure/subgroup-state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subgroup_key: subgroupKey, state: newState }),
        }).catch(function (err) {
          console.warn("Failed to save subgroup state:", err.message);
        });
      };
    }(sg.key, sgEl, sgBody, sgToggle));
  }
}
```

- [ ] **Step 2: Opdater kald til loadPanelStructure()**

I DOMContentLoaded (omkring linje 72), erstat `loadPanelGroupStates()` med `loadPanelStructure()`:

```javascript
// FØR:
loadPanelGroupStates();

// EFTER:
loadPanelStructure();
```

- [ ] **Step 3: Bevar initPanelGroupToggles() for group-level collapse**

`initPanelGroupToggles()` (linje 122-142) bevares men opdateres til at bruge `panelStructure` i stedet for `panelGroupStates`:

```javascript
function initPanelGroupToggles() {
  var headers = document.querySelectorAll(".panel-group-header");
  for (var i = 0; i < headers.length; i++) {
    headers[i].addEventListener("click", function () {
      var groupName = this.getAttribute("data-group");
      var pg = document.getElementById("pg-" + groupName);
      if (!pg) return;
      var isCollapsed = pg.classList.contains("collapsed");
      var newState = isCollapsed ? "expanded" : "collapsed";

      // Opdater lokal state
      if (panelStructure[groupName]) {
        panelStructure[groupName].state = newState;
      }
      buildPanelStructure();  // Genopbyg (bevarer subgroup states)

      fetch("/api/user-panel-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_name: groupName, state: newState }),
      }).catch(function (err) {
        console.warn("Failed to save panel group state:", err.message);
      });
    });
  }
}
```

- [ ] **Step 4: Validering**

```bash
node --check static/js/dpmtf-app.js
# Expected: PASS

grep -RIn "innerHTML" static/js/dpmtf-app.js
# Expected: kun præeksisterende matches (closeBtn + placeholders)
```

- [ ] **Step 5: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "feat: buildPanelStructure() — nested subgroups with collapse"
```

---

### Task 5: Governance — superpowers.md opdatering (CLOUD)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md`

**Udføres af claude_architect.**

- [ ] **Step 1: Tilføj subgroup regler under Scope-regler**

Efter "Panelgrupper er fixed" reglen, tilføj:

```markdown
- **Panel subgroups er valgfrie:** Hver panel-group KAN have subgroups defineret i `panel_subgroups` tabellen. Hvis en gruppe ikke har nogen subgroups, bruges en implicit "All" subgroup uden synlig header — paneler vises fladt som før.
- **Tomme patterns/subpatterns skjules:** `is_visible = 0` i `user_panel_groups` (for patterns) eller `panel_subgroups` (for subpatterns) skjuler elementet via CSS-klassen `dpmtf-hidden`. Styres af database, ikke hardcodet.
- **Subgroup struktur er database-drevet:** Ændringer i subgroup-definitioner kræver ikke HTML-ændringer. Nye subgroups tilføjes via seed data i `init_db.py`.
```

- [ ] **Step 2: Opdateringslog**

```markdown
| 2026-06-14 | Tilføjet **Panel Subgroups** scope-regler — nestede expand/collapse subgroups inden for panel-groups. Database-drevet via `panel_subgroups` + `panel_subgroup_mappings` tabeller. Implicit "All" subgroup når ingen defineret. Tomme patterns/subpatterns skjules via `is_visible`. |
```

- [ ] **Step 3: Commit**

---

### Task 6: ENO Alignment (LOKAL)

**Files:**
- Modify: `/home/svend/ENO/scripts/init_db.py`
- Modify: `/home/svend/ENO/app.py`
- Modify: `/home/svend/ENO/static/css/eno-theme.css`
- Modify: `/home/svend/ENO/static/js/eno-app.js`

**Sendes via bridge til claude_implementer.**

- [ ] **Step 1: Database — kopier tabeller + seed til ENO**

Samme ALTER + CREATE TABLE statements som Task 1, men i ENO's `scripts/init_db.py`.

Seed data for ENO:

```python
panel_subgroups_seed = [
    ("sg_periodic_pipeline", "periodic", "Pipeline", "Pipeline", 1, 1),
    ("sg_periodic_brainstorm", "periodic", "Brainstorm", "Brainstorm", 2, 1),
    ("sg_periodic_nightrun", "periodic", "Nightrun", "Nightrun", 3, 1),
]

panel_subgroup_mappings_seed = [
    ("lbl_panel_pipeline_projects", "sg_periodic_pipeline"),
    ("lbl_panel_brainstorm_projects", "sg_periodic_brainstorm"),
    ("lbl_panel_nightrun", "sg_periodic_nightrun"),
]
```

- [ ] **Step 2: API — kopier endpoints til ENO's app.py**

Samme GET /api/panel-structure og POST /api/panel-structure/subgroup-state som Task 2, men i ENO's `app.py`.

- [ ] **Step 3: CSS — kopier panel-subgroup klasser til ENO**

Samme CSS som Task 3, men i ENO's `static/css/eno-theme.css`.

- [ ] **Step 4: JS — kopier buildPanelStructure() til ENO**

Samme JS som Task 4, men i ENO's `static/js/eno-app.js`. Erstat ENO's nuværende `loadPanelGroupStates()`/`applyPanelGroupStates()`/`initPanelGroupToggles()`.

- [ ] **Step 5: Validering**

```bash
python3 -m py_compile scripts/init_db.py && python3 -m py_compile app.py
node --check static/js/eno-app.js
grep -RIn "innerHTML" static/js/eno-app.js
```

- [ ] **Step 6: Commit (af architect efter review)**

---

### Task 7: Integrationstest + NEXT_CONTEXT opdatering (CLOUD)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/docs/governance-templates/11_NEXT_CONTEXT.md`

**Udføres af claude_architect.**

- [ ] **Step 1: Start DPMtF-WebUI og verificer**

```bash
# Genstart server (kræver human approval)
fuser -k 9130/tcp
uvicorn app:app --host 0.0.0.0 --port 9130 &

# Test API
curl http://localhost:9130/api/panel-structure?locale=da-DK
# Expected: JSON med 5 grupper, journals is_visible=false,
#           periodic har 3 subgroups med danske titler
```

- [ ] **Step 2: Visuel verifikation i browser**

Åbn http://localhost:9130/ og verificer:
- [ ] Journals panel-group er skjult
- [ ] Periodic har 3 subgroups (Fase, Planlægning, Eksisterende Projekter)
- [ ] Subgroups kan expand/collapse
- [ ] Phase Status er under "Fase"
- [ ] New Project Planning er under "Planlægning"
- [ ] Andre grupper (Daily, Reports, Setup) viser paneler fladt (ingen subgroups defineret)

- [ ] **Step 3: Opdater NEXT_CONTEXT.md**

Dokumenter implementationen og sæt næste fase.

- [ ] **Step 4: Commit**

---

## Verifikation

Efter alle tasks er gennemført:

1. `python3 -m py_compile app.py` — DPMtF ✅
2. `python3 -m py_compile scripts/init_db.py` — DPMtF ✅
3. `node --check static/js/dpmtf-app.js` — DPMtF ✅
4. `grep -RIn "innerHTML" static/js/dpmtf-app.js` — kun præeksisterende ✅
5. `python3 -m py_compile app.py` — ENO ✅
6. `python3 -m py_compile scripts/init_db.py` — ENO ✅
7. `node --check static/js/eno-app.js` — ENO ✅
8. Visuel test: Journals skjult, Periodic subgroups fungerer i begge projekter
