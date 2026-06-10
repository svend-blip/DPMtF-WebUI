# DPMtF Implementerings-Prompt Skabelon

## Project Path
/fulde/sti/til/projektet

## Operation Type / Change Intent
Create / Add / Modify / Delete / Review

Uddyb hvad ændringen gør og hvorfor.

## Execution Mode
conservative / aggressive

## Goal
Hvad skal denne prompt-run opnå — konkret, målbart, afgrænset.

## Scope Contract
Klar definition af hvad der må og ikke må røres.

## Allowed Files/Resources
Filer og ressourcer som er tilladt at oprette eller redigere:
- `tilladt_fil1`
- `tilladt_fil2`

## Forbidden Files/Resources
Filer og ressourcer som IKKE må ændres:
- `forbudt_fil1`
- `forbudt_fil2`

## Expected Changed Files
Liste over filer der forventes at blive ændret eller oprettet:
- `fil1`
- `fil2`

## Expected Unchanged Files
Filer som skal være uændrede efter kørslen — verifikation påkrævet:
- `forbudt_fil1`
- `forbudt_fil2`

## Allowed Operations
Tilladte operationer:
- Oprette mapper under tilladt sti
- Skrive Markdown-filer
- Køre read-only verifikation

## Forbidden Operations
Forbudne operationer:
- Database-skrivninger
- Backend-ændringer uden for scope
- Git-commit
- Installer dependencies

## Implementation Requirements
Specifikke krav til implementeringen:
- Krav 1
- Krav 2

## Acceptance Criteria
Målbare kriterier der definerer succes:
- [ ] Kriterie 1
- [ ] Kriterie 2

## Verification
Hvordan verifikation udføres:
- Kommando 1
- Kommando 2

## Report Writing Requirements
Krav til rapport-skrivning efter implementeringen:
- Brug `implementation_report_template.md` som skabelon
- Udfyld alle sektioner
- Inkluder verifikations-output

## Stop Condition
Når alt er implementeret, verificeret og rapporten er skrevet. Print `DPMTF_PHASE_DONE_OK` og stop.

## Commit Policy
Do not commit. Vent på eksplicit instruks før git commit.
