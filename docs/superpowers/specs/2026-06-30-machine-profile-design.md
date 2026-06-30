# Machine Profile — Portabelt Setup-lag til DPMtF

> **Dato:** 2026-06-30
> **Status:** Design godkendt — afventer implementeringsplan
> **Fase:** 1 af 3 — Machine Profile + System Setup UI

---

## 1. Formål

DPMtF skal gøres mere portabelt ved at indføre et nyt Machine Profile-lag, som adskiller maskinspecifik konfiguration fra DPMtF Core.

Målet er **ikke** at migrere eksisterende flows, roller eller startkommandoer i denne fase. Målet er kun at skabe et sikkert, read-only setup-lag, som kan vise om den aktuelle maskine er korrekt konfigureret.

---

## 2. Grundregel

Flows, roller og prompt-sekvenser må ikke kende maskinspecifikke detaljer.

De må på sigt kun referere til logiske felter som:

```
runtime
provider
model
role_key
flow_key
```

Machine Profile oversætter senere disse logiske felter til konkrete værdier som:

```
paths
binaries
ports
provider endpoints
model availability
env keys
tmux capability
ollama capability
```

I Fase 1 må Machine Profile kun bruges til visning og healthcheck.

---

## 3. Arkitektur

### 3.1 Tre konfigurationslag

```
┌──────────────────────────────────────────────┐
│                  .env                         │
│  Secrets: API keys, tokens, passwords        │
│  Infra: DPMTF_BRIDGE_DIR, DPMTF_MACHINE_PROFILE │
└──────────────────────────────────────────────┘
                      │
┌──────────────────────────────────────────────┐
│            Machine Profile                    │
│  profiles/machine.<name>.json                 │
│  Stier, binaries, GPU, providers, modeller   │
│  Varierer mellem maskiner                     │
└──────────────────────────────────────────────┘
                      │
┌──────────────────────────────────────────────┐
│            DPMtF Core                         │
│  dpmtf.ini + config.py                        │
│  Porte, locales, projektnavne, governance     │
│  Ens på alle maskiner                         │
└──────────────────────────────────────────────┘
```

### 3.2 Dataflow

```
Frontend "System Setup" panel
        │
        ▼
GET /api/system/healthcheck
        │
        ▼
config.get_machine_profile()
        │
        ▼
profiles/machine.ai-pc.json  ←── valgt via DPMTF_MACHINE_PROFILE i .env
        │
        ▼
Valideringsmotor: profile → paths → binaries → ports → secrets → tmux → ollama → providers
        │
        ▼
Response: { profile, summary, checks: [{section, name, status, severity, message}] }
```

---

## 4. Filstruktur

### 4.1 Mappe og filer

```
profiles/
  .gitkeep
  machine.local.example.json
  machine.ai-pc.example.json
```

Tilføj til `.gitignore`:

```gitignore
profiles/*.json
!profiles/*.example.json
```

Formål:

| Fil | Beskrivelse |
|-----|-------------|
| `machine.local.example.json` | Neutral template — committet |
| `machine.ai-pc.example.json` | Realistisk eksempel baseret på AI-PC — committet |
| `machine.<name>.json` | Lokal, git-ignored profil |

### 4.2 Aktiv profil

Vælges via `.env`:

```env
DPMTF_MACHINE_PROFILE=machine.ai-pc.json
```

Fallback hvis env ikke er sat: `machine.local.json`

Hvis ingen profil findes, skal appen stadig starte og eksisterende funktionalitet fortsætte uændret.

---

## 5. Machine Profile filformat

### 5.1 `schema_version`

Alle Machine Profiles skal have:

```json
{
  "schema_version": 1,
  "name": "AI-PC"
}
```

Healthcheck skal kunne advare hvis profilens `schema_version` ikke matcher appens forventede version:

```
⚠️ Machine Profile schema_version=1, expected=2
```

Forventet version i Fase 1: **1**

### 5.2 Komplet format — `machine.local.example.json`

