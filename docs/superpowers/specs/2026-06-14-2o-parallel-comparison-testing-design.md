# 2O: Parallel-kørsel test cloud vs lokal — Design Spec

> **Hybrid tilgang.** Fase 2O-a: 3 parallel-kørsler med eksisterende infrastruktur, baseline data.
> Fase 2O-b: Comparison panel i DPMtF-WebUI (designes separat efter 2O-a data).

---

## 1. Formål

2O er sidste fase i Blok 6 af DPMtF-WebUI's roadmap. Den etablerer det **empiriske grundlag**
for model selection decision tree i superpowers.md ved at køre identiske prompts på cloud-model
(deepseek-v4-pro:cloud) og lokal model (qwen36-27b-q4km:latest) og sammenligne resultaterne
på tværs af 6 metrikker.

**Eksisterende infrastruktur der bruges:**
- prompt_templates, prompt_runs, template_model_hitrates (DPMtF-WebUI database)
- Tmux bridge protocol (cloud→lokal kommunikation via review_claude session)
- 6 succesfulde lokal-model prompts som baseline (ENO-6 Fase 1 + bridge tests)

---

## 2. Arkitektur

```
CLOUD MODEL (denne session)          LOKAL MODEL (review_claude tmux)
─────────────────────────────────    ──────────────────────────────────
1. Eksekver prompt                    (samme prompt sendes via bridge)
   └─ Registrer i prompt_runs        4. Eksekver prompt
      (PRUN-2O-XXXX-CLOUD)              └─ Skriv result.md til claude-bridge/
                                     5. Cloud reviewer diff + result.md
2. Skriv handoff.md til claude-bridge/
3. Send via tmux:
   /clear → handoff instruktion      6. Registrer i prompt_runs
                                        (PRUN-2O-XXXX-LOCAL)
                                     7. Skriv comparison summary
                                     8. Opdatér template_model_hitrates
```

---

## 3. De 3 parallel-kørsler

### Run #1: Genbrug — README.md v3-specifik (lav sværhed)

**Prompt:** Prompt #4 fra ENO-6 (README.md v3-specifik). 1 .md fil.
**Formål:** Bias-check. Lokal model har allerede kørt denne (first-try success).
Cloud model kører samme prompt — sammenlign output quality, duration, governance compliance.

### Run #2: Ny — Footer med build-info (medium sværhed)

**Ny prompt — ingen af modellerne har set den før.**

Opgave: Tilføj en footer til v3's `templates/index.html` der viser:
- Build timestamp (fra `git log -1 --format=%ci`)
- Port nummer (9123)
- Projektnavn ("AI PC Resource WebUI v3")

Filer: `templates/index.html` + `static/js/app.js` + `static/css/app.css` (3 filer).
Governance-krav: lbl() til tekst, ingen innerHTML, mørkt tema farver.

### Run #3: Ny — CHANGELOG opdatering (medium-lav sværhed)

**Ny prompt — ingen af modellerne har set den før.**

