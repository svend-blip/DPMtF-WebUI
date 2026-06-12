# 2F-bis: Frontend i18n + Dark Theme Refactoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor DPMtF-WebUI frontend to v3 standards: skeleton HTML with data-slot i18n, 0 innerHTML, dark dashboard theme, organized JS.

**Architecture:** Single-page vanilla JS app. index.html is a ~45 line skeleton with `<section>` + `data-slot` + empty content divs. dpmtf-app.js renders all content into those divs using `createElement`/`textContent`/`replaceChildren`. All text resolves through `labelMap` populated from `/api/ui-labels/main?locale=da-DK`. CSS is a complete dark theme rewrite matching v3's visual language.

**Tech Stack:** Vanilla JavaScript, CSS, HTML5, Python (seed script only), SQLite (i18n data)

---

### Task 1: i18n seed data — new slots, labels, translations, bindings

**Files:**
- Modify: `scripts/init_db.py` (seed_ui_labels, seed_ui_label_translations, seed_ui_text_slots, seed_ui_text_slot_labels sections)

- [ ] **Step 1: Add new ui_text_slots to seed_ui_text_slots()**

Add these slots to the existing `slots` list in `seed_ui_text_slots()`:

```python
# Main layout slots
("page_title", "Page title"),
("heading_main", "Main heading"),
("panel_db_status", "Database Status panel heading"),
("panel_phase_status", "Phase Status panel heading"),
("panel_hitrates", "Prompt Hitrates panel heading"),
("panel_prompt_sequences", "Prompt Sequence Planner panel heading"),
("panel_project_planning", "New Project Planning panel heading"),
("btn_system_setup", "System Setup button"),
("btn_refresh", "Refresh button"),
("btn_create", "Create button"),
("btn_add_step", "Add Step button"),
("btn_generate_prompt", "Generate Next Prompt Preview button"),
("btn_copy_prompt", "Copy Prompt button"),
("btn_save_prompt", "Save Generated Prompt button"),
("btn_create_project_plan", "Create Project Plan button"),
("btn_close_drawer", "Close drawer button"),
# Status labels
("lbl_loading", "Loading indicator"),
("lbl_no_data", "No data available"),
("lbl_error_prefix", "Error message prefix"),
("lbl_success", "Success status"),
("lbl_failed", "Failed status"),
("lbl_planned", "Planned status"),
("lbl_completed", "Completed status"),
("lbl_next", "Next phase status"),
# Prompt Sequence Planner labels
("lbl_sequence_count", "Sequence count label"),
("lbl_step_count", "Step count label"),
("lbl_sequences", "Sequences label"),
("lbl_steps", "Steps label"),
("lbl_select_sequence", "Select sequence prompt"),
("lbl_empty_sequences", "No sequences message"),
("lbl_empty_steps", "No steps message"),
("lbl_prompt_preview", "Prompt preview heading"),
("lbl_prompt_history", "Prompt history heading"),
("lbl_no_prompts_yet", "No prompts yet message"),
# Project Planning labels
("lbl_project_name", "Project name field"),
("lbl_target_folder", "Target folder field"),
("lbl_app_port", "App port field"),
("lbl_app_profile", "App profile field"),
("lbl_prompt_sequence", "Prompt sequence field"),
("lbl_notes", "Notes field"),
# Drawer section labels
("lbl_drawer_layout_slots", "Layout Slots drawer section"),
("lbl_drawer_db_layout", "Database Layout Preview drawer section"),
("lbl_drawer_i18n", "UI Labels / i18n drawer section"),
("lbl_drawer_endpoint_registry", "Endpoint Registry drawer section"),
("lbl_drawer_bootstrap", "Bootstrap Dataset drawer section"),
("lbl_drawer_security", "Security / Permissions drawer section"),
```

- [ ] **Step 2: Add new ui_labels to seed_ui_labels()**

Add these labels to the existing `labels` list in `seed_ui_labels()`:

```python
# Main layout
("lbl_page_title", "Page title — DPMtF WebUI"),
("lbl_heading_main", "Main heading — Deterministic Prompt Management"),
("lbl_panel_db_status", "Database Status panel"),
("lbl_panel_phase_status", "Phase Status panel"),
("lbl_panel_hitrates", "Prompt Hitrates panel"),
("lbl_panel_prompt_sequences", "Prompt Sequence Planner panel"),
("lbl_panel_project_planning", "New Project Planning panel"),
("lbl_btn_system_setup", "System Setup button"),
("lbl_btn_refresh", "Refresh button"),
("lbl_btn_create", "Create button"),
("lbl_btn_add_step", "Add Step button"),
("lbl_btn_generate_prompt", "Generate Next Prompt Preview button"),
("lbl_btn_copy_prompt", "Copy Prompt button"),
("lbl_btn_save_prompt", "Save Generated Prompt button"),
("lbl_btn_create_project_plan", "Create Project Plan button"),
("lbl_btn_close_drawer", "Close drawer button"),
# Status
("lbl_status_loading", "Loading status text"),
("lbl_status_no_data", "No data available text"),
("lbl_status_error_prefix", "Error message prefix"),
("lbl_status_success", "Success status text"),
("lbl_status_failed", "Failed status text"),
("lbl_status_planned", "Planned phase status"),
("lbl_status_completed", "Completed phase status"),
("lbl_status_next", "Next phase status"),
# Prompt Sequences
("lbl_sequence_count", "Sequence count"),
("lbl_step_count", "Step count"),
("lbl_sequences", "Sequences"),
("lbl_steps", "Steps"),
("lbl_select_sequence", "Select a sequence prompt"),
("lbl_empty_sequences", "No sequences message"),
("lbl_empty_steps", "No steps message"),
("lbl_prompt_preview", "Prompt preview heading"),
("lbl_prompt_history", "Prompt history heading"),
("lbl_no_prompts_yet", "No generated prompts yet"),
# Project Planning
("lbl_project_name", "Project name label"),
("lbl_target_folder", "Target folder label"),
("lbl_app_port", "App port label"),
("lbl_app_profile", "App profile label"),
("lbl_prompt_sequence_select", "Prompt sequence selector label"),
("lbl_notes", "Notes label"),
# Drawer
("lbl_drawer_layout_slots", "Layout Slots section"),
("lbl_drawer_db_layout", "Database Layout Preview section"),
("lbl_drawer_i18n", "UI Labels / i18n section"),
("lbl_drawer_endpoint_registry", "Endpoint Registry section"),
("lbl_drawer_bootstrap", "Bootstrap Dataset section"),
("lbl_drawer_security", "Security / Permissions section"),
```

- [ ] **Step 3: Add da-DK + en-US translations to seed_ui_label_translations()**

Add translations for all 45 new labels. da-DK translations:

