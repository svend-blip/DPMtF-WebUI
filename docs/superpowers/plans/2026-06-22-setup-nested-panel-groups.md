# Setup Nested Panel Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gøre de 6 sektioner i Setup-gruppen til nestede `<section class="panel-group">` elementer med uafhængig expand/collapse state persistent via `/api/user-panel-groups`.

**Architecture:** Genbruger eksisterende `.panel-group` CSS pattern (dpmtf-theme.css:367-410) og JS toggle handler (dpmtf-app.js:255-278). Tilføjer nestede panel groups som `<section class="panel-group">` med egen header/body/toggle. State gemmes via eksisterende POST /api/user-panel-groups endpoint — udvides til at acceptere subgroup keys.

**Tech Stack:** HTML, JavaScript (vanilla), SQLite seed data (init_db.py)

## Global Constraints

- NO innerHTML for dynamic content — use textContent, createElement(), etc.
- ALL user-facing text MUST use lbl(key, fallback) — no hardcoded strings in DOM
- Parameterized SQL only — ? placeholders, never f-strings/concatenation in SQL
- DO NOT COMMIT. Leave all changes unstaged.
- Dark theme (GitHub-dark palette). No light-theme colors.
- All code and comments MUST be in English (en-US).

---

# PLAN BREAKDOWN — 3 handoffs

This plan is split into **3 BridgeV002 handoffs** because they are independently testable units:
1. **HTML structure** — pure structural change, visually verifiable
2. **JS toggle listeners + state persistence** — logic + API changes
3. **DB seed data** — text slot seed for 6 new labels

---

## Handoff A: HTML Structure Changes (handoff #A)

### Affected Files
- **Modify:** `templates/index.html` lines 66–130

### Task: Wrap 6 flat sections as nested panel groups

#### Step 1: Replace flat sections with nested panel-group structure

Find lines 72–130 (the `<div class="panel-group-body">` inside `#pg-setup`) and replace entirely:

**Current (flat):**
```html
<div class="panel-group-body">
    <button id="system-setup-btn" type="button" data-slot="lbl_btn_system_setup">System Setup</button>
    <div id="system-setup-drawer" class="drawer">
        <div id="drawer-content"></div>
    </div>

    <!-- Bridge Setup -->
    <section id="bridge-setup-section"> ... </section>
    <section id="bridge-steps-section"> ... </section>
    <section id="bridge-roles-section"> ... </section>
    <section id="bridge-conventions-section"> ... </section>
    <section id="bridge-export-section"> ... </section>

    <section id="db-status-section"> ... </section>
</div>
```

**New (nested panel groups):**
```html
<div class="panel-group-body">
    <button id="system-setup-btn" type="button" data-slot="lbl_btn_system_setup">System Setup</button>
    <div id="system-setup-drawer" class="drawer">
        <div id="drawer-content"></div>
    </div>

    <!-- Subgroup: Bridge Setup -->
    <section class="panel-group" id="pg-bridge-setup" data-group="bridge-setup">
        <div class="panel-group-header" data-group="bridge-setup">
            <h2 data-slot="pg_bridge_setup">🌉 Bro-setup</h2>
            <span class="panel-group-toggle">▼</span>
        </div>
        <div class="panel-group-body">
            <!-- bridge-flows-section (existing, unchanged) -->
            <!-- bridge-steps-section (existing, unchanged) -->
            <!-- bridge-roles-section (existing, unchanged) -->
            <!-- bridge-conventions-section (existing, unchanged) -->
            <!-- bridge-export-section (existing, unchanged) -->
        </div>
    </section>

    <!-- Subgroup: Steps -->
    <section class="panel-group" id="pg-steps" data-group="steps">
        <div class="panel-group-header" data-group="steps">
            <h2 data-slot="pg_steps">🔧 Trin</h2>
            <span class="panel-group-toggle">▼</span>
        </div>
        <div class="panel-group-body">
            <section id="bridge-steps-section"> ... </section>
        </div>
    </section>

    <!-- Subgroup: Roles -->
    <section class="panel-group" id="pg-roles" data-group="roles">
        <div class="panel-group-header" data-group="roles">
            <h2 data-slot="pg_roles">👤 Roller</h2>
            <span class="panel-group-toggle">▼</span>
        </div>
        <div class="panel-group-body">
            <section id="bridge-roles-section"> ... </section>
        </div>
    </section>

    <!-- Subgroup: Conventions -->
    <section class="panel-group" id="pg-conventions" data-group="conventions">
        <div class="panel-group-header" data-group="conventions">
            <h2 data-slot="pg_conventions">📐 Konventioner</h2>
            <span class="panel-group-toggle">▼</span>
        </div>
        <div class="panel-group-body">
            <section id="bridge-conventions-section"> ... </section>
        </div>
    </section>

    <!-- Subgroup: Export -->
    <section class="panel-group" id="pg-export" data-group="export">
        <div class="panel-group-header" data-group="export">
            <h2 data-slot="pg_export">📦 Eksport</h2>
            <span class="panel-group-toggle">▼</span>
        </div>
        <div class="panel-group-body">
            <section id="bridge-export-section"> ... </section>
        </div>
    </section>

    <!-- Subgroup: Database Status -->
    <section class="panel-group" id="pg-db-status" data-group="db-status">
        <div class="panel-group-header" data-group="db-status">
            <h2 data-slot="pg_db_status">🗄 Database Status</h2>
            <span class="panel-group-toggle">▼</span>
        </div>
        <div class="panel-group-body">
            <section id="db-status-section"> ... </section>
        </div>
    </section>

</div>
```

