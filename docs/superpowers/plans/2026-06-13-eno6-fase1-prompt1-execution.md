# ENO-6 Fase 1: Prompt #1 Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generér Prompt #1 (v3 governance doc alignment), send til lokal Ollama model, review output, og registrér resultat i prompt_runs.

**Architecture:** Process-orienteret implementation. Prompt #1 er allerede designet i spec'en. Denne plan handler om at outputte prompten som en brugbar fil, etablere baseline for rollback, eksekvere via lokal model, review'e, og registrere.

**Tech Stack:** Claude Code (cloud) til generering og review. Claude Code (lokal Ollama qwen36-27b-q4km) til eksekvering. DPMtF-WebUI API (port 9130) til resultat-registrering.

---

## File Structure

| File | Rolle | Action |
|---|---|---|
| `docs/superpowers/prompts/2026-06-13-prompt1-v3-gov-doc-alignment.md` | Prompt #1 klar til copy-paste | Create |
| `docs/superpowers/prompts/2026-06-13-prompt1-review-checklist.md` | Review-checkliste til Prompt #1 | Create |
| `/home/svend/ai-pc-resource-webui-v3/` (git) | Target-projekt — modificeres af lokal model | Modify (by local model) |
| DPMtF-WebUI `prompt_runs` tabel | Resultat-registrering | POST via API |

---

### Task 1: Output Prompt #1 som standalone fil

**Files:**
- Create: `docs/superpowers/prompts/2026-06-13-prompt1-v3-gov-doc-alignment.md`

- [ ] **Step 1: Skriv Prompt #1 til fil**

Prompt #1 er allerede designet i spec'en. Output den som en ren markdown-fil der kan copy-pastes direkte ind i en lokal Claude Code session.

```markdown
# Prompt #1: v3 Governance Doc Alignment

Kopier hele indholdet af denne kodeblok og indsæt i en lokal Claude Code session
(startet med `--model qwen36-27b-q4km:latest` eller tilsvarende).

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
```

- [ ] **Step 2: Verificér at prompt-filen er læsbar**

```bash
head -5 docs/superpowers/prompts/2026-06-13-prompt1-v3-gov-doc-alignment.md
```
Expected: Viser "# Prompt #1: v3 Governance Doc Alignment"

- [ ] **Step 3: Commit prompt-filen**

```bash
git add docs/superpowers/prompts/2026-06-13-prompt1-v3-gov-doc-alignment.md
git commit -m "feat: add Prompt #1 — v3 governance doc alignment for local model testing"
```
Co-Authored-By: Claude <noreply@anthropic.com>

---

### Task 2: Etablér v3 baseline for rollback

**Files:**
- Read: `/home/svend/ai-pc-resource-webui-v3/` (git status)

- [ ] **Step 1: Tag v3's nuværende HEAD**

```bash
git -C /home/svend/ai-pc-resource-webui-v3 log --oneline -1
```
Expected: Viser nuværende HEAD (f.eks. `2a23a34 feat: add language dropdown styles`)

- [ ] **Step 2: Bekræft clean working tree**

```bash
git -C /home/svend/ai-pc-resource-webui-v3 status --short
```
Expected: Tom output (clean tree). Hvis ikke — stop og afklar med Svend.

- [ ] **Step 3: Notér baseline i plan-log**

Baseline registreret: `git -C /home/svend/ai-pc-resource-webui-v3 log --oneline -1` output.
Hvis rollback nødvendig: `git -C /home/svend/ai-pc-resource-webui-v3 reset --hard <baseline-commit>`

---

### Task 3: Opret review-checkliste til Prompt #1

**Files:**
- Create: `docs/superpowers/prompts/2026-06-13-prompt1-review-checklist.md`

- [ ] **Step 1: Skriv review-checkliste**