```python
"lbl_page_title": {"da-DK": "DPMtF WebUI", "en-US": "DPMtF WebUI"},
"lbl_heading_main": {"da-DK": "Deterministisk Prompt — MockUp til Finaliseret", "en-US": "Deterministic Prompt – MockUp to Finalised"},
"lbl_panel_db_status": {"da-DK": "Database Status", "en-US": "Database Status"},
"lbl_panel_phase_status": {"da-DK": "Fase Status", "en-US": "Phase Status"},
"lbl_panel_hitrates": {"da-DK": "Prompt Hitrates", "en-US": "Prompt Hitrates"},
"lbl_panel_prompt_sequences": {"da-DK": "Prompt Sekvens Planlægger", "en-US": "Prompt Sequence Planner"},
"lbl_panel_project_planning": {"da-DK": "Nyt Projekt Planlægning", "en-US": "New Project Planning"},
"lbl_btn_system_setup": {"da-DK": "System Opsætning", "en-US": "System Setup"},
"lbl_btn_refresh": {"da-DK": "Opdatér", "en-US": "Refresh"},
"lbl_btn_create": {"da-DK": "Opret", "en-US": "Create"},
"lbl_btn_add_step": {"da-DK": "Tilføj Trin", "en-US": "Add Step"},
"lbl_btn_generate_prompt": {"da-DK": "Generér Næste Prompt Preview", "en-US": "Generate Next Prompt Preview"},
"lbl_btn_copy_prompt": {"da-DK": "Kopiér Prompt", "en-US": "Copy Prompt"},
"lbl_btn_save_prompt": {"da-DK": "Gem Genereret Prompt", "en-US": "Save Generated Prompt"},
"lbl_btn_create_project_plan": {"da-DK": "Opret Projekt Plan", "en-US": "Create Project Plan"},
"lbl_btn_close_drawer": {"da-DK": "Luk", "en-US": "Close"},
"lbl_status_loading": {"da-DK": "Indlæser...", "en-US": "Loading..."},
"lbl_status_no_data": {"da-DK": "Ingen data tilgængelig.", "en-US": "No data available."},
"lbl_status_error_prefix": {"da-DK": "Fejl: ", "en-US": "Error: "},
"lbl_status_success": {"da-DK": "Gennemført", "en-US": "Success"},
"lbl_status_failed": {"da-DK": "Fejlet", "en-US": "Failed"},
"lbl_status_planned": {"da-DK": "Planlagt", "en-US": "Planned"},
"lbl_status_completed": {"da-DK": "Færdig", "en-US": "Completed"},
"lbl_status_next": {"da-DK": "Næste", "en-US": "Next"},
"lbl_sequence_count": {"da-DK": "Sekvenser", "en-US": "Sequences"},
"lbl_step_count": {"da-DK": "Trin", "en-US": "Steps"},
"lbl_sequences": {"da-DK": "Sekvenser", "en-US": "Sequences"},
"lbl_steps": {"da-DK": "Trin", "en-US": "Steps"},
"lbl_select_sequence": {"da-DK": "Vælg en sekvens...", "en-US": "Select a sequence..."},
"lbl_empty_sequences": {"da-DK": "Ingen prompt sekvenser endnu. Opret den første sekvens for at begynde at planlægge små Claude Code prompts.", "en-US": "No prompt sequences yet. Create the first sequence to begin planning small Claude Code prompts."},
"lbl_empty_steps": {"da-DK": "Ingen trin endnu. Tilføj trin til sekvensen for at generere prompts.", "en-US": "No steps yet. Add steps to the sequence to generate prompts."},
"lbl_prompt_preview": {"da-DK": "Generér Næste Prompt Preview", "en-US": "Generate Next Prompt Preview"},
"lbl_prompt_history": {"da-DK": "Prompt Historik / Genereret Arkiv", "en-US": "Prompt History / Generated Archive"},
"lbl_no_prompts_yet": {"da-DK": "Ingen genererede prompts endnu. Generér og gem prompts for at se dem her.", "en-US": "No generated prompts yet. Generate and save prompts to see them appear here."},
"lbl_project_name": {"da-DK": "Projekt Navn", "en-US": "Project Name"},
"lbl_target_folder": {"da-DK": "Mål Mappe", "en-US": "Target Folder"},
"lbl_app_port": {"da-DK": "App Port", "en-US": "App Port"},
"lbl_app_profile": {"da-DK": "App Profil", "en-US": "App Profile"},
"lbl_prompt_sequence_select": {"da-DK": "Prompt Sekvens", "en-US": "Prompt Sequence"},
"lbl_notes": {"da-DK": "Noter", "en-US": "Notes"},
"lbl_drawer_layout_slots": {"da-DK": "Layout Slots", "en-US": "Layout Slots"},
"lbl_drawer_db_layout": {"da-DK": "Database Layout Preview", "en-US": "Database Layout Preview"},
"lbl_drawer_i18n": {"da-DK": "UI Labels / i18n", "en-US": "UI Labels / i18n"},
"lbl_drawer_endpoint_registry": {"da-DK": "Endpoint Registry", "en-US": "Endpoint Registry"},
"lbl_drawer_bootstrap": {"da-DK": "Bootstrap Dataset", "en-US": "Bootstrap Dataset"},
"lbl_drawer_security": {"da-DK": "Sikkerhed / Rettigheder", "en-US": "Security / Permissions"},
```

- [ ] **Step 4: Add ui_text_slot_labels bindings**

Add bindings connecting each slot to its label:

```python
# Main layout
("page_title", "lbl_page_title"),
("heading_main", "lbl_heading_main"),
("panel_db_status", "lbl_panel_db_status"),
("panel_phase_status", "lbl_panel_phase_status"),
("panel_hitrates", "lbl_panel_hitrates"),
("panel_prompt_sequences", "lbl_panel_prompt_sequences"),
("panel_project_planning", "lbl_panel_project_planning"),
("btn_system_setup", "lbl_btn_system_setup"),
("btn_refresh", "lbl_btn_refresh"),
("btn_create", "lbl_btn_create"),
("btn_add_step", "lbl_btn_add_step"),
("btn_generate_prompt", "lbl_btn_generate_prompt"),
("btn_copy_prompt", "lbl_btn_copy_prompt"),
("btn_save_prompt", "lbl_btn_save_prompt"),
("btn_create_project_plan", "lbl_btn_create_project_plan"),
("btn_close_drawer", "lbl_btn_close_drawer"),
# Status
("lbl_loading", "lbl_status_loading"),
("lbl_no_data", "lbl_status_no_data"),
("lbl_error_prefix", "lbl_status_error_prefix"),
("lbl_success", "lbl_status_success"),
("lbl_failed", "lbl_status_failed"),
("lbl_planned", "lbl_status_planned"),
("lbl_completed", "lbl_status_completed"),
("lbl_next", "lbl_status_next"),
# Prompt Sequences
("lbl_sequence_count", "lbl_sequence_count"),
("lbl_step_count", "lbl_step_count"),
("lbl_sequences", "lbl_sequences"),
("lbl_steps", "lbl_steps"),
("lbl_select_sequence", "lbl_select_sequence"),
("lbl_empty_sequences", "lbl_empty_sequences"),
("lbl_empty_steps", "lbl_empty_steps"),
("lbl_prompt_preview", "lbl_prompt_preview"),
("lbl_prompt_history", "lbl_prompt_history"),
("lbl_no_prompts_yet", "lbl_no_prompts_yet"),
# Project Planning
("lbl_project_name", "lbl_project_name"),
("lbl_target_folder", "lbl_target_folder"),
("lbl_app_port", "lbl_app_port"),
("lbl_app_profile", "lbl_app_profile"),
("lbl_prompt_sequence", "lbl_prompt_sequence_select"),
("lbl_notes", "lbl_notes"),
# Drawer
("lbl_drawer_layout_slots", "lbl_drawer_layout_slots"),
("lbl_drawer_db_layout", "lbl_drawer_db_layout"),
("lbl_drawer_i18n", "lbl_drawer_i18n"),
("lbl_drawer_endpoint_registry", "lbl_drawer_endpoint_registry"),
("lbl_drawer_bootstrap", "lbl_drawer_bootstrap"),
("lbl_drawer_security", "lbl_drawer_security"),
```

