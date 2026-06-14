# 2O-a: Parallel Comparison Runs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kør 3 parallelle prompts på cloud (deepseek-v4-pro:cloud) og lokal (qwen36-27b-q4km:latest) model, sammenlign resultater på 6 metrikker, og producér baseline data til model selection decision tree.

**Architecture:** Process-orienteret. Hver run følger samme workflow: cloud eksekverer → registrer → send via tmux bridge til lokal → lokal eksekverer → cloud reviewer → registrer → comparison summary → commit. Ingen ny kode i DPMtF-WebUI.

**Tech Stack:** Claude Code (cloud) + Claude Code (lokal via tmux bridge) + DPMtF-WebUI prompt_runs API (port 9130) + git (v3 target).

---

## File Structure

| File | Rolle | Action |
|---|---|---|
| `/home/svend/claude-bridge/handoff.md` | Handoff fil (cloud→lokal) | Write per run |
| `/home/svend/claude-bridge/result.md` | Resultat fil (lokal→cloud) | Read per run |
| `/home/svend/ai-pc-resource-webui-v3/` | Target-projekt for prompts | Modify (by both models) |
| `docs/superpowers/comparisons/2026-06-14-cmp-0001.md` | Comparison summary #1 | Create |
| `docs/superpowers/comparisons/2026-06-14-cmp-0002.md` | Comparison summary #2 | Create |
| `docs/superpowers/comparisons/2026-06-14-cmp-0003.md` | Comparison summary #3 | Create |
| DPMtF-WebUI `prompt_runs` tabel | Resultat-registrering | POST via API |
| `docs/governance-templates/superpowertemplates/superpowers.md` | Model decision tree update | Modify after all 3 runs |

---

### Task 1: Run #1 — README.md v3-specifik (genbrug, bias-check)

**Prompt:** Prompt #4 fra ENO-6. 1 .md fil. Lav sværhed.
**Formål:** Bias-check — lokal model har allerede kørt denne (first-try success).

- [ ] **Step 1: Cloud eksekverer Prompt #4**

Cloud model (denne session) eksekverer Prompt #4 på v3:
- Læs `/home/svend/DPMtF-WebUI/docs/superpowers/prompts/2026-06-13-prompt4-v3-readme.md`
- Eksekver på `/home/svend/ai-pc-resource-webui-v3`
- **COMMIT IKKE** — samme constraint som lokal model
- Notér start-tid og slut-tid for duration estimat

- [ ] **Step 2: Registrér cloud resultat i prompt_runs**

```bash
curl -s -X POST http://localhost:9130/api/prompt-runs \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "PRUN-2O-0001-CLOUD",
    "phase_key": "2O",
    "target_project": "ai-pc-resource-webui-v3",
    "prompt_summary": "Prompt 4: README.md v3-specific. Reused from ENO-6 for bias-check.",
    "success": true,
    "duration_seconds": <cloud_duration>,
    "model_used": "deepseek-v4-pro:cloud",
    "model_type": "cloud",
    "template_key": "tpl_update_edit_local",
    "execution_status": "completed",
    "first_try_success": true,
    "manual_corrections": 0,
    "validation_passed": true,
    "notes": "comparison_id=CMP-0001, role=cloud, output_quality=5/5, governance_compliance=100%"
  }'
```
Expected: 201 Created.

- [ ] **Step 3: Skriv handoff.md til lokal model**

Skriv `/home/svend/claude-bridge/handoff.md` med Prompt #4 indhold + constraint:
```
<constraint>
COMMIT IKKE. Stop efter implementation.
Skriv resultat til /home/svend/claude-bridge/result.md
</constraint>
```

- [ ] **Step 4: Send til lokal model via tmux bridge**

```bash
tmux send-keys -t review_claude "$(cat /home/svend/claude-bridge/clear.md)" Enter
sleep 1
tmux send-keys -t review_claude "Read and execute the instructions in /home/svend/claude-bridge/handoff.md" Enter
sleep 1
tmux send-keys -t review_claude Enter  # Ekstra Enter — kendt bridge issue
```

- [ ] **Step 5: Afvent lokal model**

Vent på at `/home/svend/claude-bridge/result.md` dukker op.
Tjek: `cat /home/svend/claude-bridge/result.md 2>/dev/null || echo "Afventer..."`

- [ ] **Step 6: Review lokal models output**

```bash
git -C /home/svend/ai-pc-resource-webui-v3 diff --stat
git -C /home/svend/ai-pc-resource-webui-v3 diff docs/dpmtf/README.md
```
Kør review-checks: scope (kun 1 fil?), titel nævner v3?, port 9123 nævnt?, v3-Specific Notes findes?, Prompt-Run Templates fjernet?, markdown OK?

- [ ] **Step 7: Registrér lokal resultat i prompt_runs**

```bash
curl -s -X POST http://localhost:9130/api/prompt-runs \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "PRUN-2O-0001-LOCAL",
    "phase_key": "2O",
    "target_project": "ai-pc-resource-webui-v3",
    "prompt_summary": "Prompt 4: README.md v3-specific. Reused from ENO-6 for bias-check.",
    "success": <true/false>,
    "duration_seconds": <local_duration>,
    "model_used": "qwen36-27b-q4km:latest",
    "model_type": "local",
    "template_key": "tpl_update_edit_local",
    "execution_status": "<completed/partial/failed>",
    "first_try_success": <true/false>,
    "manual_corrections": <antal>,
    "validation_passed": <true/false>,
    "notes": "comparison_id=CMP-0001, role=local, output_quality=<X>/5, governance_compliance=<Y>%"
  }'
```

- [ ] **Step 8: Skriv comparison summary CMP-0001**

Opret `docs/superpowers/comparisons/2026-06-14-cmp-0001.md`:

```markdown
# Comparison CMP-0001: README.md v3-specifik (Prompt #4 genbrug)

| Metrik | Cloud (deepseek-v4-pro) | Lokal (qwen36-27b-q4km) | Delta |
|---|---|---|---|
| Success | <cloud> | <local> | — |
| First-try | <cloud> | <local> | — |
| Duration | <cloud>s | <local>s | ±Xs |
| Output quality | <cloud>/5 | <local>/5 | ±N |
| Gov compliance | <cloud>% | <local>% | ±N% |
| Cost | ~<cloud> EUR | 0 EUR | — |

**Konklusion:** <hvilken model var bedst til denne opgavetype?>
```

- [ ] **Step 9: Commit (Svend godkender)**

Hvis begge acceptable: commit begge ændringer til v3.
Hvis kun én: commit den acceptable, rollback den anden.

---

### Task 2: Run #2 — Footer med build-info (ny prompt, medium)

**Prompt:** Ny — tilføj footer til v3 med build timestamp, port, projektnavn.
3 filer: HTML + JS + CSS. Medium sværhed. Ingen af modellerne har set den før.

- [ ] **Step 1: Skriv Prompt #5 (footer feature)**

Opret `docs/superpowers/prompts/2026-06-14-prompt5-v3-footer.md` med prompt der specificerer:
- Tilføj `<footer>` til `templates/index.html` med data-slot attributter
- Tilføj `initFooter()` til `static/js/app.js` der henter git info og sætter tekst via lbl()
- Tilføj footer styles til `static/css/app.css` (mørkt tema farver)
- Governance: lbl() til tekst, ingen innerHTML, mørkt tema

- [ ] **Step 2: Cloud eksekverer Prompt #5**

Samme workflow som Run #1 Step 1. COMMIT IKKE.

- [ ] **Step 3: Registrér cloud resultat (PRUN-2O-0002-CLOUD)**

Samme format som Run #1 Step 2, med comparison_id=CMP-0002.

- [ ] **Step 4: Send til lokal model via bridge**

Samme som Run #1 Steps 3-4.

- [ ] **Step 5: Afvent + review lokal model**

Samme som Run #1 Steps 5-6. Review-checks: scope (HTML+JS+CSS?), lbl() brugt?, ingen innerHTML?, mørkt tema farver?, footer viser korrekt info?

- [ ] **Step 6: Registrér lokal resultat (PRUN-2O-0002-LOCAL)**

Samme format som Run #1 Step 7, med comparison_id=CMP-0002.

- [ ] **Step 7: Skriv comparison summary CMP-0002**

Samme format som Run #1 Step 8.

- [ ] **Step 8: Commit (Svend godkender)**

---

### Task 3: Run #3 — CHANGELOG opdatering (ny prompt, medium-lav)

**Prompt:** Ny — opdatér v3's CHANGELOG med entries for seneste commits.
1 .md fil. Medium-lav sværhed. Ingen af modellerne har set den før.

- [ ] **Step 1: Skriv Prompt #6 (CHANGELOG update)**

Opret `docs/superpowers/prompts/2026-06-14-prompt6-v3-changelog.md` med prompt der specificerer:
- Læs v3's git log for at finde commits siden sidste CHANGELOG entry
- Skriv CHANGELOG entries for: bridge tests, CSS dark theme, panel groups, lbl(), gov docs
- Følg CHANGELOG format (date, phase key, description, bullets)
- Append-only — tilføj til eksisterende entries

- [ ] **Step 2: Cloud eksekverer Prompt #6**

Samme workflow. COMMIT IKKE.

- [ ] **Step 3: Registrér cloud resultat (PRUN-2O-0003-CLOUD)**

comparison_id=CMP-0003.

- [ ] **Step 4: Send til lokal model via bridge**

- [ ] **Step 5: Afvent + review lokal model**

Review-checks: scope (kun CHANGELOG?), korrekt format?, append-only?, commit hashes korrekte?, dækker alle seneste features?

- [ ] **Step 6: Registrér lokal resultat (PRUN-2O-0003-LOCAL)**

- [ ] **Step 7: Skriv comparison summary CMP-0003**

- [ ] **Step 8: Commit (Svend godkender)**

---

### Task 4: Opdatér model decision tree

**Files:**
- Modify: `docs/governance-templates/superpowertemplates/superpowers.md`
- Modify: `docs/governance-templates/superpowertemplates/localmodel.md`
- Modify: `docs/governance-templates/superpowertemplates/alignmentstructure.md`

- [ ] **Step 1: Analysér alle 3 comparison summaries**

Besvar:
- Hvilken model vandt flest runs?
- Ved hvilken sværhedsgrad skifter fordelen?
- Er lokal model sufficient til medium-høj opgaver?
- Hvad er cost-forskellen per run?

- [ ] **Step 2: Opdatér superpowers.md Model Selection Decision Tree**

Tilføj empirisk data node:
```
├─ Er opgaven medium-høj eller lavere?
│   └─ BRUG: Lokal Ollama model (qwen36-27b-q4km)
│      Evidens: X/Y first-try success på tværs af Z opgavetyper.
│      Cost: 0 EUR vs ~X EUR for cloud.
```

- [ ] **Step 3: Opdatér localmodel.md med 2O baseline**

Tilføj update-log entry med 2O resultater og anbefalinger.

- [ ] **Step 4: Opdatér alignmentstructure.md**

Tilføj 2O til alignment-status: ✅ completed.

- [ ] **Step 5: Commit governance updates**

```bash
git add docs/governance-templates/superpowertemplates/
git commit -m "docs: 2O baseline data — model decision tree updated with empirical evidence"
```
Co-Authored-By: Claude <noreply@anthropic.com>
