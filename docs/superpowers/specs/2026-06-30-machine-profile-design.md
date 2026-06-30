# Machine Profile — Portabelt Setup-lag til DPMtF

> **Dato:** 2026-06-30
> **Status:** Design godkendt — afventer implementeringsplan
> **Fase:** 1 af 3 — Machine Profile + System Setup UI

---

## 1. Problem

DPMtF er hardcodet til én maskine ("AI-PC"). Ved kopiering til en anden maskine knækker:

- Absolutte stier i `dpmtf.ini`, `.env`, `bridge_flow_steps.deliverable_dir`
- Runtime-kommandoer i `bridge_roles.start_cmd_suffix` (20 roller)
- CUDA devices, Ollama endpoint, OpenCode config stier
- Modelnavne og provider-konfiguration spredt over database og scripts

**Mål:** Separér "DPMtF Core" (projektlogik) fra "Machine Profile" (maskindetaljer) så samme kodebase kan køre på AI-PC, Mac Neo, Son PC, remote VPS — med forskellige providers og modeller.

---

## 2. Arkitektur

### 2.1 Tre konfigurationslag

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

### 2.2 Princip

- **Flows og roller må kun referere til logiske felter** — aldrig stier, kommandoer eller maskindetaljer
- **Machine Profile oversætter logiske felter til konkrete værdier** — f.eks. `runtime: "claude"` → `/home/svend/.npm-global/bin/claude`
- **Eksisterende config forbliver urørt i Fase 1** — Machine Profile er et nyt lag, ikke en erstatning

### 2.3 Dataflow

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
Valideringsmotor: paths → porte → secrets → tmux → ollama → binaries
        │
        ▼
