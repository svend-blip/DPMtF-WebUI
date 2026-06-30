# Machine Profile Fase 2A — Role Runtime Config: Design Spec

> **Dato:** 2026-06-30
> **Status:** Design godkendt — afventer implementeringsplan
> **Fase:** 2A — Role Runtime Config
> **Bygger på:** Fase 1 Machine Profile (profiles/, healthcheck, System Setup)

---

## 1. Formål

Afkobl `bridge_roles.start_cmd_suffix` fra maskinspecifikke kommandoer ved at indføre logiske felter (runtime, provider, model) på roller og en `build_start_command()` funktion der oversætter disse til konkrete startkommandoer via Machine Profile.

Målet er **ikke** at massemigrere alle flows. Målet er at gøre det muligt at migrere ét flow ad gangen via `use_machine_profile` flaget på flowet.

---

## 2. Grundregel

```
Flow bestemmer OM Machine Profile bruges.
Rolle bestemmer HVAD der skal køres.
Machine Profile bestemmer HVORDAN maskinen kan køre det.
Builder oversætter til konkret kommando.
Renderer gør kommandoen tmux-klar.
```

---

## 3. Arkitektur

### 3.1 Ansvarsfordeling

| Komponent | Felt | Betydning |
|-----------|------|-----------|
| `bridge_flows` | `use_machine_profile` | 0 = legacy `start_cmd_suffix`, 1 = Machine Profile |
| `bridge_roles` | `default_runtime` | Hvilket program starter rollen |
| `bridge_roles` | `default_provider` | Hvor modellen kommer fra |
| `bridge_roles` | `default_model` | Hvilken model der bruges |
| `bridge_roles` | `start_cmd_suffix` | Legacy kommando (bevares) |
| Machine Profile | `binaries` | Hvor ligger claude, opencode, freebuff |
| Machine Profile | `runtimes` | Runtime-specifik config (config_base, default_env) |
| Machine Profile | `providers` | Endpoints, env_key-navne, model-lister |
| `build_start_command()` | Python | 5 faste opskrifter |

### 3.2 Dataflow ved flow-start

```
start_coding.py
  │
  ├─ load flow, load role
  │
  ├─ if flow.use_machine_profile == 0
  │     └─ brug role.start_cmd_suffix (uændret legacy path)
  │
  └─ if flow.use_machine_profile == 1
        ├─ machine_profile = config.get_machine_profile()
        ├─ command_object = build_start_command(
        │      runtime=role.default_runtime,
        │      provider=role.default_provider,
        │      model=role.default_model,
        │      role_key=role.role_key,
        │      machine_profile=machine_profile
        │   )
        └─ command_string = render_tmux_shell_string(command_object)
```

---

## 4. Database schema ændringer

### 4.1 `bridge_flows`

```sql
ALTER TABLE bridge_flows ADD COLUMN use_machine_profile INTEGER DEFAULT 0;
```

- `0` eller `NULL` = legacy mode (brug `start_cmd_suffix`)
- `1` = Machine Profile mode (brug `build_start_command()`)

### 4.2 `bridge_roles`

```sql
ALTER TABLE bridge_roles ADD COLUMN default_runtime TEXT DEFAULT NULL;
ALTER TABLE bridge_roles ADD COLUMN default_provider TEXT DEFAULT NULL;
ALTER TABLE bridge_roles ADD COLUMN default_model TEXT DEFAULT NULL;
```

- Alle nullable, default `NULL`
- Kun påkrævet når et flow med `use_machine_profile=1` bruger rollen
- `start_cmd_suffix` forbliver urørt
- Freebuff-undtagelse: `default_provider` må være `NULL` når `default_runtime=freebuff`

---

## 5. De 5 understøttede builder-mønstre

### 5.1 Builder registry

```python
SUPPORTED_COMMAND_BUILDERS = {
    ("claude", "local_ollama"): build_claude_ollama_command,
    ("claude", "cloud_ollama"): build_claude_ollama_command,
    ("opencode", "local_ollama"): build_opencode_ollama_command,
    ("opencode", "openrouter"): build_opencode_openrouter_command,
    ("freebuff", None): build_freebuff_command,
}
```

### 5.2 Claude + local_ollama / cloud_ollama

Input: `runtime=claude, provider=local_ollama, model=qwen3.6:35b-a3b-64k`

Machine Profile anvender:
- `binaries.claude`
- `providers.<provider>.endpoint` + `auth_token`
- `runtimes.claude.default_env`

