# Design: i18n Compliance + Database-Driven Collapsible Panel Groups — AI PC Resource WebUI v2

> **en-US is the standard language for all governance-templates-v2 files.**

## 1. Purpose

Refactor `/home/svend/ai-pc-resource-webui-v2/` to achieve full DPMtF-i18n compliance without adding new panels. Two changes:
1. Full i18n labels system — own database + `lbl()` in frontend
2. Collapsible panel groups — native `<details>/<summary>` wrapping the 3 existing sections, **with state persisted in local DB** (survives browser refresh)

No new panels, no breaking backend contracts, no scope creep.

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Labels storage | Own DB (`databases/ai_resource_webui.db`) | Father's tables are specific to DPMtF-WebUI's panel structure; no cross-project pollution |
| Language default | en-US | User preference |
| Collapsible UI | Native `<details>/<summary>` — **state stored in local DB** | Database-driven per user_id, mirrors Father's `user_panel_groups` pattern adapted to local DB |
| lbl() pattern | Copy dpmtf-app.js 4-layer traversal | Existing implementer knows the patterns; reviewers can validate against known standards |
| Language picker | Dropdown in header (like Father) | Persistent per-user, fetches from own DB `/api/available-languages` |
| Panel subgroup registration | Local DB only (`ai_panel_subgroups`) | No Father registration needed — fully self-contained project |

## 3. Database Schema

New database: `databases/ai_resource_webui.db` with tables paralleling Father's pattern:

### i18n Tables (4 layers)
```
ai_text_slots          — slot_key (PK, unique) for each UI text element
ai_text_slot_labels    — maps slot_key → label_id (FK to ai_labels.slot_key via label_id)
ai_labels              — id (PK), display_name, is_active, slot_key
ai_label_translations  — (label_id, locale) composite PK, translated_text, is_active
```

All tables mirror Father's `ui_text_slots`, `ui_text_slot_labels`, `ui_labels`, `ui_label_translations` structure. Naming uses `ai_` prefix to distinguish from Father's tables.

### Panel Groups Tables (mirror Father's pattern for local DB)
```
ai_panel_subgroups     — subgroup_key (PK), group_name, title_en, title_da, is_visible, sort_order
ai_panel_subgroup_mappings — (subgroup_key, slot_key) composite PK
ai_user_panel_groups   — id (PK), user_id, subgroup_key, state ("expanded"/"collapsed"), is_visible, updated_at
```

**`ai_user_panel_groups` mirrors Father's `user_panel_groups` exactly** — same columns except prefixed with `ai_`. State identified via `os.getlogin()` with fallback to `"default"`, stored via `INSERT OR REPLACE`.

## 4. Backend API Endpoints (app.py)

### i18n Endpoints
Four new endpoints, following existing app.py REST conventions:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/available-languages` | GET | Return distinct locales + display_names from `ai_label_translations` |
| `/api/user-language` | GET/POST | GET → current locale from session; POST → save user's locale preference. Uses `user_language` table, mirrors Father's implementation (lines 772-850 of app.py) |
| `/api/ui-labels/main?locale=en-US` | GET | Return slot_key + translated_text for all active slots in given locale (4-layer traversal). Mirrors Father's implementation (lines 852-910 of app.py) |

### Panel Groups Endpoints
Mirrors Father's `user_panel_groups` and `panel-structure` endpoints exactly, adapted to local `ai_*` tables:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/user-panel-groups` | GET | Return `{user_id, groups: {subgroup_key: {state, is_visible}}}` from `ai_user_panel_groups`. User via `os.getlogin()` → fallback `"default"`. Empty groups if no data. |
| `/api/user-panel-groups` | POST | Store collapse state: body `{subgroup_key, state}` → `INSERT OR REPLACE INTO ai_user_panel_groups`. Validates state against `VALID_PANEL_STATES = {"expanded", "collapsed"}`. |
| `/api/panel-structure` | GET | Return panel hierarchy with subgroups, visibility, and collapse states for all 3 sections. Titles resolved to requested locale (title_en vs title_da). |

Each endpoint mirrors Father's equivalent pattern but queries `ai_*` prefixed tables. No new dependencies.

## 5. Seed Data

Self-contained `init_db.py` seeds the database in idempotent fashion:

- **Panel subgroups** (3 entries):
  - `sg_system_resources` — group_name: "daily", title_en: "System Resources", title_da: "Systemressourcer"
  - `sg_pipeline_status` — group_name: "daily", title_en: "Pipeline Status", title_da: "Pipeline-status"
  - `sg_pipeline_action_mapping` — group_name: "daily", title_en: "Pipeline Action Mapping", title_da: "Pipeline Handlingskortlægning"

- **Panel subgroup mappings** (3 entries): maps each subgroup_key to its section slot key

- **~16 UI texts** for language picker + labels × 2 locales = ~32 translation rows
- Total ≈ **80 seed INSERTs** — no UPDATEs, upsert via `INSERT OR REPLACE`

The seed covers every user-facing text: panel subgroup titles (en-US + da-DK), language picker labels ("Language", "Select language"), and any system messages in the label store.

## 6. Frontend Changes

### lbl() Helper

Copy dpmtf-app.js pattern verbatim, targeting own DB:
```js
function lbl(key, fallback) {
  var value = currentLabels[key] || fallback;
  return value;
}
```

