# Prompt #3: Panel Groups til v3

> **Svend:** Kopier hele kodeblokken nedenfor og indsæt i en lokal Claude Code session
> startet med lokal Ollama model (qwen36-27b-q4km:latest).

```
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md
- /home/svend/DPMtF-WebUI/docs/governance-templates/05_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates/04_ARCHITECTURE.md

Nøgleregler der SKAL overholdes:
- Panelgrupper er fixed: Daily, Journals, Reports, Periodic, Setup.
  Ændringer kræver ny design-specifikation og Human Approval Gate. (superpowers.md)
- ALLE brugervendte frontend-tekster SKAL bruge lbl(key, fallback).
  Ingen hardcodede engelske strenge i DOM-konstruktion. (superpowers.md)
- Ingen innerHTML til dynamisk indhold — brug createElement() / textContent /
  appendChild() / replaceChildren(). (05_CODING_STANDARD.md)
- 4-lags i18n: nye UI tekster skal have ui_text_slots → ui_text_slot_labels →
  ui_labels → ui_label_translations seed-data. (04_ARCHITECTURE.md)
- Brug DPMtF-WebUI's implementation som REFERENCE-MØNSTER — ikke kopier 1:1.
  Tilpas til v3's egen panel-struktur og navngivning.
</governance>

<task>
Implementér panel-group collapse/expand i v3. Projektet har aktuelt 2 paneler:
"system-resources-section" og "pipeline-status-section".

1. DATABASE: Tilføj user_panel_groups tabel til scripts/seed_database.py
   - CREATE TABLE IF NOT EXISTS user_panel_groups (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       user_id TEXT NOT NULL DEFAULT 'default',
       panel_group TEXT NOT NULL,
       is_collapsed INTEGER NOT NULL DEFAULT 0,
       UNIQUE(user_id, panel_group)
     )
   - Tilføj seed_user_panel_groups() funktion der indsætter default rækker
     for de 2 panel groups med is_collapsed=0 (expanded).
   - Kald seed_user_panel_groups() fra main() efter de andre seed funktioner.

2. API: Tilføj endpoints til app.py
   - GET /api/user-panel-groups?user_id=default
     Returnerer liste af {panel_group, is_collapsed} for brugeren.
   - POST /api/user-panel-groups
     Body: {user_id, panel_group, is_collapsed}
     UPSERT: INSERT OR REPLACE INTO user_panel_groups
     Returnerer den opdaterede række.
   - Brug parameterized SQL queries (ingen string formatting).

3. HTML: Wrap panels i panel-group containers i templates/index.html
   - Opret 2 panel-groups der matcher v3's domæne:
     • "daily" — indeholder system-resources-section
     • "reports" — indeholder pipeline-status-section
   - Hver panel-group container skal have:
     • En header-div med data-panel-group attribut og panel-group-toggle klasse
     • En content-div med panel-group-content klasse der wrapper section'en
     • Header-tekst via lbl() med slot_keys: "pg_daily" og "pg_reports"
   - Eksempel struktur:
     <div class="panel-group">
       <div class="panel-group-header" data-panel-group="daily">
         <span class="panel-group-toggle">▼</span>
         <span class="panel-group-title"></span>
       </div>
       <div class="panel-group-content">
         <section id="system-resources-section">...</section>
       </div>
     </div>

4. CSS: Tilføj panel-group styles til static/css/app.css
   - .panel-group: container med margin-bottom
   - .panel-group-header: flex, cursor pointer, padding, border-bottom
   - .panel-group-toggle: transition transform 0.2s, font-size
   - .panel-group-content: overflow hidden, transition max-height
   - .panel-group.collapsed .panel-group-content: max-height 0
   - .panel-group.collapsed .panel-group-toggle: rotate -90deg
   - Brug v3's eksisterende farvepalet og CSS variabler.

5. JS: Tilføj panel-group collapse/expand logik til static/js/app.js
   - Efter DOMContentLoaded, initialisér panel groups:
     • Hent panel-group state fra GET /api/user-panel-groups
     • For hver panel-group header, sæt title-tekst via lbl()
     • Sæt collapsed klasse på containers hvor is_collapsed=true
   - Toggle ved klik på panel-group-header:
     • Skift collapsed klasse på parent .panel-group
     • Opdatér toggle ikon (▼ ↔ ▶)
     • POST til /api/user-panel-groups for at persistere state
   - Brug lbl() til ALLE panel-group titler:
     • "daily" → lbl("pg_daily", "Daily")
     • "reports" → lbl("pg_reports", "Reports")

6. i18n: Tilføj labels til scripts/seed_database.py
   - 2 nye ui_labels: pg_daily, pg_reports
   - 4 nye ui_label_translations (da-DK + en-US):
     • pg_daily: da-DK="📆 Daglig", en-US="📆 Daily"
     • pg_reports: da-DK="📊 Rapporter", en-US="📊 Reports"
   - 2 nye ui_text_slots: pg_daily, pg_reports
   - 2 nye ui_text_slot_labels: begge mapper slot_key → label_key 1:1
</task>

<scope>
Filer du MÅ modificere:
- /home/svend/ai-pc-resource-webui-v3/scripts/seed_database.py
- /home/svend/ai-pc-resource-webui-v3/app.py
- /home/svend/ai-pc-resource-webui-v3/templates/index.html
- /home/svend/ai-pc-resource-webui-v3/static/css/app.css
- /home/svend/ai-pc-resource-webui-v3/static/js/app.js

Filer du IKKE må røre:
- Alle andre filer i /home/svend/ai-pc-resource-webui-v3/
- /home/svend/DPMtF-WebUI/ (father project)
- /home/svend/ENO/ (søn-projekt)
</scope>

<validation>
Før du melder færdig, verificér:
1. Python syntaks: "python3 -m py_compile app.py" og "python3 -m py_compile scripts/seed_database.py"
2. JS syntaks: "node --check static/js/app.js"
3. Ingen nye innerHTML: "grep -RIn 'innerHTML' static/js/app.js" skal returnere 0
4. Alle panel-group titler bruger lbl(): grep efter "pg_daily" og "pg_reports" i JS
5. user_panel_groups tabel eksisterer i seed_database.py med korrekt schema
6. GET/POST /api/user-panel-groups endpoints findes i app.py
7. Panel-group containers i index.html wrapper de 2 sections
8. CSS indeholder .panel-group, .panel-group-header, .panel-group-content, .collapsed styles
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Jeg reviewer diff'en før commit.
</constraint>
```
