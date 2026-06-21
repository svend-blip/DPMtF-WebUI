# Convention Auto-Fill Condition — Design

## Problem

`_autoFillFromConvention` i `static/js/dpmtf-app.js` (linje 2418–2431) udfylder unconditionally alle 3 felter (Deliverable Directory, Deliverable Pattern, Error Message) når Convention Rule ændres — også ved **redigering af eksisterende steps**. Brugeren ønsker at auto-fill kun skal ske når man vælger en Convention Rule for første gang på et **nyt** step.

## Løsning: Flag-baseret (Tilgang A)

Tilføj et boolean-flag `isNewStep` som sættes baseret på om `_bridgeEditingStepId` er null (nyt) eller sat (edit). Gør auto-fill betinget af dette flag.

### Ændringer i `static/js/dpmtf-app.js`

1. I `buildBridgeStepForm()`, tilføj efter form-div oprettes:
   ```js
   var isNewStep = !_bridgeEditingStepId;
   ```

2. Tilføj flag til meta-objektet som overføres til `_autoFillFromConvention`:
   ```js
   rkSelect.onchange = function () {
     _autoFillFromConvention(this.value, form, meta.available_conventions, isNewStep);
   };
   ```

3. I `_autoFillFromConvention`, tilføj parameter og ekstra betingelse:
   ```js
   function _autoFillFromConvention(ruleKey, form, conventions, isNewStep) {
     if (!ruleKey || !conventions || !isNewStep) return;
     // ... resten uændret
   }
   ```

## Kriterier for succes

- Når man opretter et **nyt** step og vælger en Convention Rule → felterne auto-fyldes som før
- Når man **redigerer** et eksisterende step og skifter Convention Rule → ingen auto-fill, brugerens værdier beholdes
- Ingen andre ændringer i koden

## Filændringer

| Fil | Ændring |
|-----|---------|
| `static/js/dpmtf-app.js` | +6 linjer (isNewStep flag + overførsel + betingelse) |
