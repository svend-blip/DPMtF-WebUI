# Tmux Bridge Protocol — Python-drevet 3-lags kommunikation

> **3-lags Claude Code kommunikation via tmux:**
> `claude_implementer` (lokal) ←→ `claude_review` (cloud, billig) ←→ `claude_architect` (cloud, kapabel).
> Loades når cloud model skal sende instruktioner til lokal model,
> når lokal model sender resultat tilbage, eller når review eskalerer
> en beslutning til architect.
> Refereret fra [[superpowers]] og [[localmodel]].

---

## 1. Infrastruktur

| Komponent | Placering | Formål |
|---|---|---|
| `start_review_claude.sh` | `/home/svend/start_review_claude.sh` | Starter lokal Claude Code i tmux session `claude_implementer` |
| `claude-bridge/` | `/home/svend/claude-bridge/` | Handoff-filer for alle 3 kommunikations-lag |
| `bridge.py` | `/home/svend/claude-bridge/bridge.py` | **Kerne:** tmux injection med korrekt Enter key-argument via Python subprocess. 4 kommandoer: send, complete, ask-architect, answer-review |
| `clear.md` | `/home/svend/claude-bridge/clear.md` | Indeholder `/clear` kommando til session-reset |
| `reviewtoimplementor/` | `/home/svend/claude-bridge/reviewtoimplementor/` | **Review → Implementer:** handoff-filer med unikt ID |
| `implementertoreview/` | `/home/svend/claude-bridge/implementertoreview/` | **Implementer → Review:** resultat + notification + callback-filer |
| `reviewtoarchitect/` | `/home/svend/claude-bridge/reviewtoarchitect/` | **Review → Architect:** spørgsmål/escalering når review ikke kan tage beslutning alene |
| `architecttoreview/` | `/home/svend/claude-bridge/architecttoreview/` | **Architect → Review:** svar + response + callback-filer |
| `trace.log` | `/home/svend/claude-bridge/trace.log` | Append-only log over ALL bridge-aktivitet |
| tmux session (architect) | `claude_architect` | **Cloud model (deepseek-v4-pro:cloud)** — kapabel, har overblik, tager komplekse beslutninger |
| tmux session (review) | `claude_review` | Cloud model (deepseek-v4-flash:cloud) — billigere tokens, håndterer rutine-opgaver og review |
| tmux session (implementer) | `claude_implementer` | Lokal Ollama model (qwen36-27b-q4km) — 0 EUR cost, udfører implementationer |

### Mappestruktur

```
/home/svend/claude-bridge/
├── bridge.py                            # Python tmux-bridge (4 kommandoer)
├── clear.md                             # /clear kommando
├── restart-handoff.md                   # Session restart info
├── trace.log                            # Append-only log
├── reviewtoimplementor/                 # Review → Implementer (Lag 1)
│   ├── 001-handoff.md                   # Handoff #1
│   ├── 002-handoff.md                   # Handoff #2 (osv.)
│   └── current.md → 001-handoff.md      # Symlink til nuværende
├── implementertoreview/                 # Implementer → Review (Lag 1)
│   ├── 001-result.md                    # Resultat #1
│   ├── 001-notification.md             # Notification #1
│   ├── 001-callback.md                 # Callback-prompt
│   ├── current.md → 001-result.md      # Symlink til nuværende
│   └── notification-template.md         # Skabelon til notifications
├── reviewtoarchitect/                   # Review → Architect (Lag 2) — NY
│   ├── 001-handoff.md                   # Spørgsmål/escalering #1
│   ├── 002-handoff.md                   # Spørgsmål #2 (osv.)
│   └── current.md → 001-handoff.md      # Symlink til nuværende
└── architecttoreview/                   # Architect → Review (Lag 2) — NY
    ├── 001-response.md                  # Architectens svar #1
    ├── 001-callback.md                 # Callback-prompt
    ├── current.md → 001-response.md     # Symlink til nuværende
    └── notification-template.md         # Skabelon til architect-svar
```

---

## 2. Bridge.py kommando-reference

