# Plan: Model Allocator Carve-Out

## Goal

Move all model-allocator UI and config management into the model-allocator
repo. DPMtF-WebUI is simplified to just reference an allocation model alias
and test "OK" — nothing more.

---

## Current State (Problem)

DPMtF-WebUI contains:
- `static/js/allocator.js` (371 lines) — full allocator dashboard
- `routers/bridge.py` — 81 lines referencing allocator, including:
  - `GET /allocator/aliases` — list aliases
  - `POST /allocator/validate` — validate alias
  - `GET /allocator/status/{alias}` — runtime status
  - `POST /allocator/start/{alias}` — start model
  - `POST /allocator/stop/{alias}` — stop model
  - `GET /allocator/config` — show config
  - `POST /allocator/config/alias` — set alias
  - `DELETE /allocator/config/alias/{alias}` — delete alias
  - `POST /allocator/config/role` — set role
  - `DELETE /allocator/config/role/{role}` — delete role
- `bridge_roles` table — `default_model_source`, `default_model_alias` columns
- `bridge_flow_steps` table — `model_source`, `model_alias` columns
- `dispatch.py` — `_run_allocator_start()`, `_run_allocator_stop()`,
  `_model_allocator_path()`, warm-up calls
- `scheduler.py` — `_resolve_alias()`, `_resolve_context_window()`,
  `allocator_script` path
- `bridge_lib.py` — `get_effective_model_source()` (queries DPMtF DB for
  alias, then shells out to allocator CLI)
- `start_coding.py` — uses `get_effective_model_source()` + allocator
  `run` command to start coding frontends

Model-allocator repo contains:
- CLI with `config set-alias`, `config delete-alias`, `config set-role`,
  `config delete-role`, `validate`, `list`, `start`, `stop`, `status`,
  `run`, `resolve`, `preflight`, `doctor`
- YAML config (`models.yaml`, `roles.yaml`, `runtime_profiles.yaml`)
- 95 tests
- MCP server (onyx tools)
- **No frontend/UI**

## Target State

### Model-Allocator Repo (gains frontend)

New: `src/model_allocator/web/` — FastAPI web server + static frontend:

**Frontend pages:**
1. **Aliases** — list all allocation models, create new, edit, delete,
   validate (OK/Error), start/stop runtime
2. **Roles** — list role→alias mappings, create new, edit, delete
3. **Runtime Profiles** — list/edit runtime profiles (Ollama, llama.cpp,
   cloud endpoints)
4. **Validate** — select alias + client → run `validate` → show OK/Error
   with details (resolved backend, model, context window)
5. **Preflight** — select alias → run `preflight` → show full check
   (resolve + validate + start + reachability)

**API endpoints (new, in model-allocator repo):**
```
GET    /api/models                     — list all allocation models
POST   /api/models                     — create/update allocation model
DELETE /api/models/{alias}             — delete allocation model
POST   /api/models/{alias}/validate    — validate model for client
POST   /api/models/{alias}/start       — start model runtime
POST   /api/models/{alias}/stop        — stop model runtime
GET    /api/models/{alias}/status      — runtime status

GET    /api/profiles                   — list runtime profiles
POST   /api/profiles                   — create/update profile

GET    /api/config                     — full config dump (JSON)
POST   /api/doctor                     — run doctor checks
```

Note: No `/api/roles` endpoints — roles live in DPMtF.

**Tech stack:** FastAPI + vanilla JS, following DPMtF-WebUI frontend
governance (`30_FRONTEND_GOVERNANCE.md`):
- Dark theme (GitHub-dark palette: `#0d1117` background, `#e6edf3` text,
  `#30363d` borders, `#58a6ff` accents) — reuse `dpmtf-theme.css` or
  extract a shared theme file
- `const` by default, `let` only when reassignment needed. Never `var`.
- Event delegation on container elements, not individual listeners
- Class-based selectors (not ID selectors for styling)
- No inline `style=""` attributes for layout
- `dpmtf-hidden` class for hiding elements
- No `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`
- `node --check` MUST pass on all JS files
- `data-slot` attributes on headings for i18n label binding
- Every user-facing string uses `lbl(key, fallback)` pattern

