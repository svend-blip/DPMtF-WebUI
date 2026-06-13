# Tmux Bridge Protocol

> **Cloud-til-lokal Claude Code kommunikation via tmux.**
> Loades når cloud model skal sende instruktioner til lokal Ollama model.
> Refereret fra [[superpowers]] og [[localmodel]].

---

## 1. Infrastruktur

| Komponent | Placering | Formål |
|---|---|---|
| `start_review_claude.sh` | `/home/svend/start_review_claude.sh` | Starter lokal Claude Code i tmux session |
| `claude-bridge/` | `/home/svend/claude-bridge/` | Handoff-filer mellem cloud og lokal |
| `clear.md` | `/home/svend/claude-bridge/clear.md` | Indeholder `/clear` kommando til session-reset |
| tmux session | `review_claude` | Persistent tmux session med lokal Claude Code |

---

## 2. Workflow

```
CLOUD MODEL (denne session)                    LOKAL MODEL (review_claude tmux)
─────────────────────────────────────────      ──────────────────────────────────
1. Skriv handoff fil til claude-bridge/
   ├─ /home/svend/claude-bridge/handoff.md
   └─ Indeholder: prompt + instruktioner

2. Send /clear til lokal session
   └─ tmux send-keys -t review_claude
      "$(cat /home/svend/claude-bridge/clear.md)" Enter

3. Inject handoff instruktion
   └─ tmux send-keys -t review_claude
      "Read and execute /home/svend/claude-bridge/handoff.md" Enter
                                              4. Lokal model læser handoff.md
                                              5. Eksekverer prompt (COMMITTER IKKE)
                                              6. Skriver resultat til claude-bridge/
                                                 └─ /home/svend/claude-bridge/result.md

7. Læs resultat
   └─ cat /home/svend/claude-bridge/result.md

8. Review diff i target-projektet
   └─ git -C <project> diff

9. Commit / Rollback (Svend godkender)
```

---

## 3. Kommando-reference

### Start lokal session (hvis ikke kørende)

```bash
/home/svend/start_review_claude.sh
```

### Tjek om session kører

```bash
tmux ls | grep review_claude
```

### Send /clear til lokal session

```bash
tmux send-keys -t review_claude "$(cat /home/svend/claude-bridge/clear.md)" Enter
```

### Send handoff instruktion

```bash
tmux send-keys -t review_claude "Read and execute the instructions in /home/svend/claude-bridge/handoff.md" Enter
```

### Tilslut manuelt (for inspektion)

```bash
tmux attach -t review_claude
```

### Detach fra session

```
Ctrl+b, d
```

---

## 4. Handoff fil-format

### handoff.md (cloud → lokal)

```markdown
<role>Du er Implementer i DPMtF governance rollen.</role>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md
...

Nøgleregler der SKAL overholdes:
- ...
</governance>

<task>
...
</task>

<scope>
Filer du MÅ modificere:
- ...
Filer du IKKE må røre:
- ...
</scope>

<validation>
...
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Skriv en resultat-fil til /home/svend/claude-bridge/result.md med:
- Hvilke filer du modificerede
- Hvilke validerings-checks du kørte og deres resultater
- En kort opsummering af hvad du gjorde
</constraint>
```

### result.md (lokal → cloud)

```markdown
# Resultat: [Prompt navn]

## Filer modificeret
- [fil1]
- [fil2]

## Validerings-resultater
| Check | Resultat |
|---|---|
| [check1] | PASS/FAIL |
| [check2] | PASS/FAIL |

## Opsummering
[Kort beskrivelse af hvad der blev gjort]

## Status
✅ Alle valideringer bestået. Ikke committet per instruks. Diff klar til review.
```

---

## 5. Sikkerheds-regler

1. **Lokal model COMMITTER ALDRIG** — constraint er altid med i handoff.
2. **Cloud model reviewer ALTID** før commit — ingen automatisk commit.
3. **Svend godkender ALTID commit** — Human Approval Gate før git commit.
4. **Rollback altid mulig** — `git reset --hard <baseline>` hvis resultat afvises.
5. **/clear mellem hver prompt** — sendes via `clear.md` for at nulstille lokal models kontekst.

---

## 6. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — tmux bridge infrastruktur, handoff protokol, kommando-reference. Baseret på ENO-6 Fase 1 erfaring (4 manuelle prompts → automatiseret via tmux). |