```json
{
  "schema_version": 1,
  "name": "AI-PC",
  "description": "Primary development machine — local Ollama + OpenCode",

  "capabilities": {
    "tmux": true,
    "cuda": true,
    "local_ollama": true,
    "cloud_models": true,
    "telegram_bridge": true,
    "cron": true
  },

  "paths": {
    "project_root": "/home/svend/DPMtF-WebUI",
    "bridge_dir": "/home/svend/flows",
    "trade_inbox": "/home/svend/trade-ui/inbox/pending",
    "log_dir": "/home/svend/DPMtF-WebUI/logs",
    "exports_dir": "/home/svend/DPMtF-WebUI/exports"
  },

  "binaries": {
    "python": "python3",
    "tmux": "tmux",
    "ollama": "ollama",
    "claude": "/home/svend/.npm-global/bin/claude",
    "opencode": "/home/svend/.opencode/bin/opencode",
    "freebuff": "/home/svend/.local/bin/freebuff"
  },

  "runtimes": {
    "claude": {
      "binary_ref": "claude",
      "default_env": {
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "65536"
      }
    },
    "opencode": {
      "binary_ref": "opencode",
      "config_base": "$HOME/.config/opencode-roles"
    },
    "freebuff": {
      "binary_ref": "freebuff"
    }
  },

  "providers": {
    "local_ollama": {
      "available": true,
      "endpoint": "http://127.0.0.1:11434",
      "auth_token": "ollama",
      "models": [
        "qwen3.6:35b-a3b-64k",
        "qwen3.6:27b-q4_K_M",
        "qwen3.6:35b-a3b",
        "qwen3.6-27b-coder:latest"
      ]
    },
    "cloud_ollama": {
      "available": true,
      "endpoint": "http://127.0.0.1:11434",
      "auth_token": "ollama",
      "models": [
        "deepseek-v4-pro:cloud"
      ]
    },
    "openrouter": {
      "available": true,
      "env_key": "OPENROUTER_API_KEY",
      "models": [
        "z-ai/glm-5.2",
        "minimax/MiniMax-M3",
        "deepseek/deepseek-v4-pro"
      ]
    },
    "anthropic_direct": {
      "available": false,
      "env_key": "ANTHROPIC_API_KEY",
      "models": []
    }
  },

  "ports": {
    "app": 9130,
    "ollama": 11434,
    "resource_webui": 9121,
    "expected_children": {
      "ENO": 9131,
      "ai-pc-resource-webui-v3": 9123
    }
  },

  "checks": {
    "required_paths": [
      "project_root",
      "bridge_dir"
    ],
    "required_binaries": [
      "python",
      "tmux"
    ],
    "required_ports": [
      "app"
    ],
    "required_secrets": [],
    "required_providers": []
  }
}
```

### 5.3 Runtimes og providers — adskillelse

Definition:

| Begreb | Betydning | Eksempel |
|--------|-----------|----------|
| `runtime` | Hvilket program starter rollen | `claude`, `opencode`, `freebuff` |
| `provider` | Hvor modellen kommer fra | `local_ollama`, `openrouter` |
| `model` | Hvilken model der bruges | `qwen3.6:27b-q4_K_M` |

Eksempler på kombinationer:

```
runtime: claude       provider: local_ollama    model: qwen3.6:27b-q4_K_M
runtime: opencode     provider: openrouter      model: z-ai/glm-5.2
runtime: freebuff     provider: none            model: freebuff-default
```

**Freebuff** er en runtime, ikke en provider. Den har sin egen CLI og model-håndtering. Den ligger derfor under `runtimes`, ikke under `providers`.

### 5.4 Provider-typer i brug

| # | Provider | Eksempel model | Runtime | Hvordan |
|---|----------|---------------|---------|---------|
| 1 | `local_ollama` | `qwen3.6:35b-a3b-64k` | `claude` | `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN=ollama` |
| 2 | `cloud_ollama` | `deepseek-v4-pro:cloud` | `claude` | Samme endpoint, anden model |
| 3 | `openrouter` | `openrouter/z-ai/glm-5.2` | `opencode` | `OPENROUTER_API_KEY` |
| 4 | `anthropic_direct` | — | `opencode` | `ANTHROPIC_API_KEY` |

### 5.5 Rolle → Kommando oversættelse (Fase 2, ikke nu)

Nuværende (maskinspecifik):
```
opencode --model openrouter/z-ai/glm-5.2
```