**Panel layout — mandatory structure:**

The allocator frontend MUST use the same panel-group architecture as
DPMtF-WebUI. Panel groups are fixed and ordered:

```
Daily → Journals → Reports → Periodic → Setup
```

Each group has a collapsible header with a toggle arrow (▼/▶) and
contains subgroups (also collapsible). State is persisted via API.

**Panel placement for allocator UI:**

| Group | Subgroup | Content | Slot Key |
|-------|----------|---------|----------|
| **Setup** | Allocation Models | Model CRUD, validate, start/stop, status | `lbl_allocator_models` |
| **Setup** | Runtime Profiles | Backend profile CRUD (Ollama, llama.cpp, cloud) | `lbl_allocator_profiles` |
| **Setup** | Validation | Validate model + preflight checks | `lbl_allocator_validation` |
| **Setup** | System | Doctor diagnostics, config overview | `lbl_allocator_system` |

All panels go in the **Setup** group — the allocator is a configuration
tool, not a daily/reports tool. The Setup group is the last group in the
layout, matching DPMtF convention.

**NOTE: "Roles" page is REMOVED from allocator UI.** DPMtF owns roles.
The allocator only manages allocation models. DPMtF roles point to
allocation models via `bridge_roles.default_model_alias` (string reference).

**Data structure — 1:N relationship:**

```
Allocation Model (1) ←──── (N) DPMtF Roles

  archi-local              archi01      (strict_review)
  ├─ backend: ollama       archi01cloud (cloud_llm)
  ├─ model: qwen3.6:35b    analyst01_trade (trade)
  ├─ context: 65536        sim01_trade (trade)
  └─ clients: opencode
     
  review02-local           review01    (strict_review)
  ├─ backend: ollama       review01cloud (cloud_llm)
  ├─ model: ornith35b      review01pay (cloud_pay)
  ├─ context: 65536        review01_trade (trade)
  └─ clients: opencode     review02    (strict_review)
```

- **1 Allocation Model** can be referenced by **N DPMtF Roles**
- **1 DPMtF Role** points to exactly **1 Allocation Model** (via `default_model_alias`)
- The allocator does NOT know which roles use its models — it just manages the models
- DPMtF is the single source of truth for role→model assignments

**What moves where:**

| Data | Now | After |
|------|-----|-------|
| Allocation model config (alias, backend, model, context, clients) | allocator `models.yaml` | allocator UI (manages `models.yaml`) |
| Role→alias mapping | allocator `roles.yaml` AND DPMtF `bridge_roles` | **DPMtF `bridge_roles` only** (allocator `roles.yaml` eliminated) |
| `config_dir` (opencode config directory) | allocator `roles.yaml` | DPMtF `bridge_roles.config_dir` (already exists) |
| Per-client alias override | allocator `roles.yaml` `client_aliases` | DPMtF `bridge_flow_steps.model_alias` (step-level override) |

**Allocator `roles.yaml` is eliminated.** `start_coding.py` reads alias
directly from DPMtF DB and passes it to `model-allocator run --alias X --client Y`
instead of `model-allocator run --role R --client Y`.

**Expand/collapse — mandatory behavior:**

Both panel groups AND subgroups MUST support expand/collapse with state
persistence, exactly as DPMtF-WebUI implements:

1. **Panel groups** — `.panel-group` with `.panel-group-header` (clickable),
   `.panel-group-toggle` (▼/▶ arrow), `.panel-group-body` (collapsible).
   Click header → toggle `.collapsed` class → hide/show body.
   State saved via `POST /api/user-panel-groups { group_name, state }`.

2. **Subgroups** — `.panel-subgroup` with `.panel-subgroup-header` (clickable),
   `.panel-subgroup-toggle` (▼/▶ arrow), `.panel-subgroup-body` (collapsible).
   Built dynamically from DB (`panel_subgroups` + `panel_subgroup_mappings`).
   Click header → toggle `.collapsed` class → hide/show body.
   State saved via `POST /api/panel-structure/subgroup-state`.

