# Design: Dekomponeret `start_cmd` på bridge_roles

**Dato:** 2026-06-24
**Forfatter:** svend + Claude
**Scope:** BridgeV002 — start_cmd dekomponering og "Start code interface"

## Problem

`start_cmd` på `bridge_roles` er én lang hardcodet streng:
```
tmux send-keys -t imple01 'cd /home/svend/DPMtF-WebUI && OPENCODE_CONFIG_DIR=...' Enter
```

Problemer:
1. `tmux_session` står både i `start_cmd` og i feltet `tmux_session` — duplikering
2. Target project er hardcodet — kan ikke genbruges på tværs af projekter
3. Hele strengen skal redigeres manuelt — let at lave tastefejl

## Løsning

Dekomponer `start_cmd` i separate felter og generer den aggregerede streng automatisk.

### Database

Nyt felt på `bridge_roles`:
```sql
ALTER TABLE bridge_roles ADD COLUMN start_cmd_suffix TEXT DEFAULT NULL;
```

Eksisterende `start_cmd` beholdes urørt som fallback.

### Felter vist på role (top-down = aggregeret rækkefølge)

```
tmux send-keys -t  [tmux_session]  'cd  [target_project]  [start_cmd_suffix]
                   ↑ redigerbar      ↑ read-only           ↑ redigerbar
                                        (fra Prompt Compiler)
```

| # | Felt | Kilde | Redigerbar? | Eksempel |
|---|------|-------|------------|----------|
| 1 | `tmux_session` | `bridge_roles` (eksisterende) | ✅ | `imple01` |
| 2 | `target_project` | `user_preferences` → Prompt Compiler | ❌ Read-only | `/home/svend/DPMtF-WebUI` |
| 3 | `start_cmd_suffix` | `bridge_roles` (nyt) | ✅ | `&& OPENCODE_CONFIG_DIR=... opencode --model ollama/...' Enter` |
| — | **Aggregeret streng** | Genereret fra 1+2+3 | ❌ Read-only | `tmux send-keys -t imple01 'cd /home/svend/DPMtF-WebUI && ...' Enter` |

### Aggregeringslogik

```
Hvis start_cmd_suffix er udfyldt:
  aggregeret = "tmux send-keys -t " + tmux_session + " 'cd " + target_project + " " + start_cmd_suffix
Ellers:
  brug eksisterende start_cmd (fallback)
```

### Frontend

**Rolle-kort (visning):**
- Felter vises i aggregeret rækkefølge (1→2→3→aggregeret)
- `target_project` vises read-only med værdi fra Prompt Compiler
- Aggregeret streng vises read-only nederst som validering

**Edit-form:**
- `start_cmd_suffix` input-felt tilføjes efter `target_project` visning
- `target_project` vises som read-only tekst (ikke input)

**Create-form:**
- `start_cmd_suffix` input-felt tilføjes

### Backend

- `start_cmd_suffix` tilføjes til POST/PUT endpoints (som `enter_command` blev det)
- GET endpoints returnerer feltet automatisk via `SELECT *`

### "Start code interface" (`start_coding.py`)

- Looper over alle roller i flow (uændret)
- Hvis `start_cmd_suffix` er udfyldt → generer aggregeret streng og kør den
- Ellers → brug `start_cmd` som fallback (nuværende adfærd)
- Hvis ingen af delene → fejl (powertool — skjul ikke)

### Bagudkompatibilitet

- `start_cmd` felt beholdes urørt
- `start_cmd_suffix` er NULL som default → fallback til `start_cmd`
- Alle eksisterende roller virker uændret
- Rolle-for-rolle migration når man er klar