Output command object:
```python
{
    "cwd": "<project_root>",
    "env": {
        "ANTHROPIC_BASE_URL": "<endpoint>",
        "ANTHROPIC_AUTH_TOKEN": "<auth_token>",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "65536"
    },
    "argv": ["<claude_binary>", "--model", "<model>"]
}
```

### 5.3 OpenCode + local_ollama

Input: `runtime=opencode, provider=local_ollama, model=qwen3.6:27b-q4_K_M`

Model argument får `ollama/` prefix: `ollama/qwen3.6:27b-q4_K_M`

Output command object:
```python
{
    "cwd": "<project_root>",
    "env": {
        "OPENCODE_CONFIG_DIR": "<config_base>/<role_key>",
        "OPENCODE_CONFIG": "<config_base>/<role_key>/opencode.json"
    },
    "argv": ["<opencode_binary>", "--model", "ollama/<model>"]
}
```

### 5.4 OpenCode + openrouter

Input: `runtime=opencode, provider=openrouter, model=z-ai/glm-5.2`

Model argument får `openrouter/` prefix: `openrouter/z-ai/glm-5.2`

Output command object:
```python
{
    "cwd": "<project_root>",
    "env": {
        "OPENCODE_CONFIG_DIR": "<config_base>/<role_key>",
        "OPENCODE_CONFIG": "<config_base>/<role_key>/opencode.json"
    },
    "argv": ["<opencode_binary>", "--model", "openrouter/<model>"]
}
```

OpenRouter API key kommer fra miljø — indgår IKKE i command object.

### 5.5 Freebuff

Input: `runtime=freebuff, provider=None, model=freebuff-default`

Output command object:
```python
{
    "cwd": "<project_root>",
    "env": {},
    "argv": ["<freebuff_binary>"]
}
```

Freebuff prompt injection håndteres separat — ikke i `build_start_command()`.

---

## 6. Command object og rendering

### 6.1 Command object struktur

```python
{
    "cwd": str,       # working directory
    "env": dict,      # miljøvariable
    "argv": list[str] # kommando og argumenter
}
```

### 6.2 Renderer

```python
def render_tmux_shell_string(command_object):
    """Render command object to tmux-safe shell string."""
```

Ansvarlig for shell-quoting og tmux-kompatibel formatering.

### 6.3 Fordele ved struktureret output

- Lettere at teste (sammenlign dict, ikke strings)
- Mindre quoting-risiko
- Kan senere bruges uden tmux
- Klar adskillelse mellem bygning og eksekvering

---

## 7. Modelnavne — rene værdier

Rollen gemmer rene modelnavne uden runtime-prefix:

| Provider | Rolle gemmer | Builder producerer |
|----------|-------------|-------------------|
| `openrouter` | `z-ai/glm-5.2` | `openrouter/z-ai/glm-5.2` |
| `local_ollama` | `qwen3.6:27b-q4_K_M` | `ollama/qwen3.6:27b-q4_K_M` (kun opencode) |
| `local_ollama` | `qwen3.6:35b-a3b-64k` | `qwen3.6:35b-a3b-64k` (claude, intet prefix) |
| `cloud_ollama` | `deepseek-v4-pro:cloud` | `deepseek-v4-pro:cloud` (claude, intet prefix) |

---

## 8. Fejlhåndtering

### 8.1 Manglende felter (flow har use_machine_profile=1)

| Situation | Fejl |
|-----------|------|
| `default_runtime` er NULL | `Role <key> has use_machine_profile flow enabled but missing default_runtime` |
| `default_provider` er NULL (ikke freebuff) | `Role <key> has use_machine_profile flow enabled but missing default_provider` |
| `default_model` er NULL | `Role <key> has use_machine_profile flow enabled but missing default_model` |

### 8.2 Ukendte kombinationer

| Situation | Fejl |
|-----------|------|
| Runtime/provider ikke i registry | `Unsupported runtime/provider combination: <runtime>/<provider>` |
| Provider ikke i Machine Profile | `Provider not configured in Machine Profile: <provider>` |
| Runtime binary ikke fundet | `Runtime binary not found: <binary>` |

### 8.3 Ingen fallback

Når `use_machine_profile=1`, må systemet IKKE falde tilbage til `start_cmd_suffix` ved fejl. Fejl skal være synlige.

---

## 9. Sikkerhedsregler

- **Tilladt:** `ANTHROPIC_AUTH_TOKEN=ollama` (lokal dummy-token)
- **Ikke tilladt:** `OPENROUTER_API_KEY=sk-or-...` eller `ANTHROPIC_API_KEY=sk-ant-...` i command object
- Cloud secrets kommer fra miljø, ikke fra `build_start_command()` output
- Ingen `shell=True` i Python execution
- Renderer skal shell-quote værdier sikkert

