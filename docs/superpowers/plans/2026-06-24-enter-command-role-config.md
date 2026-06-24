# enter_command på bridge_roles — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tilføj `enter_command` felt til `bridge_roles` så hver role kan specificere hvordan prompts submit'es i tmux (default Enter, eller to-trins C-m/C-j/C-d for Freebuff og lignende).

**Architecture:** Én ny databasekolonne, én modificeret inject-funktion i dispatch.py, bagudkompatibelt — alle eksisterende roller fortsætter uændret med `default`.

**Tech Stack:** Python 3.12, SQLite3, tmux send-keys, subprocess

## Global Constraints

- `python3 -m py_compile <file>` MUST pass before signaling completion
- Parameterized SQL only — `?` placeholders, never f-strings/concatenation in SQL
- No hardcoded paths — use config.py getters
- Bagudkompatibel: `enter_command` default `'default'` — eksisterende roller uændrede
- Alle eksisterende tests skal stadig passere

---

## Filstruktur

| Fil | Ansvar | Ændring |
|-----|--------|---------|
| `scripts/init_db.py` | Database-skema + seed data | Tilføj migration for `enter_command` kolonne |
| `scripts/bridgeV002/dispatch.py` | Prompt-injektion i tmux | Modificer `inject_via_send_keys()`, `inject_via_paste_buffer()`, `inject_prompt()`, og 5 kaldere |
| `scripts/bridgeV002/bridge_lib.py` | Database-opslag | **Ingen ændring** — `SELECT *` returnerer automatisk ny kolonne |

---

### Task 1: Database-migration for enter_command

**Files:**
- Modify: `scripts/init_db.py` — tilføj migration efter linje ~4591 (efter G1 role_type migration)

**Interfaces:**
- Produces: `enter_command` kolonne i `bridge_roles` med default `'default'`

- [ ] **Step 1: Tilføj migration i init_db.py**

Indsæt efter G1 role_type migration-blokken (efter linje 4591):

```python
# H150: enter_command column on bridge_roles — how Enter is sent for tmux injection
# Values: 'default' (Enter in same command), 'c-m' (two-step: text then separate C-m),
#         'c-j' (two-step with C-j), 'c-d' (two-step with C-d)
try:
    cursor.execute("""
        ALTER TABLE bridge_roles ADD COLUMN enter_command TEXT DEFAULT 'default'
    """)
except sqlite3.OperationalError:
    pass
```

- [ ] **Step 2: Kør init_db.py for at verificere migrationen**

```bash
cd /home/svend/DPMtF-WebUI && python3 scripts/init_db.py
```

Forventet: Ingen fejl. Migrationen kører (eller springes over hvis kolonnen allerede findes).

- [ ] **Step 3: Verificer at kolonnen findes i databasen**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "PRAGMA table_info(bridge_roles)" | grep enter_command
```

Forventet: `enter_command|TEXT|0|'default'|0`

- [ ] **Step 4: Verificer at eksisterende roller har default værdi**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "SELECT role_key, enter_command FROM bridge_roles"
```

Forventet: Alle roller viser `default`.

- [ ] **Step 5: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/init_db.py && git commit -m "feat: add enter_command column to bridge_roles

Migration H150 — enables per-role Enter key configuration for tmux injection.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Modificer inject-funktioner i dispatch.py

**Files:**
- Modify: `scripts/bridgeV002/dispatch.py` — `inject_via_send_keys()` (linje 87-104), `inject_via_paste_buffer()` (linje 107-125), `inject_prompt()` (linje 128-145)

**Interfaces:**
- Consumes: `enter_command` fra `bridge_roles` (via parameter)
- Produces: `inject_via_send_keys(session_name, text, enter_command="default")`, `inject_via_paste_buffer(session_name, text, enter_command="default")`, `inject_prompt(session_name, text, enter_command="default")`

- [ ] **Step 1: Modificer inject_via_send_keys()**

Erstat funktionen (linje 87-104) med:

```python
def inject_via_send_keys(session_name, text, enter_command="default"):
    """Send text + submit key via tmux send-keys.

    Supports per-role enter_command:
      - 'default': Enter in same command (Claude Code, standard)
      - 'c-m': Two-step — text first, then separate C-m (Freebuff)
      - 'c-j': Two-step with C-j (Ctrl+J / line feed)
      - 'c-d': Two-step with C-d (Ctrl+D / EOF)
    """
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="bridge-inject-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp], check=True)

        # Submit based on enter_command
        if enter_command == "c-m":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-m"], check=True
            )
        elif enter_command == "c-j":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-j"], check=True
            )
        elif enter_command == "c-d":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-d"], check=True
            )
        else:  # "default" — original behavior
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Enter"], check=True
            )
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
```

- [ ] **Step 2: Modificer inject_via_paste_buffer()**

Erstat funktionen (linje 107-125) med:

```python
def inject_via_paste_buffer(session_name, text, enter_command="default"):
    """Write to temp file, load-buffer, paste-buffer, send submit key. Used for OpenCode sessions.

    Supports per-role enter_command (same values as inject_via_send_keys).
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="bridge-prompt-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp_path], check=True)
        subprocess.run(["tmux", "paste-buffer", "-t", session_name], check=True)
        time.sleep(0.3)

        # Submit based on enter_command
        if enter_command == "c-m":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-m"], check=True
            )
        elif enter_command == "c-j":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-j"], check=True
            )
        elif enter_command == "c-d":
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "", "C-d"], check=True
            )
        else:  # "default" — original behavior
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Enter"], check=True
            )
        time.sleep(0.3)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
```

- [ ] **Step 3: Modificer inject_prompt()**

Erstat funktionen (linje 128-145) med:

```python
def inject_prompt(session_name, text, enter_command="default"):
    """Detect tool type and route to correct injection method.

    For OpenCode sessions, prepends soft-clear preamble before actual prompt.
    For Claude Code sessions, uses send-keys directly.

    enter_command controls how the submit key is sent:
      - 'default': Enter (standard for Claude Code / OpenCode)
      - 'c-m': Two-step C-m (Freebuff)
      - 'c-j': Two-step C-j
      - 'c-d': Two-step C-d
    """
    tool = get_pane_command(session_name)
    if tool == "opencode":
        soft_clear = (
            "Start a new logical task now. "
            "Ignore earlier conversation context unless this prompt explicitly references it. "
            "Do not continue previous plans, assumptions, file edits, or task state. "
            "Treat this message as the authoritative task."
        )
        combined = f"{soft_clear}\n\n{text}"
        inject_via_paste_buffer(session_name, combined, enter_command)
    else:
        inject_via_send_keys(session_name, text, enter_command)
```

- [ ] **Step 4: Kør py_compile for at verificere syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py
```

Forventet: Ingen output (kompilering succes).

- [ ] **Step 5: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/bridgeV002/dispatch.py && git commit -m "feat: add enter_command support to inject functions

inject_via_send_keys, inject_via_paste_buffer, and inject_prompt now
accept enter_command parameter for per-role submit key configuration.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Opdater kaldere til at sende enter_command

**Files:**
- Modify: `scripts/bridgeV002/dispatch.py` — `run_flow_step_db()` (linje 585), `signal_complete()` (linje 778), `signal_escalation()` (linje 960), `signal_answer()` (linje 1095), `signal_send()` (linje 1306)

**Interfaces:**
- Consumes: `to_role["enter_command"]` (findes automatisk via `load_role_from_db()` som returnerer `SELECT *`)
- Produces: Alle kald til `inject_prompt()` inkluderer `enter_command`

- [ ] **Step 1: Opdater run_flow_step_db() — linje 585**

Find linjen:
```python
    inject_prompt(tmux_session, prompt_text)
```

Erstat med:
```python
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role.get("enter_command", "default"))
```

- [ ] **Step 2: Opdater signal_complete() — linje 778**

Find linjen:
```python
    inject_prompt(tmux_session, prompt_text)
```

Erstat med:
```python
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role.get("enter_command", "default"))
```

- [ ] **Step 3: Opdater signal_escalation() — linje 960**

Find linjen:
```python
    inject_prompt(tmux_session, prompt_text)
```

Erstat med:
```python
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
```

- [ ] **Step 4: Opdater signal_answer() — linje 1095**

Find linjen:
```python
    inject_prompt(tmux_session, prompt_text)
```

Erstat med:
```python
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
```

- [ ] **Step 5: Opdater signal_send() — linje 1306**

Find linjen:
```python
    inject_prompt(tmux_session, prompt_text)
```

Erstat med:
```python
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
```

- [ ] **Step 6: Kør py_compile for at verificere syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py
```

Forventet: Ingen output (kompilering succes).

- [ ] **Step 7: Commit**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/bridgeV002/dispatch.py && git commit -m "feat: wire enter_command through all dispatch callers

All five call sites (run_flow_step_db, signal_complete, signal_escalation,
signal_answer, signal_send) now pass enter_command from role config to
inject_prompt.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Integrationstest med Freebuff

**Files:**
- Ingen nye filer — manuel test mod kørende Freebuff session

- [ ] **Step 1: Sæt enter_command for en test-role**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "UPDATE bridge_roles SET enter_command = 'c-m' WHERE role_key = 'imple01'"
```

- [ ] **Step 2: Verificer at værdien er gemt**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "SELECT role_key, enter_command FROM bridge_roles WHERE role_key = 'imple01'"
```

Forventet: `imple01|c-m`

- [ ] **Step 3: Send en test-prompt via dispatch til en Freebuff-session**

Hvis Freebuff kører i tmux-session "freebuff":
```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
from scripts.bridgeV002.dispatch import inject_prompt
inject_prompt('freebuff', 'echo hello from bridgeV002', enter_command='c-m')
"
```

Forventet: Prompten "echo hello from bridgeV002" submit'es og Freebuff begynder at tænke.

- [ ] **Step 4: Nulstil enter_command til default**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "UPDATE bridge_roles SET enter_command = 'default' WHERE role_key = 'imple01'"
```

- [ ] **Step 5: Commit (hvis test-data blev committed)**

Kun hvis testen involverede filændringer. Ellers: ingen commit — testen er manuel verifikation.