3. **CSS rules** (must match DPMtF exactly):
   ```css
   .panel-group.collapsed .panel-group-body { display: none; }
   .panel-subgroup.collapsed .panel-subgroup-body { display: none; }
   .panel-group.dpmtf-hidden { display: none; }
   ```

4. **Subgroup building** — `buildSubgroups(body, groupName, subgroups)`
   function reads from DB, creates subgroup DOM elements, moves panels
   into correct subgroup bodies based on slot→subgroup mappings.
   If no subgroups defined: implicit "All" subgroup, flat display.

**i18n — multilingual support (mandatory):**

The allocator frontend MUST include full i18n language switching,
following the same pattern as DPMtF-WebUI:

- **Language selector** in header — `<select id="lang-dropdown">` populated
  from `GET /api/available-languages`, saves preference via
  `POST /api/user-language { locale: "da-DK" }`
- **Label system** — `ui_labels` table (label_key, default_text, domain) +
  `ui_label_translations` table (label_id, locale, translated_text).
  Allocator has its own SQLite DB (`allocator.db`) with these tables.
- **Supported locales at launch:** `en-US` (default), `da-DK`, `de-DE`,
  `el-GR`, `sv-SE` — same set as DPMtF
- **Label loader** — `loadLabels()` fetches `GET /api/ui-labels/main?locale=xx`,
  populates `labelMap`, applies to all `[data-slot]` elements via
  `el.textContent = labelMap[key]`
- **Language switch** — `switchLanguage(newLocale)` saves preference,
  reloads labels, re-renders all panels with new text
- **Fallback** — if a translation is missing, `default_text` (en-US) is used
- **Every user-facing string** — button labels, panel titles, column headers,
  error messages, status text — MUST have a `label_key` and use
  `lbl(key, fallback)` — no hardcoded strings

**i18n API endpoints (in model-allocator web server):**
```
GET  /api/available-languages    — list supported locales
GET  /api/user-language           — get current user locale preference
POST /api/user-language           — save locale preference { locale: "da-DK" }
GET  /api/ui-labels/{domain}      — get labels for domain + current locale
```

**Panel structure DB tables (in allocator.db):**
```sql
-- Panel group collapse state (per user)
CREATE TABLE user_panel_groups (
    user_id    TEXT NOT NULL,
    group_name TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'expanded',
    is_visible INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, group_name)
);

-- Subgroup definitions
CREATE TABLE panel_subgroups (
    subgroup_key  TEXT PRIMARY KEY,
    group_name    TEXT NOT NULL,        -- 'daily', 'journals', 'reports', 'periodic', 'setup'
    title_da      TEXT NOT NULL,
    title_en      TEXT NOT NULL,
    sort_order    INTEGER DEFAULT 0,
    is_visible    INTEGER DEFAULT 1
);

-- Slot → subgroup mappings (which panel goes in which subgroup)
CREATE TABLE panel_subgroup_mappings (
    slot_key      TEXT NOT NULL,
    subgroup_key  TEXT NOT NULL,
    PRIMARY KEY (slot_key, subgroup_key)
);

-- Subgroup collapse state (per user)
CREATE TABLE user_panel_subgroup_states (
    user_id       TEXT NOT NULL,
    subgroup_key  TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'expanded',
    PRIMARY KEY (user_id, subgroup_key)
);
```

**Panel structure API endpoints:**
```
GET  /api/panel-structure                    — full panel structure (groups + subgroups + states)
GET  /api/user-panel-groups                  — get group collapse states for current user
POST /api/user-panel-groups                  — save group collapse state { group_name, state }
POST /api/panel-structure/subgroup-state     — save subgroup collapse state { subgroup_key, state }
```

**Seed data for panel subgroups:**
```sql
INSERT INTO panel_subgroups VALUES
('sg_setup_models',   'setup', 'Allokeringsmodeller', 'Allocation Models', 1, 1),
('sg_setup_profiles', 'setup', 'Runtime Profiler',   'Runtime Profiles',  2, 1),
('sg_setup_validate', 'setup', 'Validering',         'Validation',        3, 1),
('sg_setup_system',   'setup', 'System',             'System',            4, 1);

INSERT INTO panel_subgroup_mappings VALUES
('lbl_allocator_models',    'sg_setup_models'),
('lbl_allocator_profiles',  'sg_setup_profiles'),
('lbl_allocator_validation','sg_setup_validate'),
('lbl_allocator_system',   'sg_setup_system');
```