| Kommando | Fra | Til | Handling |
|---|---|---|---|
| `bridge.py send <ID>` | Review (claude_review) | Implementer (claude_implementer) | `/clear` + inject handoff-instruktion |
| `bridge.py complete <ID>` | Implementer (claude_implementer) | Review (claude_review) | Inject resultat-prompt i review-session |
| `bridge.py ask-architect <ID>` | Review (claude_review) | Architect (claude_architect) | `/clear` + inject spørgsmål/escalering |
| `bridge.py answer-review <ID>` | Architect (claude_architect) | Review (claude_review) | Inject svar-prompt i review-session |

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

### bridge.py ask-architect <ID>

```python
# Eksempel: Send spørgsmål 003 til claude_architect — kaldes af claude_review
python3 /home/svend/claude-bridge/bridge.py ask-architect 003
```

Gør:
1. Tjekker at `claude_architect` session kører
2. Tjekker at handoff-fil findes (`reviewtoarchitect/003-handoff.md`)
3. Sender `/clear` til `claude_architect` via tmux
4. Sender `"Read and execute ... 003-handoff.md"` + **Enter** til `claude_architect`
5. Opdaterer `reviewtoarchitect/current.md` symlink
6. Logger `R→A` i `trace.log`

### bridge.py answer-review <ID>

```python
# Eksempel: Send svar 003 til claude_review — kaldes af claude_architect
python3 /home/svend/claude-bridge/bridge.py answer-review 003
```

Gør:
1. Tjekker at `claude_review` session kører
2. Skriver `architecttoreview/{ID}-callback.md` (hvis den ikke findes)
3. Injecter prompt: `"Read and execute ... architecttoreview/{ID}-callback.md"` + **Enter**
   — PRÆCIS samme mønster som `bridge.py send` og `bridge.py complete`
4. Logger `A→R` i `trace.log`
5. Opdaterer `architecttoreview/current.md` symlink

### bridge.py next-id

```bash
# Find næste ledige handoff-ID på tværs af ALLE mapper
python3 /home/svend/claude-bridge/bridge.py next-id
# → 4 (hvis 001-003 findes i reviewtoimplementor/ eller reviewtoarchitect/)
```

---

## 3. 3-lags Workflow

### Lag 1: Review ↔ Implementer (implementation)

```
REVIEW (claude_review)                              IMPLEMENTER (claude_implementer)
───────────────────────────────────────────        ──────────────────────────────────

1. TJEK at implementer session kører
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

### Lag 2: Review ↔ Architect (escalering)

Når claude_review rammer en beslutning den ikke kan tage alene (scope-ændring,
arkitektur-valg, kompleks tværprojekt-koordinering), eskalerer den til claude_architect.

```
REVIEW (claude_review)                              ARCHITECT (claude_architect)
───────────────────────────────────────────        ──────────────────────────────────

1. REVIEW rammer beslutningspunkt
   └─ Kan ikke afgøre alene — har brug for architect-overblik

2. BESTEM næste handoff ID
   └─ python3 bridge.py next-id

3. SKRIV spørgsmål til reviewtoarchitect/
   ├─ reviewtoarchitect/{ID}-handoff.md
   └─ Indeholder: kontekst, spørgsmål, mulige valg

4. SEND spørgsmål med bridge.py:
   python3 /home/svend/claude-bridge/bridge.py ask-architect {ID}

   Dette gør:
   ├─ /clear til claude_architect
   ├─ Inject "Read and execute ... reviewtoarchitect/{ID}-handoff.md"
   ├─ Logger R→A i trace.log
   └─ Returnér kontrol til review               5. ARCHITECT læser spørgsmålet
                                                  6. Analyserer kontekst og overblik
                                                  7. Træffer beslutning
                                                  8. Skriver svar til:
                                                     └─ architecttoreview/{ID}-response.md
                                                  9. KALDER bridge.py answer-review:
                                                     python3 /home/svend/claude-bridge/bridge.py answer-review {ID}
                                                     Dette gør:
                                                     ├─ Skriver architecttoreview/{ID}-callback.md
                                                     └─ Inject "Read and execute ...
                                                        architecttoreview/{ID}-callback.md"
                                                        + logger A→R i trace.log