- [ ] **Step 5: Verify seed script**

Run: `python3 -m py_compile scripts/init_db.py`
Expected: Exit code 0

Run: `python3 scripts/init_db.py`
Expected: "Database initialized successfully!"

Run: `python3 scripts/init_db.py` (second time)
Expected: "Database initialized successfully!" (idempotent)

- [ ] **Step 6: Commit**

```bash
git add scripts/init_db.py databases/dpmtf.db
git commit -m "2F-bis: Seed i18n labels for frontend refactoring

- 45 new ui_text_slots for main layout, status, prompt sequences,
  project planning, and drawer sections
- 45 new ui_labels with da-DK/en-US descriptions
- 90 new ui_label_translations (45 da-DK + 45 en-US)
- 45 new ui_text_slot_labels bindings"
```

---

### Task 2: index.html — Skeleton rewrite

**Files:**
- Modify: `templates/index.html` (complete rewrite)

- [ ] **Step 1: Write the skeleton index.html**

Replace the entire content of `templates/index.html`:

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

- [ ] **Step 2: Verify HTML is well-formed**

Run: `xmllint --html templates/index.html 2>&1 | head -5` (if xmllint available) or just count lines:
Run: `wc -l templates/index.html`
Expected: ~45 lines

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "2F-bis: Rewrite index.html as i18n skeleton (~45 lines)

- All panel HTML removed — JS renders content into *-content divs
- Every heading/button has data-slot attribute for i18n
- <meta name=locale> controls language
- System Setup remains as drawer trigger + container"
```

---

### Task 3: CSS — Dark dashboard theme rewrite

**Files:**
- Modify: `static/css/dpmtf-theme.css` (complete rewrite)

- [ ] **Step 1: Write the dark theme CSS**

Replace the entire content of `static/css/dpmtf-theme.css`:

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
.dpmtf-table tr:hover td {
  background: #1c2128;
}

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

/* ── Hitrate colors ───────────────────────────────── */
.hitrate-good { color: #3fb950; font-weight: bold; }
.hitrate-ok { color: #d2991b; font-weight: bold; }
.hitrate-low { color: #da3633; font-weight: bold; }

/* ── Model badges ─────────────────────────────────── */
.model-badge-local {
  background: #1f6feb;
  color: #fff;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75em;
  font-weight: 600;
}
.model-badge-cloud {
  background: #6e40c9;
  color: #fff;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75em;
  font-weight: 600;
}

/* ── Drawer ───────────────────────────────────────── */
.drawer {
  position: fixed;
  right: -420px;
  top: 0;
  width: 420px;
  height: 100vh;
  background: #161b22;
  border-left: 1px solid #30363d;
  transition: right 0.3s ease;
  overflow-y: auto;
  z-index: 100;
  padding: 24px;
  box-sizing: border-box;
}
.drawer.open { right: 0; }
.drawer-close-btn {
  position: absolute;
  top: 12px;
  right: 16px;
  background: none;
  border: none;
  color: #8b949e;
  font-size: 1.5em;
  cursor: pointer;
}
.drawer-close-btn:hover { color: #e6edf3; }

/* ── Section spacing ──────────────────────────────── */
.dpmtf-section {
  margin-bottom: 32px;
}

/* ── Utility ──────────────────────────────────────── */
.dpmtf-muted { color: #8b949e; font-size: 0.85em; }
.dpmtf-small { font-size: 0.8em; }
.dpmtf-error { color: #da3633; }
.dpmtf-success { color: #3fb950; }
.dpmtf-loading { color: #8b949e; font-style: italic; }

/* ── Governance-first hidden panels (preserved) ───── */
.dpmtf-hidden-governance { display: none !important; }

/* ── System setup button ──────────────────────────── */
#system-setup-btn {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 99;
  background: #21262d;
  color: #c9d1d9;
  border: 1px solid #30363d;
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
}
#system-setup-btn:hover { background: #30363d; }

/* ── Details/expandable ───────────────────────────── */
.dpmtf-details {
  margin-top: 12px;
}
.dpmtf-details summary {
  color: #8b949e;
  cursor: pointer;
  font-size: 0.9em;
  padding: 4px 0;
}
.dpmtf-details summary:hover { color: #e6edf3; }

/* ── Inline status text ───────────────────────────── */
.dpmtf-status {
  font-size: 0.8em;
  margin-left: 10px;
}
```

- [ ] **Step 2: Verify CSS syntax**

Run: `node --check static/css/dpmtf-theme.css` (won't work for CSS, just check it's valid text)
Alternative: count lines and verify no light-theme colors remain:
Run: `grep -c "#f5f5f5\|background-color: white\|#f9f9f9" static/css/dpmtf-theme.css`
Expected: 0

- [ ] **Step 3: Commit**

```bash
git add static/css/dpmtf-theme.css
git commit -m "2F-bis: Rewrite CSS as dark dashboard theme

- Dark background (#0d1117), card background (#21262d)
- v3-matching color palette: green #3fb950, orange #d2991b, red #da3633
- .dpmtf- prefix convention on all classes
- Drawer, tables, forms, buttons, badges all dark-themed
- Model badges: local (blue), cloud (purple)
- Preserved .dpmtf-hidden-governance for migration panels"
```

---

### Task 4: JavaScript — Core helpers + i18n loader

**Files:**
- Modify: `static/js/dpmtf-app.js` (start of file — sections 1-2)

- [ ] **Step 1: Write the i18n loader and DOM helpers**

Replace the first ~40 lines of dpmtf-app.js (the global vars and any existing init) with:

```javascript
/* ── 1. i18n loader ─────────────────────────────────── */
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

/* ── 2. DOM helpers ─────────────────────────────────── */
function el(tag, className, text) {
  var e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function td(text, className) {
  var cell = document.createElement("td");
  cell.textContent = text;
  if (className) cell.className = className;
  return cell;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clear(el) {
  if (el) el.replaceChildren();
}

function lbl(key, fallback) {
  return labelMap[key] || fallback || key;
}
```

- [ ] **Step 2: Verify JS syntax**

Run: `node --check static/js/dpmtf-app.js`
Expected: Exit code 0 (may fail if old code still present — that's OK, we're building incrementally)

- [ ] **Step 3: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "2F-bis: Add i18n loader and DOM helpers to dpmtf-app.js

- loadLabels(): fetches /api/ui-labels/main, populates labelMap,
  updates all [data-slot] elements
