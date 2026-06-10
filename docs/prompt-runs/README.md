# DPMtF Prompt-Run History

## Formål

Denne mappe indeholder struktureret historik over alle Claude Code prompt-kørsler (prompt-runs) for DPMtF-projektet. Hver kørsel dokumenteres med prompt, implementeringsrapport, gennemgang og verifikation — så fremtidige sessioner kan genfinde præcis hvad der besluttes, ændres og verificeres uden at stole på lange terminal copy/paste.

## Beslutning: Git-sporede rapportfil

Rapportfiler er normale git-sporede filer i dette repo. De udgør primær historik for projektets udvikling.

## Beslutning: Ingen tar-arkiver i normal workflow

Tar-arkiver er ikke en del af normal workflow. Alle rapporter ligger som almindelige Markdown/JSON-filer og spores via git.

## Mappe-naming-konvention

Hver prompt-run får sit eget nummererede undermappe:

```
docs/prompt-runs/000001_2D-D_pipeline_status_requirements/
docs/prompt-runs/000002_2D-G_example/
```

Format: `<SEQ>_<PHASE_KEY>_kort-beskrivelse/`

- `SEQ`: 6-cifret sekvensnummer (000001, 000002, …)
- `PHASE_KEY`: Fase-nøgle f.eks. `2D-D`, `2D-G` osv.

## prompt_run_id-konvention

Hver prompt-run får et unikt ID:

```
PRUN-000001
PRUN-000002
```

Format: `PRUN-<SEQ>` hvor `<SEQ>` er 6-cifret sekvensnummer.

## Obligatoriske filer pr. prompt-run mappe

Hver prompt-run mappe skal indeholde:

| Fil | Beskrivelse |
|-----|-------------|
| `prompt.md` | Den fulde prompt brugt i implementerings-kørslen |
| `implementation_report.md` | Rapport genereret efter implementering |
| `review_prompt.md` | Prompt til anden-gennemgang (second-pass review) |
| `review_report.md` | Rapport fra gennemgangen |
| `verification_commands.md` | Verifikationskommandoer og resultater |
| `metadata.json` | Struktureret metadata i JSON-format |

## Second-Pass Gennemgang

En second-pass review er en gennemning udført af samme model efter en `/clear`-kommando:

- Samme model efter `/clear` kan udføre nyttig second-pass review
- Den er **ikke** fuldt uafhængig — modellen har potentiel kontekst fra tidligere i sessionen via cache og hukommelse
- Second-pass review fanger stadig scope-violationer, manglende verifikation og logiske inkonsekvenser
- Gennemgang-vurderinger (verdict values):
  - `pass` — Alt godkendt, ingen ændringer nødvendige
  - `pass_with_notes` — Godkendt med bemærkninger; ingen blockerende problemer
  - `fail_requires_fix` — Nødvendige rettelser før merge

## Eksekverings-tilstande (Execution Modes)

### Conservative Mode

- Standard tilstand for de fleste ændringer
- Fokus på minimal risiko og graduel fremgang
- Rapporter skrives altid fuldt ud
- Verifikation udføres før færdigmelding

### Aggressive Mode

- Kræver strengere scope-definition
- Kræver et klart rollback-point før start
- Tillader bredere ændringer inden for defineret scope
- Manglende rollback-point = mode skal ikke bruges

## Skabeloner

Se `templates/` mappen for:

- `prompt_template.md` — Reusable implementerings-prompt-skabelon
- `review_prompt_template.md` — Reusable review-prompt-skabelon
- `implementation_report_template.md` — Implementeringsrapport-skabelon
- `review_report_template.md` — Gennemgangsrapport-skabelon
- `metadata_template.json` — JSON-metadataskabelon