**Seed labels** for allocator UI (`en-US` defaults + `da-DK` translations):
- `lbl_page_title` — "Model Allocator" / "Model Allocator"
- `lbl_heading_main` — "Allocation Models" / "Allokeringsmodeller"
- `lbl_tab_models` — "Allocation Models" / "Allokeringsmodeller"
- `lbl_tab_profiles` — "Runtime Profiles" / "Runtime Profiler"
- `lbl_btn_new_model` — "New Model" / "Ny Model"
- `lbl_btn_validate` — "Validate" / "Valider"
- `lbl_btn_start` — "Start" / "Start"
- `lbl_btn_stop` — "Stop" / "Stoppet"
- `lbl_btn_delete` — "Delete" / "Slet"
- `lbl_btn_save` — "Save" / "Gem"
- `lbl_col_alias` — "Alias" / "Alias"
- `lbl_col_backend` — "Backend" / "Backend"
- `lbl_col_model` — "Model" / "Model"
- `lbl_col_context` — "Context" / "Kontekst"
- `lbl_col_status` — "Status" / "Status"
- `lbl_col_actions` — "Actions" / "Handlinger"
- `lbl_col_used_by` — "Used by" / "Brugt af"
- `lbl_status_ok` — "OK" / "OK"
- `lbl_status_error` — "Error" / "Fejl"
- `lbl_status_running` — "Running" / "Kører"
- `lbl_status_stopped` — "Stopped" / "Stoppet"
- `lbl_lang_label` — "Language" / "Sprog"

Runs on port 9140.

### DPMtF-WebUI (simplified)

**Removed from DPMtF-WebUI (completely — zero allocator UI):**
- `static/js/allocator.js` — deleted entirely (371 lines)
- All `/api/bridge-v2/allocator/*` endpoints — removed from `bridge.py` (81 lines)
- `_parse_allocator_validate_text()` — removed
- Allocator dashboard panel — removed from frontend panel config in DB
- Allocator subgroup — removed from `panel_subgroups` + `panel_subgroup_mappings`
- All allocator-related i18n labels — removed from `ui_labels` + `ui_label_translations`
- `_resolve_context_window()` in scheduler — simplified (see below)
- `allocator_script` path in scheduler — removed
- **No allocator panels, no allocator subgroups, no allocator tabs, no allocator
  dashboard — nothing allocator-related visible in DPMtF frontend**

**Kept in DPMtF-WebUI (backend only — no UI):**
- `bridge_roles.default_model_alias` — still stores the alias name
  (e.g., `archi-local`). This is just a string reference — DPMtF doesn't
  resolve it, doesn't manage it, doesn't validate it beyond "exists".
- `bridge_roles.default_model_source` — simplified to always be
  `model_allocator` (or `python_runtime` for non-tmux roles). No more
  dropdown with multiple options.
- `get_effective_model_source()` in bridge_lib.py — kept, but simplified.
  Reads alias from DB, returns `(source, alias)` tuple. DPMtF uses this
  to pass the alias to allocator CLI for start/stop.
- `dispatch.py` `_run_allocator_start()` / `_run_allocator_stop()` — kept.
  DPMtF still needs to warm/stop models during dispatch, but it just calls
  the allocator CLI — it doesn't manage config.
- `start_coding.py` — kept. Uses allocator CLI `run` command to start
  coding frontends. No config management.
- `scheduler.py` `_resolve_alias()` — kept. Reads alias from DB.
- `scheduler.py` `_resolve_context_window()` — simplified: call allocator
  CLI `validate --alias X --client opencode --json` and read
  `resolved_context` from JSON output. Same as now, just without the
  DPMtF-side config dashboard.