Fremtidig (logiske felter på rollen):
```json
{
  "provider": "openrouter",
  "model": "z-ai/glm-5.2",
  "runtime": "opencode"
}
```

Machine Profile oversætter til konkret kommando.

---

## 6. Healthcheck

### 6.1 Response-format

```json
{
  "profile": {
    "name": "AI-PC",
    "filename": "machine.ai-pc.json",
    "schema_version": 1
  },
  "summary": {
    "passed": 8,
    "warnings": 2,
    "failed": 1
  },
  "checks": [
    {
      "section": "paths",
      "name": "project_root",
      "status": "pass",
      "severity": "error",
      "message": "/home/svend/DPMtF-WebUI exists"
    },
    {
      "section": "secrets",
      "name": "OPENROUTER_API_KEY",
      "status": "warning",
      "severity": "warning",
      "message": "Env key not found"
    },
    {
      "section": "ports",
      "name": "ENO",
      "status": "fail",
      "severity": "warning",
      "message": "Port 9131 is not responding"
    }
  ]
}
```

### 6.2 Status og severity

Tilladte `status`-værdier:

| Status | Betydning |
|--------|-----------|
| `pass` | Check bestået |
| `warning` | Problem fundet, ikke kritisk |
| `fail` | Check fejlet |
| `skip` | Check ikke relevant (f.eks. provider deaktiveret) |

Tilladte `severity`-værdier:

| Severity | Betydning |
|----------|-----------|
| `error` | Kan senere blokere start (Fase 2+) |
| `warning` | Vises men blokerer ikke |
| `info` | Kun oplysning |

I Fase 1 må healthcheck **ikke** blokere eksisterende funktionalitet.

### 6.3 Healthcheck-sektioner

#### profile

Checker:
- Aktiv profil valgt
- Profilfil findes
- JSON kan parses
- `schema_version` findes
- `schema_version` matcher forventet version

Hvis ingen profil findes:
```json
{
  "section": "profile",
  "name": "machine_profile",
  "status": "warning",
  "severity": "warning",
  "message": "No Machine Profile configured. Existing functionality is unchanged."
}
```

#### paths

Checker alle paths i `profile.paths`.

Regler:
- `required_paths` mangler eller findes ikke → `fail` / `error`
- Ikke-required paths mangler → `warning` / `warning`
- Paths der findes → `pass` / `info`

#### binaries

Checker binaries i `profile.binaries`.

Regler:
- Hvis værdi er absolut sti: check om fil findes og er executable
- Hvis værdi ikke er absolut sti: brug `shutil.which()`
- `required_binaries` mangler → `fail` / `error`
- Ikke-required binaries mangler → `warning` / `warning`

#### ports

Checker porte i `profile.ports`.

Regler:
- `app`-port: `pass` hvis appen selv svarer
- `ollama`-port: checker endpoint hvis `local_ollama` er enabled
- `expected_children`: må kun give `warning`, ikke `error`

#### secrets

Checker env keys defineret i providers.

Regler:
- Hvis `provider.available=true` og `provider.env_key` findes:
  - env key sat → `pass`
  - env key mangler → `warning`
- Hvis `provider.available=false` → `skip`
- **Secrets må aldrig returneres i API response** — kun found/missing status

#### tmux

Checker kun hvis `capabilities.tmux=true`.

Regler:
- `tmux` binary fundet → `pass`
- `tmux ls` kan køres → `pass`/`warning` afhængigt af resultat
- Ingen tmux sessions → `warning`/`info`, ikke `error`

#### ollama

Checker kun hvis `capabilities.local_ollama=true` eller provider `local_ollama.available=true`.

Regler:
- Endpoint reachable → `pass`
- Endpoint ikke reachable → `warning`/`error` afhængigt af om `local_ollama` er required
- Models i `profile.providers.local_ollama.models`:
  - pulled → `pass`
  - missing → `warning`

I Fase 1 må manglende Ollama-modeller ikke blokere appen.

#### providers

Checker:
- Mindst én provider `available=true`
- Provider har enten `endpoint` eller `env_key` hvor relevant
- `model_count`

Hvis ingen provider er `available` → `warning`. Ikke `error` i Fase 1.

---

## 7. API endpoints