**Nøgleændringer:**
- 5 `<section>` elementer (bridge-flows/steps/roles/conventions/export) flyttes fra `#pg-setup > .panel-group-body` ind i `#pg-bridge-setup > .panel-group-body`
- Alle 6 sektioner får: `class="panel-group"`, `data-group="<key>"`, header med toggle, og body wrapper
- Headers bruger `data-slot` (ikke hardcoded tekst) — lbl() loads ved runtime
- `system-setup-btn` og drawer bevares øverst i `.panel-group-body`

#### Step 2: Verify HTML structure

```bash
grep -n 'class="panel-group"' templates/index.html | wc -l  # should be 11 (5 top + 6 nested)
grep -RIn "innerHTML" templates/ static/  # must return empty
```

---

## Handoff B: JS Toggle Listeners + State Persistence (handoff #B)

### Affected Files
- **Modify:** `static/js/dpmtf-app.js` — add toggle handlers + state restore for subgroups
- **Modify:** `app.py` line 904 — expand VALID_PANEL_GROUPS to include subgroup keys

### Task: Wire up toggle listeners and state persistence for nested panel groups

#### Step 1: Expand VALID_PANEL_GROUPS in app.py

Find line 904 in app.py:
```python
VALID_PANEL_GROUPS = {"daily", "journals", "reports", "periodic", "setup"}
```

Add subgroup keys:
```python
VALID_PANEL_GROUPS = {
    "daily", "journals", "reports", "periodic", "setup",
    # Subgroups (nested inside pg-setup)
    "bridge-setup", "steps", "roles", "conventions", "export", "db-status",
}
```

This allows `/api/user-panel-groups` POST to accept subgroup group names.

#### Step 2: Add toggle handler for nested panel groups in dpmtf-app.js

After the existing `initPanelGroupToggles()` function (around line 278), add a new function that binds toggle handlers specifically for the subgroup panels:

```javascript
// ── Nested Panel Group Toggles (Setup subgroups) ─────────────
function initSubgroupPanelToggles() {
  var headers = document.querySelectorAll("#pg-setup .panel-group-header");
  for (var i = 0; i < headers.length; i++) {
    headers[i].addEventListener("click", function () {
      var groupKey = this.getAttribute("data-group");
      var pg = document.getElementById("pg-" + groupKey);
      if (!pg) return;

      // Toggle collapsed state
      var isCollapsed = pg.classList.contains("collapsed");
      var newState = isCollapsed ? "expanded" : "collapsed";

      // Update UI
      if (newState === "collapsed") {
        pg.classList.add("collapsed");
        var body = pg.querySelector(".panel-group-body");
        if (body) body.style.display = "none";
        var toggle = pg.querySelector(".panel-group-toggle");
        if (toggle) toggle.textContent = "▶"; // ▶
      } else {
        pg.classList.remove("collapsed");
        var body = pg.querySelector(".panel-group-body");
        if (body) body.style.display = "";
        var toggle = pg.querySelector(".panel-group-toggle");
        if (toggle) toggle.textContent = "▼"; // ▼
      }

      // Persist state via existing API
      fetch("/api/user-panel-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_name: groupKey, state: newState }),
      }).catch(function (err) {
        console.warn("Failed to save subgroup state for '" + groupKey + "':", err.message);
      });
    });
  }
}
```