10. MODTAGER prompt via tmux:
    "Read and execute /home/.../architecttoreview/{ID}-callback.md"

11. LÆSER callback.md → læser architectens svar
12. FORTSÆTTER med opgaven baseret på architectens beslutning
```

**Escalerings-princip:** Billige modeller arbejder mest muligt. Architect involveres kun
når en beslutning kræver tværprojekt-overblik, arkitektur-forståelse, eller scope-ændring.
Dette minimerer token-forbrug på den dyre model.

---

## 4. Handoff fil-format

### reviewtoimplementor/{ID}-handoff.md (review → implementer)

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

### implementertoreview/{ID}-notification.md (implementer → review)

```markdown
# Notification — Handoff {ID}
Status: completed | failed | partial
Summary: {Kort beskrivelse — max 2 linjer}
Result file: {ID}-result.md
Next action: {Review diff | Commit | Rerun | Acknowledge}
```

### reviewtoarchitect/{ID}-handoff.md (review → architect)

Bruges når claude_review eskalerer en beslutning til claude_architect.

```markdown
<role>Du er Architect i DPMtF governance rollen. Du har det fulde overblik over
alle projekter (DPMtF-WebUI, ENO, v3) og bridge-infrastrukturen.</role>

<handoff_id>{ID}</handoff_id>

<escalation_from>claude_review (deepseek-v4-flash:cloud)</escalation_from>

<context>
[Hvad claude_review arbejdede på — projekt, fase, opgave]
</context>

<question>
[Det specifikke spørgsmål — hvad kan claude_review ikke afgøre alene?]
</question>

<options>
- [Mulighed A]
- [Mulighed B]
- [Mulighed C]
</options>

<governance>
Læs og anvend:
- /home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates/superpowers.md
- /home/svend/DPMtF-WebUI/docs/governance-templates/11_NEXT_CONTEXT.md
</governance>

<task>
1. Læs <context> og <question> — forstå hvad claude_review har brug for
2. Konsulter relevante governance-filer for overblik
3. Træf en beslutning og skriv svaret til:
   /home/svend/claude-bridge/architecttoreview/{ID}-response.md
4. Skriv NOTIFICATION til:
   /home/svend/claude-bridge/architecttoreview/{ID}-notification.md
5. SEND SIGNAL til claude_review:
   python3 /home/svend/claude-bridge/bridge.py answer-review {ID}
</task>

<constraint>
SVAR KUN på spørgsmålet. Start ikke nye implementationer.
Udfør ALLE steps i <task> — især step 5 (bridge.py answer-review).
</constraint>
```

### architecttoreview/{ID}-response.md (architect → review)

Architectens svar på review's spørgsmål.

```markdown
# Architect Svar — Spørgsmål {ID}

## Beslutning
[Den trufne beslutning — klar og entydig]

## Begrundelse
[Hvorfor denne beslutning — kontekst fra tværprojekt-overblik]

## Næste skridt for claude_review
[Konkrete instruktioner til hvad claude_review skal gøre nu]