**New in DPMtF-WebUI (minimal — not a dashboard):**
- **"Test OK" button** on role editor — calls allocator CLI
  `validate --alias {alias} --client {client} --json` and shows
  OK / Error inline. One button, one check. No config editing.
  This is a single button in the existing role editor, NOT a separate
  panel or page.
- **Link to allocator UI** — a single link in the Setup panel that opens
  `http://localhost:9140` (model-allocator frontend) in a new tab.
  Labelled "Manage allocation models →".
  This is a hyperlink, NOT a panel.

### Data Flow (After)

```
User creates/edits allocation models
    → model-allocator UI (port 9140)
    → models.yaml / runtime_profiles.yaml

User assigns alias to DPMtF role
    → DPMtF role editor (port 9130) — existing bridge_roles form
    → bridge_roles.default_model_alias = "archi-local"
    → "Test OK" button → allocator CLI validate → OK/Error (inline, one button)

DPMtF dispatches a job
    → scheduler reads bridge_roles.default_model_alias
    → dispatch.py calls allocator CLI: start --alias archi-local
    → injects prompt into tmux
    → after completion: allocator CLI: stop --alias archi-local
```

DPMtF frontend has ZERO allocator panels. The only allocator touchpoint in
DPMtF UI is: (1) a text field for alias name in the role editor, (2) a "Test OK"
button next to it, (3) a hyperlink to port 9140.

---

## Implementation Steps

### Phase 1: Build Model-Allocator Frontend (in model-allocator repo)

1. **Add FastAPI web server** — `src/model_allocator/web/app.py`
   - Serves static frontend + JSON API
   - API endpoints wrap existing CLI functions (no business logic
     duplication — calls `config_loader`, `config_writer`, `validator`,
     `resolver` directly)
   - Port 9140

2. **Build frontend pages** — `src/model_allocator/web/static/`
   - `index.html` — SPA template following DPMtF pattern:
     - `<select id="lang-dropdown">` in `.header-row` (language selector)
     - 5 panel-group sections: `#pg-daily`, `#pg-journals`, `#pg-reports`,
       `#pg-periodic`, `#pg-setup` — all with `data-group` attributes
     - Each group: `.panel-group-header` (clickable, with toggle arrow)
       + `.panel-group-body` (collapsible)
     - Allocator panels placed in `#pg-setup` with `data-slot` attributes
     - All headings use `data-slot="lbl_..."` for i18n binding
   - `app.js` — vanilla JS:
     - i18n: `loadLabels()`, `switchLanguage()`, `lbl(key, fallback)`,
       language dropdown population + persistence
     - Panel groups: `applyPanelStructure()`, click handlers for
       expand/collapse with state persistence via API
     - Subgroups: `buildSubgroups(body, groupName, subgroups)` — reads
       from DB, creates subgroup DOM, moves panels into correct subgroups
       based on slot→subgroup mappings, click handlers for collapse
     - CRUD: alias/role/profile create/edit/delete via API calls
     - Validate: `POST /api/aliases/{alias}/validate` → show OK/Error
     - Runtime: start/stop/status via API
     - All DOM via `createElement`/`textContent`/`appendChild` (no innerHTML)
     - `dpmtf-hidden` class for toggling visibility
   - `theme.css` — GitHub-dark palette matching DPMtF exactly:
     - `.panel-group`, `.panel-group-header`, `.panel-group-toggle`,
       `.panel-group-body`, `.panel-group.collapsed .panel-group-body`
     - `.panel-subgroup`, `.panel-subgroup-header`, `.panel-subgroup-toggle`,
       `.panel-subgroup-body`, `.panel-subgroup.collapsed .panel-subgroup-body`
     - `.dpmtf-hidden`, `.dpmtf-card`, `.lang-selector`
     - Same colors: `#0d1117`, `#161b22`, `#21262d`, `#30363d`,
       `#58a6ff`, `#8b949e`, `#c9d1d9`, `#e6edf3`
   - All text via `data-slot` + `lbl(key, fallback)` — no hardcoded strings