#### Step 3: Add state restore after page load

In the DOMContentLoaded handler, find where `buildPanelStructure()` is called. After it completes, call a new function to restore subgroup states:

```javascript
function restoreSubgroupStates(callback) {
  fetch("/api/user-panel-groups")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var groups = data.groups || {};
      var subgroups = document.querySelectorAll("#pg-setup > .panel-group");
      for (var i = 0; i < subgroups.length; i++) {
        var pg = subgroups[i];
        var key = pg.dataset.group;
        var groupInfo = groups[key] || { state: "expanded" };
        if (groupInfo.state === "collapsed") {
          pg.classList.add("collapsed");
          var body = pg.querySelector(".panel-group-body");
          if (body) body.style.display = "none";
          var toggle = pg.querySelector(".panel-group-toggle");
          if (toggle) toggle.textContent = "▶"; // ▶
        }
      }
      if (callback) callback();
    })
    .catch(function (err) {
      console.warn("Failed to restore subgroup states:", err.message);
      if (callback) callback();
    });
}
```

#### Step 4: Wire into existing lifecycle

In the `DOMContentLoaded` handler, after `buildPanelStructure()` and before any UI rendering that depends on visibility, call `restoreSubgroupStates()`:

```javascript
// After buildPanelStructure(), before render:
buildPanelStructure(function () {
  restoreSubgroupStates();
});
```

**Note:** Check if `buildPanelStructure` accepts a callback. If not, chain after its execution:
```javascript
buildPanelStructure();
restoreSubgroupStates();
```

#### Step 5: Call initSubgroupPanelToggles() in lifecycle

In the DOMContentLoaded handler, add:
```javascript
initSubgroupPanelToggles();
```

### Validation for Handoff B

```bash
node --check static/js/dpmtf-app.js && echo "JS syntax OK"
python3 -m py_compile app.py && echo "app.py OK"
grep -n '"bridge-setup"' app.py  # verify VALID_PANEL_GROUPS was expanded
```

---

## Handoff C: DB Seed Data (handoff #C)

### Affected Files
- **Modify:** `scripts/init_db.py` — add seed data for 6 new UI text slots + labels + translations

### Task: Seed text slots and labels for 6 new panel group headings

Find the existing text slot/label seed section in init_db.py (look for patterns like `pg_daily`, `pg_journals`). Add 6 new entries:

#### Step 1: Insert text slots

For each of the 6 new panel group headings, insert into `ui_text_slots`:

```sql
INSERT OR IGNORE INTO ui_text_slots (slot_key) VALUES ('pg_bridge_setup');
INSERT OR IGNORE INTO ui_text_slots (slot_key) VALUES ('pg_steps');
INSERT OR IGNORE INTO ui_text_slots (slot_key) VALUES ('pg_roles');
INSERT OR IGNORE INTO ui_text_slots (slot_key) VALUES ('pg_conventions');
INSERT OR IGNORE INTO ui_text_slots (slot_key) VALUES ('pg_export');
INSERT OR IGNORE INTO ui_text_slots (slot_key) VALUES ('pg_db_status');
```

#### Step 2: Insert slot-to-label mappings

```sql
INSERT OR IGNORE INTO ui_text_slot_labels (slot_id, ui_label_id, locale_code)
SELECT ts.id, ul.id, 'da-DK'
FROM ui_text_slots ts
JOIN ui_labels ul ON ul.slot_key = ts.slot_key
WHERE ts.slot_key IN ('pg_bridge_setup','pg_steps','pg_roles','pg_conventions','pg_export','pg_db_status');

INSERT OR IGNORE INTO ui_text_slot_labels (slot_id, ui_label_id, locale_code)
SELECT ts.id, ul.id, 'en-US'
FROM ui_text_slots ts
JOIN ui_labels ul ON ul.slot_key = ts.slot_key
WHERE ts.slot_key IN ('pg_bridge_setup','pg_steps','pg_roles','pg_conventions','pg_export','pg_db_status');
```

