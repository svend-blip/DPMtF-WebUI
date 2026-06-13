# Prompt #1 Review Checklist

Bruges efter lokal model har eksekveret Prompt #1 (uden commit).

## Pre-review: Git diff

```bash
git -C /home/svend/ai-pc-resource-webui-v3 diff
git -C /home/svend/ai-pc-resource-webui-v3 diff --stat
```

## Review-punkter

| # | Check | Metode | Forventet |
|---|-------|--------|-----------|
| 1 | **Scope: Kun tilladte filer?** | `git diff --stat` viser kun `docs/dpmtf/02_SCOPE.md` og `docs/dpmtf/00_PROJECT.md` | Kun 2 filer |
| 2 | **02_SCOPE.md: Fase opdateret?** | Læs Phase linjen | Viser "3C-14" eller nyere — IKKE "3C-3" |
| 3 | **02_SCOPE.md: In/Out Scope opdateret?** | Læs sektionerne | Afspejler faktisk nuværende fase |
| 4 | **02_SCOPE.md: Scope Change Log tilføjet?** | Læs log-tabellen | Ny entry med dato 2026-06-13 |
| 5 | **00_PROJECT.md: Current Commit opdateret?** | Sammenlign med `git log --oneline -1` | Matcher faktisk HEAD |
| 6 | **00_PROJECT.md: Current Status opdateret?** | Læs linjen | Afspejler faktisk tilstand (ikke "Initial skeleton") |
| 7 | **00_PROJECT.md: Andre felter bevaret?** | Sammenlign Project Name, Purpose, Port, Repository, Runtime Command, Related Projects | Uændrede |
| 8 | **Markdown-syntaks OK?** | Visuel inspektion | Ingen broken tables, headings, eller fence blocks |

## Verdict

- **ACCEPT:** Alle 8 checks passer → klar til commit
- **DELVIST ACCEPT:** 1-2 checks fejler → notér fixes, ret manuelt, commit
- **AFVIS:** 3+ checks fejler eller scope-overtrædelse → `git reset --hard <baseline>`

## Evaluerings-noter

Efter review, notér her:

| Kriterie | Vurdering |
|---|---|
| Governance compliance | Ja / Delvist / Nej |
| Scope compliance | Ja / Nej |
| Validation compliance | Ja / Delvist / Nej |
| First-try success | Ja / Nej / Antal rettelser |
| Task completion | Completed / Partial / Failed |
| Prompt clarity | Tydelig / Mindre uklar / Mangelfuld |

**Fund og bemærkninger:**
(udfyldes efter review)

**Governance-forbedringsforslag:**
(udfyldes efter review)