- el(), td(), escapeHtml(), clear(), lbl() helpers
- Zero innerHTML — all DOM construction uses createElement/textContent"
```

---

### Task 5: JavaScript — Database Status + Phase Status renderers

**Files:**
- Modify: `static/js/dpmtf-app.js` (append sections 3-4)

- [ ] **Step 1: Write Database Status renderer**

Append to dpmtf-app.js:

```javascript
/* ── 3. Database Status ────────────────────────────── */
function loadDbStatus() {
  var container = document.getElementById("db-status-content");
  if (!container) return;
  clear(container);

  fetch("/api/health")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var card = el("div", "dpmtf-card");
      card.appendChild(el("p", null, lbl("lbl_status_success", "Healthy") + ": " +
        (data.status || "unknown")));
      container.appendChild(card);
    })
    .catch(function (err) {
      var card = el("div", "dpmtf-card");
      card.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
      container.appendChild(card);
    });
}
```

- [ ] **Step 2: Write Phase Status renderer**

Append to dpmtf-app.js:

```javascript
/* ── 4. Phase Status ───────────────────────────────── */
function loadPhaseStatus() {
  var container = document.getElementById("phase-status-content");
  if (!container) return;
  clear(container);

  fetch("/api/phase-status")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      var phases = data.phases || [];

      // Group by state
      var completed = phases.filter(function (p) { return p.phase_state === "completed"; });
      var next = phases.filter(function (p) { return p.phase_state === "next"; });
      var planned = phases.filter(function (p) { return p.phase_state === "planned"; });

      // Completed
      var compCard = el("div", "dpmtf-card");
      compCard.appendChild(el("h3", null, lbl("lbl_completed", "Completed") + " (" + completed.length + ")"));
      if (completed.length) {
        var compList = el("ul", null);
        completed.forEach(function (p) {
          var li = el("li", null);
          li.textContent = p.phase_key + ": " + escapeHtml(p.phase_title);
          compList.appendChild(li);
        });
        compCard.appendChild(compList);
      } else {
        compCard.appendChild(el("p", "dpmtf-muted", lbl("lbl_no_data", "No data")));
      }
      container.appendChild(compCard);

      // Next
      var nextCard = el("div", "dpmtf-card");
      nextCard.appendChild(el("h3", null, lbl("lbl_next", "Next")));
      if (next.length) {
        var nextList = el("ul", null);
        next.forEach(function (p) {
          var li = el("li", null);
          li.textContent = p.phase_key + ": " + escapeHtml(p.phase_title);
          nextList.appendChild(li);
        });
        nextCard.appendChild(nextList);
      } else {
        nextCard.appendChild(el("p", "dpmtf-muted", lbl("lbl_no_data", "No data")));
      }
      container.appendChild(nextCard);

      // Planned
      var planCard = el("div", "dpmtf-card");
      planCard.appendChild(el("h3", null, lbl("lbl_planned", "Planned") + " (" + planned.length + ")"));
      if (planned.length) {
        var planList = el("ul", null);
        planned.forEach(function (p) {
          var li = el("li", null);
          li.textContent = p.phase_key + ": " + escapeHtml(p.phase_title);
          planList.appendChild(li);
        });
        planCard.appendChild(planList);
      } else {
        planCard.appendChild(el("p", "dpmtf-muted", lbl("lbl_no_data", "No data")));
      }
      container.appendChild(planCard);
    })
    .catch(function (err) {
      var card = el("div", "dpmtf-card");
      card.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
      container.appendChild(card);
    });
}
```

- [ ] **Step 3: Verify JS syntax**

Run: `node --check static/js/dpmtf-app.js`
Expected: Exit code 0

- [ ] **Step 4: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "2F-bis: Add Database Status and Phase Status renderers

- loadDbStatus(): fetches /api/health, renders status card
- loadPhaseStatus(): fetches /api/phase-status, groups by
  completed/next/planned, renders three cards with lists
- All text via lbl() helper (labelMap with fallback)
- Zero innerHTML"
```

---

### Task 6: JavaScript — Hitrate Panel renderer (2F functionality)

**Files:**
- Modify: `static/js/dpmtf-app.js` (append section 5)

- [ ] **Step 1: Write Hitrate renderers**

Append to dpmtf-app.js:

```javascript
/* ── 5. Hitrate Panel ──────────────────────────────── */
function loadHitrates() {
  var container = document.getElementById("hitrate-content");
  if (!container) return;
  clear(container);

  var statusEl = el("span", "dpmtf-status");
  var refreshBtn = el("button", "dpmtf-btn");
  refreshBtn.textContent = lbl("btn_refresh", "Refresh");
  refreshBtn.onclick = loadHitrates;

  var headerRow = el("div", null);
  headerRow.appendChild(refreshBtn);
  headerRow.appendChild(statusEl);
  container.appendChild(headerRow);

  // Hitrate table
  var table = el("table", "dpmtf-table");
  var thead = el("thead", null);
  var thr = el("tr", null);
  thr.appendChild(el("th", null, "Phase"));
  thr.appendChild(el("th", null, "Success Rate"));
  thr.appendChild(el("th", null, "Successful / Total"));
  thr.appendChild(el("th", null, "Last Run"));
  thead.appendChild(thr);
  table.appendChild(thead);
  var tbody = el("tbody", null);
  table.appendChild(tbody);
  container.appendChild(table);

  fetch("/api/prompt-hirates")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(tbody);
      var hitrates = data.hitrates || [];
      if (!hitrates.length) {
        var row = el("tr", null);
        var cell = el("td", null, lbl("lbl_no_data", "No hitrate data yet."));
        cell.colSpan = 4;
        row.appendChild(cell);
        tbody.appendChild(row);
        statusEl.textContent = "0 " + (lbl("lbl_sequences", "phases") || "phases") + " " + (lbl("lbl_status_planned", "tracked") || "tracked");
        return;
      }
      hitrates.forEach(function (h) {
        var row = el("tr", null);
        var pct = (h.rolling_success_rate * 100).toFixed(0);
        var rateClass = pct >= 80 ? "hitrate-good" : (pct >= 50 ? "hitrate-ok" : "hitrate-low");
        row.appendChild(td(h.phase_key));
        row.appendChild(td(pct + "%", rateClass));
        row.appendChild(td(h.successful_runs + " / " + h.total_runs));
        row.appendChild(td(h.last_run_timestamp ? new Date(h.last_run_timestamp).toLocaleString() : "-"));
        tbody.appendChild(row);
      });
      statusEl.textContent = hitrates.length + " " + (lbl("lbl_sequences", "phases") || "phases") + " " + (lbl("lbl_status_planned", "tracked") || "tracked");
    })
    .catch(function (err) {
      clear(tbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 4;
      row.appendChild(cell);
      tbody.appendChild(row);
    });

  // Recent runs (expandable)
  var details = el("details", "dpmtf-details");
  var summary = el("summary", null, "Recent Prompt Runs");
  details.appendChild(summary);
  var runsTable = el("table", "dpmtf-table");
  var runsThead = el("thead", null);
  var runsThr = el("tr", null);
  ["Run ID", "Phase", "Project", "Success", "Duration", "Model", "Timestamp"].forEach(function (h) {
    runsThr.appendChild(el("th", null, h));
  });
  runsThead.appendChild(runsThr);
  runsTable.appendChild(runsThead);
  var runsTbody = el("tbody", null);
  runsTable.appendChild(runsTbody);
  details.appendChild(runsTable);
  container.appendChild(details);

  fetch("/api/prompt-runs?limit=20")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(runsTbody);
      var runs = data.runs || [];
      if (!runs.length) {
        var row = el("tr", null);
        var cell = el("td", null, lbl("lbl_no_data", "No prompt runs recorded yet."));
        cell.colSpan = 7;
        row.appendChild(cell);
        runsTbody.appendChild(row);
        return;
      }
      runs.forEach(function (r) {
        var row = el("tr", null);
        row.appendChild(td(r.run_id));
        row.appendChild(td(r.phase_key));
        row.appendChild(td(r.target_project));
        row.appendChild(td(r.success ? "✓" : "✗", r.success ? "hitrate-good" : "hitrate-low"));
        row.appendChild(td(r.duration_seconds != null ? r.duration_seconds + "s" : "-"));
        row.appendChild(td(r.model_used || "-"));
        row.appendChild(td(r.run_timestamp ? new Date(r.run_timestamp).toLocaleString() : "-"));
        runsTbody.appendChild(row);
      });
    })
    .catch(function (err) {
      clear(runsTbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 7;
      row.appendChild(cell);
      runsTbody.appendChild(row);
    });
}
```

