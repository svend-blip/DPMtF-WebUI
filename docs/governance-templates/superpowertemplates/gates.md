# Gates

> **Gate-spørgsmål der SKAL stilles før kritiske operationer.**
> Loades når en gate-trigger rammes.
> Refereret fra [[superpowers]].

---

## 1. Definerede Gates

### GATE-V3: Reference-projekt beskyttelse

```
TRIGGER: Brugeren beder om ændringer i ai-pc-resource-webui-v3
         OG ændringen er IKKE en governance-template synkronisering.

SPØRGSMÅL: "ai-pc-resource-webui-v3 is our current reference project
for testing the DPMtF prompt compiler. Are you sure you want to modify it?"

KONSEKVENS:
  - Bruger siger JA  → fortsæt med ændringen, dokumenter i alignmentstructure.md
  - Bruger siger NEJ → stop, afklar hvad der skal ske i stedet
```

### GATE-SCOPE: Scope-overskridelse

```
TRIGGER: En ændring falder uden for nuværende fase-scope
         defineret i 02_SCOPE.md.

SPØRGSMÅL: "This change exceeds the current phase scope defined in
02_SCOPE.md. Should we update the scope first?"

KONSEKVENS:
  - Bruger siger JA  → opdater 02_SCOPE.md + 09_DECISIONS.md først, fortsæt derefter
  - Bruger siger NEJ → stop ændringen, hold inden for scope
```

### GATE-MODEL: Billigere model-valg

```
TRIGGER: En opgave vurderes som mekanisk/triviel
         (1-2 filer, veldefineret spec, ingen design-beslutninger)
         OG deepseek-v4-flash:cloud kan løse den.

SPØRGSMÅL: "This task could be done by a cheaper model.
Proposed: deepseek-v4-flash:cloud. Switch?"

KONSEKVENS:
  - Bruger siger JA  → skift model for denne opgave
  - Bruger siger NEJ → fortsæt med nuværende model (deepseek-v4-pro:cloud)
```

### GATE-FEATURE-ROLLOUT: Feature-udrulning

```
TRIGGER: En feature implementeres i DPMtF-WebUI
         OG brugeren har IKKE specificeret om den skal udrulles til andre projekter.

SPØRGSMÅL: "Should this feature also be implemented in ENO?"

KONSEKVENS:
  - Bruger siger JA  → tilføj til alignment matrix i alignmentstructure.md,
                       implementer i ENO efter DPMtF-WebUI er færdig
  - Bruger siger NEJ → marker som DPMtF-WebUI only i alignmentstructure.md
```

### GATE-GOVERNANCE-SYNC: Governance template synkronisering

Denne gate har **to triggere** — strukturel divergens og projekt-specifik staleness.

#### Trigger A: Strukturel divergens

```
TRIGGER: Strukturelle governance templates (01, 03-09, 13-17) i et søn-projekt
         (ENO, v3) er divergeret fra DPMtF-WebUI's master-kopier.

SPØRGSMÅL: "Structural governance templates in [projekt] have diverged from
DPMtF-WebUI master. Is this divergence intentional, or should they be synchronized?"

KONSEKVENS:
  - Bruger siger BEVIDST → dokumenter i alignmentstructure.md at divergensen er
                           intentional, opdater ikke templates
  - Bruger siger SYNC  → overskriv sønnens strukturelle templates med DPMtF-WebUI's
                         master via initialize_target_project_governance.py,
                         dokumenter i alignmentstructure.md
```

#### Trigger B: Projekt-specifik staleness

```
TRIGGER: Et Child projects projekt-specifikke filer (00_PROJECT, 02_SCOPE,
         10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README)
         er stadig Father-kopier og afspejler IKKE projektets egen identitet.
         Eksempler: 00_PROJECT siger forkert projektnavn/port, 02_SCOPE viser
         forkert fase, 10_CHANGELOG indeholder Father's historik.

SPØRGSMÅL: "Governance templates in [projekt] have diverged from DPMtF-WebUI
master — but in the wrong direction. [Projekt]'s project-specific files
(00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT,
README) are still DPMtF-WebUI copies and don't reflect [projekt]'s own identity,
port, or git history. Should these 6 files be updated to reflect [projekt]'s
actual project, phases, and history?"

KONSEKVENS:
  - Bruger siger JA → opdatér de 6 projekt-specifikke filer så de afspejler
                      projektets egen identitet og historik (følg
                      opdateringsprocessen i superpowers.md Sektion 1).
                      Strukturelle templates forbliver uændrede.
                      Dokumenter i alignmentstructure.md og projektets CHANGELOG.
  - Bruger siger NEJ → dokumenter i alignmentstructure.md at staleness er
                       accepteret (sjældent — normalt skal disse filer opdateres)
```

---

## 2. Gate-regler

### Præcision

- Alle gates skal stilles **PRÆCIST som defineret** — ikke parafraseret
- Brug den eksakte ordlyd fra denne fil
- Tilføj ikke ekstra kontekst eller meninger til gate-spørgsmålet

### Dokumentation

- Brugerens svar på en gate dokumenteres i:
  - `alignmentstructure.md` for GATE-V3, GATE-FEATURE-ROLLOUT, og GATE-GOVERNANCE-SYNC (begge triggere)
  - `09_DECISIONS.md` for GATE-SCOPE
  - `superpowers.md` decision tree for GATE-MODEL
  - Child projektets `10_CHANGELOG.md` og `11_NEXT_CONTEXT.md` for GATE-GOVERNANCE-SYNC Trigger B (projekt-specifik opdatering)

### Prioritet

Hvis flere gates trigger samtidigt, stil dem i denne rækkefølge:

1. GATE-SCOPE (scope skal afklares først)
2. GATE-V3 (projekt-beskyttelse)
3. GATE-MODEL (model-valg)
4. GATE-FEATURE-ROLLOUT (udrulning)
5. GATE-GOVERNANCE-SYNC Trigger A (strukturel template synkronisering)
6. GATE-GOVERNANCE-SYNC Trigger B (projekt-specifik staleness — auditeres ved hver superpowers-session)

### Nye gates

Nye gates kan tilføjes efter behov:
- Tilføj en ny sektion i denne fil med TRIGGER, SPØRGSMÅL, KONSEKVENS
- Opdater `superpowers.md`'s workflow-sektion med den nye gate
- Dokumenter tilføjelsen i opdateringsloggen nedenfor

---

## 3. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — GATE-V3, GATE-SCOPE, GATE-MODEL, GATE-FEATURE-ROLLOUT |
| 2026-06-13 | Tilføjet GATE-GOVERNANCE-SYNC — governance template divergens spørgsmål |
| 2026-06-13 | GATE-GOVERNANCE-SYNC udvidet med **Trigger B: Projekt-specifik staleness** — dækker situationen hvor Child projects' 00_PROJECT, 02_SCOPE, 10_CHANGELOG, 11_NEXT_CONTEXT, 12_IMPLEMENTATION_REPORT, README er stale Father-kopier. Trigger A (strukturel divergens) og Trigger B (projekt-specifik staleness) har separate spørgsmål og konsekvenser. Dokumentation udvidet: Child's CHANGELOG og NEXT_CONTEXT nævnt som dokumentationsmål for Trigger B. Gate-prioritet opdateret. Baseret på ENO-5 governance update. |
