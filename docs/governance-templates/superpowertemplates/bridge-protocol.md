# Tmux Bridge Protocol — Python-drevet tovejskommunikation

> **Cloud-til-lokal OG lokal-til-cloud Claude Code kommunikation via tmux.**
> Loades når cloud model skal sende instruktioner til lokal Ollama model,
> eller når lokal model sender resultat/notifikation tilbage til cloud.
> Refereret fra [[superpowers]] og [[localmodel]].

---

## 1. Infrastruktur

| Komponent | Placering | Formål |
|---|---|---|
| `start_review_claude.sh` | `/home/svend/start_review_claude.sh` | Starter lokal Claude Code i tmux session `claude_implementer` |
| `claude-bridge/` | `/home/svend/claude-bridge/` | Handoff-filer mellem cloud og lokal |
| `bridge.py` | `/home/svend/claude-bridge/bridge.py` | **Kerne:** tmux injection med korrekt Enter key-argument via Python subprocess |
| `clear.md` | `/home/svend/claude-bridge/clear.md` | Indeholder `/clear` kommando til session-reset |
| `reviewtoimplementor/` | `/home/svend/claude-bridge/reviewtoimplementor/` | **Cloud → Lokal:** handoff-filer med unikt ID |
| `implementertoreview/` | `/home/svend/claude-bridge/implementertoreview/` | **Lokal → Cloud:** resultat + notification + callback-filer |
| `trace.log` | `/home/svend/claude-bridge/trace.log` | Append-only log over ALL bridge-aktivitet |
| tmux session (cloud) | `claude_review` | Cloud model (deepseek-v4-flash:cloud) — denne session |
| tmux session (lokal) | `claude_implementer` | Lokal Ollama model (qwen36-27b-q4km) |

### Mappestruktur

```
/home/svend/claude-bridge/
├── bridge.py                            # Python tmux-bridge
├── clear.md                             # /clear kommando
├── restart-handoff.md                   # Session restart info
├── trace.log                            # Append-only log
├── reviewtoimplementor/                 # Cloud → Lokal
│   ├── 001-handoff.md                   # Handoff #1
│   ├── 002-handoff.md                   # Handoff #2 (osv.)
│   └── current.md → 001-handoff.md      # Symlink til nuværende
├── implementertoreview/                 # Lokal → Cloud
│   ├── 001-result.md                    # Resultat #1
│   ├── 001-notification.md             # Notification #1
│   ├── 001-callback.md                 # Callback-prompt (hvad cloud skal gøre)
│   ├── current.md → 001-result.md      # Symlink til nuværende
│   └── notification-template.md         # Skabelon til notifications
```

---

## 2. Bridge.py kommando-reference

| Kommando | Fra | Til | Handling |
|---|---|---|---|
| `bridge.py send <ID>` | Cloud (claude_review) | Lokal (claude_implementer) | `/clear` + inject handoff-instruktion |
| `bridge.py complete <ID>` | Lokal (claude_implementer) | Cloud (claude_review) | Inject resultat-prompt i cloud-session |

### bridge.py send <ID>

```python
# Eksempel: Send handoff 002 til claude_implementer
python3 /home/svend/claude-bridge/bridge.py send 002
```

Gør:
1. Tjekker at `claude_implementer` session kører
2. Tjekker at handoff-fil findes (`reviewtoimplementor/002-handoff.md`)
3. Sender `/clear` til `claude_implementer` via tmux
4. Sender `"Read and execute ... 002-handoff.md"` + **Enter** til `claude_implementer`
5. Opdaterer `current.md` symlink
6. Logger i `trace.log`

### bridge.py complete <ID>

```python
# Eksempel: Signalér handoff 002 færdig — kaldes af lokal model
python3 /home/svend/claude-bridge/bridge.py complete 002
```

Gør:
1. Tjekker at `claude_review` session kører
2. Skriver `implementertoreview/{ID}-callback.md` (hvis den ikke findes)
3. Injecter prompt: `"Read and execute ... implementertoreview/{ID}-callback.md"` + **Enter**
   — PRÆCIS samme mønster som `bridge.py send`
4. Logger i `trace.log`
5. Opdaterer `implementertoreview/current.md` symlink

### bridge.py next-id