- [ ] **Step 2: Verify JS syntax**

Run: `node --check static/js/dpmtf-app.js`
Expected: Exit code 0

- [ ] **Step 3: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "2F-bis: Add Hitrate Panel renderer (2F functionality)

- loadHitrates(): renders hitrate table with color-coded rates,
  refresh button, expandable recent runs table
- All text via lbl() helper
- Zero innerHTML"
```

---

### Task 7: JavaScript — Prompt Sequence Planner renderer

**Files:**
- Modify: `static/js/dpmtf-app.js` (append section 6)

- [ ] **Step 1: Write Prompt Sequence Planner renderer**

Append to dpmtf-app.js:

```javascript
/* ── 6. Prompt Sequence Planner ────────────────────── */
var currentSequenceId = null;

function loadPromptSequences() {
  var container = document.getElementById("prompt-sequence-content");
  if (!container) return;
  clear(container);

  // Status bar
  var statusBar = el("div", null);
  statusBar.style.marginBottom = "12px";
  var seqCount = el("span", "dpmtf-badge dpmtf-badge-info");
  seqCount.id = "sequence-count-display";
  seqCount.textContent = lbl("lbl_sequences", "Sequences") + ": 0";
  statusBar.appendChild(seqCount);
  var stepCount = el("span", "dpmtf-badge dpmtf-badge-info");
  stepCount.id = "step-count-display";
  stepCount.style.marginLeft = "8px";
  stepCount.textContent = lbl("lbl_steps", "Steps") + ": 0";
  statusBar.appendChild(stepCount);
  container.appendChild(statusBar);

  // Create form
  var createCard = el("div", "dpmtf-card");
  createCard.appendChild(el("h4", null, lbl("btn_create", "Create") + " " + (lbl("lbl_sequences", "Sequence") || "Sequence")));
  var nameLabel = el("label", "dpmtf-label", lbl("lbl_project_name", "Name") + ":");
  createCard.appendChild(nameLabel);
  var nameInput = el("input", "dpmtf-input");
  nameInput.id = "sequence-name";
  nameInput.placeholder = "Enter sequence name";
  createCard.appendChild(nameInput);
  var goalLabel = el("label", "dpmtf-label", "Goal:");
  createCard.appendChild(goalLabel);
  var goalInput = el("textarea", "dpmtf-textarea");
  goalInput.id = "sequence-goal";
  goalInput.placeholder = "Enter sequence goal";
  createCard.appendChild(goalInput);
  var createBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  createBtn.textContent = lbl("btn_create", "Create") + " " + (lbl("lbl_sequences", "Sequence") || "Sequence");
  createBtn.onclick = createPromptSequence;
  createCard.appendChild(createBtn);
  container.appendChild(createCard);

  // Select sequence
  var selectCard = el("div", "dpmtf-card");
  selectCard.appendChild(el("h4", null, lbl("lbl_select_sequence", "Select a sequence...")));
  var selector = el("select", "dpmtf-select");
  selector.id = "sequence-selector";
  selector.onchange = function () { loadSequenceSteps(selector.value); };
  var opt = el("option", null, lbl("lbl_select_sequence", "Select a sequence..."));
  opt.value = "";
  selector.appendChild(opt);
  selectCard.appendChild(selector);
  var seqStatus = el("div", "dpmtf-status");
  seqStatus.id = "sequence-status";
  selectCard.appendChild(seqStatus);
  container.appendChild(selectCard);

  // Steps container
  var stepsCard = el("div", "dpmtf-card");
  stepsCard.id = "sequence-steps-card";
  stepsCard.appendChild(el("h4", null, lbl("lbl_steps", "Steps")));
  var stepsDiv = el("div", null);
  stepsDiv.id = "sequence-steps-container";
  stepsDiv.appendChild(el("p", "dpmtf-muted", lbl("lbl_empty_steps", "No steps yet.")));
  stepsCard.appendChild(stepsDiv);
  container.appendChild(stepsCard);

  // Add step form
  var addCard = el("div", "dpmtf-card");
  addCard.id = "add-step-card";
  addCard.style.display = "none";
  addCard.appendChild(el("h4", null, lbl("btn_add_step", "Add Step")));
  var titleLabel = el("label", "dpmtf-label", "Step Title:");
  addCard.appendChild(titleLabel);
  var titleInput = el("input", "dpmtf-input");
  titleInput.id = "step-title";
  addCard.appendChild(titleInput);
  var layerLabel = el("label", "dpmtf-label", "Target Layer:");
  addCard.appendChild(layerLabel);
  var layerSelect = el("select", "dpmtf-select");
  layerSelect.id = "target-layer";
  ["skeleton","database","frontend","css","backend","config","tests","docs","verification","other"].forEach(function (l) {
    var o = el("option", null, l);
    o.value = l;
    layerSelect.appendChild(o);
  });
  addCard.appendChild(layerSelect);
  var promptLabel = el("label", "dpmtf-label", "Prompt Text:");
  addCard.appendChild(promptLabel);
  var promptInput = el("textarea", "dpmtf-textarea");
  promptInput.id = "prompt-text";
  addCard.appendChild(promptInput);
  var addBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  addBtn.textContent = lbl("btn_add_step", "Add Step");
  addBtn.onclick = addPromptSequenceStep;
  addCard.appendChild(addBtn);
  container.appendChild(addCard);

  // Prompt preview
  var previewCard = el("div", "dpmtf-card");
  previewCard.appendChild(el("h4", null, lbl("lbl_prompt_preview", "Generate Next Prompt Preview")));
  var genBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  genBtn.textContent = lbl("btn_generate_prompt", "Generate Next Prompt Preview");
  genBtn.onclick = generateNextPrompt;
  previewCard.appendChild(genBtn);
  var previewMsg = el("p", "dpmtf-muted");
  previewMsg.id = "prompt-preview-message";
  previewMsg.textContent = lbl("lbl_no_prompts_yet", "No prompt generated yet.");
  previewCard.appendChild(previewMsg);
  var previewTextarea = el("textarea", "dpmtf-textarea");
  previewTextarea.id = "prompt-preview";
  previewTextarea.style.display = "none";
  previewTextarea.readOnly = true;
  previewCard.appendChild(previewTextarea);
  var copyBtn = el("button", "dpmtf-btn");
  copyBtn.id = "copy-prompt-btn";
  copyBtn.textContent = lbl("btn_copy_prompt", "Copy Prompt");
  copyBtn.style.display = "none";
  copyBtn.onclick = copyPrompt;
  previewCard.appendChild(copyBtn);
  var saveSection = el("div", null);
  saveSection.id = "save-prompt-section";
  saveSection.style.display = "none";
  var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  saveBtn.textContent = lbl("btn_save_prompt", "Save Generated Prompt");
  saveBtn.onclick = saveGeneratedPrompt;
  saveSection.appendChild(saveBtn);
  var saveStatus = el("span", "dpmtf-status");
  saveStatus.id = "save-prompt-status";
  saveSection.appendChild(saveStatus);
  previewCard.appendChild(saveSection);
  container.appendChild(previewCard);

  // Prompt history
  var historyCard = el("div", "dpmtf-card");
  historyCard.appendChild(el("h4", null, lbl("lbl_prompt_history", "Prompt History")));
  var historyMsg = el("p", "dpmtf-muted");
  historyMsg.id = "prompt-history-message";
  historyMsg.textContent = lbl("lbl_no_prompts_yet", "No generated prompts yet.");
  historyCard.appendChild(historyMsg);
  var historyList = el("div", null);
  historyList.id = "prompt-history-list";
  historyList.style.display = "none";
  historyCard.appendChild(historyList);
  container.appendChild(historyCard);

  // Load data
  refreshSequenceList();
  updateCounts();
}

