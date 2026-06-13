# Prompt #2: Tilføj lbl() helper til v3

> **Svend:** Kopier hele kodeblokken nedenfor og indsæt i en lokal Claude Code session
> startet med lokal Ollama model (qwen36-27b-q4km:latest).

```
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/05_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md

Nøgleregler der SKAL overholdes:
- ALLE brugervendte frontend-tekster SKAL bruge lbl(key, fallback) — auto-fail i validation.
  Ingen hardcodede engelske strenge i DOM-konstruktion. (superpowers.md Sektion 2: Kode-standard)
- lbl() funktionen skal have præcis denne signatur:
  function lbl(key, fallback) { return labelMap[key] || fallback || key; }
- Ingen innerHTML til dynamisk indhold — brug createElement() / textContent / appendChild().
  (05_CODING_STANDARD.md)
- Eksisterende funktionalitet MÅ IKKE brydes. labelMap hentes stadig fra /api/labels.
</governance>

<task>
1. Tilføj lbl() helper-funktionen til /home/svend/ai-pc-resource-webui-v3/static/js/app.js
   - Placér den lige efter labelMap initialiseringen (ca. linje 10-15, efter "var labelMap = {};")
   - Funktionen skal have præcis denne signatur og implementation:
     function lbl(key, fallback) {
         return labelMap[key] || fallback || key;
     }
   - Den skal være globalt tilgængelig for alle funktioner i filen.

2. Migrér ALLE eksisterende "labelMap[\"key\"] || \"fallback\"" kald til lbl() kald.
   - Der er ca. 19 forekomster i filen.
   - Eksempel: labelMap["slot_gpu_utilization"] || "Utilisation"
     Bliver til: lbl("slot_gpu_utilization", "Utilisation")
   - Eksempel: labelMap["lbl_requires"] || "Requires:"
     Bliver til: lbl("lbl_requires", "Requires:")
   - VIGTIGT: Bevar de eksisterende fallback-strenge PRÆCIST som de er.
   - VIGTIGT: Hvis et kald bruger labelMap uden || fallback (f.eks. assignment),
     skal det IKKE ændres — kun "labelMap[x] || y" mønstret migreres.

3. Verificér at ALLE 19+ forekomster er migreret.
   - Søg efter "labelMap[" i filen — der bør kun være assignments tilbage
     (f.eks. "labelMap = map;") og IKKE nogen "labelMap[x] || y" mønstre.
</task>

<scope>
Filer du MÅ modificere:
- /home/svend/ai-pc-resource-webui-v3/static/js/app.js

Filer du IKKE må røre:
- Alle andre filer i /home/svend/ai-pc-resource-webui-v3/
- /home/svend/DPMtF-WebUI/ (father project)
- /home/svend/ENO/ (søn-projekt)
</scope>

<validation>
Før du melder færdig, verificér:
1. lbl() funktionen findes i app.js med korrekt signatur: function lbl(key, fallback) { return labelMap[key] || fallback || key; }
2. Ingen "labelMap[\"x\"] || \"y\"" mønstre tilbage i filen (kun rene assignments som "labelMap = map;")
3. Alle fallback-strenge er bevaret uændrede fra originalerne.
4. Ingen nye innerHTML kald introduceret.
5. JavaScript-syntaks er korrekt: kør "node --check static/js/app.js"
6. Filen har stadig samme struktur — kun lbl() funktionen tilføjet + labelMap kald migreret.
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Jeg reviewer diff'en før commit.
</constraint>
```
