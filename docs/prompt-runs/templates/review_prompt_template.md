# DPMtF Review-Prompt Skabelon

## Project Path
/fulde/sti/til/projektet

## Operation Type / Change Intent
Validation / Review

## Review Mode
second-pass same-model

## Goal
Gennemgå en tidligere prompt-run — verificer at scope-contract overholdes, acceptanskriterier er opfyldt og verifikation er komplet.

## Inputs to Review
Hvad der skal gennemgås:
- `docs/prompt-runs/000000_2D-X/prompt.md` — Original prompt
- `docs/prompt-runs/000000_2D-X/implementation_report.md` — Implementeringsrapport
- Git-diff for ændrede filer
- Verifikations-output

## Scope Contract
Kopier scope-contract fra original prompt. Denne review tjekker om det er overholdt.

## Allowed Read-Only Files/Resources
Filer der må læses som en del af gennemgangen:
- `docs/prompt-runs/000000_2D-X/*`
- Git-diff af ændrede filer
- Relevant kildekode read-only

## Forbidden Modifications
Ingen filer må modificeres under review. Review er read-only.

## Review Tasks
Gennemgang-opgaver:
1. Tjek om changed files matcher expected changed files
2. Verificer at unchanged files ikke er ændret
3. Evaluer acceptance criteria resultater
4. Tjek om verifikationskommandoer er kørt og vellykkede
5. Identificer scope-violationer
6. Vurder risk level
7. Give verdict

## Verdict Rules
- `pass` — Alle kriterier opfyldt, ingen scope-violationer, komplet verifikation
- `pass_with_notes` — Kriterier opfyldt men med mindre bemærkninger; ingen blockerende problemer
- `fail_requires_fix` — Scope-violationer, manglende verifikation, eller acceptanskriterier ikke opfyldt

## Review Report Requirements
- Brug `review_report_template.md` som skabelon
- Udfyld alle sektioner
- Dokumentér fund med fil-referencer og linjenumre
- Hvis verdict er `fail_requires_fix`, inkluder en recommended fix prompt

## Stop Condition
Når gennemgangen er fuldført, rapporten er skrevet og verdict er afgivet. Print `REVIEW_DONE_OK` og stop.

## Commit Policy
Do not commit. Review er read-only — ingen filer ændres.
