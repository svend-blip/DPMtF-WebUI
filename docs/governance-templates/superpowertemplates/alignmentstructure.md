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
| i18n database schema alignment | ✅ | ✅ | — | 2026-06-13 | ENO: 9073de2. v3 har allerede standard |
| Database merge (DPMtF governance tables) | ✅ | ✅ | — | 2026-06-13 | ENO: 05f9b0d. v3 har eget schema |
| Prompt Template Manager (2H) | ✅ | — | — | 2026-06-13 | DPMtF-WebUI only — redesigned based on Excel data analysis of 8 prompt runs. 6 templates, complexity tiers, per-model hitrate tracking, mandatory outcome fields. |
| Local Prompt Compiler (2I) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
| Validation Automation (2J) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
| Git Sync Management (2K) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
| Platform Adapter Framework (2L) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
| Local Claude Code Session Manager (2M) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
| Prompt→Implementer→Validator loop (2N) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
| Parallel-kørsel test cloud vs lokal (2O) | ⏳ | — | — | 2026-06-13 | DPMtF-WebUI only — governance-infrastruktur |
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
| Governance templates | ✅ Synkroniseret (strukturelle) | Synkroniseret 2026-06-12 | 14/19 identiske. 5 ENO-specifikke (CHANGELOG, NEXT_CONTEXT, IMPLEMENTATION_REPORT, README) — bevidst divergens |
| Sprog/language | ✅ Synkroniseret | ✅ Synkroniseret | ENO: e867ad8 — user_language tabel + /api/user-language endpoints + dropdown |
| i18n database schema | ✅ Synkroniseret | ✅ Synkroniseret | ENO: 9073de2 — aligned til DPMtF standard |
| Database struktur | ✅ Synkroniseret | — | ENO: 05f9b0d — fuld merge af DPMtF-WebUI tabeller + egne domæne-tabeller |
| Panelgrupper | ✅ Synkroniseret | ⏳ Afventer udrulning | ENO: 4 commits (dfaa96c→320a7a6). v3 udrulles senere |
| CSS theme | ✅ Synkroniseret | — | Begge bruger dark theme (GitHub-dark) — allerede aligned |
| Frontend features | ✅ Afklaret | — | ENO har domæne-specifikke paneler. v3 har resource/pipeline paneler |
| Governance-infrastruktur (2H-2O) | ⏳ Under udbygning (2H ✅) | — | DPMtF-WebUI only — 2H completed (prompt templates redesigned). 2I-2O pending: compiler, validation, git sync, platform adapter, session manager, prompt loop, parallel test |
| | | | |

---

## 5. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — initial alignment matrix, projekt-registre, rollout regler |
| 2026-06-13 | Opdateret alignment matrix: ENO sprog/i18n/database/panelgrupper rettet fra ⏳ til ✅ (allerede committed). Tilføjet DPMtF-WebUI 2H-2O roadmap som DPMtF-WebUI-only. Alignment-status sektion opdateret med commit-referencer. GATE-FEATURE-ROLLOUT: 2H-2O er DPMtF-WebUI-only governance-infrastruktur — udrulles ikke til ENO eller v3. |
| 2026-06-13 | 2H markeret som ✅ — Prompt Template Manager redesign implementeret. 6 templates med complexity tiers, capture sources, per-model hitrate tracking, og obligatoriske outcome-felter. Baseret på Excel-dataanalyse af 8 prompt-runs fra claude_ollama_prompt_history.xlsx. |