## Berørte projekter/filer
- [Liste hvis relevant]
```

### architecttoreview/{ID}-notification.md (architect → review)

```markdown
# Notification — Architect Svar {ID}
Status: answered
Summary: {Kort beskrivelse af architectens svar — max 2 linjer}
Response file: {ID}-response.md
Next action: {Fortsæt med opgave | Eskaler til Svend | Afvent yderligere input}
```

---

## 5. Hvorfor Python?

| Problem | Løsning i Python |
|---|---|
| Modeller forstår ikke `Enter` som tmux-key-navn | `subprocess.run(["tmux", "send-keys", ..., "Enter"])` sender Enter som **separat argument** — tmux fortolker det korrekt som tastetryk, ikke som tekst |
| Modeller skriver `echo` foran tmux-kommandoer | Modellen kalder `python3 bridge.py <kommando> {ID}` — én simpel kommando, ingen tmux-logik |
| Modeller ignorerer separat `<callback>` sektion | `bridge.py` injecter prompt direkte i target-session — modellen skal kun kalde scriptet |
| Skal virke på tværs af ALLE modeller (cloud + lokal) | Python subprocess er OS-niveau — uafhængigt af hvilken LLM der kører |
| Skal virke ALLE veje i 3-lags arkitektur | `send`/`complete`/`ask-architect`/`answer-review` — symmetrisk design for alle 3 lag |
| Review skal kunne eskalere til architect | `ask-architect` + `answer-review` — samme mønster som send/complete, bare mellem cloud-sessioner |

---

## 6. Kommando-reference

### Send handoff til implementer (review → implementer)

```bash
python3 /home/svend/claude-bridge/bridge.py send 002
```

### Signalér færdig (implementer → review, kaldes af lokal model)

```bash
python3 /home/svend/claude-bridge/bridge.py complete 002
```

### Eskaler spørgsmål til architect (review → architect)

```bash
python3 /home/svend/claude-bridge/bridge.py ask-architect 003
```

### Send svar til review (architect → review, kaldes af architect)

```bash
python3 /home/svend/claude-bridge/bridge.py answer-review 003
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
5. **/clear mellem hver prompt** — håndteres af `bridge.py send` og `bridge.py ask-architect`.
6. **Handoff ID'er er unikke og sekventielle** — brug `bridge.py next-id` (scanner ALLE mapper).
7. **trace.log er append-only** — redigér aldrig eksisterende entries.
8. **bridge.py complete og answer-review kaldes UDEN /clear** — ellers overskrives prompten før modtager ser den.
9. **Architect eskalering er read-only** — architect træffer kun beslutninger, implementerer ikke. Implementation sker altid via implementer→review loopet.
10. **Ingen direkte architect→implementer kommunikation** — al kommunikation går gennem review-laget. Review koordinerer alt arbejde.

---

## 8. Fejlhåndtering

### Scenario A: Notification udebliver efter 5+ min (Lag 1)

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
# Se brugte ID'er på tværs af alle lag
grep -E "C→L|R→A" /home/svend/claude-bridge/trace.log
# Brug næste ledige
python3 /home/svend/claude-bridge/bridge.py next-id
```

### Scenario D: Architect svar udebliver efter 5+ min (Lag 2)

```bash
# Tjek om architect session stadig kører
tmux ls | grep claude_architect

# Tjek om svar alligevel blev skrevet
ls -la /home/svend/claude-bridge/architecttoreview/

# Hvis svar findes → kør answer-review manuelt
python3 /home/svend/claude-bridge/bridge.py answer-review {ID}

# Hvis intet svar → tilslut og inspicér
tmux attach -t claude_architect
```

---

## 9. Opdateringslog

| Dato | Ændring |
|---|---|
| 2026-06-13 | Oprettet — tmux bridge infrastruktur, handoff protokol, kommando-reference |
| 2026-06-14 | **Tovejs-opgradering:** `reviewtoimplementor/` + `implementertoreview/` mapper, callback sektion, trace.log |
| 2026-06-14 | **Python bridge implementeret:** `bridge.py` med `send` og `complete` kommandoer. Enter håndteres korrekt via `subprocess.run` som key-argument. Lokal model kalder `python3 bridge.py complete {ID}` i stedet for rå tmux-kommandoer. Ingen polling, ingen parallel kørsel. Samme princip begge veje. `send-signal.sh` erstattet. |
| 2026-06-14 | **3-lags arkitektur:** `reviewtoarchitect/` + `architecttoreview/` mapper oprettet. `bridge.py` udvidet med `ask-architect` og `answer-review` kommandoer. Review kan nu eskalere beslutninger til architect. Architect svarer via samme bridge-mønster. `next-id` scanner alle mapper. 10 sikkerheds-regler (2 nye: architect read-only, ingen direkte architect→implementer). Nyt fejlscenarie D (architect svar udebliver). |