```bash
# Find næste ledige handoff-ID
python3 /home/svend/claude-bridge/bridge.py next-id
# → 3 (hvis 001 og 002 findes)
```

---

## 3. Tovejs-workflow

```
CLOUD (claude_review — denne session)              LOKAL (claude_implementer)
───────────────────────────────────────────        ──────────────────────────────────

1. TJEK at lokal session kører
   └─ bridge.py forudsætter at session findes

2. BESTEM næste handoff ID
   └─ python3 bridge.py next-id

3. SKRIV handoff.md til reviewtoimplementor/
   ├─ reviewtoimplementor/{ID}-handoff.md
   └─ <task> indeholder ALLE steps inkl. signal
      Sidste step: python3 bridge.py complete {ID}

4. SEND handoff med bridge.py:
   python3 /home/svend/claude-bridge/bridge.py send {ID}

   Dette gør:
   ├─ /clear til claude_implementer
   ├─ Inject "Read and execute ... reviewtoimplementor/{ID}-handoff.md"
   ├─ Logger C→L i trace.log
   └─ Returnér kontrol til cloud                       5. LOKAL MODEL læser handoff.md
                                                        6. Eksekverer opgave (COMMITTER IKKE)
                                                        7. Skriver resultat til:
                                                           └─ implementertoreview/{ID}-result.md
                                                        8. Skriver NOTIFICATION til:
                                                            └─ implementertoreview/{ID}-notification.md
                                                        9. KALDER bridge.py complete:
                                                            python3 /home/svend/claude-bridge/bridge.py complete {ID}
                                                            Dette gør:
                                                            ├─ Skriver implementertoreview/{ID}-callback.md
                                                            └─ Inject "Read and execute ...
                                                               implementertoreview/{ID}-callback.md"
                                                               + logger L→C i trace.log

10. MODTAGER prompt via tmux:
    "Read and execute /home/.../implementertoreview/{ID}-callback.md"

11. LÆSER callback.md — prompt om at læse resultatet
12. Læs notification og resultat
13. REVIEW diff (git -C <project> diff)
14. Commit / Rollback / Næste handoff (Svend godkender)
```

**Nøgleprincip:** Én session arbejder ad gangen. Ingen polling, ingen background monitors.
`bridge.py complete` injecter en prompt i `claude_review` — den prompt sætter cloud-modellen
i gang med at læse resultatet. Sekventielt og deterministisk.

---

## 4. Handoff fil-format

### reviewtoimplementor/{ID}-handoff.md (cloud → lokal)

**VIGTIGT:** Kommunikations-steps (resultat, notification, signal) skal være
**inde i `<task>`** — modellen hopper over en separat `<callback>` sektion.

```markdown
<role>Du er Implementer i DPMtF governance rollen.</role>

<handoff_id>{ID}</handoff_id>

<project>/home/svend/ai-pc-resource-webui-v3</project>

<governance>
Læs og anvend disse governance filer FØR du starter:
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md

Nøgleregler:
- CHANGELOG er append-only — tilføj nye entries i bunden
- Brug git log til at finde præcise commit hashes
</governance>

<task>
[Specifik opgavebeskrivelse]

Når opgaven er udført, udfør disse steps:

1. Skriv resultat-fil til /home/svend/claude-bridge/implementertoreview/{ID}-result.md
2. Skriv NOTIFICATION til /home/svend/claude-bridge/implementertoreview/{ID}-notification.md
3. SEND SIGNAL til claude_review (INGEN /clear først):
   python3 /home/svend/claude-bridge/bridge.py complete {ID}
</task>

<scope>
Filer du MÅ modificere:
- [sti1]
Filer du IKKE må røre:
- [sti2]
</scope>

<validation>
[Valideringschecks]
</validation>

<constraint>
COMMIT IKKE. Stop efter implementation.
Udfør ALLE steps i <task> — især step 3 (bridge.py complete).
</constraint>
```

### implementertoreview/{ID}-callback.md (lokal → cloud)

Valgfri fil. Hvis den findes, bruger `bridge.py complete` dens indhold som prompt
til `claude_review`. Hvis den ikke findes, genereres en standard-prompt.

