# Prompt #5: Footer med build-info til v3

> **2O Run #2 — Ny prompt. Ingen af modellerne har set den før.**

```
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/05_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md

Nøgleregler der SKAL overholdes:
- ALLE brugervendte frontend-tekster SKAL bruge lbl(key, fallback).
  Ingen hardcodede engelske strenge i DOM-konstruktion. (superpowers.md)
- Ingen innerHTML til dynamisk indhold — brug createElement() / textContent /
  appendChild(). (05_CODING_STANDARD.md)
- CSS: Class-based selectors, mørkt tema farver (#0d1117, #21262d, #30363d,
  #e6edf3, #8b949e). (05_CODING_STANDARD.md)
- 4-lags i18n: nye UI tekster skal have ui_text_slots → ui_text_slot_labels →
  ui_labels → ui_label_translations seed-data. (04_ARCHITECTURE.md)
</governance>

<task>
Tilføj en footer til v3's index.html der viser build-information.

1. HTML: Tilføj <footer> til bunden af <main> i templates/index.html
   - Footer skal have 3 data-slot spans:
     • slot_footer_project — projektnavn
     • slot_footer_port — port nummer
     • slot_footer_build — build timestamp
   - Placér den lige før det eksisterende <footer> (linje ~50)

2. JS: Tilføj initFooter() funktion til static/js/app.js
   - Hent git build info: kør "git log -1 --format=%ci" via fetch til
     et nyt /api/build-info endpoint (ELLER: brug en statisk approach —
     læs fra en data-attribut i HTML'en)
   - ENKLERE APPROACH: Brug document.lastModified eller en hardcodet
     build timestamp i HTML'en. Ingen nyt endpoint nødvendigt.
   - Sæt footer tekst via lbl():
     • lbl("slot_footer_project", "AI PC Resource WebUI v3")
     • lbl("slot_footer_port", "Port 9123")
     • lbl("slot_footer_build", "Build: " + timestamp)
   - Kald initFooter() fra onReady() efter loadLabels()

3. CSS: Tilføj footer styles til static/css/app.css
   - footer: text-align center, padding, margin-top, border-top
   - .footer-item: inline-block, margin, font-size, color #8b949e
   - Brug mørkt tema farver

4. i18n: Tilføj labels til scripts/seed_database.py
   - 3 nye ui_labels: slot_footer_project, slot_footer_port, slot_footer_build
   - 6 nye ui_label_translations (da-DK + en-US)
   - 3 nye ui_text_slots
   - 3 nye ui_text_slot_labels
</task>

<scope>
Filer du MÅ modificere:
- /home/svend/ai-pc-resource-webui-v3/templates/index.html
- /home/svend/ai-pc-resource-webui-v3/static/js/app.js
- /home/svend/ai-pc-resource-webui-v3/static/css/app.css
- /home/svend/ai-pc-resource-webui-v3/scripts/seed_database.py

Filer du IKKE må røre:
- Alle andre filer i /home/svend/ai-pc-resource-webui-v3/
- /home/svend/DPMtF-WebUI/
- /home/svend/ENO/
</scope>

<validation>
Før du melder færdig, verificér:
1. Footer vises i index.html med 3 data-slot spans
2. initFooter() findes i app.js og kaldes fra onReady()
3. Footer tekst sættes via lbl() — ingen hardcodede strenge
4. Footer CSS bruger mørkt tema farver
5. 3 nye labels seedet i seed_database.py
6. Python syntaks: "python3 -m py_compile scripts/seed_database.py"
7. JS syntaks: "node --check static/js/app.js"
8. Ingen nye innerHTML
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Skriv en resultat-fil til /home/svend/claude-bridge/result.md med:
- Hvilke filer du modificerede
- Hvilke validerings-checks du kørte og deres resultater
- En kort opsummering af hvad du gjorde
</constraint>
```