---

## 10. Frontend ændringer

### 10.1 Flow-formular

- Ny checkbox: `use_machine_profile` — "Brug Machine Profile til startkommandoer"
- Hvis Machine Profile findes: enabled
- Hvis Machine Profile mangler: disabled + hjælpetekst
- Default: 0 (legacy mode)

### 10.2 Rolle-formular

- Tre nye dropdowns: `default_runtime`, `default_provider`, `default_model`
- Populeres fra Machine Profile når den findes
- Disabled når Machine Profile mangler
- Freebuff: `default_provider` dropdown tillader tom værdi

### 10.3 System Setup

Uændret fra Fase 1 — read-only.

---

## 11. Migreringssti

```
1. Tilføj use_machine_profile på bridge_flows (default 0)
2. Tilføj default_runtime/default_provider/default_model på bridge_roles
3. Udfyld default-felter ud fra analyserede start_cmd_suffix mønstre
4. Implementér build_start_command() + renderer
5. Sammenlign genereret kommando med eksisterende start_cmd_suffix
6. Aktiver use_machine_profile=1 på ét testflow
7. Verificér at andre flows stadig bruger start_cmd_suffix
8. Migrér næste flow efter godkendt verdict
```

---

## 12. Stopregel

### Fase 2A må gerne

- Tilføje `use_machine_profile` på `bridge_flows`
- Tilføje `default_runtime`, `default_provider`, `default_model` på `bridge_roles`
- Implementere `build_start_command()` og command object renderer
- Aktivere Machine Profile for ét flow ad gangen
- Bevare `start_cmd_suffix` som legacy fallback

### Fase 2A må ikke

- Fjerne `start_cmd_suffix`
- Massemigrere alle flows
- Aktivere Machine Profile globalt på alle roller
- Tilføje `command_templates` til Machine Profile
- Tilføje `runtime_commands` database-tabel
- Bygge flow-role overrides (Fase 2B)
- Ændre tmux injection semantics
- Ændre prompt injection
- Ændre deliverable_dir resolution
- Ændre flow execution logic ud over valg af startkommando

---

## 13. Testkrav

| # | Test |
|---|------|
| 1 | Flow med `use_machine_profile=0` bruger `start_cmd_suffix` uændret |
| 2 | Flow med `use_machine_profile=1` bruger `build_start_command()` |
| 3 | Samme rolle i to flows påvirkes ikke globalt |
| 4 | `strict_review` kan migreres uden at `cloud_llm` påvirkes |
| 5 | Manglende `default_runtime` giver fejl når `use_machine_profile=1` |
| 6 | Manglende `default_provider` giver fejl (undtagen freebuff) |
| 7 | Manglende `default_model` giver fejl |
| 8 | Ukendt runtime/provider giver fejl |
| 9 | Manglende runtime binary giver fejl |
| 10 | OpenRouter secret indgår ikke i command object eller shell-string |
| 11 | Renderer shell-quoter værdier sikkert |
| 12 | `use_machine_profile` default er 0 for alle eksisterende flows |

---

## 14. Fremtidig udvidelse (Fase 2B, ikke nu)

Flow-role overrides så samme rolle kan bruge forskellig model i forskellige flows:

```sql
ALTER TABLE bridge_flow_steps ADD COLUMN runtime_override TEXT;
ALTER TABLE bridge_flow_steps ADD COLUMN provider_override TEXT;
ALTER TABLE bridge_flow_steps ADD COLUMN model_override TEXT;
```

Resolving:
```python
runtime = step.runtime_override or role.default_runtime
provider = step.provider_override or role.default_provider
model = step.model_override or role.default_model
```

---

## 15. Filoversigt

| Fil | Handling |
|------|----------|
| `scripts/init_db.py` | **Opdater** — nye kolonner + seed data for default-felter |
| `scripts/bridgeV002/start_coding.py` | **Opdater** — brug `build_start_command()` når `use_machine_profile=1` |
| `scripts/bridgeV002/command_builder.py` | **Ny** — `build_start_command()` + 5 builders + renderer |
| `app.py` | **Opdater** — API endpoints for nye felter (allerede delvist understøttet) |
| `static/js/dpmtf-app.js` | **Opdater** — flow checkbox + rolle dropdowns |
| `docs/governance-templates-v2/11_SCOPE.md` | **Opdater** |
| `docs/governance-templates-v2/20_GATES.md` | **Opdater** |
