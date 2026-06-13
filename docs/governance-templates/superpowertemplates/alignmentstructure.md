# Alignment Structure

> **Feature-alignment på tværs af DPMtF-afledte projekter.**
> Loades når en feature implementeres eller udrulles.
> Refereret fra [[superpowers]].

---

## 1. Alignment Matrix

Tracker hvilke features der gælder for hvilke projekter.

| Feature | DPMtF-WebUI (9130) | ENO (9131) | ai-pc-resource-webui-v3 (9123) | Dato | Note |
|---|---|---|---|---|---|
| Sprog-tabel + dropdown | ✅ | ✅ | ✅ | 2026-06-12 | Fælles i18n-feature. ENO: e867ad8 |
| "Vis fuldførte faser" filter default false | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only |
| GitHub fase-synkronisering | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only |
| Panelgrupper (collapse/expand) | ✅ | ✅ | ⏳ | 2026-06-13 | ENO: 4 commits (dfaa96c→320a7a6). Udrulles senere til v3 |
| i18n 4-lags arkitektur alignment | ✅ | ✅ | — | 2026-06-13 | DPMtF-WebUI API rettet til fuld 4-lags traversering (slot→label→translation). ENO: 9073de2 — allerede korrekt 4-lags flow. v3 har allerede standard. |
| Database merge (DPMtF governance tables) | ✅ | ✅ | — | 2026-06-13 | ENO: 05f9b0d. v3 har eget schema |
| Prompt Template Manager (2H) | ✅ | — | — | 2026-06-13 | DPMtF-WebUI only — redesigned based on Excel data analysis of 8 prompt runs. 6 templates, complexity tiers, per-model hitrate tracking, mandatory outcome fields. |
| Local Prompt Compiler (2I) | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only — governance-infrastruktur. Commits: 5d389b8, 06d8dd5, fdea70e |
| Validation Automation (2J) | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only — governance-infrastruktur. Commits: 5b4a44b, 80a1034, 9493961, 1a9d6ba |
| Git Sync Management (2K) | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only — governance-infrastruktur. Commits: 7d78926, 342c309, 85498f1 |
| Platform Adapter Framework (2L) | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only — governance-infrastruktur. Commits: 7cbc34e, a951d20 |
| Local Claude Code Session Manager (2M) | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only — governance-infrastruktur. Commits: 9bf352f, 379b169 |
| Prompt→Implementer→Validator loop (2N) | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only — governance-infrastruktur. Commits: 700a513, cb074f5 |
| Parallel-kørsel test cloud vs lokal (2O) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — Næste fase. Sidste i Blok 6 |
| | | | | | |

**Tegnforklaring:**
- ✅ = Implementeret
- — = Ikke relevant / kun father project
- ⏳ = Planlagt, ikke implementeret endnu

---

## 2. Feature Rollout Regler

### Regel 1: Spørg hvis ikke specificeret

Når en feature implementeres i DPMtF-WebUI, og brugeren ikke har specificeret
om den skal udrulles til andre projekter:

> **Stil spørgsmålet:** "Er dette kun en DPMtF-WebUI feature, eller skal den
> også udrulles til ENO og/eller ai-pc-resource-webui-v3?"

Opdater alignment matrix med svaret.

### Regel 2: Rollout-rækkefølge

Når en feature skal udrulles til flere projekter:

1. **Implementer i DPMtF-WebUI** (father project) først
2. **Udrul til ENO** (første søn-projekt)
3. **For v3:** Stil GATE-V3 først (se [[gates]])

### Regel 3: DPMtF-WebUI only

Hvis en feature kun er relevant for DPMtF-WebUI (f.eks. governance-værktøjer,
prompt compiler, validation automation):

- Marker i alignment matrix med "✅" kun for DPMtF-WebUI
- Sæt "—" for andre projekter
- Tilføj note om hvorfor

### Regel 4: Nye projekter

Når et nyt projekt tilføjes under DPMtF governance:

1. Tilføj projektet til Projekt-registre nedenfor
2. Initialiser governance templates via `scripts/initialize_target_project_governance.py`
3. Tilføj en kolonne i Alignment Matrix
4. Evaluer eksisterende features for rollout til det nye projekt
5. **Opdatér projektets projekt-specifikke filer** (00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README) så de afspejler det nye projekts identitet — IKKE efterlad dem som Father-kopier

### Regel 5: Periodisk governance audit (OBLIGATORISK)

Ved hver superpowers-session (når bruger refererer til `superpowers.md`):

1. **Auditér ALLE Child projects' projekt-specifikke filer** mod audit-checklisten i superpowers.md Sektion 1.
2. **Opdatér alignment-status tabellen** nedenfor med fund.
3. **Ved discrepancy:** Trigger GATE-GOVERNANCE-SYNC (se [[gates]]).
4. **Efter godkendt opdatering:** Dokumentér i Child's CHANGELOG og NEXT_CONTEXT, og opdatér denne fil's alignment-status.

Denne regel sikrer at ingen Child projects kører med stale governance-filer der viser forkert projektnavn, port, fase, eller historik — som ENO gjorde før ENO-5 (00_PROJECT sagde "AI PC Resource WebUI v3", 02_SCOPE viste fase 3C-3).

---

## 3. Projekt-registre

| Projekt | Port | Sti | Governance | Beskrivelse |
|---|---|---|---|---|
| **DPMtF-WebUI** | 9130 | `/home/svend/DPMtF-WebUI` | Master i `docs/governance-templates/` | Father project — governance engine, prompt compiler, validation |
| **ENO** | 9131 | `/home/svend/ENO` | Kopi i `docs/dpmtf/` | Evaluate Next Optimization — første søn-projekt |
| **ai-pc-resource-webui-v3** | 9123 | `/home/svend/ai-pc-resource-webui-v3` | Kopi i `docs/dpmtf/` | Reference-projekt til test af DPMtF prompt compiler |

---

## 4. Alignment-status

Nuværende alignment mellem projekter:

| Alignment-område | DPMtF-WebUI ↔ ENO | DPMtF-WebUI ↔ v3 | Note |
|---|---|---|---|
| Governance templates (strukturelle) | ✅ Synkroniseret (13/13) | ✅ Synkroniseret (13/13) | 01, 03-09, 13-17. Synkroniseret via initialize_target_project_governance.py. Father's master er autoritativ. |
| Governance docs (projekt-specifikke) | ✅ ENO-5 completed 2026-06-13 | ✅ v3 fully aligned 2026-06-13 (Prompts #1, #4) | 00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README. ENO: opdateret til egen identitet. v3: alle 6 filer afspejler nu v3's egen identitet — 02_SCOPE (3C-14), 00_PROJECT (HEAD+status), README (v3-specifik). CHANGELOG, NEXT_CONTEXT, IMPLEMENTATION_REPORT var allerede korrekte. |
| Sprog/language | ✅ Synkroniseret | ✅ Synkroniseret | ENO: e867ad8 — user_language tabel + /api/user-language endpoints + dropdown |
| i18n 4-lags arkitektur | ✅ Synkroniseret | ✅ Synkroniseret | DPMtF-WebUI API rettet 2026-06-13 til fuld 4-lags traversering (slot→label→translation). ENO havde allerede korrekt flow. Begge returnerer nu {slot_key: text}. |
| Database struktur | ✅ Synkroniseret | — | ENO: 05f9b0d — fuld merge af DPMtF-WebUI tabeller + egne domæne-tabeller |
| Panelgrupper | ✅ Synkroniseret | ✅ Udrullet 2026-06-13 (Prompt #3) | ENO: 4 commits (dfaa96c→320a7a6). v3: 1ffd4a1 — panel-group containers, collapse/expand, user_panel_groups tabel, i18n labels. Udført af lokal model (qwen36-27b-q4km), first-try success. |
| CSS theme | ✅ Synkroniseret | — | Begge bruger dark theme (GitHub-dark) — allerede aligned |
| Frontend features | ✅ Afklaret | — | ENO har domæne-specifikke paneler. v3 har resource/pipeline paneler |
| Governance-infrastruktur (2H-2O) | ⏳ Under udbygning (2H-2N ✅, 2O ⏳) | — | DPMtF-WebUI only — 2H-2N completed og committed. 2O (parallel-kørsel test cloud vs lokal) er sidste manglende fase i Blok 6 |
| | | | |

---

## 5. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — initial alignment matrix, projekt-registre, rollout regler |
| 2026-06-13 | Opdateret alignment matrix: ENO sprog/i18n/database/panelgrupper rettet fra ⏳ til ✅ (allerede committed). Tilføjet DPMtF-WebUI 2H-2O roadmap som DPMtF-WebUI-only. Alignment-status sektion opdateret med commit-referencer. GATE-FEATURE-ROLLOUT: 2H-2O er DPMtF-WebUI-only governance-infrastruktur — udrulles ikke til ENO eller v3. |
| 2026-06-13 | 2H markeret som ✅ — Prompt Template Manager redesign implementeret. 6 templates med complexity tiers, capture sources, per-model hitrate tracking, og obligatoriske outcome-felter. Baseret på Excel-dataanalyse af 8 prompt-runs fra claude_ollama_prompt_history.xlsx. |
| 2026-06-13 | i18n 4-lags arkitektur alignment gennemført. DPMtF-WebUI's `get_ui_labels_for_domain()` omskrevet til at traversere alle 4 lag (slot→slot_label→label→translation) og returnere `{slot_key: text}` — samme flow som ENO. 108 slots, 108 mappings, 108 labels, 216 translations. Panel-gruppe labels (pg_daily, pg_journals, pg_reports, pg_periodic, pg_setup) tilføjet. 05_CODING_STANDARD.md og superpowers.md opdateret med 4-lags arkitektur som obligatorisk standard. |
| 2026-06-13 | Alignment matrix opdateret: 2I-2N rettet fra ⏳ til ✅ — alle var allerede committed (2I: 5d389b8→fdea70e, 2J: 5b4a44b→1a9d6ba, 2K: 7d78926→85498f1, 2L: 7cbc34e→a951d20, 2M: 9bf352f→379b169, 2N: 700a513→cb074f5). 2O forbliver ⏳ som sidste fase i Blok 6. Alignment-status sektion opdateret. |
| 2026-06-13 | Tilføjet **Regel 5: Periodisk governance audit** — obligatorisk ved hver superpowers-session. Audit-checkliste for Child projects' projekt-specifikke filer. Alignment-status sektion opdateret: "Governance templates" splittet i "Governance templates (strukturelle)" og "Governance docs (projekt-specifikke)" med separat tracking. v3 markeret ⚠️ — skal auditeres for samme stale-docs problem som ENO havde. |
| 2026-06-13 | **ENO-6 Prompt #1 gennemført:** v3's 02_SCOPE.md (fase 3C-3→3C-14) og 00_PROJECT.md (Current Commit+Status) opdateret af lokal Ollama model (qwen36-27b-q4km). First-try success — alle 8 review-checks passeret, 0 manuelle rettelser, kun 2 tilladte filer modificeret. Prompt clarity: Tydelig. v3's governance docs status: ⚠️→✅. |
| 2026-06-13 | **ENO-6 Prompt #2 gennemført:** lbl() helper tilføjet til v3, alle 19 labelMap["key"]||fallback migreret til lbl(key, fallback). First-try success, 0 rettelser, JS syntaks OK. |
| 2026-06-13 | **ENO-6 Prompt #3 gennemført:** Panel groups udrullet til v3 — user_panel_groups migration, GET/POST endpoints, panel-group containers (daily, reports), collapse/expand CSS+JS, pg_daily/pg_reports i18n labels. First-try success, 5 filer, 6 delopgaver. Panelgrupper alignment: ⏳→✅. Kapabilitets-baseline for qwen36-27b-q4km komplet: medium-lav ✅, medium ✅, medium-høj ✅. |
| 2026-06-13 | **ENO-6 Prompt #4 gennemført:** v3 README.md gjort v3-specifik — titel, port 9123, reference-projekt status, v3-Specific Notes sektion, Governance Sync sektion. First-try success. v3 alignment komplet: alle 6 projekt-specifikke filer afspejler nu v3's egen identitet. |