```markdown
# Prompt #1 Review Checklist

Bruges efter lokal model har eksekveret Prompt #1 (uden commit).

## Pre-review: Git diff

```bash
git -C /home/svend/ai-pc-resource-webui-v3 diff
git -C /home/svend/ai-pc-resource-webui-v3 diff --stat
```

## Review-punkter

| # | Check | Metode | Forventet |
|---|-------|--------|-----------|
| 1 | **Scope: Kun tilladte filer?** | `git diff --stat` viser kun `docs/dpmtf/02_SCOPE.md` og `docs/dpmtf/00_PROJECT.md` | Kun 2 filer |
| 2 | **02_SCOPE.md: Fase opdateret?** | Læs Phase linjen | Viser "3C-14" eller nyere — IKKE "3C-3" |
| 3 | **02_SCOPE.md: In/Out Scope opdateret?** | Læs sektionerne | Afspejler faktisk nuværende fase |
| 4 | **02_SCOPE.md: Scope Change Log tilføjet?** | Læs log-tabellen | Ny entry med dato 2026-06-13 |
| 5 | **00_PROJECT.md: Current Commit opdateret?** | Sammenlign med `git log --oneline -1` | Matcher faktisk HEAD |
| 6 | **00_PROJECT.md: Current Status opdateret?** | Læs linjen | Afspejler faktisk tilstand (ikke "Initial skeleton") |
| 7 | **00_PROJECT.md: Andre felter bevaret?** | Sammenlign Project Name, Purpose, Port, Repository, Runtime Command, Related Projects | Uændrede |
| 8 | **Markdown-syntaks OK?** | Visuel inspektion | Ingen broken tables, headings, eller fence blocks |

## Verdict

- **ACCEPT:** Alle 8 checks passer → klar til commit
- **DELVIST ACCEPT:** 1-2 checks fejler → notér fixes, ret manuelt, commit
- **AFVIS:** 3+ checks fejler eller scope-overtrædelse → `git reset --hard <baseline>`
```

- [ ] **Step 2: Commit review-checkliste**

```bash
git add docs/superpowers/prompts/2026-06-13-prompt1-review-checklist.md
git commit -m "feat: add review checklist for Prompt #1"
```
Co-Authored-By: Claude <noreply@anthropic.com>

---

### Task 4: Svend sender prompt til lokal model

**Dette trin udføres af Svend — ikke af Claude Code.**

- [ ] **Step 1: Åbn lokal Claude Code session**

```bash
claude --model qwen36-27b-q4km:latest
```
(eller tilsvarende kommando for at starte Claude Code med lokal Ollama model)

- [ ] **Step 2: Indsæt Prompt #1**

Copy-paste hele indholdet af kodeblokken fra:
`docs/superpowers/prompts/2026-06-13-prompt1-v3-gov-doc-alignment.md`

- [ ] **Step 3: Lad lokal model eksekvere**

Lokal model læser governance-filer, modificerer 02_SCOPE.md og 00_PROJECT.md,
kører validation-checks, og melder færdig. **Den committer IKKE.**

- [ ] **Step 4: Vend tilbage til cloud session**

Når lokal model er færdig, vend tilbage til denne session for review.

---

### Task 5: Review lokal models output

**Files:**
- Read: `/home/svend/ai-pc-resource-webui-v3/docs/dpmtf/02_SCOPE.md`
- Read: `/home/svend/ai-pc-resource-webui-v3/docs/dpmtf/00_PROJECT.md`

- [ ] **Step 1: Hent git diff**

```bash
git -C /home/svend/ai-pc-resource-webui-v3 diff --stat
git -C /home/svend/ai-pc-resource-webui-v3 diff
```
Expected: Kun `docs/dpmtf/02_SCOPE.md` og `docs/dpmtf/00_PROJECT.md` i diff.

- [ ] **Step 2: Kør review-checkliste**

Gennemgå alle 8 checks fra `docs/superpowers/prompts/2026-06-13-prompt1-review-checklist.md`.
Notér resultat per check (PASS/FAIL).

- [ ] **Step 3: Afsig verdict**

Baseret på checkliste-resultater:
- ACCEPT → fortsæt til commit (Task 6)
- DELVIST ACCEPT → notér fixes, ret manuelt, fortsæt til commit
- AFVIS → `git -C /home/svend/ai-pc-resource-webui-v3 reset --hard <baseline>` (rollback)

- [ ] **Step 4: Dokumentér fund**

Notér i prompt-run:
- Hvilke checks fejlede og hvorfor
- Hvad den lokale model gjorde rigtigt/forkert
- Om prompten var tilstrækkelig klar
- Forslag til governance-template forbedringer

---

### Task 6: Registrér resultat i prompt_runs

**Files:**
- API: `POST /api/prompt-runs` (DPMtF-WebUI, port 9130)