Response: { checks: [{name, status, message}], summary: {passed, warnings, failed} }
```

---

## 3. Machine Profile filformat

### 3.1 Filstruktur

```
profiles/
├── machine.local.example.json   ← committet skabelon
├── machine.ai-pc.json           ← git-ignored
├── machine.mac-neo.json         ← git-ignored
├── machine.son-pc.json          ← git-ignored
└── machine.remote-vps.json      ← git-ignored
```

Aktiv profil vælges via `.env`:
```
DPMTF_MACHINE_PROFILE=machine.ai-pc.json
```

Fallback: `machine.local.json` hvis env variabel ikke er sat.

### 3.2 Format — `machine.local.example.json`

```json
{
  "name": "AI-PC",
  "description": "Primary development machine — local Ollama + OpenCode",
  "paths": {
    "project_root": "/home/svend/DPMtF-WebUI",
    "bridge_dir": "/home/svend/flows",
    "trade_inbox": "/home/svend/trade-ui/inbox/pending",
    "log_dir": "/home/svend/DPMtF-WebUI/logs",
    "exports_dir": "/home/svend/DPMtF-WebUI/exports"
  },
  "binaries": {
    "claude": "/home/svend/.npm-global/bin/claude",
    "opencode": "/home/svend/.opencode/bin/opencode",
    "freebuff": "/home/svend/.local/bin/freebuff",
    "python": "python3",
    "tmux": "tmux",
    "ollama": "ollama"
  },
  "runtimes": {
    "claude": {
      "binary": "/home/svend/.npm-global/bin/claude",
      "env": {
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "65536"
      }
    },
    "opencode": {
      "binary": "/home/svend/.opencode/bin/opencode",
      "config_base": "$HOME/.config/opencode-roles"
    },
    "freebuff": {
      "binary": "/home/svend/.local/bin/freebuff"
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
    },
    "freebuff": {
      "available": true,
      "binary": "freebuff",
      "models": ["Freebuf"]
    }
  },
  "ports": {
    "app": 9130,
    "expected_children": {
      "ENO": 9131,
      "ai-pc-resource-webui-v3": 9123
    }
  },
  "checks": {
    "required_paths": ["project_root", "bridge_dir"],
    "required_binaries": ["tmux", "python"],
    "required_models": [],
    "required_ports": ["app"],
    "required_secrets": []
  }
}
```

### 3.3 Provider-typer

Fra databasen er 5 provider-typer i brug:

| # | Type | Eksempel model | Runtime | Hvordan |
|---|------|---------------|---------|---------|
| 1 | `local_ollama` | `qwen3.6:35b-a3b-64k` | `claude` | `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN=ollama` |
| 2 | `cloud_ollama` | `deepseek-v4-pro:cloud` | `claude` | Samme endpoint, anden model |
| 3 | `openrouter` | `openrouter/z-ai/glm-5.2` | `opencode` | `OPENROUTER_API_KEY` |
| 4 | `anthropic_direct` | — | `opencode` | `ANTHROPIC_API_KEY` |
| 5 | `freebuff` | `Freebuf` | `freebuff` | Custom CLI |

### 3.4 Rolle → Kommando oversættelse (Fase 2, ikke nu)

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

## 4. System Setup UI

### 4.1 Panelstruktur

Nyt panel under "Setup" med disse sektioner:

| Sektion | Indhold |
|---------|---------|
| **Machine Profile** | Aktiv profil navn, skift profil (fremtidig), profil metadata |
| **Model Providers** | Hver provider med ✅/❌ + tilgængelige modeller |
| **Role Runtime Config** | Hver runtime binary med ✅/❌ status |
| **Path Checks** | ✅/⚠️/❌ for hver sti i `paths` |
| **Port Checks** | ✅/❌ for hver port i `ports` |
| **Secrets Check** | ✅/⚠️ for hver env variabel i providers |
| **Tmux Session Check** | Kørende sessioner, forventede sessioner |
| **Ollama Model Check** | Pulled/missing for hver model i `providers.*.models` |
| **Migration** | Export/import Machine Profile (fremtidig) |

### 4.2 Visning

Hver check vises med status-ikon og besked:

```
✅ project_root        /home/svend/DPMtF-WebUI
✅ bridge_dir          /home/svend/flows
✅ trade_inbox         /home/svend/trade-ui/inbox/pending
✅ claude binary       /home/svend/.npm-global/bin/claude
✅ opencode binary     /home/svend/.opencode/bin/opencode
✅ Ollama reachable    http://127.0.0.1:11434
✅ API key             OPENROUTER_API_KEY found
✅ tmux installed      tmux 3.4
⚠️  Model              qwen3.6:27b-q4_K_M not pulled
❌ Port 9131           ENO not running
```

### 4.3 Interaktion

- "Kør alle checks" knap øverst
- Individuelle "Kør" knapper per sektion
- `data-slot` attributter for i18n
- Maskinens navn vises øverst: `Maskine: AI-PC (machine.ai-pc.json)`
- Hvis ingen Machine Profile findes: "Ingen Machine Profile konfigureret. Opret profiles/machine.local.json"

### 4.4 API endpoints

| Method | Path | Beskrivelse |
|--------|------|-------------|
| `GET` | `/api/system/healthcheck` | Kører alle aktive checks fra `checks` sektionen |
| `GET` | `/api/system/healthcheck/{section}` | Kører én sektion (paths, ports, secrets, tmux, ollama, binaries) |
| `GET` | `/api/system/machine-profile` | Returnerer nuværende profil metadata (navn, beskrivelse, providers) |

Ingen POST/PUT i Fase 1 — Machine Profile redigeres manuelt i filen.

---

## 5. Migreringssti

### 5.1 Fase 1 — Machine Profile + System Setup (denne fase)

**Varighed:** 2-3 uger

| Trin | Beskrivelse |
|------|-------------|
| 1.1 | Opret `profiles/` mappe + `machine.local.example.json` |
| 1.2 | Tilføj `profiles/*.json` til `.gitignore` (undtagen `.example`) |
| 1.3 | `config.get_machine_profile()` — indlæser aktiv profil, returnerer `{}` hvis ingen |
| 1.4 | `GET /api/system/healthcheck` — valideringsmotor |
| 1.5 | `GET /api/system/machine-profile` — profil metadata |
| 1.6 | System Setup panel i frontend |
| 1.7 | i18n labels for alle nye UI-elementer |
| 1.8 | Opdater `11_SCOPE.md`, `20_GATES.md`, `17_DATABASE.md` |

**Intet eksisterende røres.** Alle flows, roller, scripts kører uændret.

### 5.2 Fase 2 — Role Runtime Config (næste fase)

1. `bridge_roles` får nye kolonner: `provider`, `runtime` (logiske felter)
2. `start_cmd_suffix` forbliver — `build_start_command()` bruger Machine Profile når logiske felter er udfyldt
3. `use_machine_profile` boolean på `bridge_flows`
4. Per-flow aktivering — tester ét flow ad gangen
5. Når alle flows er migreret: fjern `start_cmd_suffix` og parameteren

### 5.3 Fase 3 — Deliverable Dir afkobling

`bridge_flow_steps.deliverable_dir` erstattes af relative stier der resolves mod Machine Profile's `paths.bridge_dir`.

### 5.4 Bagudkompatibilitet

```python
def get_machine_profile():
    """Indlæser aktiv Machine Profile, eller returnerer tom dict."""
    profile_name = os.environ.get("DPMTF_MACHINE_PROFILE", "machine.local.json")
    profile_path = os.path.join(get_project_root(), "profiles", profile_name)
    if os.path.exists(profile_path):
        with open(profile_path) as f:
            return json.load(f)
    return {}  # Tom — alle Machine Profile features deaktiveret
```

- Ingen Machine Profile fil → alle nye features usynlige, alt eksisterende kører som før
- Machine Profile fil findes men er tom/partiel → healthcheck viser warnings, ikke fejl
- Eksisterende `config.py` getters forbliver uændrede

---

## 6. Governance opdateringer

### 6.1 `11_SCOPE.md` — tilføjelse

```markdown
## Aktivt scope — Machine Profile (Fase 1)

### Inden for scope
- `profiles/` mappe med machine profiles (JSON)
- `machine.local.example.json` committet skabelon
- `config.get_machine_profile()` getter
- `GET /api/system/healthcheck` endpoint
- `GET /api/system/machine-profile` endpoint
- System Setup panel i frontend (nyt panel under Setup)
- i18n labels for alle nye UI-elementer

### Uden for scope (fase 2+)
- Ændring af `bridge_roles` skema eller data
- Ændring af `bridge_flow_steps` skema eller data
- Ændring af `start_cmd_suffix` logik
- `use_machine_profile` parameter på flows
- Automatisk kommando-bygning fra Machine Profile
```

### 6.2 `20_GATES.md` — tilføjelse

```markdown
## Gate M1: Machine Profile eksisterer
- Spørgsmål: Findes `profiles/<aktiv>.json`?
- Hvis NEJ: System Setup viser "Ingen Machine Profile".
  Alle Machine Profile features deaktiveret.
  Eksisterende funktionalitet upåvirket.

## Gate M2: Kritiske stier valideret
- Spørgsmål: Eksisterer `paths.project_root` og `paths.bridge_dir`?
- Hvis NEJ: App starter men viser ⚠️ i System Setup.
  Healthcheck returnerer warnings.

## Gate M3: Mindst én provider tilgængelig
- Spørgsmål: Er mindst én provider `available: true`?
- Hvis NEJ: System Setup viser ⚠️.
  Flows kan ikke startes før en provider er konfigureret.
```

### 6.3 `17_DATABASE.md` — tilføjelse

```markdown
## Machine Profile (filsystem)

Machine Profiles gemmes som JSON-filer i `profiles/` — ikke i databasen.
Årsag: Machine Profile skal kunne læses før databasen er tilgængelig.

Aktiv profil vælges via `DPMTF_MACHINE_PROFILE` i `.env`.
```

---

## 7. Maskinspecifikke hardcoding — nuværende tilstand

Oversigt over hvad der findes i dag og hvornår det adresseres:

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

## 8. Filoversigt

| Fil | Handling |
|------|----------|
| `profiles/machine.local.example.json` | **Ny** — committet skabelon |
| `profiles/.gitkeep` | **Ny** — holder mappen i git |
| `.gitignore` | **Opdater** — tilføj `profiles/*.json` undtagen `.example` |
| `config.py` | **Opdater** — ny `get_machine_profile()` getter |
| `app.py` | **Opdater** — 2-3 nye endpoints |
| `static/js/dpmtf-app.js` | **Opdater** — System Setup panel |
| `scripts/init_db.py` | **Opdater** — seed data for nye UI labels |
| `docs/governance-templates-v2/11_SCOPE.md` | **Opdater** |
| `docs/governance-templates-v2/20_GATES.md` | **Opdater** |
| `docs/governance-templates-v2/17_DATABASE.md` | **Opdater** |
