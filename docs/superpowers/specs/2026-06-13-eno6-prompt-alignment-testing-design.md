# ENO-6: Prompt-generering til alignment-test med lokal Ollama model

> **Design spec.** Hybrid tilgang — start lightweight, byg tracker incrementalt.
> Fase 1: 2-3 prompts, manuel proces, baseline data.
> Fase 2: Alignment-dashboard i ENO baseret på fase 1 erfaringer.

---

## 1. Formål

ENO-6 er ENO's næste funktionelle fase. Den bruger ENO's eksisterende evaluerings-infrastruktur
til systematisk at teste hvor godt den lokale Ollama model (qwen36-27b-q4km:latest) kan udføre
alignment-opgaver på Child projects under DPMtF governance.

**To overordnede mål:**

1. **Forbedre governance templates** — identificér hvilke regler den lokale model har svært ved
   at forstå eller overholde. Opdatér templates så de bliver mere maskin-læsbare og entydige.
2. **Kortlæg lokal models kapabilitets-grænser** — forstå hvilken størrelse og type opgaver
   den lokale model kan udføre korrekt, givet optimale governance templates og optimale prompts.

**Test-projekt:** `/home/svend/ai-pc-resource-webui-v3` (port 9123) — reference-projektet.

---

## 2. Prompt-template struktur

Alle prompts følger denne 6-sektions struktur. Sektionerne giver den lokale model præcis
kontekst og boundaries, og refererer eksplicit til DPMtF-WebUI's governance-filer.

```
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>{target_project_path}</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- {governance_file_1}
- {governance_file_2}
Nøgleregler der SKAL overholdes:
- {key_rule_1}
- {key_rule_2}
</governance>

<task>
{concrete_task_description}
</task>

<scope>
Filer du MÅ modificere:
- {allowed_file_1}
- {allowed_file_2}
Filer du IKKE må røre:
- {forbidden_file_1}
</scope>

<validation>
Før du melder færdig, verificér:
1. {validation_check_1}
2. {validation_check_2}
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Jeg reviewer diff'en før commit.
</constraint>
```

### Sektions-beskrivelser

| Sektion | Formål | Indhold |
|---|---|---|
| `<role>` | Sætter governance-kontekst | "Du er Implementer i DPMtF governance rollen." |
| `<project>` | Angiver target | Absolut sti til projektet der skal alignes |
| `<governance>` | Refererer autoritative regler | Stier til relevante governance-filer + udvalgte nøgleregler |
| `<task>` | Konkret opgavebeskrivelse | Hvad skal gøres, i hvilken rækkefølge, med hvilket resultat |
| `<scope>` | Boundaries | Hvilke filer må røres, hvilke er forbudte |
| `<validation>` | Selv-verificering | Konkrete checks den lokale model skal køre før den melder færdig |
| `<constraint>` | Hard constraint | "COMMIT IKKE" — altid til stede |

---

## 3. Workflow

```
1. GENERÉR PROMPT (Claude Code, cloud model)
   ├─ Analysér alignment-gaps for target-projekt
   ├─ Udfyld prompt-template med konkrete værdier
   └─ Output: komplet prompt klar til lokal model

2. SEND TIL LOKAL MODEL (Svend)
   ├─ Åbn separat Claude Code session med lokal Ollama model
   ├─ Indsæt prompt
   └─ Lokal model eksekverer — COMMITTER IKKE

3. REVIEW (Claude Code, cloud model)
   ├─ Læs git diff i target-projektet: "git -C {project} diff"
   ├─ Tjek mod governance-reglerne fra promptens <governance> sektion
   ├─ Specifikke review-checks:
   │  • Scope: Kun tilladte filer modificeret?
   │  • innerHTML: Ingen nye innerHTML til dynamisk indhold?
   │  • i18n: Bruges lbl() eller labelMap korrekt?
   │  • Markdown: Ingen broken tables/headings?
   │  • Opgave: Er alle task-punkter udført?
   ├─ Vurdér: acceptér / delvist acceptér (nævn specifikke fixes) / afvis
   └─ Dokumentér fund i prompt-runs noter

4. COMMIT / ROLLBACK (Svend)
   ├─ Hvis accept: commit med Co-Authored-By: Claude <noreply@anthropic.com>
   ├─ Hvis delvist: manuelle rettelser, derefter commit
   └─ Hvis afvist: git reset --hard (rollback)

5. REGISTRÉR RESULTAT
   ├─ POST /api/prompt-runs (DPMtF-WebUI, port 9130)
   ├─ Obligatoriske felter: execution_status, first_try_success, validation_passed, template_key
   ├─ Metadata: model_used=qwen36-27b-q4km:latest, model_type=local, tokens, duration
   └─ Dette opdaterer template_model_hitrates og prompt_hitrates

6. FORBEDR GOVERNANCE TEMPLATES
   ├─ Analysér hvad der gik galt / godt
   ├─ Opdatér relevante governance-filer i DPMtF-WebUI
   └─ Dokumentér i alignmentstructure.md
```

---

## 4. Fase 1: Prompt-pipeline (lightweight)

### Prompt #1: v3 Governance Doc Alignment

**Sværhed:** Medium-lav. **Filer:** 2 (.md only). **Risiko:** Lav.

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

### Prompt #2: Tilføj lbl() helper til v3 *(skitse — færdigskrives efter Prompt #1 baseline)*

