# Design Subpatterns — Panel Subgroups Design Spec

> **Formål:** Indfør "Design subpatterns" (panel-subgroup) som nestede expand/collapse containere
> inden for de 5 faste "Design patterns" (panel-group). Database-drevet synlighed for både
> patterns og subpatterns. DPMtF først, ENO alignment herefter.

---

## 1. Nuværende tilstand

DPMtF og ENO har 5 hardcodede panel-groups: Daily, Journals, Reports, Periodic, Setup.
Hver har expand/collapse via `user_panel_groups` tabel + API. Paneler ligger fladt i
`panel-group-body`.

**Begrænsninger:**
- Tomme grupper (f.eks. Journals i DPMtF) vises stadig
- Ingen underopdeling inden for en gruppe — alle paneler er på samme niveau
- Ingen database-drevet synlighedsstyring

---

## 2. Design

### 2.1 Hierarki

```
Page
└── Design pattern (panel-group) — 5 fixed: Daily, Journals, Reports, Periodic, Setup
    └── Design subpattern (panel-subgroup) — optional, nested, expand/collapse
        └── Panels (eksisterende sektioner)
```

### 2.2 Regler

1. **Tomme patterns skjules:** Hvis `is_visible = 0` i `user_panel_groups`, skjules hele panel-group.
2. **Tomme subpatterns skjules:** Hvis `is_visible = 0` i `panel_subgroups`, skjules subgroup.
3. **Subpatterns er valgfrie:** Hvis ingen subgroups defineret for en gruppe, bruges implicit "All" subgroup uden header.
4. **"All" default:** Ved migration eller nye projekter uden subgroups, samles alle paneler under usynlig "All".
5. **Data-drevet collapse:** Både panel-group og panel-subgroup collapse-states gemmes i database.
6. **HTML-skal forbliver:** De 5 panel-group containere forbliver hardcodet i `index.html`. Subgroups bygges dynamisk af JS.

---

## 3. Database

### 3.1 Udvidelse: `user_panel_groups`

```sql
ALTER TABLE user_panel_groups ADD COLUMN is_visible INTEGER DEFAULT 1;
```

### 3.2 Ny tabel: `panel_subgroups`

```sql
CREATE TABLE IF NOT EXISTS panel_subgroups (
    subgroup_key  TEXT PRIMARY KEY,
    group_name    TEXT NOT NULL,         -- "daily", "periodic", etc.
    title_da      TEXT NOT NULL,
    title_en      TEXT NOT NULL,
    sort_order    INTEGER DEFAULT 0,
    is_visible    INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 Ny tabel: `panel_subgroup_mappings`

```sql
CREATE TABLE IF NOT EXISTS panel_subgroup_mappings (
    slot_key      TEXT NOT NULL,
    subgroup_key  TEXT NOT NULL,
    PRIMARY KEY (slot_key, subgroup_key)
);
```

### 3.4 Seed data — DPMtF

```sql
-- Periodic subgroups
INSERT OR REPLACE INTO panel_subgroups VALUES
('sg_periodic_phase', 'periodic', 'Fase', 'Phase', 1, 1, datetime('now')),
('sg_periodic_planning', 'periodic', 'Planlægning', 'Planning', 2, 1, datetime('now')),
('sg_periodic_existing', 'periodic', 'Eksisterende Projekter', 'Existing Projects', 3, 1, datetime('now'));

-- Periodic mappings
INSERT OR REPLACE INTO panel_subgroup_mappings VALUES
('lbl_panel_phase_status', 'sg_periodic_phase'),
('lbl_panel_project_planning', 'sg_periodic_planning');

-- Journals: tom → is_visible = 0
UPDATE user_panel_groups SET is_visible = 0 WHERE group_name = 'journals';
```

### 3.5 Seed data — ENO

```sql
-- Periodic subgroups
INSERT OR REPLACE INTO panel_subgroups VALUES
('sg_periodic_pipeline', 'periodic', 'Pipeline', 'Pipeline', 1, 1, datetime('now')),
('sg_periodic_brainstorm', 'periodic', 'Brainstorm', 'Brainstorm', 2, 1, datetime('now')),
('sg_periodic_nightrun', 'periodic', 'Nightrun', 'Nightrun', 3, 1, datetime('now'));