Opgave: Opdatér v3's `docs/dpmtf/10_CHANGELOG.md` med entries for:
- Bridge test #1 (panel-group CSS dark theme fix)
- Bridge test #2 (complete CSS dark theme migration)
- Panel groups feature (Prompt #3)
- lbl() helper (Prompt #2)
- Governance doc alignment (Prompt #1)

Filer: 1 .md fil. Kræver at læse git log for at finde commit hashes og beskrivelser.

---

## 4. Sammenlignings-metrikker

Hver parallel-kørsel evalueres på 6 metrikker:

| Metrik | Måling | Skala |
|---|---|---|
| **Success** | Blev opgaven fuldført? | completed / partial / failed |
| **First-try** | Var rettelser nødvendige? | yes / no / antal rettelser |
| **Duration** | Hvor lang tid tog eksekvering? | sekunder (estimeret) |
| **Output quality** | Hvor godt var resultatet? Målt som andel af review-checks passeret + kvalitative bemærkninger. | 1-5 (1=afvist, 3=delvist accept, 5=accept alle checks) |
| **Governance compliance** | Overholdt modellen alle governance-regler fra promptens `<governance>` sektion? | 0-100% (andel af nøgleregler overholdt) |
| **Cost** | Hvad kostede kørslen? | EUR (estimeret for cloud via token cost, 0 for lokal) |
| **Duration** | Hvor lang tid tog eksekvering? Målt fra prompt start til resultatfil skrevet (lokal) eller task færdig (cloud). | sekunder (estimeret) |

---

## 5. Data-registrering

### prompt_runs records

Hver parallel-kørsel producerer 2 prompt_runs records med fælles comparison_id:

```
Cloud record:
  run_id: PRUN-2O-0001-CLOUD
  phase_key: 2O
  model_used: deepseek-v4-pro:cloud
  model_type: cloud
  template_key: tpl_update_edit_local (eller relevant)
  notes: comparison_id=CMP-0001, role=cloud, output_quality=X/5, governance_compliance=Y%

Local record:
  run_id: PRUN-2O-0001-LOCAL
  phase_key: 2O
  model_used: qwen36-27b-q4km:latest
  model_type: local
  template_key: (samme som cloud)
  notes: comparison_id=CMP-0001, role=local, output_quality=X/5, governance_compliance=Y%
```

### Comparison summary filer

Efter hver parallel-kørsel skrives en comparison summary til:
`docs/superpowers/comparisons/2026-06-14-cmp-XXXX.md`

Format: Tabel med cloud vs lokal på alle 6 metrikker + delta + konklusion.

### template_model_hitrates

Efter hver registrering opdateres template_model_hitrates automatisk via
POST /api/prompt-runs (eksisterende logik).

---

## 6. Workflow per run

```
1. CLOUD EKSEKVERER
   ├─ Cloud model (denne session) modtager prompt
   ├─ Eksekverer på target-projektet (v3)
   ├─ COMMITTER IKKE — samme constraint som lokal model.
   │  Dette er VIGTIGT for fair sammenligning: begge modeller
   │  skal arbejde under samme begrænsninger.
   └─ Estimerer duration, tokens, cost

2. REGISTRÉR CLOUD RESULTAT
   ├─ POST /api/prompt-runs med PRUN-2O-XXXX-CLOUD
   └─ Notér comparison_id, output_quality, governance_compliance i notes

3. SEND TIL LOKAL MODEL
   ├─ Skriv handoff.md til /home/svend/claude-bridge/
   ├─ tmux send-keys /clear + handoff instruktion
   └─ Evt. ekstra Enter hvis nødvendigt (kendt bridge issue)

4. LOKAL MODEL EKSEKVERER
   ├─ Læser handoff.md
   ├─ Eksekverer på target-projektet
   ├─ COMMITTER IKKE
   └─ Skriver result.md til /home/svend/claude-bridge/

5. CLOUD REVIEWER LOKAL RESULTAT
   ├─ Læs result.md
   ├─ git diff i target-projektet
   ├─ Kør review-checks (scope, innerHTML, i18n, syntaks, etc.)
   └─ Afsig verdict: accept / delvist / afvis

6. REGISTRÉR LOKAL RESULTAT
   ├─ POST /api/prompt-runs med PRUN-2O-XXXX-LOCAL
   └─ Notér comparison_id, output_quality, governance_compliance i notes

7. SKRIV COMPARISON SUMMARY
   ├─ Opret docs/superpowers/comparisons/2026-06-14-cmp-XXXX.md
   ├─ Udfyld 6-metrik tabel for cloud vs lokal
   └─ Skriv konklusion: hvilken model var bedst til denne opgavetype?

8. COMMIT (Svend godkender)
   ├─ Hvis begge acceptable: commit begge ændringer
   ├─ Hvis kun én acceptable: commit den ene, rollback den anden
   └─ Hvis ingen acceptable: rollback begge
```

---

## 7. Fase 2O-b: Comparison panel (fremtidig)

Efter 2O-a data er indsamlet og analyseret:

- **Ny tabel `comparison_runs`:** comparison_id, prompt_template_key, task_type, complexity_tier, cloud_run_id, local_run_id, cloud_verdict, local_verdict, winner (cloud/local/tie), created_at.
- **GET /api/comparison-runs:** List alle comparisons med filtre (complexity_tier, winner, task_type).
- **Frontend panel i System Setup drawer:** Side-by-side visning af cloud vs lokal resultater. Farvekodning: grøn=cloud vinder, blå=lokal vinder, grå=tie.
- **Model decision tree opdatering:** superpowers.md opdateres med empirisk data og anbefalinger.

Designes i separat spec efter 2O-a er gennemført.

---

## 8. Success-kriterier

### 2O-a

- [ ] 3 parallel-kørsler gennemført (cloud + lokal på samme prompt)
- [ ] 6 prompt_runs records registreret (3 cloud + 3 lokal)
- [ ] 3 comparison summaries skrevet til docs/superpowers/comparisons/
- [ ] template_model_hitrates opdateret for begge modeller
- [ ] Model decision tree i superpowers.md opdateret med empirisk data
- [ ] Baseline-data: hvilken model er bedst til hvilken opgavetype?

### 2O-b (fremtidig)

- [ ] comparison_runs tabel + API + frontend panel
- [ ] Data-drevet model selection anbefalinger i superpowers.md

---

## 9. Scope-afgrænsning

### In scope (2O-a)

- 3 parallel-kørsler via tmux bridge
- Registrering i prompt_runs med comparison metadata
- Comparison summaries i docs/superpowers/comparisons/
- Opdatering af model decision tree i superpowers.md
- Opdatering af alignmentstructure.md og localmodel.md med 2O resultater

### Out of scope

- Ny kode i DPMtF-WebUI (ingen nye endpoints, tabeller, eller frontend)
- Ændringer i ENO eller andre projekter
- Automatisk model-routing baseret på resultater
- Test på andre modeller end deepseek-v4-pro:cloud og qwen36-27b-q4km:latest
- Comparison panel (2O-b — separat spec)