**Sværhed:** Medium. **Filer:** 1 JS fil. **Risiko:** Medium (JS ændring).

v3 bruger `labelMap["key"] || "fallback"` i stedet for `lbl(key, fallback)` helper-funktionen.
Prompt #2 beder den lokale model om at tilføje `lbl()` funktionen og migrere eksisterende
`labelMap["key"] || "fallback"` kald til `lbl(key, fallback)`.

### Prompt #3: Panel groups til v3 *(skitse — færdigskrives efter Prompt #1-2 erfaring)*

**Sværhed:** Medium-høj. **Filer:** DB+JS+CSS+HTML. **Risiko:** Medium-høj.

Implementér panel-group containers, collapse/expand, og user_panel_groups tabel i v3,
baseret på DPMtF-WebUI's implementation (som reference, ikke kopieret 1:1).

### Prompt #4: README.md v3-specifik *(skitse — færdigskrives efter Prompt #1-3 erfaring)*

**Sværhed:** Lav. **Filer:** 1 .md fil. **Risiko:** Lav.

Opdatér v3's README.md til at være v3-specifik (ikke generisk governance template index).

> **Note:** Prompts #2-4 er skitser. De færdigskrives med konkrete værdier (commit hashes,
> fil-stier, nøgleregler) efter vi har baseline-data fra Prompt #1. Dette er agil tilgang —
> vi justerer prompt-strukturen baseret på hvad vi lærer undervejs.

---

## 5. Evaluerings-kriterier per prompt-run

Hver prompt-run evalueres på:

| Kriterie | Måling | Skala |
|---|---|---|
| **Governance compliance** | Overholdt den lokale model alle nøgleregler fra `<governance>` sektionen? | Ja / Delvist / Nej |
| **Scope compliance** | Modificerede den kun tilladte filer? | Ja / Nej |
| **Validation compliance** | Passerede alle validerings-checks? | Ja / Delvist / Nej |
| **First-try success** | Var manuelle rettelser nødvendige? | Ja / Nej / Antal rettelser |
| **Task completion** | Blev opgaven fuldført? | Completed / Partial / Failed |
| **Prompt clarity** | Misforstod den lokale model opgaven? Manglede prompten kontekst? Målt ved: antal afvigelser fra task-beskrivelsen, antal scope-overtrædelser, om validation-checks blev ignoreret. | Tydelig (0 afvigelser) / Mindre uklar (1-2 afvigelser) / Mangelfuld (3+ afvigelser eller total misforståelse) |

Disse registreres i DPMtF-WebUI's `prompt_runs` tabel med obligatoriske outcome-felter.

---

## 6. Fase 2: Alignment-dashboard i ENO (planlagt)

Efter 2-3 prompts i fase 1, bygges et alignment-dashboard i ENO:

- **Ny tabel `alignment_tests`:** prompt_id, target_project, governance_files_referenced,
  alignment_gaps_targeted, local_model_used, review_verdict, governance_template_changes_made.
- **Frontend panel:** Viser per-projekt alignment-status, prompt-historik, success-rate
  per opgavetype, og hvilke governance templates der er blevet forbedret som resultat.
- **Integration med DPMtF-WebUI:** Læser prompt_runs via API (port 9130) og korrelerer
  med alignment gaps fra alignmentstructure.md.

Dette designes i en separat spec efter fase 1 er gennemført og vi har baseline data.

---

## 7. Success-kriterier for ENO-6

### Fase 1

- [ ] Mindst 2 prompts genereret og eksekveret af lokal model
- [ ] Alle runs registreret i DPMtF-WebUI's prompt_runs med outcome-felter
- [ ] Mindst 1 governance-template forbedret baseret på lokal-model erfaring
- [ ] Baseline-data: forståelse af hvilke opgavetyper lokal model klarer godt/skidt

### Fase 2 (fremtidig)

- [ ] Alignment-dashboard i ENO viser per-projekt alignment-status
- [ ] Mindst 3 projekter tracket (v3, ENO selv, evt. nyt projekt)
- [ ] Data-drevet anbefalinger til model-valg (cloud vs lokal per opgavetype)

---

## 8. Governance-impact

Resultaterne fra ENO-6 føder direkte ind i:

| Governance-fil | Hvordan |
|---|---|
| `superpowers.md` | Model decision tree forbedres med empirisk data om lokal model kapabiliteter |
| `alignmentstructure.md` | Alignment matrix opdateres når v3 alignes |
| `localmodel.md` | Prompt-struktur og best practices for lokal model prompts dokumenteres |
| `05_CODING_STANDARD.md` | Evt. nye regler baseret på hvad lokal model konsekvent fejler på |
| `gates.md` | Evt. ny gate for "lokal model egnethed" baseret på opgavetype |

---

## 9. Scope-afgrænsning

### In scope (ENO-6)

- Prompt-generering (cloud model) til alignment-test
- Review af lokal models output
- Registrering i prompt_runs
- Governance-template forbedringer baseret på erfaring
- ENO alignment-dashboard (fase 2)

### Out of scope

- Automatisk prompt-eksekvering (prompts sendes manuelt af Svend)
- Ændringer i Ollama konfiguration eller model-downloads
- Ændringer i DPMtF-WebUI's prompt compiler (bruges som den er)
- Test på andre modeller end qwen36-27b-q4km:latest (fremtidig udvidelse)
