# Design: `enter_command` på bridge_roles

**Dato:** 2026-06-24
**Forfatter:** svend + Claude
**Scope:** BridgeV002 dispatch-systemet i DPMtF-WebUI

## Problem

Forskellige AI-frontends i tmux håndterer Enter/submit forskelligt:

| Frontend | Submit-metode | Virker med `tmux send-keys ... Enter`? |
|----------|--------------|---------------------------------------|
| Claude Code | Enter i én kommando | ✅ |
| OpenCode | Enter efter paste-buffer | ✅ |
| **Freebuff** | Kræver separat `"" C-m` kommando | ❌ (Enter i samme kommando virker ikke) |

Freebuff (Pascal/Lazarus-baseret TUI) kræver en **to-trins submit**:
1. `tmux send-keys -t <session> "prompt tekst"` — sender teksten
2. `tmux send-keys -t <session> "" C-m` — separat C-m for at submitte

Nuværende dispatch sender altid Enter i samme flow som teksten, hvilket gør Freebuff ubrugelig til automatiseret tmux-injektion.

## Løsning

Tilføj et `enter_command` felt på `bridge_roles` så hver role kan specificere hvordan prompts skal submit'es.

### Database

```sql
ALTER TABLE bridge_roles ADD COLUMN enter_command TEXT DEFAULT 'default';
```

Værdier:
- `default` — Enter sendes som del af samme flow (nuværende adfærd, bagudkompatibel)
- `c-m` — To-trins: først tekst, så separat `"" C-m` (Freebuff)
- `c-j` — To-trins med C-j (Ctrl+J, line feed)
- `c-d` — To-trins med C-d (Ctrl+D, EOF)

### Dispatch-ændringer

**`inject_prompt()`** får en ekstra parameter og route'r submit korrekt:

```python
def inject_prompt(session_name, text, enter_command="default"):
    tool = get_pane_command(session_name)
    if tool == "opencode":
        inject_via_paste_buffer(session_name, combined, enter_command)
    else:
        inject_via_send_keys(session_name, text, enter_command)
```

**`inject_via_send_keys()`** — den kritiske ændring:

Nuværende:
```python
subprocess.run(["tmux", "load-buffer", tmp], check=True)
subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
```

Ny:
```python
subprocess.run(["tmux", "load-buffer", tmp], check=True)
if enter_command == "c-m":
    subprocess.run(["tmux", "send-keys", "-t", session_name, "", "C-m"], check=True)
elif enter_command == "c-j":
    subprocess.run(["tmux", "send-keys", "-t", session_name, "", "C-j"], check=True)
elif enter_command == "c-d":
    subprocess.run(["tmux", "send-keys", "-t", session_name, "", "C-d"], check=True)
else:  # "default"
    subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
```

**`inject_via_paste_buffer()`** — tilsvarende ændring for OpenCode:

Nuværende:
```python
subprocess.run(["tmux", "paste-buffer", "-t", session_name], check=True)
time.sleep(0.3)
subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
```

Ny: Erstat den hårdkodede `"Enter"` med enter_command-logikken (samme if/elif/else som ovenfor).

**Alle kaldere** sender `enter_command` med:

- `run_flow_step_db()` → har `to_role` → sender `to_role.get("enter_command", "default")`
- `signal_complete()` → har `to_role` → samme
- `signal_escalation()` → har `to_role_data` → samme
- `signal_answer()` → har `to_role_data` → samme
- `signal_send()` → har `to_role_data` → samme

### `bridge_lib.py`

`load_role_from_db()` returnerer allerede alle kolonner fra `bridge_roles` — `enter_command` kommer automatisk med når kolonnen findes i tabellen. Ingen kodeændring nødvendig her.

### `init_db.py`

Tilføj `enter_command` i CREATE TABLE statement for `bridge_roles` og i seed data (default værdi for alle eksisterende roller).

## Eksempel: Freebuff som imple01

```sql
UPDATE bridge_roles 
SET enter_command = 'c-m'
WHERE role_key = 'imple01';
```

Alle prompts til imple01 bruger nu automatisk to-trins C-m submit.

## Bagudkompatibilitet

- `enter_command` har default `'default'` — alle eksisterende roller fortsætter uændret
- Ingen breaking changes for nuværende Claude Code / OpenCode roller
- Ny kolonne er bagudkompatibel med eksisterende SQL queries (SELECT * returnerer den bare)

## Test

1. Sæt en test-role's `enter_command` til `'c-m'`
2. Send en prompt via dispatch
3. Verificer at prompten submit'es korrekt i tmux-sessionen
4. Verificer at `'default'` roller stadig fungerer som før