### 7.1 `GET /api/system/machine-profile`

Returnerer kun sikker metadata og summary. Må ikke returnere secrets.

```json
{
  "active_profile": "machine.ai-pc.json",
  "exists": true,
  "name": "AI-PC",
  "description": "Primary development machine — local Ollama + OpenCode",
  "schema_version": 1,
  "capabilities": {
    "tmux": true,
    "cuda": true,
    "local_ollama": true,
    "cloud_models": true
  },
  "providers": {
    "local_ollama": {
      "available": true,
      "model_count": 4
    },
    "openrouter": {
      "available": true,
      "model_count": 3
    }
  }
}
```

### 7.2 `GET /api/system/healthcheck`

Kører alle checks. Sektioner: `profile`, `paths`, `binaries`, `ports`, `secrets`, `tmux`, `ollama`, `providers`.

### 7.3 `GET /api/system/healthcheck/{section}`

Kører én sektion. Tilladte section-værdier: `profile`, `paths`, `binaries`, `ports`, `secrets`, `tmux`, `ollama`, `providers`.

Ukendt section → `400 Bad Request`.

---

## 8. config.py ændringer

Tilføj tre nye getters:

```python
def get_machine_profile():
    """Load active Machine Profile or return empty dict.

    Machine Profile is optional in Phase 1.
    Missing, invalid, or partial profiles must not break existing app startup.
    """

def get_machine_profile_path():
    """Return resolved path to active Machine Profile."""

def get_machine_profile_metadata():
    """Return safe metadata: filename, exists, name, schema_version, description."""
```

Adfærd for `get_machine_profile()`:

1. Læs `DPMTF_MACHINE_PROFILE` fra env
2. Hvis ikke sat, brug `machine.local.json`
3. Find filen i `profiles/`
4. Hvis filen findes og er valid JSON → returnér dict
5. Hvis filen mangler → returnér `{}`
6. Hvis filen er invalid JSON → returnér `{}` og lad healthcheck vise warning

**Vigtigt:** Eksisterende config getters må ikke ændres i Fase 1. Machine Profile må ikke overtage `dpmtf.ini`, `.env` eller eksisterende runtime-logik.

---

## 9. Frontend — System Setup panel

### 9.1 Panelstruktur

Read-only panel under Setup. Sektioner:

| Sektion | Indhold |
|---------|---------|
| **Machine Profile** | Aktiv profil, schema version, capabilities |
| **Model Providers** | Hver provider med ✅/❌ + model count |
| **Role Runtime Config** | Hver runtime binary med ✅/❌ status |
| **Path Checks** | ✅/⚠️/❌ for hver sti |
| **Port Checks** | ✅/❌ for hver port |
| **Secrets Check** | ✅/⚠️ for hver env variabel |
| **Tmux Session Check** | Kørende sessioner |
| **Ollama Model Check** | Pulled/missing for hver model |
| **Migration** | Placeholder — fremtidig export/import |

### 9.2 Knapper

```
Kør alle checks
Kør paths
Kør binaries
Kør ports
Kør secrets
Kør tmux
Kør ollama
Kør providers
```

### 9.3 Visning

Øverst:

```
Maskine: AI-PC
Profil: machine.ai-pc.json
Schema: v1
Status: 8 passed / 2 warnings / 1 failed
```

Eksempel:

```
✅ project_root        /home/svend/DPMtF-WebUI
✅ bridge_dir          /home/svend/flows
✅ tmux                tmux found
✅ python              python3 found
✅ Ollama reachable    http://127.0.0.1:11434
✅ API key             OPENROUTER_API_KEY found
⚠️ Model              qwen3.6:27b-q4_K_M not pulled
⚠️ Port 9131          ENO not running
```

### 9.4 Ingen profil

Hvis ingen Machine Profile findes:

```
Ingen Machine Profile konfigureret.
Opret profiles/machine.local.json eller sæt DPMTF_MACHINE_PROFILE i .env.
Eksisterende DPMtF funktionalitet er uændret.
```

---

## 10. i18n

Alle nye UI-tekster skal have stabile labels med `data-slot`:

```
system_setup_title
system_setup_run_all_checks
system_setup_machine_profile
system_setup_model_providers
system_setup_runtime_config
system_setup_path_checks
system_setup_port_checks
system_setup_secrets_check
system_setup_tmux_check
system_setup_ollama_check
system_setup_migration
system_setup_no_profile
system_setup_existing_unchanged
```

---

## 11. Faseopdeling

### Fase 1A — Filesystem og config

```
profiles/.gitkeep
profiles/machine.local.example.json
profiles/machine.ai-pc.example.json
.gitignore update
config.get_machine_profile()
config.get_machine_profile_path()
config.get_machine_profile_metadata()
```

Ingen frontend. Ingen API endpoints.

### Fase 1B — Healthcheck backend

```
healthcheck engine (alle 8 sektioner)
GET /api/system/machine-profile
GET /api/system/healthcheck
GET /api/system/healthcheck/{section}
```

Ingen runtime-ændringer.

### Fase 1C — Frontend System Setup

```
Read-only System Setup panel
Kør alle checks
Kør enkelt sektion
Status summary
Check list rendering
No profile state
```

### Fase 1D — i18n og governance

```
i18n labels (seed data i init_db.py)
11_SCOPE.md update
20_GATES.md update
17_DATABASE.md update
```

---

## 12. Testkrav

Minimum tests:

| # | Test |
|---|------|
| 1 | App starter uden `profiles/` mappe |
| 2 | App starter uden Machine Profile fil |
| 3 | Invalid JSON i Machine Profile crasher ikke appen |
| 4 | `GET /api/system/machine-profile` returnerer `exists=false` hvis fil mangler |
| 5 | `GET /api/system/healthcheck` returnerer warning hvis fil mangler |
| 6 | Path check markerer eksisterende sti som `pass` |
| 7 | Path check markerer manglende required path som `fail`/`error` |
| 8 | Binary check virker både for absolut sti og PATH binary |
| 9 | Secrets check returnerer kun `found`/`missing` — aldrig secret value |
| 10 | Ukendt healthcheck section returnerer `400` |

Manuel verification:

```bash
curl -s http://127.0.0.1:9130/api/system/machine-profile | python3 -m json.tool
curl -s http://127.0.0.1:9130/api/system/healthcheck | python3 -m json.tool
curl -s http://127.0.0.1:9130/api/system/healthcheck/paths | python3 -m json.tool
```

---

## 13. Stram stopregel

Fase 1 skal stoppe før nogen af disse ændres:

```
bridge_roles schema
bridge_flow_steps schema
start_cmd_suffix
role start/stop logic
tmux injection logic
deliverable_dir resolution
flow execution logic
```

Hvis implementeringen får behov for disse ændringer, skal arbejdet stoppes og rapporteres som Fase 2-scope.

---

## 14. Governance opdateringer

### 14.1 `11_SCOPE.md` — tilføjelse

```markdown
## Aktivt scope — Machine Profile Fase 1

### Inden for scope

- `profiles/` mappe
- `profiles/.gitkeep`
- `profiles/machine.local.example.json`
- `profiles/machine.ai-pc.example.json`
- `.gitignore` opdatering for lokale Machine Profiles
- `config.get_machine_profile()`
- `config.get_machine_profile_path()`
- `config.get_machine_profile_metadata()`
- `GET /api/system/machine-profile`
- `GET /api/system/healthcheck`
- `GET /api/system/healthcheck/{section}`
- Read-only System Setup panel i frontend
- i18n labels for nye System Setup UI-elementer

### Uden for scope

- Ændring af `bridge_roles` schema
- Ændring af `bridge_flow_steps` schema
- Ændring af `bridge_roles.start_cmd_suffix`
- Automatisk kommando-bygning fra Machine Profile
- `use_machine_profile` på flows
- Migration af eksisterende roller
- Migration af deliverable_dir
- Start/stop af roller via Machine Profile
- Redigering af Machine Profile fra UI
```

### 14.2 `20_GATES.md` — tilføjelse