3. **Add tests** — `tests/test_web_api.py`
   - Test each API endpoint
   - Test alias CRUD, validate, start/stop
   - Test i18n endpoints: available-languages, user-language GET/POST,
     ui-labels with locale parameter
   - Test label fallback (missing translation → en-US default)
   - `node --check` on all JS files MUST pass
   - `grep -RIn "innerHTML" web/static/` MUST be empty

3b. **Seed i18n labels** — `scripts/seed_labels.py`
   - Create `ui_labels` + `ui_label_translations` tables in `allocator.db`
   - Seed all label_keys listed above with en-US defaults
   - Seed da-DK translations
   - Seed de-DE, el-GR, sv-SE (can start as en-US copies, translate later)
   - Idempotent — safe to run multiple times

4. **Update model-allocator README** — document the frontend

### Phase 2: Simplify DPMtF-WebUI

5. **Remove allocator.js** — delete `static/js/allocator.js`
6. **Remove allocator endpoints** — remove all `/allocator/*` from
   `routers/bridge.py` (81 lines → 0)
7. **Remove allocator dashboard panel** — remove from frontend panel
   config in DB
8. **Add "Test OK" button** to role editor — single validate call via
   allocator CLI, show result inline
9. **Add "Manage allocation models" link** — external link to port 9140
10. **Simplify role editor** — `default_model_source` becomes a fixed
    field (always `model_allocator` or `python_runtime`), not a dropdown.
    `default_model_alias` becomes a text field with a "Test OK" button
    next to it.

### Phase 3: Cleanup & Documentation

11. **Update DPMtF README** — remove allocator dashboard section, add
    link to model-allocator frontend
12. **Update DPMtF governance** — update role setup instructions to
    reference allocator UI (port 9140) instead of DPMtF UI for model
    config
13. **Update model-allocator README** — document frontend, add setup
    instructions
14. **Migration script** — if any DB columns need changing in DPMtF
    (likely not — `default_model_alias` stays as a string reference)

---

## What Stays in DPMtF vs. What Moves

| Capability | Now | After |
|-----------|-----|-------|
| Create/edit allocation models | DPMtF UI | **Allocator UI** |
| Delete allocation models | DPMtF UI | **Allocator UI** |
| Validate allocation model | DPMtF UI | **Allocator UI** (DPMtF has "Test OK" button only) |
| Start/stop model runtime | DPMtF UI | **Allocator UI** (DPMtF does this automatically during dispatch) |
| Runtime profile config | DPMtF UI | **Allocator UI** |
| Doctor / preflight | DPMtF UI | **Allocator UI** |
| Role→alias mapping | allocator `roles.yaml` + DPMtF `bridge_roles` | **DPMtF `bridge_roles` only** (single source of truth) |
| Assign alias to DPMtF role | DPMtF role editor | **DPMtF role editor** (stays) |
| Test alias OK for role | DPMtF validate button | **DPMtF "Test OK" button** (simplified) |
| Warm model before dispatch | dispatch.py | **dispatch.py** (stays — calls allocator CLI) |
| Stop model after dispatch | dispatch.py | **dispatch.py** (stays — calls allocator CLI) |
| Resolve context window | scheduler.py | **scheduler.py** (stays — calls allocator CLI) |
| Start coding frontend | start_coding.py | **start_coding.py** (stays — calls allocator CLI with `--alias` instead of `--role`) |

---

## Lines of Code Impact

| File | Before | After | Delta |
|------|--------|-------|-------|
| DPMtF `static/js/allocator.js` | 371 | 0 | -371 |
| DPMtF `routers/bridge.py` | ~1200 | ~1120 | -80 |
| DPMtF `bridge_lib.py` | ~900 | ~880 | -20 |
| DPMtF `scheduler.py` | ~590 | ~575 | -15 |
| Allocator `web/app.py` | 0 | ~300 | +300 |
| Allocator `web/static/` | 0 | ~500 | +500 |
| Allocator `tests/test_web_api.py` | 0 | ~200 | +200 |
| **DPMtF net** | | | **-486 lines** |
| **Allocator net** | | | **+1000 lines** |

DPMtF gets ~500 lines simpler. Allocator gains its own UI.