```markdown
Handoff {ID} er færdig. Læs implementertoreview/{ID}-result.md
og implementertoreview/{ID}-notification.md for at se resultatet.
Review diff'en og fortsæt.
```

### implementertoreview/{ID}-notification.md (lokal → cloud)

```markdown
# Notification — Handoff {ID}
Status: completed | failed | partial
Summary: {Kort beskrivelse — max 2 linjer}
Result file: {ID}-result.md
Next action: {Review diff | Commit | Rerun | Acknowledge}
```

---

## 5. Hvorfor Python?

| Problem | Løsning i Python |
|---|---|
| Lokal model forstår ikke `Enter` som tmux-key-navn | `subprocess.run(["tmux", "send-keys", ..., "Enter"])` sender Enter som **separat argument** — tmux fortolker det korrekt som tastetryk, ikke som tekst |
| Lokal model skriver `echo` foran tmux-kommandoer | Modellen kalder `python3 bridge.py complete {ID}` — én simpel kommando, ingen tmux-logik |
| Lokal model ignorerer separat `<callback>` sektion | `bridge.py complete` injecter prompt direkte i claude_review — modellen skal kun kalde scriptet |
| Skal virke på tværs af Ollama modeller | Python subprocess er OS-niveau — uafhængigt af hvilken LLM der kører |
| Skal virke begge veje | `send` = cloud→lokal, `complete` = lokal→cloud — symmetrisk design |

---

## 6. Kommando-reference

### Send handoff til lokal model

```bash
python3 /home/svend/claude-bridge/bridge.py send 002
```

### Signalér færdig (kaldes af lokal model)

```bash
python3 /home/svend/claude-bridge/bridge.py complete 002
```

### Find næste ledige ID

```bash
python3 /home/svend/claude-bridge/bridge.py next-id
```

### Tjek sessioner

```bash
tmux ls
```

### Læs trace.log

```bash
cat /home/svend/claude-bridge/trace.log
```

### Tilslut manuelt

```bash
tmux attach -t claude_implementer
# Detach: Ctrl+b, d
```

---

## 7. Sikkerheds-regler

1. **Lokal model COMMITTER ALDRIG** — constraint er altid med i handoff.
2. **Cloud model reviewer ALTID** før commit — ingen automatisk commit.
3. **Svend godkender ALTID commit** — Human Approval Gate.
4. **Rollback altid mulig** — `git reset --hard <baseline>` hvis resultat afvises.
5. **/clear mellem hver prompt** — håndteres af `bridge.py send`.
6. **Handoff ID'er er unikke og sekventielle** — brug `bridge.py next-id`.
7. **trace.log er append-only** — redigér aldrig eksisterende entries.
8. **bridge.py complete kaldes UDEN /clear** — ellers overskrives prompten før cloud ser den.

---

## 8. Fejlhåndtering

### Scenario A: Notification udebliver efter 5+ min

```bash
# Tjek om lokal session stadig kører
tmux ls | grep claude_implementer

# Tjek om resultat alligevel blev skrevet
ls -la /home/svend/claude-bridge/implementertoreview/

# Hvis resultat findes → kør complete manuelt
python3 /home/svend/claude-bridge/bridge.py complete {ID}

# Hvis intet resultat → tilslut og inspicér
tmux attach -t claude_implementer
```

### Scenario B: Lokal session er død

```bash
/home/svend/start_review_claude.sh
# Vent på at modellen er klar, resend handoff
```

### Scenario C: Forkert handoff ID

```bash
# Se brugte ID'er
grep "C→L" /home/svend/claude-bridge/trace.log
# Brug næste ledige
python3 /home/svend/claude-bridge/bridge.py next-id
```

---

## 9. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — tmux bridge infrastruktur, handoff protokol, kommando-reference |
| 2026-06-14 | **Tovejs-opgradering:** `reviewtoimplementor/` + `implementertoreview/` mapper, callback sektion, trace.log |
| 2026-06-14 | **Python bridge implementeret:** `bridge.py` med `send` og `complete` kommandoer. Enter håndteres korrekt via `subprocess.run` som key-argument. Lokal model kalder `python3 bridge.py complete {ID}` i stedet for rå tmux-kommandoer. Ingen polling, ingen parallel kørsel. Samme princip begge veje. `send-signal.sh` erstattet. |