```markdown
## Gate M1: Machine Profile optional

Spørgsmål: Findes aktiv Machine Profile?

Hvis nej:
- App må stadig starte
- Eksisterende funktionalitet må ikke påvirkes
- System Setup viser warning
- Machine Profile features behandles som deaktiveret

## Gate M2: Kritiske stier

Spørgsmål: Findes required paths fra Machine Profile?

Minimum:
- `paths.project_root`
- `paths.bridge_dir`

Hvis nej:
- Healthcheck viser fail/error
- Fase 1 må stadig ikke blokere eksisterende app-start

## Gate M3: Required binaries

Spørgsmål: Findes required binaries?

Minimum:
- `python`
- `tmux`

Hvis nej:
- Healthcheck viser fail/error
- Fase 1 må stadig ikke ændre eksisterende runtime-adfærd

## Gate M4: Provider availability

Spørgsmål: Er mindst én provider available=true?

Hvis nej:
- Healthcheck viser warning
- Ingen eksisterende flows må ændres eller blokeres i Fase 1

## Gate M5: No runtime migration in Phase 1

Spørgsmål: Ændrer implementationen eksisterende flow-, rolle- eller startkommando-logik?

Hvis ja:
- Stop
- Det er Fase 2+ scope creep
```

### 14.3 `17_DATABASE.md` — tilføjelse

```markdown
## Machine Profile

Machine Profiles gemmes som JSON-filer i `profiles/`.

De gemmes ikke i databasen i Fase 1.

Årsager:
- Machine Profile skal kunne læses før databaseafhængig runtime-logik
- Machine Profile er maskinspecifik
- Lokale profiler skal kunne være git-ignored
- Secrets må ikke gemmes i Machine Profile

Aktiv profil vælges via `.env`:

`DPMTF_MACHINE_PROFILE=machine.ai-pc.json`

Machine Profile må i Fase 1 kun bruges til read-only healthcheck og System Setup-visning.
```

---

## 15. Maskinspecifikke hardcoding — nuværende tilstand

| Lag | Antal | Eksempel | Løses i |
|-----|-------|----------|---------|
| `dpmtf.ini` | 2 | `project_root`, `bridge_dir` | Fase 1 (spejles i Machine Profile) |
| `.env` | 1 | `DPMTF_BRIDGE_DIR` | Fase 1 (spejles i Machine Profile) |
| `config.py` fallbacks | 1 | `get_trade_inbox_dir()` | Fase 1 (spejles i Machine Profile) |
| `bridge_roles.start_cmd_suffix` | 20 roller | `OPENCODE_CONFIG_DIR`, `ANTHROPIC_BASE_URL` | Fase 2 |
| `bridge_flow_steps.deliverable_dir` | 20 steps | `/home/svend/flows/...` | Fase 3 |
| Cronjob scripts | 2 | `PROJECT_ROOT` | Fase 1 (allerede delvist løst) |
| Crontab | 2 | Absolutte script-stier | Manuel (crontab er altid maskinspecifik) |

---

## 16. Filoversigt

| Fil | Handling |
|------|----------|
| `profiles/.gitkeep` | **Ny** |
| `profiles/machine.local.example.json` | **Ny** — committet neutral skabelon |
| `profiles/machine.ai-pc.example.json` | **Ny** — committet realistisk eksempel |
| `.gitignore` | **Opdater** — `profiles/*.json` undtagen `*.example.json` |
| `config.py` | **Opdater** — 3 nye getters |
| `app.py` | **Opdater** — 3 nye endpoints |
| `static/js/dpmtf-app.js` | **Opdater** — System Setup panel |
| `scripts/init_db.py` | **Opdater** — seed data for nye UI labels |
| `docs/governance-templates-v2/11_SCOPE.md` | **Opdater** |
| `docs/governance-templates-v2/20_GATES.md` | **Opdater** |
| `docs/governance-templates-v2/17_DATABASE.md` | **Opdater** |

---

## 17. Konklusion

Denne ændring indfører Machine Profile som et sikkert, valgfrit og read-only konfigurationslag.

Fase 1 giver:

- Portabilitetsgrundlag
- Synlig System Setup-status
- Healthcheck af profile, paths, binaries, ports, secrets, tmux, ollama og providers
- Ingen risiko for eksisterende flows
- Ingen runtime-migration endnu

Fase 2 kan derefter bruge Machine Profile til Role Runtime Config og dynamisk kommando-bygning, men det er eksplicit uden for denne opgave.
