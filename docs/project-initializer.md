# Project Initializer — Governance First

## Formål

Når et nyt target-projekt skal sættes op med DPMtF-governance, kopieres
standard governance-templates fra:

```
docs/governance-templates/
```

ind i target-projektet som:

```
<target-project>/docs/dpmtf/
```

Dette sikrer at hvert projekt starter med et fælles governance-basis.

## Script

```
scripts/initialize_target_project_governance.py <target-path> [--dry-run] [--overwrite]
```

### Argumenter

| Argument      | Beskrivelse                                                        |
|---------------|--------------------------------------------------------------------|
| `target-path` | Absolut sti til target-projektet (påkrævet).                       |
| `--dry-run`   | Vis hvad der ville ske — skriv ingen filer.                        |
| `--overwrite` | Overskriv eksisterende filer; lav backup først i `backups/<ts>/`.   |

### Sti-validering

Target-stien skal:

- Være absolut.
- Finde som en eksisterende mappe.
- **Ikke** være `/`, `/home/svend` eller `/mnt`.
- Finde inden for tilladte rødder:
  - `/home/svend/`
  - `/mnt/projectarchive/`

### Adfærd

1. Skab `<target>/docs/dpmtf/` hvis den ikke findes.
2. Kopiér alle filer fra `docs/governance-templates/` til destinationen.
3. Hvis en destinationsfil allerede eksisterer:
   - **Uden** `--overwrite`: spring over (udskriv `SKIPPED_EXISTING`).
   - **Med** `--overwrite`: lav backup til `backups/<YYYYMMDDTHHMMSS>/`
     og overskriv derefter.

### Eksempel — dry-run

```bash
python3 scripts/initialize_target_project_governance.py \
  /home/svend/ai-pc-resource-webui-v2 --dry-run
```

Dette viser hvad der ville kopieres uden at skrive nogen filer.

### Eksempel — kørsel med overwrite

```bash
python3 scripts/initialize_target_project_governance.py \
  /home/svend/noget-projekt --overwrite
```

## Verifikation

Før commit bør følgende køres:

```bash
python3 -m py_compile scripts/initialize_target_project_governance.py
python3 scripts/initialize_target_project_governance.py --help
python3 scripts/initialize_target_project_governance.py /home/svend/ai-pc-resource-webui-v2 --dry-run
```