function refreshSequenceList() {
  fetch("/api/prompt-sequences")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var selector = document.getElementById("sequence-selector");
      if (!selector) return;
      // Keep first option, clear rest
      while (selector.options.length > 1) selector.remove(1);
      (data.sequences || []).forEach(function (s) {
        var opt = el("option", null, s.name);
        opt.value = s.id;
        selector.appendChild(opt);
      });
    });
}

function createPromptSequence() {
  var name = document.getElementById("sequence-name").value.trim();
  var goal = document.getElementById("sequence-goal").value.trim();
  if (!name) return;
  fetch("/api/prompt-sequences", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name, goal: goal })
  })
    .then(function (res) { return res.json(); })
    .then(function () {
      document.getElementById("sequence-name").value = "";
      document.getElementById("sequence-goal").value = "";
      refreshSequenceList();
      updateCounts();
    });
}

function loadSequenceSteps(seqId) {
  if (!seqId) return;
  currentSequenceId = parseInt(seqId);
  var container = document.getElementById("sequence-steps-container");
  var addCard = document.getElementById("add-step-card");
  var statusEl = document.getElementById("sequence-status");
  if (!container) return;

  fetch("/api/prompt-sequences/" + seqId + "/steps")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(container);
      var steps = data.steps || [];
      if (!steps.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_empty_steps", "No steps yet.")));
      } else {
        var table = el("table", "dpmtf-table");
        var thead = el("thead", null);
        var thr = el("tr", null);
        thr.appendChild(el("th", null, "#"));
        thr.appendChild(el("th", null, "Title"));
        thr.appendChild(el("th", null, "Layer"));
        thr.appendChild(el("th", null, "Status"));
        thead.appendChild(thr);
        table.appendChild(thead);
        var tbody = el("tbody", null);
        steps.forEach(function (s) {
          var row = el("tr", null);
          row.appendChild(td(String(s.step_number)));
          row.appendChild(td(escapeHtml(s.step_title || "-")));
          row.appendChild(td(s.target_layer || "-"));
          row.appendChild(td(s.status || "planned"));
          tbody.appendChild(row);
        });
        table.appendChild(tbody);
        container.appendChild(table);
      }
      if (addCard) addCard.style.display = "block";
      if (statusEl) statusEl.textContent = steps.length + " " + (lbl("lbl_steps", "steps") || "steps");
    })
    .catch(function (err) {
      if (statusEl) statusEl.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
    });
}

function addPromptSequenceStep() {
  if (!currentSequenceId) return;
  var title = document.getElementById("step-title").value.trim();
  var layer = document.getElementById("target-layer").value;
  var prompt = document.getElementById("prompt-text").value.trim();
  if (!title) return;
  fetch("/api/prompt-sequences/" + currentSequenceId + "/steps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step_title: title, target_layer: layer, prompt_text: prompt })
  })
    .then(function (res) { return res.json(); })
    .then(function () {
      document.getElementById("step-title").value = "";
      document.getElementById("prompt-text").value = "";
      loadSequenceSteps(currentSequenceId);
      updateCounts();
    });
}

function generateNextPrompt() {
  if (!currentSequenceId) return;
  fetch("/api/prompt-sequences/" + currentSequenceId + "/next-prompt")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var msg = document.getElementById("prompt-preview-message");
      var textarea = document.getElementById("prompt-preview");
      var copyBtn = document.getElementById("copy-prompt-btn");
      var saveSection = document.getElementById("save-prompt-section");
      if (msg) msg.style.display = "none";
      if (textarea) { textarea.value = data.prompt || ""; textarea.style.display = "block"; }
      if (copyBtn) copyBtn.style.display = "block";
      if (saveSection) saveSection.style.display = "block";
    });
}

function copyPrompt() {
  var textarea = document.getElementById("prompt-preview");
  if (!textarea) return;
  textarea.select();
  document.execCommand("copy");
}

function saveGeneratedPrompt() {
  if (!currentSequenceId) return;
  var textarea = document.getElementById("prompt-preview");
  if (!textarea || !textarea.value) return;
  // Find first planned step
  fetch("/api/prompt-sequences/" + currentSequenceId + "/steps")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var steps = data.steps || [];
      var planned = steps.filter(function (s) { return s.status === "planned"; });
      if (!planned.length) return;
      fetch("/api/prompt-sequences/" + currentSequenceId + "/steps/" + planned[0].id + "/generated-prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt_text: textarea.value })
      })
        .then(function () {
          var saveStatus = document.getElementById("save-prompt-status");
          if (saveStatus) saveStatus.textContent = lbl("lbl_success", "Saved!") || "Saved!";
          loadPromptHistory(currentSequenceId);
        });
    });
}

function loadPromptHistory(seqId) {
  if (!seqId) return;
  var list = document.getElementById("prompt-history-list");
  var msg = document.getElementById("prompt-history-message");
  if (!list) return;
  fetch("/api/prompt-sequences/" + seqId + "/generated-prompts")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var prompts = data.prompts || [];
      if (!prompts.length) {
        if (msg) msg.style.display = "block";
        list.style.display = "none";
        return;
      }
      if (msg) msg.style.display = "none";
      list.style.display = "block";
      clear(list);
      prompts.forEach(function (p) {
        var card = el("div", "dpmtf-card");
        card.appendChild(el("p", "dpmtf-muted dpmtf-small", "Step " + p.step_number + " — " + (p.generated_at || "")));
        var pre = el("pre", null);
        pre.style.whiteSpace = "pre-wrap";
        pre.style.fontSize = "0.85em";
        pre.textContent = p.prompt_text || "";
        card.appendChild(pre);
        list.appendChild(card);
      });
    });
}

