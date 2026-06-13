# Prompt #4: README.md v3-specifik

> **Svend:** Kopier hele kodeblokken nedenfor og indsæt i en lokal Claude Code session
> startet med lokal Ollama model (qwen36-27b-q4km:latest).

```
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/alignmentstructure.md

Nøgleregler der SKAL overholdes:
- Father-Child Governance Sync (superpowers.md Sektion 1): Projekt-specifikke filer
  SKAL afspejle projektets egen identitet — IKKE være Father-kopier.
- README.md er en projekt-specifik fil — den skal beskrive DETTE projekt,
  ikke være en generisk governance-template indeks.
</governance>

<task>
Opdatér /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/README.md
så den er v3-specifik.

Nuværende README.md er en generisk governance-template indeks der beskriver
DPMtF WebUI's rolle-loop. Den skal omskrives til at beskrive
AI PC Resource WebUI v3.

1. Titel: "AI PC Resource WebUI v3 — Governance Templates"
2. Første paragraf skal nævne:
   - Dette er governance-dokumenterne for AI PC Resource WebUI v3 (port 9123)
   - v3 er et reference-projekt under DPMtF governance
   - Strukturelle templates er synkroniseret med DPMtF-WebUI's master
   - Projekt-specifikke filer vedligeholdes uafhængigt
3. Bevar template-overview tabellen (den er nyttig), men opdatér
   "How to Use These Templates" sektionen til at være v3-specifik:
   - Fjern referencen til "Project Initializer (script)" — v3 er allerede initialiseret
   - Erstat med: "Governance sync: Structural templates synced via
     initialize_target_project_governance.py. Project-specific files
     maintained independently."
4. Tilføj en kort "v3-Specific Notes" sektion der nævner:
   - v3's paneler: System Resources + Pipeline Status
   - v3's port: 9123
   - v3's formål: Database-drevet resource management og pipeline monitoring
   - Reference til DPMtF-WebUI som father project (port 9130)
5. Fjern "Prompt-Run Templates" sektionen — v3 har ikke prompt-runs.
6. Bevar "Cross-References" sektionen.
</task>

<scope>
Filer du MÅ modificere:
- /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/README.md

Filer du IKKE må røre:
- Alle andre filer i /home/svend/ai-pc-resource-webui-v3/
- /home/svend/DPMtF-WebUI/ (father project)
- /home/svend/ENO/ (søn-projekt)
</scope>

<validation>
Før du melder færdig, verificér:
1. README.md's titel nævner "AI PC Resource WebUI v3"
2. Første paragraf nævner port 9123 og reference-projekt status
3. "How to Use" sektionen er v3-specifik (ikke generisk initializer)
4. "Prompt-Run Templates" sektionen er fjernet
5. v3-Specific Notes sektion findes med port, paneler, formål
6. Markdown-syntaks er korrekt
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Jeg reviewer diff'en før commit.
</constraint>
```
