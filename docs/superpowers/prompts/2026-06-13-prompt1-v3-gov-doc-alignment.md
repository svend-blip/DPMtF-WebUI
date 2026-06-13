# Prompt #1: v3 Governance Doc Alignment

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
  (00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README)
  SKAL afspejle projektets egen identitet — IKKE være Father-kopier.
- alignmentstructure.md Regel 5: Periodisk governance audit — tjek at 00_PROJECT.md
  har korrekt projektnavn, port, repository, Current Commit, og Current Status.
- 02_SCOPE.md skal vise projektets FAKTISKE nuværende fase.
</governance>

<task>
1. Læs /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/02_SCOPE.md
   - Den viser fase "3C-3 — Initialize governance docs into AI PC Resource WebUI v3"
   - Find projektets FAKTISKE nuværende fase ved at læse 11_NEXT_CONTEXT.md
   - Opdatér 02_SCOPE.md så Phase, In Scope Now, Out of Scope Now, Constraints,
     og Success Criteria afspejler den faktiske nuværende fase.
   - Bevar Scope Change Log entries (tilføj en ny for denne ændring).

2. Læs /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/00_PROJECT.md
   - Current Commit viser "934a578 3C-2: Create initial v3 skeleton" — dette er stale.
   - Kør "git -C /home/svend/ai-pc-resource-webui-v3 log --oneline -1" for at finde
     den faktiske HEAD commit.
   - Current Status viser "Initial skeleton created and pushed" — dette er stale.
   - Opdatér Current Commit og Current Status til faktiske værdier.
   - Bevar alle andre felter (Project Name, Purpose, Port, Repository, Runtime Command,
     Related Projects) uændrede — de er korrekte.
</task>

<scope>
Filer du MÅ modificere:
- /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/02_SCOPE.md
- /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/00_PROJECT.md

Filer du IKKE må røre:
- Alle andre filer i /home/svend/ai-pc-resource-webui-v3/
- /home/svend/DPMtF-WebUI/ (father project)
- /home/svend/ENO/ (søn-projekt)
</scope>

<validation>
Før du melder færdig, verificér:
1. 02_SCOPE.md's Phase viser den faktiske nuværende fase (ikke 3C-3).
2. 00_PROJECT.md's Current Commit matcher output af "git log --oneline -1".
3. 00_PROJECT.md's Current Status afspejler projektets faktiske tilstand.
4. Ingen andre felter i 00_PROJECT.md er ændret.
5. Markdown-syntaksen er korrekt (ingen broken tables eller headings).
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Jeg reviewer diff'en før commit.
</constraint>
```