#### Step 3: Insert labels + translations

For each slot, this requires: (1) insert into `ui_labels`, (2) insert da-DK translation, (3) insert en-US translation. Pattern (follow existing seed patterns in init_db.py):

```sql
-- pg_bridge_setup
INSERT OR IGNORE INTO ui_labels (slot_key, label_text_da, label_text_en)
VALUES ('pg_bridge_setup', 'Bro-setup', 'Bridge Setup');

INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'da-DK', '🌉 Bro-setup' FROM ui_labels ul WHERE ul.slot_key = 'pg_bridge_setup';

INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'en-US', '🌉 Bridge Setup' FROM ui_labels ul WHERE ul.slot_key = 'pg_bridge_setup';

-- pg_steps
INSERT OR IGNORE INTO ui_labels (slot_key, label_text_da, label_text_en)
VALUES ('pg_steps', 'Trin', 'Steps');
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'da-DK', '🔧 Trin' FROM ui_labels ul WHERE ul.slot_key = 'pg_steps';
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'en-US', '🔧 Steps' FROM ui_labels ul WHERE ul.slot_key = 'pg_steps';

-- pg_roles
INSERT OR IGNORE INTO ui_labels (slot_key, label_text_da, label_text_en)
VALUES ('pg_roles', 'Roller', 'Roles');
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'da-DK', '👤 Roller' FROM ui_labels ul WHERE ul.slot_key = 'pg_roles';
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'en-US', '👤 Roles' FROM ui_labels ul WHERE ul.slot_key = 'pg_roles';

-- pg_conventions
INSERT OR IGNORE INTO ui_labels (slot_key, label_text_da, label_text_en)
VALUES ('pg_conventions', 'Konventioner', 'Conventions');
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'da-DK', '📐 Konventioner' FROM ui_labels ul WHERE ul.slot_key = 'pg_conventions';
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'en-US', '📐 Conventions' FROM ui_labels ul WHERE ul.slot_key = 'pg_conventions';

-- pg_export
INSERT OR IGNORE INTO ui_labels (slot_key, label_text_da, label_text_en)
VALUES ('pg_export', 'Eksport', 'Export');
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'da-DK', '📦 Eksport' FROM ui_labels ul WHERE ul.slot_key = 'pg_export';
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'en-US', '📦 Export' FROM ui_labels ul WHERE ul.slot_key = 'pg_export';

-- pg_db_status
INSERT OR IGNORE INTO ui_labels (slot_key, label_text_da, label_text_en)
VALUES ('pg_db_status', 'Database Status', 'Database Status');
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'da-DK', '🗄 Database Status' FROM ui_labels ul WHERE ul.slot_key = 'pg_db_status';
INSERT OR IGNORE INTO ui_label_translations (ui_label_id, locale_code, default_text)
SELECT ul.id, 'en-US', '🗄 Database Status' FROM ui_labels ul WHERE ul.slot_key = 'pg_db_status';
```

### Validation for Handoff C

```bash
python3 -m py_compile scripts/init_db.py && echo "init_db.py OK"
# Verify seed runs idempotent:
python3 scripts/init_db.py 2>&1 | head -5
```

---

## End-to-End Verification (all handoffs complete)

```bash
# 1. No new innerHTML
grep -RIn "innerHTML" static/ templates/  # must return empty

# 2. JS syntax OK
node --check static/js/dpmtf-app.js && echo "dpmtf-app.js OK"

# 3. Python syntax OK
python3 -m py_compile app.py && echo "app.py OK"
python3 -m py_compile scripts/init_db.py && echo "init_db.py OK"

# 4. Diff scope check
git diff --stat

# 5. Panel groups count in HTML
grep -n 'class="panel-group"' templates/index.html | wc -l  # should be 11

# 6. Subgroup data-groups are unique
grep 'data-group=' templates/index.html | sort -u | wc -l  # should match total groups

# 7. Server health
curl -s http://localhost:9130/api/health
```
