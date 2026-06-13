# Alignment Structure

> **Feature-alignment på tværs af DPMtF-afledte projekter.**
> Loades når en feature implementeres eller udrulles.
> Refereret fra [[superpowers]].

---

## 1. Alignment Matrix

Tracker hvilke features der gælder for hvilke projekter.

| Feature | DPMtF-WebUI (9130) | ENO (9131) | ai-pc-resource-webui-v3 (9123) | Dato | Note |
|---|---|---|---|---|---|
| Sprog-tabel + dropdown | ✅ | ✅ | ✅ | 2026-06-12 | Fælles i18n-feature |
| "Vis fuldførte faser" filter default false | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only |
| GitHub fase-synkronisering | ✅ | — | — | 2026-06-12 | DPMtF-WebUI only |
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
| Governance templates | ⏳ Afventer første sync | Synkroniseret 2026-06-12 | 10 af 19 templates opgraderet fra v3 |
| Sprog/language | ✅ Synkroniseret | ✅ Synkroniseret | user_language tabel + dropdown i begge |
| Frontend-struktur | ⏳ Afventer | ⏳ Afventer | Forskellige formål — ikke alignment-krævende |
| | | | |

---

## 5. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — initial alignment matrix, projekt-registre, rollout regler |
