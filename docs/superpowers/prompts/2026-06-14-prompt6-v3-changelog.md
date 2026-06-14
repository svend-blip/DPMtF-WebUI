# Prompt #6: CHANGELOG opdatering til v3

> **2O Run #3 — Ny prompt. Ingen af modellerne har set den før.**

```
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/10_CHANGELOG.md
  (brug denne som REFERENCE for formatet — append-only, dato+phase+bullets)
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md

Nøgleregler der SKAL overholdes:
- CHANGELOG er append-only — tilføj nye entries i bunden, redigér IKKE eksisterende.
- Hver entry skal have: dato (YYYY-MM-DD), phase key, kort beskrivelse, bullets
  for Changed/Added/Fixed/Removed.
- Brug git log til at finde præcise commit hashes og beskrivelser.
</governance>

<task>
Opdatér /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/10_CHANGELOG.md
med entries for de seneste features der er committed til v3.

Kør "git -C /home/svend/ai-pc-resource-webui-v3 log --oneline -15"
for at se de seneste commits og skriv CHANGELOG entries for:

1. Panel groups (ENO-6 Prompt #3) — commit 1ffd4a1
2. lbl() helper (ENO-6 Prompt #2) — commit d04b691
3. Governance doc alignment (ENO-6 Prompt #1) — commit c926242
4. CSS dark theme fixes (bridge tests) — commits 3162f73, fed7bca
5. Footer build-info (2O Run #2) — seneste commit
6. README improvements (2O Run #1) — seneste commit

Brug det eksisterende CHANGELOG format. Hver entry skal have:
### [YYYY-MM-DD] — [Phase key]: [Brief description]
- Changed/Added/Fixed: [What was done]

Tilføj entries i kronologisk rækkefølge (ældste først, nyeste sidst).
</task>

<scope>
Filer du MÅ modificere:
- /home/svend/ai-pc-resource-webui-v3/docs/dpmtf/10_CHANGELOG.md

Filer du IKKE må røre:
- Alle andre filer i /home/svend/ai-pc-resource-webui-v3/
- /home/svend/DPMtF-WebUI/
- /home/svend/ENO/
</scope>

<validation>
Før du melder færdig, verificér:
1. Alle 6 features har CHANGELOG entries
2. Hver entry har korrekt dato og phase key
3. Commit hashes matcher git log
4. Append-only — ingen eksisterende entries er redigeret
5. Kronologisk rækkefølge (ældste først)
6. Format matcher eksisterende entries (### [dato] — [phase]: [beskrivelse])
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Skriv en resultat-fil til /home/svend/claude-bridge/result.md med:
- Hvilke filer du modificerede
- Hvilke validerings-checks du kørte og deres resultater
- En kort opsummering af hvad du gjorde
</constraint>
```
