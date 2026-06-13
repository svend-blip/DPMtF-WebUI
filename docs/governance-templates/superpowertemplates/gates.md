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

---

## 2. Gate-regler

### Præcision

- Alle gates skal stilles **PRÆCIST som defineret** — ikke parafraseret
- Brug den eksakte ordlyd fra denne fil
- Tilføj ikke ekstra kontekst eller meninger til gate-spørgsmålet

### Dokumentation

- Brugerens svar på en gate dokumenteres i:
  - `alignmentstructure.md` for GATE-V3 og GATE-FEATURE-ROLLOUT
  - `09_DECISIONS.md` for GATE-SCOPE
  - `superpowers.md` decision tree for GATE-MODEL

### Prioritet

Hvis flere gates trigger samtidigt, stil dem i denne rækkefølge:

1. GATE-SCOPE (scope skal afklares først)
2. GATE-V3 (projekt-beskyttelse)
3. GATE-MODEL (model-valg)
4. GATE-FEATURE-ROLLOUT (udrulning)

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
