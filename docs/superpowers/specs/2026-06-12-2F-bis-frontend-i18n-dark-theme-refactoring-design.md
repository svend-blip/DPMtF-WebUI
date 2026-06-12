# 2F-bis: Frontend i18n + Dark Theme Refactoring — Design Spec

**Date:** 2026-06-12
**Phase:** 2F-bis (indskudt mellem 2F og 2G)
**Status:** Design approved — awaiting implementation plan

---

## Purpose

Bring DPMtF-WebUI's frontend to a usable level before building 2G's Implementation Pattern Manager on top. Three goals:

1. **i18n compliance** — all user-visible text must resolve through the four-layer i18n architecture (ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations). Static text uses `data-slot` attributes populated by `loadLabels()`. Dynamic text uses `labelMap["key"] || "fallback"`.

2. **Dark dashboard theme** — match the visual language of ai-pc-resource-webui-v3: #0d1117 background, #21262d cards, #30363d borders, green/orange/red hitrate colors.

3. **DOM safety** — replace all 39 existing `innerHTML` calls with `createElement()` / `textContent` / `replaceChildren()`. Zero innerHTML after refactoring.

4. **Architecture space** — keep System Setup drawer for endpoint registry, bootstrap dataset, and security/permissions, but make it i18n-compatible. These become proper read-only panels in future phases.

---

## Current State (baseline)