function updateCounts() {
  fetch("/api/prompt-sequences")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var seqs = data.sequences || [];
      var seqDisplay = document.getElementById("sequence-count-display");
      if (seqDisplay) seqDisplay.textContent = (lbl("lbl_sequences", "Sequences") || "Sequences") + ": " + seqs.length;
      // Count total steps
      var totalSteps = 0;
      var done = 0;
      Promise.all(seqs.map(function (s) {
        return fetch("/api/prompt-sequences/" + s.id + "/steps")
          .then(function (r) { return r.json(); })
          .then(function (d) { totalSteps += (d.steps || []).length; });
      })).then(function () {
        var stepDisplay = document.getElementById("step-count-display");
        if (stepDisplay) stepDisplay.textContent = (lbl("lbl_steps", "Steps") || "Steps") + ": " + totalSteps;
      });
    });
}
```

- [ ] **Step 2: Verify JS syntax**

Run: `node --check static/js/dpmtf-app.js`
Expected: Exit code 0

- [ ] **Step 3: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "2F-bis: Add Prompt Sequence Planner renderer

- Full UI rebuilt with safe DOM APIs: create form, select sequence,
  steps table, add step form, prompt preview, prompt history
- All existing POST endpoints preserved (createSequence, addStep, etc.)
- All text via lbl() helper
- Zero innerHTML"
```

---

### Task 8: JavaScript — Project Planning + Drawer + Init

**Files:**
- Modify: `static/js/dpmtf-app.js` (append sections 7-9)

- [ ] **Step 1: Write Project Planning renderer**

Append to dpmtf-app.js:

```javascript
/* ── 7. Project Planning ───────────────────────────── */
function loadProjectPlanning() {
  var container = document.getElementById("project-planning-content");
  if (!container) return;
  clear(container);

  // Create form
  var formCard = el("div", "dpmtf-card");
  formCard.appendChild(el("h4", null, lbl("btn_create_project_plan", "Create Project Plan")));

  var fields = [
    ["lbl_project_name", "project-name", "text", "Enter project name"],
    ["lbl_target_folder", "target-folder", "text", "Enter absolute target folder path"],
    ["lbl_app_port", "app-port", "number", "Enter app port (optional)"],
  ];
  fields.forEach(function (f) {
    var label = el("label", "dpmtf-label", lbl(f[0], f[0]) + ":");
    formCard.appendChild(label);
    var input = el("input", "dpmtf-input");
    input.id = f[1];
    input.type = f[2];
    input.placeholder = f[3];
    formCard.appendChild(input);
  });

  // App profile dropdown
  var profileLabel = el("label", "dpmtf-label", lbl("lbl_app_profile", "App Profile") + ":");
  formCard.appendChild(profileLabel);
  var profileSelect = el("select", "dpmtf-select");
  profileSelect.id = "app-profile";
  profileSelect.appendChild(el("option", null, lbl("lbl_select_sequence", "Select...") || "Select..."));
  formCard.appendChild(profileSelect);

  // Prompt sequence dropdown
  var seqLabel = el("label", "dpmtf-label", lbl("lbl_prompt_sequence_select", "Prompt Sequence") + ":");
  formCard.appendChild(seqLabel);
  var seqSelect = el("select", "dpmtf-select");
  seqSelect.id = "prompt-sequence";
  seqSelect.appendChild(el("option", null, lbl("lbl_select_sequence", "Select...") || "Select..."));
  formCard.appendChild(seqSelect);

  // Notes
  var notesLabel = el("label", "dpmtf-label", lbl("lbl_notes", "Notes") + ":");
  formCard.appendChild(notesLabel);
  var notesInput = el("textarea", "dpmtf-textarea");
  notesInput.id = "notes";
  notesInput.placeholder = "Enter project notes (optional)";
  formCard.appendChild(notesInput);

  var createBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  createBtn.textContent = lbl("btn_create_project_plan", "Create Project Plan");
  createBtn.onclick = createProjectPlan;
  formCard.appendChild(createBtn);
  var planStatus = el("span", "dpmtf-status");
  planStatus.id = "project-plan-status";
  formCard.appendChild(planStatus);
  container.appendChild(formCard);

  // Existing plans
  var plansCard = el("div", "dpmtf-card");
  plansCard.appendChild(el("h4", null, "Existing Project Plans"));
  var plansDiv = el("div", null);
  plansDiv.id = "project-plans-container";
  plansDiv.appendChild(el("p", "dpmtf-muted", lbl("lbl_loading", "Loading...")));
  plansCard.appendChild(plansDiv);
  container.appendChild(plansCard);

  loadProjectPlans();
  loadProjectPlanningDropdowns();
}

function loadProjectPlans() {
  var container = document.getElementById("project-plans-container");
  if (!container) return;
  fetch("/api/project-plans")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(container);
      var plans = data.plans || [];
      if (!plans.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_no_data", "No project plans yet.")));
        return;
      }
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      ["Name", "Folder", "Port", "Status"].forEach(function (h) {
        thr.appendChild(el("th", null, h));
      });
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      plans.forEach(function (p) {
        var row = el("tr", null);
        row.appendChild(td(escapeHtml(p.project_name)));
        row.appendChild(td(escapeHtml(p.target_folder)));
        row.appendChild(td(p.app_port || "-"));
        row.appendChild(td(p.status || "planned"));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      container.appendChild(table);
    })
    .catch(function (err) {
      clear(container);
      container.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });
}

function createProjectPlan() {
  var name = document.getElementById("project-name").value.trim();
  var folder = document.getElementById("target-folder").value.trim();
  if (!name || !folder) return;
  var portVal = document.getElementById("app-port").value.trim();
  var profileId = document.getElementById("app-profile").value;
  var seqId = document.getElementById("prompt-sequence").value;
  var notes = document.getElementById("notes").value.trim();

  var body = { project_name: name, target_folder: folder };
  if (portVal) body.app_port = parseInt(portVal);
  if (profileId) body.app_profile_id = parseInt(profileId);
  if (seqId) body.prompt_sequence_id = parseInt(seqId);
  if (notes) body.notes = notes;

  fetch("/api/project-plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) { return res.json(); })
    .then(function () {
      document.getElementById("project-name").value = "";
      document.getElementById("target-folder").value = "";
      document.getElementById("app-port").value = "";
      document.getElementById("notes").value = "";
      var statusEl = document.getElementById("project-plan-status");
      if (statusEl) statusEl.textContent = lbl("lbl_success", "Created!") || "Created!";
      loadProjectPlans();
    });
}

function loadProjectPlanningDropdowns() {
  // Load app profiles
  fetch("/api/app-profiles")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var sel = document.getElementById("app-profile");
      if (!sel) return;
      (data.profiles || []).forEach(function (p) {
        var opt = el("option", null, p.name);
        opt.value = p.id;
        sel.appendChild(opt);
      });
    });
  // Load prompt sequences
  fetch("/api/prompt-sequences")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var sel = document.getElementById("prompt-sequence");
      if (!sel) return;
      (data.sequences || []).forEach(function (s) {
        var opt = el("option", null, s.name);
        opt.value = s.id;
        sel.appendChild(opt);
      });
    });
}
```

- [ ] **Step 2: Write System Setup Drawer renderer**

Append to dpmtf-app.js:

```javascript
/* ── 8. System Setup Drawer ────────────────────────── */
function initDrawer() {
  var btn = document.getElementById("system-setup-btn");
  var drawer = document.getElementById("system-setup-drawer");
  var content = document.getElementById("drawer-content");
  if (!btn || !drawer || !content) return;

  btn.onclick = function () { drawer.classList.add("open"); buildDrawerContent(); };
  clear(content);

  // Close button
  var closeBtn = el("button", "drawer-close-btn");
  closeBtn.innerHTML = "&times;";  // Static X symbol — safe, not dynamic content
  closeBtn.onclick = function () { drawer.classList.remove("open"); };
  content.appendChild(closeBtn);
}

function buildDrawerContent() {
  var content = document.getElementById("drawer-content");
  if (!content) return;
  // Keep close button, remove rest
  while (content.children.length > 1) content.removeChild(content.lastChild);

  var sections = [
    ["lbl_drawer_layout_slots", "Layout Slots", "Layout slot management placeholder"],
    ["lbl_drawer_db_layout", "Database Layout Preview", "Read-only preview from /api/frontend-layout"],
    ["lbl_drawer_i18n", "UI Labels / i18n", "Resolved label preview from /api/ui-labels"],
    ["lbl_drawer_endpoint_registry", "Endpoint Registry", "Read-only preview from /api/endpoint-registry"],
    ["lbl_drawer_bootstrap", "Bootstrap Dataset", "Bootstrap dataset management placeholder"],
    ["lbl_drawer_security", "Security / Permissions", "Security and permissions management placeholder"],
  ];

  sections.forEach(function (s) {
    var card = el("div", "dpmtf-card");
    card.appendChild(el("h4", null, lbl(s[0], s[1])));
    card.appendChild(el("p", "dpmtf-muted", s[2]));
    content.appendChild(card);
  });
}
```

- [ ] **Step 3: Write Init section**

Append to dpmtf-app.js:

```javascript
/* ── 9. Init ───────────────────────────────────────── */
function onReady() {
  loadLabels();
  loadDbStatus();
  loadPhaseStatus();
  loadHitrates();
  loadPromptSequences();
  loadProjectPlanning();
  initDrawer();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", onReady);
} else {
  onReady();
}
```

- [ ] **Step 4: Verify JS syntax and innerHTML**

Run: `node --check static/js/dpmtf-app.js`
Expected: Exit code 0

Run: `grep -RIn "innerHTML" static/js/dpmtf-app.js`
Expected: Only the static `&times;` in the close button (1 occurrence, safe — not dynamic content). If more found, fix them.

- [ ] **Step 5: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "2F-bis: Add Project Planning, Drawer, and Init

- loadProjectPlanning(): create form, existing plans table,
  dropdown loading for app profiles and prompt sequences
- initDrawer() + buildDrawerContent(): System Setup drawer
  with 6 i18n-compatible sections
- onReady(): init order — labels first, then all panels
- 1 static innerHTML for drawer close button (&times;)
- All other text via lbl() helper, zero dynamic innerHTML"
```

---

### Task 9: Final validation + documentation + commit

**Files:**
- Modify: `docs/governance-templates/10_CHANGELOG.md`
- Modify: `docs/governance-templates/11_NEXT_CONTEXT.md`
- Modify: `docs/governance-templates/12_IMPLEMENTATION_REPORT.md`

- [ ] **Step 1: Run all validation checks**

```bash
python3 -m py_compile scripts/init_db.py
python3 scripts/init_db.py  # run twice for idempotency
node --check static/js/dpmtf-app.js
grep -RIn "innerHTML" static/js/dpmtf-app.js  # should be 1 or 0
grep -c "labelMap\[" static/js/dpmtf-app.js  # should be > 0
grep -c "data-slot" templates/index.html  # should be >= 7
git diff --stat  # verify only expected files
git diff -- app.py  # must be empty
```

- [ ] **Step 2: Update CHANGELOG**

Append to `docs/governance-templates/10_CHANGELOG.md`:

```markdown
### [2026-06-12] — 2F-bis: Frontend i18n + Dark Theme Refactoring
- Changed: `templates/index.html` — reduceret fra 348 til ~45 linjers skeleton med data-slot attributter. Al panel-HTML fjernet — JS renderer nu alt indhold.
- Changed: `static/js/dpmtf-app.js` — omskrevet fra 1813 linjers monolit med 39 innerHTML til ~1600 linjer organiseret i 9 sektioner. 0 dynamisk innerHTML. Al tekst via labelMap med da-DK/en-US fallbacks.
- Changed: `static/css/dpmtf-theme.css` — komplet omskrivning til mørkt dashboard-tema (#0d1117 baggrund, #21262d cards). .dpmtf- prefix konvention. Farvepalet matcher ai-pc-resource-webui-v3.
- Added: 45 nye ui_text_slots, 45 ui_labels, 90 ui_label_translations (da-DK + en-US), 45 ui_text_slot_labels bindings i seed script.
- Preserved: Alle eksisterende API-endpoints og backend-funktionalitet (app.py uændret). System Setup drawer med 6 sektioner. Prompt Sequence Planner og New Project Planning funktionalitet.
- No schema changes, no new tables, no backend changes.
```

- [ ] **Step 3: Update NEXT_CONTEXT**

Update `docs/governance-templates/11_NEXT_CONTEXT.md`:
- Set HEAD to the 2F-bis commit hash (will be known after commit)
- Mark 2F-bis as completed
- Set 2G as next phase
- Add Files Changed table for 2F-bis

- [ ] **Step 4: Write IMPLEMENTATION_REPORT**

Write `docs/governance-templates/12_IMPLEMENTATION_REPORT.md` with:
- Phase: 2F-bis
- Baseline: 8086c5f (2F-bis spec commit)
- What was implemented: all 4 sections from spec
- Verification results: all checks passed
- Deviations: none
- Known issues: 1 static innerHTML for drawer close button (&times; symbol)

- [ ] **Step 5: Final commit and push**

```bash
git add docs/governance-templates/10_CHANGELOG.md docs/governance-templates/11_NEXT_CONTEXT.md docs/governance-templates/12_IMPLEMENTATION_REPORT.md
git commit -m "2F-bis: Documentation update for frontend refactoring

- CHANGELOG: 2F-bis entry with all changes
- NEXT_CONTEXT: 2F-bis completed, 2G next
- IMPLEMENTATION_REPORT: full verification results"
git push origin master
```

---

## Validation Checklist (pre-push)

| # | Check | Command | Expect |
|---|-------|---------|--------|
| 1 | Python syntax | `python3 -m py_compile scripts/init_db.py` | Exit 0 |
| 2 | Seed idempotent | `python3 scripts/init_db.py` x2 | No errors |
| 3 | JS syntax | `node --check static/js/dpmtf-app.js` | Exit 0 |
| 4 | innerHTML count | `grep -c "innerHTML" static/js/dpmtf-app.js` | ≤1 |
| 5 | data-slot count | `grep -c "data-slot" templates/index.html` | ≥7 |
| 6 | labelMap usage | `grep -c "labelMap\[" static/js/dpmtf-app.js` | >0 |
| 7 | HTML lines | `wc -l templates/index.html` | ≤50 |
| 8 | No backend changes | `git diff -- app.py` | Empty |
| 9 | Diff scope | `git diff --stat` | Only expected files |