- [ ] **Step 1: Byg POST payload**

```json
{
  "run_id": "PRUN-ENO6-0001",
  "phase_key": "ENO-6",
  "target_project": "ai-pc-resource-webui-v3",
  "template_key": "tpl_update_edit_local",
  "model_used": "qwen36-27b-q4km:latest",
  "model_type": "local",
  "execution_status": "<completed|partial|failed>",
  "first_try_success": "<yes|no|partial>",
  "manual_corrections": <antal>,
  "validation_passed": "<yes|no|partial>",
  "success": <true|false>,
  "duration_seconds": <estimeret>,
  "error_summary": "<hvis fejlet, beskriv>",
  "notes": "<review fund og governance-forbedringsforslag>"
}
```

- [ ] **Step 2: Send POST til DPMtF-WebUI**

```bash
curl -X POST http://localhost:9130/api/prompt-runs \
  -H "Content-Type: application/json" \
  -d '{...payload...}'
```
Expected: 201 Created med run_id bekræftelse.

- [ ] **Step 3: Verificér at hitrates er opdateret**

```bash
curl http://localhost:9130/api/prompt-templates/tpl_update_edit_local/hitrate | python3 -m json.tool
```
Expected: Viser opdateret `total_local_runs` og `local_success_rate` for templaten.

---

### Task 7: Governance-forbedring baseret på resultat

**Files:**
- Modify: `docs/governance-templates/superpowertemplates/superpowers.md` (hvis nødvendigt)
- Modify: `docs/governance-templates/superpowertemplates/localmodel.md` (hvis nødvendigt)
- Modify: `docs/governance-templates/superpowertemplates/alignmentstructure.md` (v3 status)

- [ ] **Step 1: Analysér hvad der gik galt/godt**

Spørgsmål at besvare:
- Misforstod den lokale model nogen governance-regler? → Gør reglen mere eksplicit i templaten.
- Manglede prompten kontekst? → Tilføj sektion eller nøgleregel.
- Var opgaven for kompleks? → Notér kapabilitets-grænse i localmodel.md.
- Passerede alt perfekt? → Notér success-mønster til fremtidige prompts.

- [ ] **Step 2: Opdatér alignmentstructure.md**

Opdatér v3's række i alignment-status:
- Hvis Prompt #1 success: "Governance docs (projekt-specifikke)" → ✅ for v3
- Tilføj opdateringslog-entry

- [ ] **Step 3: Opdatér v3's 10_CHANGELOG.md (hvis commit'et)**

Hvis Prompt #1 blev commit'et til v3, tilføj en changelog-entry i v3:
```markdown
### [2026-06-13] — ENO-6 Alignment: Governance doc update
- Changed: 02_SCOPE.md — fase opdateret fra 3C-3 til 3C-14
- Changed: 00_PROJECT.md — Current Commit og Current Status opdateret
```

- [ ] **Step 4: Commit governance-forbedringer**

```bash
git add docs/governance-templates/superpowertemplates/
git commit -m "docs: governance improvements from ENO-6 Prompt #1 results"
```
Co-Authored-By: Claude <noreply@anthropic.com>

---

### Task 8: Forbered Prompt #2 (skitse → færdig)

**Files:**
- Create: `docs/superpowers/prompts/2026-06-13-prompt2-v3-lbl-helper.md`

- [ ] **Step 1: Evaluér om Prompt #2 skal justeres baseret på #1 erfaring**

Spørgsmål:
- Var Prompt #1's struktur effektiv? → Bevar eller justér.
- Var `<governance>` sektionen tilstrækkelig? → Tilføj eller fjern nøgleregler.
- Var opgavestørrelsen passende? → Justér sværhedsgrad for Prompt #2.

- [ ] **Step 2: Færdigskriv Prompt #2**

Udfyld prompt-template med konkrete værdier for lbl() helper opgaven.
Gem til `docs/superpowers/prompts/2026-06-13-prompt2-v3-lbl-helper.md`.

- [ ] **Step 3: Commit Prompt #2**

```bash
git add docs/superpowers/prompts/2026-06-13-prompt2-v3-lbl-helper.md
git commit -m "feat: add Prompt #2 — lbl() helper for v3"
```
Co-Authored-By: Claude <noreply@anthropic.com>