-- Periodic mappings
INSERT OR REPLACE INTO panel_subgroup_mappings VALUES
('lbl_panel_pipeline_projects', 'sg_periodic_pipeline'),
('lbl_panel_brainstorm_projects', 'sg_periodic_brainstorm'),
('lbl_panel_nightrun', 'sg_periodic_nightrun');
```

---

## 4. API

### 4.1 GET `/api/panel-structure` (nyt)

Returnerer fuld panel-hierarki med synlighed og collapse-states.

Response format:
```json
{
  "groups": {
    "<group_name>": {
      "is_visible": true/false,
      "state": "expanded"|"collapsed",
      "subgroups": [
        {
          "key": "sg_...",
          "title": "lokalisert titel",
          "is_visible": true/false,
          "state": "expanded"|"collapsed",
          "slots": ["slot_key1", "slot_key2"]
        }
      ]
    }
  }
}
```

Hvis en gruppe har 0 subgroups i databasen, returneres én implicit "All" subgroup
med `key: "sg_<group>_all"` og alle gruppens slots samlet.

### 4.2 POST `/api/panel-structure/subgroup-state` (nyt)

Gemmer collapse-state for en subgroup.

Request:
```json
{
  "subgroup_key": "sg_periodic_phase",
  "state": "collapsed"
}
```

### 4.3 GET `/api/user-panel-groups` (udvidet)

Eksisterende endpoint udvides til at inkludere `is_visible` i response.

### 4.4 POST `/api/user-panel-groups` (udvidet)

Accepterer også `is_visible` i request body (optional).

---

## 5. Frontend

### 5.1 HTML

Ingen ændringer i `index.html`. De 5 panel-group containere forbliver som i dag.
Subgroups bygges dynamisk af JS.

### 5.2 CSS — nye klasser

```css
.panel-subgroup {
    margin-bottom: 12px;
    border: 1px solid #21262d;
    border-radius: 6px;
    overflow: hidden;
}
.panel-subgroup-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 12px; cursor: pointer; user-select: none;
    background: #161b22;
}
.panel-subgroup-header:hover { background: #1c2129; }
.panel-subgroup-header h3 {
    font-size: 0.95rem; margin: 0; color: #c9d1d9;
}
.panel-subgroup-toggle { font-size: 0.75rem; color: #8b949e; }
.panel-subgroup-body {
    padding: 8px 12px; border-top: 1px solid #21262d;
    background: #0d1117;
}
.panel-subgroup.collapsed .panel-subgroup-body { display: none; }
.panel-subgroup-all .panel-subgroup-header { display: none; }
```

### 5.3 JS — `buildPanelStructure()`

Ny funktion der erstatter `applyPanelGroupStates()`:

1. `fetch("/api/panel-structure")` — henter struktur
2. For hver gruppe:
   - Hvis `is_visible = false`: `pg.classList.add("dpmtf-hidden")`, skip
   - Hvis `is_visible = true`: clear body, byg subgroups
3. For hver subgroup:
   - Opret `<section class="panel-subgroup">` med header + body
   - Header: `<h3>` + toggle span
   - Hvis "All" subgroup: tilføj klasse `panel-subgroup-all` (skjuler header)
   - Find paneler i DOM'en via `data-slot` match og flyt dem ind i subgroup-body
   - Sæt collapse-state fra API
   - Click-handler: toggle + POST save
4. Skjulte subgroups: `subgroup.classList.add("dpmtf-hidden")`

---

## 6. Governance

### 6.1 Nye regler i superpowers.md

Tilføj under Scope-regler:
- **Panel subgroups er valgfrie:** Hver panel-group KAN have subgroups defineret i databasen. Hvis ikke, bruges implicit "All".
- **Tomme patterns/subpatterns skjules:** `is_visible = 0` → skjules via CSS-klasse. Styres af database, ikke hardcodet.
- **Subgroup struktur er database-drevet:** Ændringer i subgroup-definitioner kræver ikke HTML-ændringer.

### 6.2 Alignment

Efter DPMtF er færdig:
1. Kopier `panel_subgroups` + `panel_subgroup_mappings` tabeller til ENO's `init_db.py`
2. Seed med ENO-specifikke subgroups
3. Kopier JS (`buildPanelStructure`) + CSS (subgroup klasser) til ENO
4. ENO's `index.html` forbliver uændret

---

## 7. Implementation — Bridge-strategi

### Hvad kører lokalt (claude_implementer, qwen36-27b-q4km)

| Opgave | Complexity | Egnet til lokal? |
|---|---|---|
| Database tabeller + seed data i init_db.py | Medium (2 filer, veldefineret mønster) | ✅ Ja |
| API endpoints i app.py | Medium (kendt mønster) | ✅ Ja |
| CSS klasser i theme.css | Lav (1 fil, mekanisk) | ✅ Ja |
| JS funktion buildPanelStructure() | Medium-høj (1 fil, ny logik) | ⚠️ Cloud anbefales |
| i18n labels for subgroups | Lav (mekanisk) | ✅ Ja |
| ENO alignment (kopiering) | Medium (kendt mønster) | ✅ Ja |

### Workflow

```
Architect (cloud) → design + handoff
  → Implementer (lokal) → database + API + CSS + i18n
  → Review (lokal) → valider
  → Architect (cloud) → JS buildPanelStructure() + integration
  → Implementer (lokal) → ENO alignment
```

---

## 8. Success-kriterier

- [ ] Journals panel-group skjult i DPMtF (tom)
- [ ] Periodic har 3 expand/collapse subgroups i DPMtF
- [ ] Subgroup collapse-states gemmes og gendannes
- [ ] "All" implicit subgroup fungerer for grupper uden definerede subgroups
- [ ] ENO Periodic har 3 subgroups (Pipeline, Brainstorm, Nightrun)
- [ ] Ingen HTML-ændringer i index.html (begge projekter)
- [ ] Alle nye frontend-tekster bruger lbl()
- [ ] Ingen innerHTML i ny kode
