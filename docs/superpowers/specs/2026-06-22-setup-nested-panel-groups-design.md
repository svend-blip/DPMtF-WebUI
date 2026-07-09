# Design — Nested Panel Groups i Setup-sektionen

**Dato:** 2026-06-22  
**Flow:** Archi01 → Implementer  
**Status:** Godkendt af Human  

---

## Problem

Setup-gruppen (`#pg-setup`) indeholder 6 sektioner som **flade `<section>` elementer** — ingen visuel adskillelse, ingen foldning, svær at overskue. Brugeren ønsker nestede panel-groups med **uafhængig expand/collapse state** gemt i user preferences.

## Krav

1. Alle 6 sektioner gøres til `<section class="panel-group">` med egen header/body/toggle.
2. Expand/collapse state gemmes via `/api/user-panel-groups` PATCH — persistent mellem side-opdateringer.
3. Alle headings bruger `data-slot` + `lbl()` (overholder CLAUDE.md §5 i18n krav).
4. Genbruger **100%** eksisterende CSS (`dpmtf-theme.css:367-410`) og JS toggle pattern — zero nye CSS-classes.

## Ændringsoversigt

### Files affected

| File | Type | Ændring |
|------|------|---------|
| `templates/index.html` | HTML | Flyt 6 `<section>` til nestede panel-groups med headers + toggles |
| `dpmtf-app.js` | JS | Toggle listeners + state persistence via `/api/user-panel-groups` API |
| `databases/dpmtf.db` | DB seed | 6 nye text slots (da-DK + en-US) via init_db.py INSERTs |

### Sektioner (i rækkefølge)

| # | Navn (en-US) | Navn (da-DK) | data-group | Eksisterende ID |
|---|-------------|---------------|------------|-----------------|
| 1 | Bridge Setup | Bro-setup | bridge-setup | bridge-setup-section |
| 2 | Steps | Trin | steps | bridge-steps-section |
| 3 | Roles | Roller | roles | bridge-roles-section |
| 4 | Conventions | Konventioner | conventions | bridge-conventions-section |
| 5 | Export | Eksport | export | bridge-export-section |
| 6 | Database Status | Database Status | db-status | db-status-section |

## UI Text Slots (seed data)

| slot_key | da-DK fallback | en-US fallback |
|----------|---------------|----------------|
| `pg_bridge_setup` | 🌉 Bro-setup | Bridge Setup |
| `pg_steps` | 🔧 Trin | Steps |
| `pg_roles` | 👤 Roller | Roles |
| `pg_conventions` | 📐 Konventioner | Conventions |
| `pg_export` | 📦 Eksport | Export |
| `pg_db_status` | 🗄 Database Status | Database Status |

## HTML-struktur (eksempel)

```html
<section class="panel-group" id="pg-bridge-setup" data-group="bridge-setup">
  <div class="panel-group-header" data-group="bridge-setup">
    <h2 data-slot="pg_bridge_setup">🌉 Bro-setup</h2>
    <span class="panel-group-toggle">▼</span>
  </div>
  <div class="panel-group-body">
    <!-- bridge-setup-section eksisterende indhold -->
  </div>
</section>
```

Genbruges for alle 6 sektioner. Bridge Setup indeholder subsections som allerede eksisterer (flows, steps, roles, conventions, export).

## JS — State persistence

### Toggle handler (eksempel)

```javascript
function toggleSubgroupState(groupKey, newState) {
  fetch(`/api/user-panel-groups`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({group: groupKey, state: newState})
  });
}
```

### Restore på load (eksempel)

```javascript
const states = await fetch("/api/user-panel-groups").then(r => r.json());
for (const pg of subgroups) {
  const key = pg.dataset.group;
  const state = states[key] || "expanded";
  if (state === "collapsed") {
    pg.classList.add("collapsed");
    const toggle = pg.querySelector(".panel-group-toggle");
    if (toggle) toggle.textContent = "▶";
  }
}
```

## Validation checklist

| # | Check | Status |
|---|-------|--------|
| 1 | ingen innerHTML calls | ✅ Ingen nye |
| 2 | lbl() + data-slot på alle headings | ✅ Alle 6 slots med data-slot |
| 3 | /home/svend/ paths — nye | ✅ None |
| 4 | py_compile app.py | ✅ Ingen Python ændringer |
| 5 | node --check dpmtf-app.js | ⏳ Efter JS-ændring |

## Risici

- **Bridge Setup subsections:** Flows/Steps/Roles/Conventions/Export er nestede inden i bridge-setup. Når bridge-setup foldes ud/sammen, vises alt internt automatisk (CSS `.panel-group.collapsed .panel-group-body { display: none }`). Ingen ekstra JS needed.
- **State key collisions:** `data-group` værdier skal være unikke på tværs af nestede niveauer (`setup` vs `bridge-setup` vs `steps` osv.).