| File | Lines | Issues |
|---|---|---|
| `templates/index.html` | 348 | All panel HTML inline, hardcoded text, no data-slot |
| `static/js/dpmtf-app.js` | 1813 | Monolithic, 39 innerHTML, no labelMap usage |
| `static/css/dpmtf-theme.css` | 491 | Light theme (#f5f5f5, white cards) |

---

## Target State

| File | Lines (target) | Characteristics |
|---|---|---|
| `templates/index.html` | ~45 | Skeleton only: sections with id + data-slot, JS renders content |
| `static/js/dpmtf-app.js` | ~1600 | Organized in 9 logical sections, 0 innerHTML, labelMap throughout |
| `static/css/dpmtf-theme.css` | ~350 | Dark dashboard theme, .dpmtf- prefix convention |

---

## Design

### 1. index.html — Skeleton

Reduce from 348 lines of inline panel HTML to a ~45 line skeleton. Every section has:
- A semantic `id` for JS to target
- A `data-slot` attribute on the heading for i18n
- An empty content div (`<div id="...-content"></div>`) for JS to populate

Sections retained:
- Database Status
- Phase Status (completed / next / planned)
- Prompt Hitrates (from 2F)
- Prompt Sequence Planner
- New Project Planning
- System Setup Drawer (trigger button + drawer container)

Sections NOT in skeleton (rendered entirely by JS):
- Panel tables, forms, dropdowns, status messages — all created by JS

```html
<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="locale" content="da-DK" />
    <title data-slot="page_title">Loading...</title>
    <link rel="stylesheet" href="/static/css/dpmtf-theme.css" />
</head>
<body>
    <main class="container">
        <h1 data-slot="heading_main">Loading...</h1>

        <section id="db-status-section">
            <h2 data-slot="panel_db_status">Database Status</h2>
            <div id="db-status-content"></div>
        </section>

        <section id="phase-status-section">
            <h2 data-slot="panel_phase_status">Phase Status</h2>
            <div id="phase-status-content"></div>
        </section>

        <section id="hitrate-section">
            <h2 data-slot="panel_hitrates">Prompt Hitrates</h2>
            <div id="hitrate-content"></div>
        </section>

        <section id="prompt-sequence-section">
            <h2 data-slot="panel_prompt_sequences">Prompt Sequence Planner</h2>
            <div id="prompt-sequence-content"></div>
        </section>

        <section id="project-planning-section">
            <h2 data-slot="panel_project_planning">New Project Planning</h2>
            <div id="project-planning-content"></div>
        </section>

        <button id="system-setup-btn" type="button" data-slot="btn_system_setup">System Setup</button>
        <div id="system-setup-drawer" class="drawer">
            <div id="drawer-content"></div>
        </div>
    </main>
    <script src="/static/js/dpmtf-app.js"></script>
</body>
</html>
```

### 2. JavaScript — Organization + i18n + innerHTML removal

**File organization** (single file, 9 logical sections):

```
1. i18n loader          — loadLabels(), labelMap, locale, data-slot population
2. DOM helpers           — el(tag, className, text), escapeHtml(str), td(text, className)
3. Database Status       — loadDbStatus()
4. Phase Status          — loadPhaseStatus(), filter buttons
5. Hitrate Panel         — loadHitrates(), loadPromptRuns(), loadPatterns() (2G-ready)
6. Prompt Sequences      — loadSequences(), createSequence(), loadSteps(), addStep(),
                           generateNextPrompt(), saveGeneratedPrompt(), loadHistory()
7. Project Planning      — loadProjectPlans(), createProjectPlan(), loadDropdowns()
8. System Setup Drawer   — openDrawer(), closeDrawer(), loadLayoutPreview(),
                           loadI18nPreview(), loadEndpointPreview()
9. Init                  — onReady(), locale detection from <meta>
```

**i18n pattern** (identical to v3):

```javascript
var labelMap = {};
var locale = "da-DK";

function loadLabels() {
  var metaLocale = document.querySelector("meta[name=locale]");
  if (metaLocale) locale = metaLocale.getAttribute("content") || locale;
  fetch("/api/ui-labels/main?locale=" + locale)
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (map) {
      labelMap = map;
      document.querySelectorAll("[data-slot]").forEach(function (el) {
        var key = el.getAttribute("data-slot");
        if (map[key]) el.textContent = map[key];
      });
    })
    .catch(function (err) {
      console.warn("Failed to load labels:", err.message);
    });
}
```

**DOM safety rules:**
- `el(tag, className, text)` — creates element, sets className if provided, sets textContent if provided, returns element
- `td(text, className)` — creates `<td>` with textContent and optional className
- `escapeHtml(str)` — replaces `<>&"` with entities
- `element.replaceChildren()` — clears containers (never `innerHTML = ''`)
- `element.appendChild()` — adds children (never `innerHTML = '...'`)

**innerHTML removal — before/after example:**

Before (current line 17-20):
```javascript
tableBody.innerHTML = '';
row.innerHTML = `<td>${panel.sort_order}</td><td>${panel.panel_key}</td>...`;
```

After:
```javascript
tableBody.replaceChildren();
var row = document.createElement("tr");
row.appendChild(td(String(panel.sort_order)));
row.appendChild(td(escapeHtml(panel.panel_key)));
```

### 3. CSS — Dark Dashboard Theme

Complete rewrite. Reference: v3's `app.css`. All classes use `.dpmtf-` prefix.

**Color palette:**

| Role | Color |
|---|---|
| Body background | `#0d1117` |
| Container | `#161b22` |
| Cards / sections | `#21262d` border `#30363d` |
| Primary text | `#e6edf3` |
| Secondary text | `#8b949e` |
| Success (green) | `#3fb950` |
| Warning (orange) | `#d2991b` |
| Danger (red) | `#da3633` |
| Links / accent | `#58a6ff` |

**Key classes:**

```css
/* Base */
body { background: #0d1117; color: #e6edf3; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }

/* Cards */
.dpmtf-card { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 16px; margin-bottom: 16px; }

/* Grid */
.dpmtf-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }

/* Tables */
.dpmtf-table { width: 100%; border-collapse: collapse; }
.dpmtf-table th { color: #8b949e; padding: 8px; border-bottom: 1px solid #30363d; }
.dpmtf-table td { padding: 8px; border-bottom: 1px solid #21262d; }

/* Buttons */
.dpmtf-btn { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 5px 16px; border-radius: 6px; }
.dpmtf-btn:hover { background: #30363d; }

/* Form elements */
.dpmtf-input, .dpmtf-select, .dpmtf-textarea { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 8px; }

/* Hitrate colors */
.hitrate-good { color: #3fb950; font-weight: bold; }
.hitrate-ok { color: #d2991b; font-weight: bold; }
.hitrate-low { color: #da3633; font-weight: bold; }

/* Model badges */
.model-badge-local { background: #1f6feb; color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; }
.model-badge-cloud { background: #6e40c9; color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; }

/* Drawer */
.drawer { position: fixed; right: -420px; top: 0; width: 420px; height: 100vh; background: #161b22; border-left: 1px solid #30363d; transition: right 0.3s; overflow-y: auto; z-index: 100; }
.drawer.open { right: 0; }

/* Governance-first hidden panels (preserved) */
.dpmtf-hidden-governance { display: none !important; }
```

### 4. i18n Seed Data — New Labels Required

The frontend references these slot keys via `data-slot` attributes and `labelMap` lookups. They must exist in the database.

**New ui_text_slots needed:**

```
page_title, heading_main, panel_db_status, panel_phase_status,
panel_hitrates, panel_prompt_sequences, panel_project_planning,
btn_system_setup, btn_refresh, btn_create, btn_add_step,
btn_generate_prompt, btn_copy_prompt, btn_save_prompt,
btn_create_project_plan, btn_close_drawer,
lbl_loading, lbl_no_data, lbl_error_prefix, lbl_success,
lbl_failed, lbl_planned, lbl_completed, lbl_next,
lbl_sequence_count, lbl_step_count, lbl_sequences, lbl_steps,
lbl_select_sequence, lbl_empty_sequences, lbl_empty_steps,
lbl_prompt_preview, lbl_prompt_history, lbl_no_prompts_yet,
lbl_project_name, lbl_target_folder, lbl_app_port,
lbl_app_profile, lbl_prompt_sequence, lbl_notes,
lbl_drawer_layout_slots, lbl_drawer_db_layout,
lbl_drawer_i18n, lbl_drawer_endpoint_registry,
lbl_drawer_bootstrap, lbl_drawer_security
```

**New ui_labels needed:** One per slot above, with da-DK and en-US translations.

**New ui_text_slot_labels:** Bind each slot to its label.

**Existing labels to preserve:** The i18n system already has labels for system_setup domain (LBL-1000001 to LBL-1000006). These are reused where applicable.

**Seed script changes:** `scripts/init_db.py` — add new slots, labels, translations, and bindings in the existing seed sections. Use INSERT OR IGNORE for idempotency.

---

## What Stays Unchanged

- **Backend (app.py):** No changes. All existing endpoints remain. The `/api/ui-labels/{domain}` endpoint already exists and serves labels correctly.
- **Database schema:** No new tables. Only seed data additions to existing i18n tables.
- **Prompt Sequence Planner logic:** Business logic unchanged — only rendering is refactored.
- **New Project Planning logic:** Unchanged.
- **System Setup drawer sections:** Content unchanged — only rendering and i18n applied.
- **Governance templates:** Updated in docs (CHANGELOG, NEXT_CONTEXT, IMPLEMENTATION_REPORT) but template files themselves unchanged.

---

## Architecture Space for Future Phases

The refactored frontend leaves clear extension points:

| Future Phase | Where It Goes |
|---|---|
| **Endpoint Registry panel** | New `<section>` in main view, or drawer section promoted to main view |
| **Bootstrap Dataset panel** | Same pattern — section + content div + JS renderer |
| **Security / Permissions panel** | Placeholder in drawer, promoted when implemented |
| **2G Pattern Manager** | New table in hitrate section, new JS section 5a |
| **2H Prompt Template Manager** | New section in prompt sequence area |

Each follows the same pattern: add `<section id="..."><h2 data-slot="...">...</h2><div id="...-content"></div></section>` to index.html, add a JS renderer function, add CSS card styles.

---

## Validation Checklist

| # | Check | Command |
|---|-------|---------|
| 1 | Python syntax (init_db.py) | `python3 -m py_compile scripts/init_db.py` |
| 2 | Seed idempotent | `python3 scripts/init_db.py` (run twice) |
| 3 | JavaScript syntax | `node --check static/js/dpmtf-app.js` |
| 4 | Zero innerHTML | `grep -RIn "innerHTML" static/js/dpmtf-app.js` must return empty |
| 5 | data-slot coverage | `grep -oP 'data-slot="[^"]+"' templates/index.html | wc -l` — verify all sections have slots |
| 6 | labelMap coverage | `grep -c "labelMap\[" static/js/dpmtf-app.js` — verify JS uses labelMap |
| 7 | Diff scope | `git diff --stat` — only expected files changed |
| 8 | No backend changes | `git diff -- app.py` must be empty |

---

## Allowed Files

- `templates/index.html`
- `static/js/dpmtf-app.js`
- `static/css/dpmtf-theme.css`
- `scripts/init_db.py`
- `docs/governance-templates/10_CHANGELOG.md`
- `docs/governance-templates/11_NEXT_CONTEXT.md`
- `docs/governance-templates/12_IMPLEMENTATION_REPORT.md`

---

## Out of Scope

- Backend changes (app.py untouched)
- New database tables
- Endpoint Registry as standalone main-view panel (stays in drawer)
- Bootstrap Dataset as standalone main-view panel (stays in drawer)
- Security/Permissions implementation (placeholder only)
- Prompt Sequence Planner feature changes
- New Project Planning feature changes

---

## Success Criteria

1. index.html is ≤50 lines, all text via data-slot
2. dpmtf-app.js has 0 innerHTML (grep returns empty)
3. dpmtf-theme.css is dark dashboard theme matching v3's visual language
4. All static text resolves through labelMap with da-DK and en-US fallbacks
5. All 5 existing panels (DB Status, Phase Status, Hitrates, Prompt Sequences, Project Planning) render correctly
6. System Setup drawer opens/closes and displays i18n-compatible content
7. Seed script is idempotent — all new labels/slots/translations/bindings present
8. All validation checks pass
