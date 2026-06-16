# Accelerated WebUI Factory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `initialize_new_webui.py` script + 8 skeleton files that enable rapid creation of new DPMtF-governed WebUI projects in ~2 minutes.

**Architecture:** Skeleton files in `templates/new-webui-skeleton/` use `{PLACEHOLDER}` tokens. Init script copies skeletons, replaces placeholders, creates venv, initializes database, and verifies health endpoint. Prompt Compiler integration already exists — only the knowledge fragment needs updating.

**Tech Stack:** Python 3.12 (FastAPI, uvicorn, sqlite3, argparse), JavaScript (vanilla, no framework), CSS (GitHub-dark palette)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `templates/new-webui-skeleton/.env` | Create | Secrets template with placeholders |
| `templates/new-webui-skeleton/requirements.txt` | Create | Python dependencies |
| `templates/new-webui-skeleton/dpmtf.ini` | Create | App-config with placeholders |
| `templates/new-webui-skeleton/config.py` | Create | Config getters (copy of DPMtF-WebUI's) |
| `templates/new-webui-skeleton/static/css/theme.css` | Create | Dark theme — panel groups, subgroups, forms, badges |
| `templates/new-webui-skeleton/templates/index.html` | Create | 5 empty panel groups with headers + toggles |
| `templates/new-webui-skeleton/static/js/app.js` | Create | Core infrastructure: lbl(), panel structure, expand/collapse, language switcher |
| `templates/new-webui-skeleton/app.py` | Create | Minimal FastAPI: health, ui-labels, available-languages, panel-structure, subgroup-state, static mount |
| `templates/new-webui-skeleton/scripts/init_db.py` | Create | 6 essential tables + seed labels in da-DK + en-US |
| `scripts/initialize_new_webui.py` | Create | Init script: argparse → validate → mkdir → copy → replace → venv → pip → init_db → verify |
| `docs/governance-templates-v2/knowledge-fragments/patterns/create-new-webui.md` | Modify | Add accelerated path section referencing init script |

---

### Task 1: Create skeleton directory and static config files

**Files:**
- Create: `templates/new-webui-skeleton/.env`
- Create: `templates/new-webui-skeleton/requirements.txt`
- Create: `templates/new-webui-skeleton/dpmtf.ini`

- [ ] **Step 1: Create skeleton directory structure**

```bash
mkdir -p templates/new-webui-skeleton/{templates,static/{js,css},scripts}
```

- [ ] **Step 2: Create requirements.txt**

Write `templates/new-webui-skeleton/requirements.txt`:

```
fastapi
uvicorn
python-dotenv
```

Note: no version pins — child project pins its own versions.

- [ ] **Step 3: Create .env template**

Write `templates/new-webui-skeleton/.env`:

```
# Environment variables for {PROJECT_NAME}
# NEVER commit this file — add to .gitignore

DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
DPMTF_IMPLEMENTER_SESSION=claude_implementer
DPMTF_REVIEW_SESSION=claude_review
DPMTF_ARCHITECT_SESSION=claude_architect
```

- [ ] **Step 4: Create dpmtf.ini template**

Write `templates/new-webui-skeleton/dpmtf.ini`:

```ini
[app]
port = {PORT}
host = 0.0.0.0
default_locale = en-US

[database]
path = databases/{DATABASE}

[paths]
project_root = {PROJECT_ROOT}
bridge_dir = /home/svend/claude-bridge
governance_dir = docs/dpmtf
log_dir = logs
exports_dir = exports

[projects]
father_project = DPMtF-WebUI
child_projects =
reference_projects =
```

- [ ] **Step 5: Commit**

```bash
git add templates/new-webui-skeleton/.env templates/new-webui-skeleton/requirements.txt templates/new-webui-skeleton/dpmtf.ini
git commit -m "feat: Spor C — skeleton static config files (.env, requirements.txt, dpmtf.ini)"
```

---

### Task 2: Create skeleton config.py

**Files:**
- Create: `templates/new-webui-skeleton/config.py`

- [ ] **Step 1: Write config.py**

Write `templates/new-webui-skeleton/config.py`:

```python
"""Central configuration for {PROJECT_NAME}.

Single source of truth for all configurable values.
Paths, ports, model names, project references MUST come from here.
Hardcoding /home/svend/... anywhere else is an auto-fail in validation.

Sources (in priority order):
1. Environment variables (secrets, infrastructure)
2. dpmtf.ini (app-config)
3. Hardcoded fallbacks (last resort, for development only)
"""

import os
import configparser
from pathlib import Path

# ── .env loading ────────────────────────────────────────────────

def _load_env():
    """Load .env file into os.environ. Manual loader — no dependencies."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

_load_env()

# ── .ini loading ────────────────────────────────────────────────

_ini_path = Path(__file__).resolve().parent / "dpmtf.ini"
_config = configparser.ConfigParser()
if _ini_path.exists():
    _config.read(_ini_path, encoding="utf-8")

# ── Getter functions ────────────────────────────────────────────

def get_db_path() -> str:
    """Database path. .ini [database] path, or fallback."""
    return _config.get("database", "path", fallback="databases/{DATABASE}")

def get_bridge_dir() -> str:
    """Bridge directory. Env var DPMTF_BRIDGE_DIR, or .ini [paths] bridge_dir, or fallback."""
    env = os.environ.get("DPMTF_BRIDGE_DIR")
    if env:
        return env
    return _config.get("paths", "bridge_dir", fallback="/home/svend/claude-bridge")

def get_project_root() -> str:
    """Project root directory. .ini [paths] project_root, or derived from this file's location."""
    configured = _config.get("paths", "project_root", fallback=None)
    if configured:
        return configured
    return str(Path(__file__).resolve().parent)

def get_governance_dir() -> str:
    """Governance docs directory (relative to project root)."""
    return _config.get("paths", "governance_dir", fallback="docs/dpmtf")

def get_governance_dir_abs() -> str:
    """Governance docs directory (absolute path)."""
    return str(Path(get_project_root()) / get_governance_dir())

def get_father_project() -> str:
    """Father project name."""
    return _config.get("projects", "father_project", fallback="DPMtF-WebUI")

def get_child_projects() -> list:
    """Child project names (comma-separated in .ini)."""
    raw = _config.get("projects", "child_projects", fallback="")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_reference_projects() -> list:
    """Reference project names (comma-separated in .ini)."""
    raw = _config.get("projects", "reference_projects", fallback="")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_port() -> int:
    """Server port."""
    return _config.getint("app", "port", fallback={PORT})

def get_host() -> str:
    """Server host."""
    return _config.get("app", "host", fallback="0.0.0.0")

def get_default_locale() -> str:
    """Default locale for i18n."""
    return _config.get("app", "default_locale", fallback="en-US")

def get_log_dir() -> str:
    """Log directory (relative to project root)."""
    return _config.get("paths", "log_dir", fallback="logs")

def get_exports_dir() -> str:
    """Exports directory (relative to project root)."""
    return _config.get("paths", "exports_dir", fallback="exports")

# ── Bridge session names (env vars with defaults) ───────────────

def get_review_session() -> str:
    return os.environ.get("DPMTF_REVIEW_SESSION", "claude_review")

def get_implementer_session() -> str:
    return os.environ.get("DPMTF_IMPLEMENTER_SESSION", "claude_implementer")

def get_architect_session() -> str:
    return os.environ.get("DPMTF_ARCHITECT_SESSION", "claude_architect")
```

Note: `{PORT}` in `get_port()` fallback is an integer placeholder — the init script replaces it with the actual port number (no quotes). `{DATABASE}` in `get_db_path()` fallback is a string placeholder.

- [ ] **Step 2: Commit**

```bash
git add templates/new-webui-skeleton/config.py
git commit -m "feat: Spor C — skeleton config.py with placeholder system"
```

---

### Task 3: Create skeleton theme.css

**Files:**
- Create: `templates/new-webui-skeleton/static/css/theme.css`

- [ ] **Step 1: Write theme.css**

Write `templates/new-webui-skeleton/static/css/theme.css`:

```css
/* ── Base ─────────────────────────────────────────── */
body {
  background: #0d1117;
  color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  margin: 0;
  padding: 0;
}
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

/* ── Header row & language selector ────────────────── */
.header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}
.header-row h1 { margin-bottom: 0; }
.lang-selector {
    display: flex;
    align-items: center;
    gap: 6px;
}
.lang-label {
    font-size: 0.8rem;
    color: #8b949e;
}
.lang-selector select {
    padding: 4px 8px;
    border: 1px solid #30363d;
    border-radius: 4px;
    font-size: 0.85rem;
    background: #21262d;
    color: #c9d1d9;
    cursor: pointer;
}
.lang-selector select:focus {
    outline: none;
    border-color: #58a6ff;
}

/* ── Headings ─────────────────────────────────────── */
h1 { color: #e6edf3; font-size: 1.6em; margin: 0 0 8px 0; }
h2 { color: #e6edf3; font-size: 1.2em; border-bottom: 1px solid #30363d; padding-bottom: 8px; margin: 24px 0 12px 0; }
h3 { color: #e6edf3; font-size: 1.0em; margin: 0 0 8px 0; }
h4 { color: #8b949e; font-size: 0.9em; margin: 12px 0 6px 0; }

/* ── Cards ────────────────────────────────────────── */
.dpmtf-card {
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}

/* ── Grid ─────────────────────────────────────────── */
.dpmtf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

/* ── Tables ───────────────────────────────────────── */
.dpmtf-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}
.dpmtf-table th {
  text-align: left;
  color: #8b949e;
  font-weight: 600;
  font-size: 0.85em;
  padding: 8px 10px;
  border-bottom: 1px solid #30363d;
}
.dpmtf-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #21262d;
  color: #e6edf3;
  font-size: 0.9em;
}
.dpmtf-table tr:hover td { background: #1c2128; }

/* ── Buttons ──────────────────────────────────────── */
.dpmtf-btn {
  background: #21262d;
  color: #c9d1d9;
  border: 1px solid #30363d;
  padding: 5px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
  transition: background 0.15s;
}
.dpmtf-btn:hover { background: #30363d; }
.dpmtf-btn-primary {
  background: #238636;
  color: #fff;
  border-color: #238636;
}
.dpmtf-btn-primary:hover { background: #2ea043; }
.dpmtf-btn-danger {
  background: #da3633;
  color: #fff;
  border-color: #da3633;
}
.dpmtf-btn-danger:hover { background: #f85149; }

/* ── Form elements ────────────────────────────────── */
.dpmtf-input, .dpmtf-select, .dpmtf-textarea {
  background: #0d1117;
  color: #e6edf3;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 0.9em;
  width: 100%;
  box-sizing: border-box;
  margin: 4px 0 10px 0;
}
.dpmtf-input:focus, .dpmtf-select:focus, .dpmtf-textarea:focus {
  border-color: #58a6ff;
  outline: none;
}
.dpmtf-textarea { min-height: 80px; resize: vertical; }
.dpmtf-label {
  color: #8b949e;
  font-size: 0.85em;
  display: block;
  margin-top: 8px;
}

/* ── Status badges ────────────────────────────────── */
.dpmtf-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75em;
  font-weight: 600;
}
.dpmtf-badge-success { background: #238636; color: #fff; }
.dpmtf-badge-warning { background: #9e6a03; color: #fff; }
.dpmtf-badge-danger { background: #da3633; color: #fff; }
.dpmtf-badge-info { background: #1f6feb; color: #fff; }

/* ── Utility ──────────────────────────────────────── */
.dpmtf-muted { color: #8b949e; font-size: 0.85em; }
.dpmtf-small { font-size: 0.8em; }
.dpmtf-error { color: #da3633; }
.dpmtf-success { color: #3fb950; }
.dpmtf-loading { color: #8b949e; font-style: italic; }
.dpmtf-hidden { display: none !important; }

/* ── Panel Groups (collapse/expand) ─────────────────── */
.panel-group {
    margin-bottom: 16px;
    border: 1px solid #30363d;
    border-radius: 8px;
    overflow: hidden;
}
.panel-group-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    cursor: pointer;
    user-select: none;
    background: #161b22;
}
.panel-group-header:hover { background: #1c2129; }
.panel-group-header h2 {
    font-size: 1.1rem;
    margin: 0;
    color: #e6edf3;
}
.panel-group-toggle {
    font-size: 0.8rem;
    color: #8b949e;
}
.panel-group-body {
    padding: 10px 14px;
    border-top: 1px solid #30363d;
    background: #0d1117;
}
.panel-group.collapsed .panel-group-body { display: none; }

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
.panel-subgroup-header:hover { background: #1c2129; }
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
.panel-subgroup.collapsed .panel-subgroup-body { display: none; }
.panel-subgroup-all .panel-subgroup-header { display: none; }
.panel-group.dpmtf-hidden { display: none; }
```

This is the full DPMtF theme minus DPMtF-specific elements (hitrate colors, model badges, complexity tiers, capture badges, execution status badges, drawer, system-setup button, template detail panel). Those are added by implementer when needed.

- [ ] **Step 2: Commit**

```bash
git add templates/new-webui-skeleton/static/css/theme.css
git commit -m "feat: Spor C — skeleton theme.css (GitHub-dark, panel groups, subgroups)"
```

---

### Task 4: Create skeleton index.html

**Files:**
- Create: `templates/new-webui-skeleton/templates/index.html`

- [ ] **Step 1: Write index.html**

Write `templates/new-webui-skeleton/templates/index.html`:

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
                <select id="lang-dropdown">
                    <!-- Populated dynamically from /api/available-languages -->
                </select>
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

- [ ] **Step 2: Commit**

```bash
git add templates/new-webui-skeleton/templates/index.html
git commit -m "feat: Spor C — skeleton index.html (5 empty panel groups)"
```

---

### Task 5: Create skeleton app.js

**Files:**
- Create: `templates/new-webui-skeleton/static/js/app.js`

- [ ] **Step 1: Write app.js — Part 1: Utilities and i18n**

Write `templates/new-webui-skeleton/static/js/app.js`:

```javascript
/* ── {PROJECT_NAME} — Core Frontend Infrastructure ────
 *
 * Provides the database-driven panel system that every
 * DPMtF-governed WebUI needs:
 *   - lbl() i18n helper (4-layer architecture)
 *   - el() safe DOM creation (no innerHTML)
 *   - Panel structure: visibility, expand/collapse, subgroups
 *   - Language switcher
 *
 * Domain-specific panel loading functions are added by
 * the implementer for each project.
 */

/* ── 1. Utilities ──────────────────────────────────── */

function el(tag, className, text) {
  var e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function escapeHtml(str) {
  var div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/* ── 2. i18n ────────────────────────────────────────── */

var currentLocale = "en-US";
var labelMap = {};

function lbl(key, fallback) {
  if (labelMap[key]) return labelMap[key];
  return fallback || key;
}

function loadLabels(locale) {
  return fetch("/api/ui-labels/main?locale=" + encodeURIComponent(locale))
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      labelMap = data.labels || {};
      // Update all data-slot elements
      document.querySelectorAll("[data-slot]").forEach(function (el) {
        var key = el.getAttribute("data-slot");
        if (labelMap[key]) el.textContent = labelMap[key];
      });
    });
}

function switchLanguage(locale) {
  currentLocale = locale;
  document.querySelector("meta[name='locale']").setAttribute("content", locale);
  loadLabels(locale)
    .then(function () {
      // Re-render panel structure with new locale
      loadPanelStructure();
    })
    .catch(function (err) {
      console.warn("Failed to switch language:", err.message);
    });
}

function loadLanguageDropdown() {
  fetch("/api/available-languages")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var select = document.getElementById("lang-dropdown");
      if (!select) return;
      select.innerHTML = "";
      (data.languages || []).forEach(function (lang) {
        var opt = document.createElement("option");
        opt.value = lang.locale;
        opt.textContent = lang.label;
        if (lang.locale === currentLocale) opt.selected = true;
        select.appendChild(opt);
      });
      select.addEventListener("change", function () {
        switchLanguage(this.value);
      });
    })
    .catch(function (err) {
      console.warn("Failed to load languages:", err.message);
    });
}

/* ── 3. Panel Structure ────────────────────────────── */

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
      // Fallback: render with defaults if API unavailable
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

    // Hide invisible groups
    if (!info.is_visible) {
      pg.classList.add("dpmtf-hidden");
      continue;
    }
    pg.classList.remove("dpmtf-hidden");

    // Set group collapse state
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

    // Build subgroups inside body
    if (body) buildSubgroups(body, gn, info.subgroups);
  }
}

function buildSubgroups(body, groupName, subgroups) {
  // Move panels back to body before removing subgroups (don't delete panels)
  var existing = body.querySelectorAll(".panel-subgroup");
  for (var i = 0; i < existing.length; i++) {
    var sgBody = existing[i].querySelector(".panel-subgroup-body");
    if (sgBody) {
      while (sgBody.firstChild) {
        body.appendChild(sgBody.firstChild);
      }
    }
    existing[i].remove();
  }

  if (!subgroups || !subgroups.length) {
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

    // Move panels into subgroup based on slot mapping
    if (sg.slots && sg.slots.length) {
      for (var k = 0; k < sg.slots.length; k++) {
        var slotKey = sg.slots[k];
        var panel = body.querySelector('[data-slot="' + slotKey + '"]');
        if (panel) {
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
    header.addEventListener("click", (function (subgroupKey, el, bodyEl, toggleEl) {
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
    })(sg.key, sgEl, sgBody, sgToggle));
  }
}

function initPanelGroupToggles() {
  var headers = document.querySelectorAll(".panel-group-header");
  for (var i = 0; i < headers.length; i++) {
    headers[i].addEventListener("click", function () {
      var groupName = this.getAttribute("data-group");
      var pg = document.getElementById("pg-" + groupName);
      if (!pg) return;
      var isCollapsed = pg.classList.contains("collapsed");
      var newState = isCollapsed ? "expanded" : "collapsed";

      if (panelStructure[groupName]) {
        panelStructure[groupName].state = newState;
      }
      buildPanelStructure();

      // Persist group state
      fetch("/api/panel-structure/group-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_name: groupName, state: newState }),
      }).catch(function (err) {
        console.warn("Failed to save group state:", err.message);
      });
    });
  }
}

/* ── 4. Init ────────────────────────────────────────── */

function init() {
  loadLabels(currentLocale)
    .then(function () {
      return loadPanelStructure();
    })
    .then(function () {
      initPanelGroupToggles();
      loadLanguageDropdown();
    })
    .catch(function (err) {
      console.warn("Init error:", err.message);
      // Still try to render with defaults
      buildPanelStructure();
      initPanelGroupToggles();
      loadLanguageDropdown();
    });
}

document.addEventListener("DOMContentLoaded", init);
```

- [ ] **Step 2: Validate JavaScript syntax**

```bash
node --check templates/new-webui-skeleton/static/js/app.js
```

Expected: no output (exit 0).

- [ ] **Step 3: Commit**

```bash
git add templates/new-webui-skeleton/static/js/app.js
git commit -m "feat: Spor C — skeleton app.js (lbl, panel structure, expand/collapse, language switcher)"
```

---

### Task 6: Create skeleton app.py

**Files:**
- Create: `templates/new-webui-skeleton/app.py`

- [ ] **Step 1: Write app.py**

Write `templates/new-webui-skeleton/app.py`:

```python
"""{PROJECT_TITLE} — Minimal FastAPI backend.

Provides the core endpoints every DPMtF-governed WebUI needs:
  - Health check
  - i18n label resolution (4-layer architecture)
  - Available languages
  - Panel structure (visibility, collapse state, subgroups)
  - Static file serving

Domain-specific endpoints are added by the implementer.
"""

import os
import sqlite3
import config
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="{PROJECT_TITLE}")

DB_PATH = config.get_db_path()

# ── Static files ──────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

# Mount after explicit routes to avoid conflicts
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Health ────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    database_exists = os.path.exists(DB_PATH)
    return {
        "status": "healthy" if database_exists else "unhealthy",
        "app": "{PROJECT_TITLE}",
        "database_path": DB_PATH,
        "database_exists": database_exists,
    }


# ── i18n ──────────────────────────────────────────────

def get_ui_labels_for_domain(domain, locale):
    """Resolve labels via 4-layer i18n architecture.
    
    ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations.
    Fallback chain: requested locale → en-US → default_text → label_key.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.slot_key, l.label_key, l.default_text,
               COALESCE(t_en.translation, l.default_text, l.label_key) AS text_en,
               COALESCE(t_req.translation, t_en.translation, l.default_text, l.label_key) AS text_req
        FROM ui_text_slots s
        JOIN ui_text_slot_labels sl ON s.slot_key = sl.slot_key
        JOIN ui_labels l ON sl.label_key = l.label_key
        LEFT JOIN ui_label_translations t_en ON l.label_key = t_en.label_key AND t_en.locale = 'en-US'
        LEFT JOIN ui_label_translations t_req ON l.label_key = t_req.label_key AND t_req.locale = ?
        WHERE sl.label_domain = ?
    """, (locale, domain))
    
    labels = {}
    for row in cursor.fetchall():
        r = dict(row)
        labels[r["slot_key"]] = r["text_req"] if r["text_req"] else r["text_en"]
    
    conn.close()
    return labels


@app.get("/api/ui-labels/{label_domain}")
async def get_ui_labels(label_domain: str, locale: str = "en-US"):
    """Return resolved labels for a domain."""
    labels = get_ui_labels_for_domain(label_domain, locale)
    return {
        "label_domain": label_domain,
        "locale": locale,
        "labels": labels,
    }


@app.get("/api/available-languages")
async def get_available_languages():
    """Return list of available locales from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT locale FROM ui_label_translations
        UNION
        SELECT 'en-US' AS locale
        ORDER BY locale
    """)
    locales = [dict(r)["locale"] for r in cursor.fetchall()]
    conn.close()
    
    # Map locale codes to human-readable labels
    locale_labels = {
        "en-US": "English",
        "da-DK": "Dansk",
        "de-DE": "Deutsch",
        "sv-SE": "Svenska",
    }
    
    return {
        "languages": [
            {"locale": loc, "label": locale_labels.get(loc, loc)}
            for loc in locales
        ]
    }


# ── Panel Structure ───────────────────────────────────

@app.get("/api/panel-structure")
async def get_panel_structure(locale: str = "en-US"):
    """Return full panel hierarchy with subgroups, visibility, and collapse states."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT group_name, state, is_visible FROM user_panel_groups WHERE user_id = 'default'"
    )
    group_rows = {r["group_name"]: r for r in cursor.fetchall()}
    
    cursor.execute(
        "SELECT * FROM panel_subgroups WHERE is_visible = 1 ORDER BY sort_order"
    )
    subgroups = [dict(r) for r in cursor.fetchall()]
    
    # Slot mappings for subgroups
    cursor.execute("SELECT * FROM panel_subgroup_mappings")
    mappings = {}
    for r in cursor.fetchall():
        sg = r["subgroup_key"]
        if sg not in mappings:
            mappings[sg] = []
        mappings[sg].append(r["slot_key"])
    
    # Subgroup collapse states
    cursor.execute(
        "SELECT group_name, state FROM user_panel_groups WHERE user_id = 'default' AND group_name LIKE 'sg_%'"
    )
    subgroup_states = {r["group_name"]: r["state"] for r in cursor.fetchall()}
    
    group_names = ["daily", "journals", "reports", "periodic", "setup"]
    result = {}
    title_field = "title_da" if locale == "da-DK" else "title_en"
    
    for gn in group_names:
        gr = group_rows.get(gn)
        is_visible = gr["is_visible"] if gr else 1
        state = gr["state"] if gr else "expanded"
        
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
            subgroup_list = [{
                "key": f"sg_{gn}_all",
                "title": "",
                "is_visible": True,
                "state": "expanded",
                "slots": [],
            }]
        
        result[gn] = {
            "is_visible": bool(is_visible),
            "state": state,
            "subgroups": subgroup_list,
        }
    
    conn.close()
    return {"groups": result}


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


@app.post("/api/panel-structure/group-state")
async def save_group_state(request: Request):
    """Save collapse state for a panel group."""
    data = await request.json()
    group_name = data.get("group_name")
    state = data.get("state", "expanded")
    
    if not group_name:
        raise HTTPException(status_code=400, detail="group_name required")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
        VALUES ('default', ?, ?, 1, datetime('now'))
    """, (group_name, state))
    conn.commit()
    conn.close()
    return {"status": "saved", "group_name": group_name, "state": state}
```

- [ ] **Step 2: Validate Python syntax**

```bash
python3 -m py_compile templates/new-webui-skeleton/app.py
```

Expected: no output (exit 0).

- [ ] **Step 3: Commit**

```bash
git add templates/new-webui-skeleton/app.py
git commit -m "feat: Spor C — skeleton app.py (health, i18n, panel-structure, static mount)"
```

---

### Task 7: Create skeleton init_db.py

**Files:**
- Create: `templates/new-webui-skeleton/scripts/init_db.py`

- [ ] **Step 1: Write init_db.py — Part 1: Table creation**

Write `templates/new-webui-skeleton/scripts/init_db.py`:

```python
"""{PROJECT_NAME} — Database initialization and seed script.

Creates the 6 essential tables every DPMtF-governed WebUI needs:
  - i18n: ui_text_slots, ui_text_slot_labels, ui_labels, ui_label_translations
  - Panel structure: user_panel_groups, panel_subgroups, panel_subgroup_mappings

Seeds essential labels in da-DK and en-US locales.
Idempotent — safe to re-run (INSERT OR IGNORE/REPLACE).
"""

import sqlite3
import os

DB_PATH = "databases/{DATABASE}"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ── i18n Tables ───────────────────────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_text_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_text_slot_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT NOT NULL,
    label_key TEXT NOT NULL,
    label_domain TEXT NOT NULL DEFAULT 'main',
    UNIQUE(slot_key, label_key)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_key TEXT UNIQUE NOT NULL,
    default_text TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_label_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_key TEXT NOT NULL,
    locale TEXT NOT NULL,
    translation TEXT NOT NULL,
    UNIQUE(label_key, locale)
)
""")

# ── Panel Structure Tables ────────────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_panel_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    group_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'expanded',
    is_visible INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, group_name)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subgroup_key TEXT UNIQUE NOT NULL,
    group_name TEXT NOT NULL,
    title_en TEXT NOT NULL DEFAULT '',
    title_da TEXT NOT NULL DEFAULT '',
    is_visible INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroup_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subgroup_key TEXT NOT NULL,
    slot_key TEXT NOT NULL,
    UNIQUE(subgroup_key, slot_key)
)
""")
```

- [ ] **Step 2: Write init_db.py — Part 2: Seed data**

Append to `templates/new-webui-skeleton/scripts/init_db.py`:

```python
# ── Seed: UI Labels ───────────────────────────────────

labels_seed = [
    # (label_key, default_text, description)
    ("lbl_page_title", "{PROJECT_TITLE}", "Page title"),
    ("lbl_heading_main", "{PROJECT_TITLE}", "Main heading"),
    ("pg_daily", "📋 Daily", "Daily panel group"),
    ("pg_journals", "📓 Journals", "Journals panel group"),
    ("pg_reports", "📊 Reports", "Reports panel group"),
    ("pg_periodic", "🔄 Periodic", "Periodic panel group"),
    ("pg_setup", "⚙️ Setup", "Setup panel group"),
    ("lbl_status_loading", "Loading...", "Loading status"),
    ("lbl_status_error_prefix", "Error: ", "Error prefix"),
    ("lbl_lang_selector", "Language", "Language selector label"),
]

for label_key, default_text, description in labels_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_labels (label_key, default_text, description)
        VALUES (?, ?, ?)
    """, (label_key, default_text, description))

# ── Seed: Translations ────────────────────────────────

translations_seed = [
    # (label_key, locale, translation)
    # da-DK
    ("lbl_page_title", "da-DK", "{PROJECT_TITLE}"),
    ("lbl_heading_main", "da-DK", "{PROJECT_TITLE}"),
    ("pg_daily", "da-DK", "📋 Daglig"),
    ("pg_journals", "da-DK", "📓 Journaler"),
    ("pg_reports", "da-DK", "📊 Rapporter"),
    ("pg_periodic", "da-DK", "🔄 Periodisk"),
    ("pg_setup", "da-DK", "⚙️ Opsætning"),
    ("lbl_status_loading", "da-DK", "Indlæser..."),
    ("lbl_status_error_prefix", "da-DK", "Fejl: "),
    ("lbl_lang_selector", "da-DK", "Sprog"),
    # de-DE
    ("lbl_page_title", "de-DE", "{PROJECT_TITLE}"),
    ("lbl_heading_main", "de-DE", "{PROJECT_TITLE}"),
    ("pg_daily", "de-DE", "📋 Täglich"),
    ("pg_journals", "de-DE", "📓 Journale"),
    ("pg_reports", "de-DE", "📊 Berichte"),
    ("pg_periodic", "de-DE", "🔄 Periodisch"),
    ("pg_setup", "de-DE", "⚙️ Einrichtung"),
    ("lbl_status_loading", "de-DE", "Laden..."),
    ("lbl_status_error_prefix", "de-DE", "Fehler: "),
    ("lbl_lang_selector", "de-DE", "Sprache"),
    # sv-SE
    ("lbl_page_title", "sv-SE", "{PROJECT_TITLE}"),
    ("lbl_heading_main", "sv-SE", "{PROJECT_TITLE}"),
    ("pg_daily", "sv-SE", "📋 Daglig"),
    ("pg_journals", "sv-SE", "📓 Journaler"),
    ("pg_reports", "sv-SE", "📊 Rapporter"),
    ("pg_periodic", "sv-SE", "🔄 Periodisk"),
    ("pg_setup", "sv-SE", "⚙️ Inställningar"),
    ("lbl_status_loading", "sv-SE", "Laddar..."),
    ("lbl_status_error_prefix", "sv-SE", "Fel: "),
    ("lbl_lang_selector", "sv-SE", "Språk"),
]

for label_key, locale, translation in translations_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_label_translations (label_key, locale, translation)
        VALUES (?, ?, ?)
    """, (label_key, locale, translation))

# ── Seed: Text Slots ──────────────────────────────────

slots_seed = [
    # (slot_key, description)
    ("lbl_page_title", "Page title"),
    ("lbl_heading_main", "Main heading"),
    ("pg_daily", "Daily panel group header"),
    ("pg_journals", "Journals panel group header"),
    ("pg_reports", "Reports panel group header"),
    ("pg_periodic", "Periodic panel group header"),
    ("pg_setup", "Setup panel group header"),
    ("lbl_status_loading", "Loading status text"),
    ("lbl_status_error_prefix", "Error message prefix"),
    ("lbl_lang_selector", "Language selector label"),
]

for slot_key, description in slots_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slots (slot_key, description)
        VALUES (?, ?)
    """, (slot_key, description))

# ── Seed: Slot → Label Mappings ───────────────────────

slot_label_mappings = [
    # (slot_key, label_key, label_domain)
    ("lbl_page_title", "lbl_page_title", "main"),
    ("lbl_heading_main", "lbl_heading_main", "main"),
    ("pg_daily", "pg_daily", "main"),
    ("pg_journals", "pg_journals", "main"),
    ("pg_reports", "pg_reports", "main"),
    ("pg_periodic", "pg_periodic", "main"),
    ("pg_setup", "pg_setup", "main"),
    ("lbl_status_loading", "lbl_status_loading", "main"),
    ("lbl_status_error_prefix", "lbl_status_error_prefix", "main"),
    ("lbl_lang_selector", "lbl_lang_selector", "main"),
]

for slot_key, label_key, domain in slot_label_mappings:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key, label_domain)
        VALUES (?, ?, ?)
    """, (slot_key, label_key, domain))

# ── Seed: Panel Groups (default state) ────────────────

group_names = ["daily", "journals", "reports", "periodic", "setup"]
for gn in group_names:
    cursor.execute("""
        INSERT OR IGNORE INTO user_panel_groups (user_id, group_name, state, is_visible)
        VALUES ('default', ?, 'expanded', 1)
    """, (gn,))

conn.commit()
conn.close()

print("Database initialized: " + DB_PATH)
print("Tables created: ui_text_slots, ui_text_slot_labels, ui_labels, ui_label_translations, user_panel_groups, panel_subgroups, panel_subgroup_mappings")
print("Seed data: 10 labels × 4 locales, 10 text slots, 5 panel groups")
```

- [ ] **Step 3: Validate Python syntax**

```bash
python3 -m py_compile templates/new-webui-skeleton/scripts/init_db.py
```

Expected: no output (exit 0).

- [ ] **Step 4: Commit**

```bash
git add templates/new-webui-skeleton/scripts/init_db.py
git commit -m "feat: Spor C — skeleton init_db.py (6 tables, 10 labels × 4 locales)"
```

---

### Task 8: Create initialize_new_webui.py script

**Files:**
- Create: `scripts/initialize_new_webui.py`

- [ ] **Step 1: Write initialize_new_webui.py — Part 1: Imports and argument parsing**

Write `scripts/initialize_new_webui.py`:

```python
#!/usr/bin/env python3
"""Initialize a new DPMtF-governed WebUI project from skeleton templates.

Creates a complete, runnable WebUI project in ~2 minutes.
Uses skeleton files from DPMtF-WebUI/templates/new-webui-skeleton/.

Usage:
    python3 scripts/initialize_new_webui.py \\
        --name my-project \\
        --port 9132 \\
        --title "My Project Title"

After running:
    cd /home/svend/my-project
    .venv/bin/uvicorn app:app --host 0.0.0.0 --port 9132 --reload &
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


# ── Constants ─────────────────────────────────────────

SKELETON_DIR = Path(__file__).resolve().parent.parent / "templates" / "new-webui-skeleton"
HOME = str(Path.home())
VALID_PORT_RANGE = range(9132, 9200)


# ── CLI ────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Initialize a new DPMtF-governed WebUI project"
    )
    parser.add_argument(
        "--name", required=True,
        help="Project name (lowercase, hyphenated, e.g. 'my-project')"
    )
    parser.add_argument(
        "--port", type=int, required=True,
        help="Port number (9132-9199)"
    )
    parser.add_argument(
        "--title", required=True,
        help="Project title (displayed in page title and heading)"
    )
    return parser.parse_args()


# ── Validation ─────────────────────────────────────────

def validate_name(name):
    """Project name must be lowercase-hyphenated, no spaces or special chars."""
    if not name:
        return "Project name is required"
    if " " in name:
        return "Project name must not contain spaces (use hyphens)"
    if name != name.lower():
        return "Project name must be lowercase"
    if not all(c.isalnum() or c == "-" for c in name):
        return "Project name must only contain letters, digits, and hyphens"
    return None


def validate_port(port):
    """Port must be in valid range and not in use."""
    if port not in VALID_PORT_RANGE:
        return f"Port must be in range {VALID_PORT_RANGE.start}-{VALID_PORT_RANGE.stop - 1}"
    # Check if port is in use
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return None
    except OSError:
        s.close()
        return f"Port {port} is already in use"
    finally:
        try:
            s.close()
        except Exception:
            pass


def validate_title(title):
    """Title must be non-empty."""
    if not title or not title.strip():
        return "Project title is required"
    return None


def validate_not_exists(project_dir):
    """Project directory must not already exist."""
    if project_dir.exists():
        return f"Directory already exists: {project_dir}"
    return None
```

- [ ] **Step 2: Write initialize_new_webui.py — Part 2: Placeholder replacement**

Append to `scripts/initialize_new_webui.py`:

```python
# ── Placeholder System ────────────────────────────────

def build_placeholders(args, project_dir):
    """Build the placeholder → value mapping."""
    return {
        "{PROJECT_NAME}": args.name,
        "{PROJECT_TITLE}": args.title,
        "{PROJECT_ROOT}": str(project_dir),
        "{PORT}": str(args.port),
        "{FATHER_PROJECT}": "DPMtF-WebUI",
        "{DATABASE}": f"{args.name}.db",
        "{CSS_FILE}": f"{args.name}-theme.css",
        "{JS_FILE}": f"{args.name}-app.js",
    }


def replace_placeholders(file_path, placeholders):
    """Replace all placeholders in a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for placeholder, value in placeholders.items():
        content = content.replace(placeholder, value)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def rename_file(file_path, placeholders):
    """Rename a file if its name contains placeholders."""
    old_name = str(file_path)
    new_name = old_name
    for placeholder, value in placeholders.items():
        new_name = new_name.replace(placeholder, value)
    if new_name != old_name:
        os.rename(old_name, new_name)
        return Path(new_name)
    return file_path
```

- [ ] **Step 3: Write initialize_new_webui.py — Part 3: Main flow**

Append to `scripts/initialize_new_webui.py`:

```python
# ── Main Flow ──────────────────────────────────────────

def main():
    args = parse_args()
    
    # 1. Validate inputs
    print("=" * 60)
    print(f"Initializing new WebUI: {args.name}")
    print("=" * 60)
    
    errors = []
    for validator, value, label in [
        (validate_name, args.name, "name"),
        (validate_port, args.port, "port"),
        (validate_title, args.title, "title"),
    ]:
        err = validator(value)
        if err:
            errors.append(f"  ❌ {label}: {err}")
        else:
            print(f"  ✅ {label}: {value}")
    
    project_dir = Path(HOME) / args.name
    err = validate_not_exists(project_dir)
    if err:
        errors.append(f"  ❌ {err}")
    else:
        print(f"  ✅ directory: {project_dir} (does not exist)")
    
    if errors:
        print("\nVALIDATION FAILED:")
        for e in errors:
            print(e)
        sys.exit(1)
    
    placeholders = build_placeholders(args, project_dir)
    
    # 2. Verify skeleton directory exists
    if not SKELETON_DIR.exists():
        print(f"\n❌ Skeleton directory not found: {SKELETON_DIR}")
        sys.exit(1)
    print(f"\n📁 Skeleton source: {SKELETON_DIR}")
    
    # 3. Create directory structure
    print("\n📂 Creating directory structure...")
    dirs = [
        project_dir,
        project_dir / "templates",
        project_dir / "static" / "js",
        project_dir / "static" / "css",
        project_dir / "scripts",
        project_dir / "databases",
        project_dir / "docs" / "dpmtf",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {d}")
    
    # 4. Copy skeleton files
    print("\n📋 Copying skeleton files...")
    copied = []
    for item in SKELETON_DIR.rglob("*"):
        if item.is_file():
            rel = item.relative_to(SKELETON_DIR)
            dest = project_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            copied.append(dest)
            print(f"  ✅ {rel}")
    
    # 5. Replace placeholders in all copied files
    print("\n🔄 Replacing placeholders...")
    for file_path in copied:
        if file_path.suffix in (".py", ".html", ".js", ".css", ".ini", ".txt") or file_path.name == ".env":
            replace_placeholders(file_path, placeholders)
    
    # 6. Rename files with placeholder names
    print("\n🏷️ Renaming files...")
    for file_path in list(copied):
        new_path = rename_file(file_path, placeholders)
        if new_path != file_path:
            print(f"  ✅ {file_path.name} → {new_path.name}")
    
    # 7. Create venv
    print("\n🐍 Creating virtual environment...")
    result = subprocess.run(
        ["python3", "-m", "venv", str(project_dir / ".venv")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ❌ venv creation failed: {result.stderr}")
        sys.exit(1)
    print("  ✅ .venv created")
    
    # 8. Install dependencies
    print("\n📦 Installing dependencies...")
    pip = str(project_dir / ".venv" / "bin" / "pip")
    result = subprocess.run(
        [pip, "install", "-r", str(project_dir / "requirements.txt")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ❌ pip install failed: {result.stderr}")
        sys.exit(1)
    print("  ✅ Dependencies installed")
    
    # 9. Initialize database
    print("\n🗄️ Initializing database...")
    python = str(project_dir / ".venv" / "bin" / "python3")
    result = subprocess.run(
        [python, str(project_dir / "scripts" / "init_db.py")],
        capture_output=True, text=True, cwd=str(project_dir)
    )
    if result.returncode != 0:
        print(f"  ❌ Database init failed: {result.stderr}")
        sys.exit(1)
    print(f"  {result.stdout.strip()}")
    
    # 10. Verify health endpoint
    print("\n🏥 Verifying health endpoint...")
    uvicorn_path = str(project_dir / ".venv" / "bin" / "uvicorn")
    server_proc = subprocess.Popen(
        [uvicorn_path, "app:app", "--host", "0.0.0.0", "--port", str(args.port)],
        cwd=str(project_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Wait for server to start
    time.sleep(2)
    
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(f"http://localhost:{args.port}/api/health")
        resp = urllib.request.urlopen(req, timeout=5)
        import json
        data = json.loads(resp.read())
        print(f"  ✅ Health check: {data}")
    except Exception as e:
        print(f"  ❌ Health check failed: {e}")
        server_proc.terminate()
        sys.exit(1)
    finally:
        server_proc.terminate()
        server_proc.wait()
    
    # 11. Summary
    print("\n" + "=" * 60)
    print("✅ PROJECT INITIALIZED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Name:       {args.name}")
    print(f"  Title:      {args.title}")
    print(f"  Directory:  {project_dir}")
    print(f"  Port:       {args.port}")
    print(f"  Database:   {args.name}.db")
    print()
    print("Next steps:")
    print(f"  cd {project_dir}")
    print(f"  .venv/bin/uvicorn app:app --host 0.0.0.0 --port {args.port} --reload &")
    print(f"  Open http://localhost:{args.port}/")
    print()
    print("Add domain-specific panels and endpoints via prompts.")
    print("Governance files to create in docs/dpmtf/:")
    print("  - 10_PROJECT.md (project identity)")
    print("  - 11_SCOPE.md (current phase scope)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Validate Python syntax**

```bash
python3 -m py_compile scripts/initialize_new_webui.py
```

Expected: no output (exit 0).

- [ ] **Step 5: Commit**

```bash
git add scripts/initialize_new_webui.py
git commit -m "feat: Spor C — initialize_new_webui.py (validate → copy → replace → venv → db → verify)"
```

---

### Task 9: Update knowledge fragment for accelerated path

**Files:**
- Modify: `docs/governance-templates-v2/knowledge-fragments/patterns/create-new-webui.md`

- [ ] **Step 1: Read current fragment**

The fragment currently describes 11 manual steps. We add an accelerated path section after the overview.

- [ ] **Step 2: Add accelerated path section**

Insert after the "Overview" section (after line 13, before "### Prerequisites"):

```markdown
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
```

- [ ] **Step 3: Verify fragment structure**

```bash
grep -n "^##\|^###" docs/governance-templates-v2/knowledge-fragments/patterns/create-new-webui.md
```

Expected: Overview, Accelerated Path, Standard Path, Prerequisites, Step Pattern, Governance Files, Verification Commands.

- [ ] **Step 4: Commit**

```bash
git add docs/governance-templates-v2/knowledge-fragments/patterns/create-new-webui.md
git commit -m "feat: Spor C — add accelerated path to create-new-webui knowledge fragment"
```

---

### Task 10: End-to-end validation

**Files:**
- None (test only)

- [ ] **Step 1: Run init script end-to-end**

```bash
python3 scripts/initialize_new_webui.py --name test-webui --port 9132 --title "Test WebUI"
```

Expected: All 11 steps pass, health check returns `{"status":"healthy","app":"Test WebUI"}`.

- [ ] **Step 2: Verify health endpoint**

```bash
# Start the test project
cd /home/svend/test-webui
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9132 --reload &
sleep 2
curl -s http://localhost:9132/api/health | python3 -m json.tool
```

Expected:
```json
{
    "status": "healthy",
    "app": "Test WebUI",
    "database_path": "databases/test-webui.db",
    "database_exists": true
}
```

- [ ] **Step 3: Verify panel structure API**

```bash
curl -s http://localhost:9132/api/panel-structure | python3 -c "
import json, sys
data = json.load(sys.stdin)
groups = data['groups']
assert len(groups) == 5, f'Expected 5 groups, got {len(groups)}'
for gn in ['daily', 'journals', 'reports', 'periodic', 'setup']:
    assert gn in groups, f'Missing group: {gn}'
    assert groups[gn]['is_visible'] == True, f'{gn} not visible'
    assert groups[gn]['state'] == 'expanded', f'{gn} not expanded'
print('✅ Panel structure OK')
"
```

Expected: `✅ Panel structure OK`

- [ ] **Step 4: Verify i18n**

```bash
curl -s "http://localhost:9132/api/ui-labels/main?locale=da-DK" | python3 -c "
import json, sys
data = json.load(sys.stdin)
labels = data['labels']
assert labels.get('pg_daily') == '📋 Daglig', f'Expected 📋 Daglig, got {labels.get(\"pg_daily\")}'
assert labels.get('lbl_status_loading') == 'Indlæser...', f'Expected Indlæser..., got {labels.get(\"lbl_status_loading\")}'
print('✅ i18n OK')
"
```

Expected: `✅ i18n OK`

- [ ] **Step 5: Verify no hardcoded paths**

```bash
grep -RIn '"/home/svend' /home/svend/test-webui/app.py /home/svend/test-webui/scripts/
```

Expected: NO results (exit 1).

- [ ] **Step 6: Verify HTML structure**

```bash
curl -s http://localhost:9132/ | grep -c "panel-group"
```

Expected: `5` (five panel groups).

- [ ] **Step 7: Kill test server and cleanup**

```bash
kill $(pgrep -f "uvicorn app:app.*9132") 2>/dev/null
rm -rf /home/svend/test-webui
```

- [ ] **Step 8: Commit validation report**

```bash
git add -A
git commit -m "test: Spor C — end-to-end validation passed (test-webui created and verified)"
```