On init: fetch `/api/ui-labels/main?locale=en-US` (or user preference), populate `currentLabels` object. On language switch: same fetch for new locale, update all `[data-slot]` elements.

### Language Picker Dropdown

In `<header>`: add a `<select id="lang-dropdown">` that:
1. Fetches `/api/available-languages` on init
2. Populates options with `locale` value and `display_name` text
3. On change: save via POST to `/api/user-language`, re-fetch labels, update DOM

### Database-Driven Collapsible Panels

**Initial load**: fetch `/api/panel-structure` → read collapse state for each subgroup → set `<details open>` or `<details>` (collapsed) on each section accordingly.

**Toggle**: when user clicks summary to expand/collapse, dispatch a POST to `/api/user-panel-groups` with `{subgroup_key, state}` to persist the new state.

```html
<section id="system-resources-section">
  <h2 data-slot="system_resources_title">System Resources</h2>
  <details class="panel-collapsible" data-subgroup="sg_system_resources" open>
    <summary data-slot="sg_system_resources_label">▼ System Resources</summary>
    <div id="system-resources-grid" class="sr-grid">...</div>
  </details>
</section>
```

- **`open` attribute set dynamically** from DB state on page load (not hardcoded)
- **`data-subgroup`** maps the `<details>` element to its `subgroup_key` in the database
- **`<summary>` text via lbl()** for i18n compliance — slot_key resolved from `ai_panel_subgroups.title_en/title_da`
- **Toggle handler**: on `toggle` event → read `dataset.subgroup` and `open` status → POST to `/api/user-panel-groups`
- Browser handles the visual expand/collapse natively; we only handle DB persistence

### Event Handler Pattern
```js
document.querySelectorAll('.panel-collapsible').forEach(function(details) {
  details.addEventListener('toggle', function() {
    var subgroup = this.dataset.subgroup;
    var state = this.open ? 'expanded' : 'collapsed';
    fetch('/api/user-panel-groups', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subgroup_key: subgroup, state: state})
    });
  });
});
```

### Existing JavaScript Updates

- `app.js`: Replace hardcoded panel title strings with `lbl()` calls
- Add panel structure fetch on init to set initial `<details open>` states
- Add language picker rendering to header on init
- Add label-refresh handler for language switch events
- All dynamic content still uses `createElement()`/`textContent` (zero innerHTML for dynamic content)

## 7. CSS Changes

Minimal — style the `<details>/<summary>` elements:
```css
.panel-collapsible { margin-top: 0; }
.panel-collapsible summary { cursor: pointer; user-select: none; font-weight: bold; }
.panel-collapsible[open] summary::before { content: "▼ "; }
.panel-collapsible:not([open]) summary::before { content: "▶ "; }
```

Dark theme compatible (GitHub-dark palette). No layout-breaking changes.

## 8. Files Changed

| File | Action |
|------|--------|
| `databases/ai_resource_webui.db` | New — empty init, seeded by init_db.py |
| `init_db.py` | New — seed tables + ~80 rows (idempotent) |
| `app.py` | +7 nye endpoints: 3 i18n + 3 panel groups + 1 panel structure |
| `static/js/app.js` | +lbl(), sprogvælger-render, data-slot update på language switch, panel state fetch on init, toggle handler for DB persistence |
| `templates/index.html` | `<details>/<summary>` wrappers med `data-subgroup` omkring de 3 sektioner + sprog-vælger i header |
| `static/css/app.css` | Styling for collapsible panels + dropdown |

## 9. Verification Checklist

- [ ] `python3 -m py_compile app.py init_db.py` — OK
- [ ] `node --check static/js/app.js` — OK
- [ ] `grep -RIn "innerHTML" static/ templates/` — tom (kun pre-existing container-clearing patterns)
- [ ] Alle user-facing strings via lbl() eller data-slot
- [ ] Sprog-vælger viser begge sprog og skifter uden JS-fejl
- [ ] `<details>/<summary>` udgiver korrekt i alle 3 sektioner, state huskes ved refresh
- [ ] init_db.py er idempotent (kør to gange uden fejl)
- [ ] Ingen nye panel-grupper tilføjet
- [ ] Kun lokal database — ingen Father-tabletillæg

## 10. Governance Compliance

| Rule | Status |
|------|--------|
| Panel groups are fixed (Daily/Journals/Reports/Periodic/Setup) | ✅ 3 sektioner under Daily — ingen nye grupper overhovedet |
| No hardcoded English strings | ✅ lbl() dækker alle tekster |
| No innerHTML for dynamic content | ✅ createElement-based som før |
| i18n labels for all new UI text | ✅ Egen DB, 4-lags struktur |
| node --check passes | ✅ Valideres før handoff |
| py_compile passes | ✅ Valideres før handoff |
| Expand/Collapse state survives browser refresh | ✅ Database-styret via ai_user_panel_groups |

## 11. Scope Boundaries

**Files that MAY be modified:** app.py, init_db.py, static/js/app.js, templates/index.html, static/css/app.css

**Files that MUST NOT be touched:** /home/svend/DPMtF-WebUI/ (Father project), any governance template files, any database outside ai-pc-resource-webui-v2/

## 12. Constraints

- DO NOT COMMIT. Leave all changes unstaged.
- Execute ALL steps in task — especially the bridge signal.
- Stop after 2 failed patching attempts — document, do not guess.
- No new panel groups. No new panel registrations in Father's DB.
- All state stored in ai-pc-resource-webui-v2's OWN local database only.
