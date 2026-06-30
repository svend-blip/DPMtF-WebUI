# Machine Profile Fase 1 — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Indfør Machine Profile som et sikkert, valgfrit, read-only konfigurationslag med healthcheck og System Setup UI.

**Architecture:** Machine Profile er JSON-filer i `profiles/` mappen. `config.py` får 3 nye getters til at indlæse profilen. `app.py` får 3 nye endpoints til healthcheck og profilmetadata. Frontend får et nyt read-only System Setup panel under Setup. Intet eksisterende røres — alle flows, roller og scripts kører uændret videre.

**Tech Stack:** Python 3 (FastAPI), JavaScript (vanilla), SQLite (kun til i18n labels), JSON (Machine Profile filer)

## Global Constraints

- **Stopregel (skærpet):** Må IKKE ændre: `bridge_roles` schema, `bridge_flow_steps` schema, `start_cmd_suffix`, tmux injection logic, deliverable_dir resolution, flow execution logic, role start/stop logic, dynamic command building, `use_machine_profile` flag. Kun read-only GET endpoints. Tilladte filer: `profiles/`, `.gitignore`, `config.py`, `scripts/system_healthcheck.py`, `app.py`, `static/js/dpmtf-app.js`, `templates/index.html`, `scripts/init_db.py`, governance docs.
- Machine Profile er valgfri — app skal starte uden den
- Tre tilstande skal kunne skelnes: (1) profilfil mangler, (2) profilfil findes men JSON er invalid, (3) profilfil findes og er valid men tom/partiel
- Invalid JSON i Machine Profile må ikke crashe appen — `get_machine_profile()` returnerer `{}`, metadata returnerer `parse_error`
- Secrets må aldrig returneres i API responses — kun `found`/`not found`/`skipped`
- Alle frontend-tekster skal bruge `lbl(key, fallback)` — danske fallback-tekster
- Ingen `innerHTML` til dynamisk indhold — brug `createElement()`/`textContent`/`appendChild()`. Brug IKKE `escapeHtml()` med `textContent` (unødvendigt)
- Python: `python3 -m py_compile` før færdigmeldelse
- Shell: `bash -n` før færdigmeldelse
- `schema_version` forventet: 1

---

## Fase 1A — Filesystem og config

### Task 1: Opret profiles/ mappe og example-filer

**Files:**
- Create: `profiles/.gitkeep`
- Create: `profiles/machine.local.example.json`
- Create: `profiles/machine.ai-pc.example.json`

**Interfaces:**
- Produces: `profiles/` directory with two committed example files

- [ ] **Step 1: Opret mappe og .gitkeep**

```bash
mkdir -p /home/svend/DPMtF-WebUI/profiles
touch /home/svend/DPMtF-WebUI/profiles/.gitkeep
```

- [ ] **Step 2: Skriv machine.local.example.json**

```json
{
  "schema_version": 1,
  "name": "My Machine",
  "description": "Machine Profile — copy to machine.<name>.json and customize",

  "capabilities": {
    "tmux": true,
    "cuda": false,
    "local_ollama": false,
    "cloud_models": false,
    "telegram_bridge": false,
    "cron": false
  },

  "paths": {
    "project_root": "/home/user/DPMtF-WebUI",
    "bridge_dir": "/home/user/flows",
    "trade_inbox": "/home/user/trade-ui/inbox/pending",
    "log_dir": "/home/user/DPMtF-WebUI/logs",
    "exports_dir": "/home/user/DPMtF-WebUI/exports"
  },

  "binaries": {
    "python": "python3",
    "tmux": "tmux",
    "ollama": "ollama",
    "claude": "claude",
    "opencode": "opencode",
    "freebuff": "freebuff"
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
      "available": false,
      "endpoint": "http://127.0.0.1:11434",
      "auth_token": "ollama",
      "models": []
    },
    "cloud_ollama": {
      "available": false,
      "endpoint": "http://127.0.0.1:11434",
      "auth_token": "ollama",
      "models": []
    },
    "openrouter": {
      "available": false,
      "env_key": "OPENROUTER_API_KEY",
      "models": []
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
    "expected_children": {}
  },

  "checks": {
    "required_paths": ["project_root", "bridge_dir"],
    "required_binaries": ["python", "tmux"],
    "required_ports": ["app"],
    "required_secrets": [],
    "required_providers": []
  }
}
```

- [ ] **Step 3: Skriv machine.ai-pc.example.json**

Kopiér `machine.local.example.json` og udfyld med AI-PC's faktiske værdier (stier, modeller, providers fra den nuværende database).

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
    "required_paths": ["project_root", "bridge_dir"],
    "required_binaries": ["python", "tmux"],
    "required_ports": ["app"],
    "required_secrets": [],
    "required_providers": []
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add profiles/.gitkeep profiles/machine.local.example.json profiles/machine.ai-pc.example.json
git commit -m "[trade] Opret profiles/ mappe med Machine Profile example-filer"
```

---

### Task 2: Opdater .gitignore

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Produces: Lokale `profiles/*.json` filer ignoreres af git, example-filer forbliver tracked

- [ ] **Step 1: Tilføj profiles regel til .gitignore**

Tilføj disse linjer til slutningen af `.gitignore`:

```gitignore
# Machine Profiles — local copies are git-ignored
profiles/*.json
!profiles/*.example.json
```

- [ ] **Step 2: Verificer at example-filer stadig er tracked**

```bash
git status --short profiles/
```

Forventet: `machine.local.example.json` og `machine.ai-pc.example.json` vises som nye filer (tracked fra Task 1).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "[trade] Git-ignore lokale Machine Profiles, behold example-filer"
```

---

### Task 3: Tilføj config.py getters

**Files:**
- Modify: `config.py`

**Interfaces:**
- Produces:
  - `get_machine_profile() -> dict` — indlæser aktiv profil, returnerer `{}` hvis ingen
  - `get_machine_profile_path() -> str` — returnerer resolved sti til aktiv profil
  - `get_machine_profile_metadata() -> dict` — returnerer sikker metadata

- [ ] **Step 1: Tilføj get_machine_profile_path()**

Indsæt efter `get_trade_inbox_dir()` i `config.py`:

```python
def get_machine_profile_path() -> str:
    """Return resolved path to active Machine Profile.

    Reads DPMTF_MACHINE_PROFILE from env, falls back to machine.local.json.
    Returns the absolute path whether or not the file exists.
    """
    profile_name = os.environ.get("DPMTF_MACHINE_PROFILE", "machine.local.json")
    return os.path.join(get_project_root(), "profiles", profile_name)
```

- [ ] **Step 2: Tilføj get_machine_profile()**

```python
def get_machine_profile() -> dict:
    """Load active Machine Profile or return empty dict.

    Machine Profile is optional in Phase 1.
    Missing, invalid, or partial profiles must not break existing app startup.

    Returns:
        dict with profile data, or {} if file missing/invalid.
    """
    profile_path = get_machine_profile_path()
    if not os.path.exists(profile_path):
        return {}
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
```

Bemærk: `json` er allerede importeret i `config.py`? Tjek — hvis ikke, tilføj `import json` i toppen.

- [ ] **Step 3: Tilføj get_machine_profile_metadata()**

```python
def get_machine_profile_metadata() -> dict:
    """Return safe metadata about the active Machine Profile.

    Never returns secrets, paths, or raw profile data.
    Safe for exposure via API.
    Distinguishes three states: missing, invalid JSON, valid.

    Returns:
        dict with keys: active_profile, exists, parse_error, name,
                        description, schema_version, capabilities,
                        providers
    """
    profile_path = get_machine_profile_path()
    profile_name = os.environ.get("DPMTF_MACHINE_PROFILE", "machine.local.json")
    exists = os.path.exists(profile_path)

    result = {
        "active_profile": profile_name,
        "exists": exists,
        "parse_error": None,
        "name": None,
        "description": None,
        "schema_version": None,
        "capabilities": {},
        "providers": {},
    }

    if not exists:
        return result

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except json.JSONDecodeError as e:
        result["parse_error"] = str(e)
        return result
    except IOError as e:
        result["parse_error"] = str(e)
        return result

    if not profile:
        return result

    result["name"] = profile.get("name")
    result["description"] = profile.get("description")
    result["schema_version"] = profile.get("schema_version")
    result["capabilities"] = profile.get("capabilities", {})

    # Summarize providers — only available + model_count, never secrets
    providers = profile.get("providers", {})
    for pkey, pdata in providers.items():
        result["providers"][pkey] = {
            "available": pdata.get("available", False),
            "model_count": len(pdata.get("models", [])),
        }

    return result
```

- [ ] **Step 4: Tjek om json import mangler**

```bash
grep -n "^import json" /home/svend/DPMtF-WebUI/config.py
```

Hvis ingen resultat: tilføj `import json` efter `import os` (linje 13).

- [ ] **Step 5: Valider syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/config.py
```

Forventet: ingen output (success).

- [ ] **Step 6: Test getters**

```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
import config
print('path:', config.get_machine_profile_path())
print('profile:', config.get_machine_profile())
print('metadata:', config.get_machine_profile_metadata())
"
```

Forventet: `path` peger på `profiles/machine.local.json`, `profile` er `{}` (fil findes ikke endnu), `metadata` viser `exists: false`.

- [ ] **Step 7: Commit**

```bash
git add config.py
git commit -m "[trade] Tilføj Machine Profile getters til config.py"
```

---

## Fase 1B — Healthcheck backend

### Task 4: Opret healthcheck motor

**Files:**
- Create: `scripts/system_healthcheck.py`

**Interfaces:**
- Produces:
  - `run_healthcheck(profile: dict, section: str | None = None) -> dict` — kører alle eller én sektion
  - `run_section_profile(profile: dict, profile_path: str) -> list[dict]`
  - `run_section_paths(profile: dict) -> list[dict]`
  - `run_section_binaries(profile: dict) -> list[dict]`
  - `run_section_ports(profile: dict) -> list[dict]`
  - `run_section_secrets(profile: dict) -> list[dict]`
  - `run_section_tmux(profile: dict) -> list[dict]`
  - `run_section_ollama(profile: dict) -> list[dict]`
  - `run_section_providers(profile: dict) -> list[dict]`

- [ ] **Step 1: Opret scripts/system_healthcheck.py**

```python
"""Machine Profile healthcheck engine — Phase 1 read-only validation.

Runs checks against the active Machine Profile and returns structured results.
Never modifies state. Never returns secrets.
"""

import os
import json
import shutil
import subprocess
import config


EXPECTED_SCHEMA_VERSION = 1

VALID_SECTIONS = [
    "profile", "paths", "binaries", "ports",
    "secrets", "tmux", "ollama", "providers",
]


def _check_result(section, name, status, severity, message):
    return {
        "section": section,
        "name": name,
        "status": status,
        "severity": severity,
        "message": message,
    }


def run_section_profile(profile, profile_path):
    """Check Machine Profile file itself.

    Distinguishes three states:
    1. Profile file missing → warning
    2. Profile file exists but JSON invalid → fail/error
    3. Profile file exists and valid → check schema_version etc.
    """
    results = []
    profile_name = os.environ.get("DPMTF_MACHINE_PROFILE", "machine.local.json")

    # State 1: File missing
    if not os.path.exists(profile_path):
        results.append(_check_result(
            "profile", "machine_profile", "warning", "warning",
            "No Machine Profile configured. "
            "Create profiles/machine.local.json or set DPMTF_MACHINE_PROFILE in .env. "
            "Existing functionality is unchanged."
        ))
        return results

    # State 2: File exists — try to parse
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
    except json.JSONDecodeError as e:
        results.append(_check_result(
            "profile", "json_valid", "fail", "error",
            f"Profile JSON is invalid: {e}"
        ))
        return results
    except IOError as e:
        results.append(_check_result(
            "profile", "json_valid", "fail", "error",
            f"Cannot read profile file: {e}"
        ))
        return results

    # State 3: Valid JSON
    results.append(_check_result(
        "profile", "json_valid", "pass", "info",
        "Profile JSON is valid"
    ))

    if not parsed:
        results.append(_check_result(
            "profile", "profile_content", "warning", "warning",
            "Machine Profile is empty or incomplete"
        ))
        return results

    # Check schema_version
    sv = parsed.get("schema_version")
    if sv is None:
        results.append(_check_result(
            "profile", "schema_version", "warning", "warning",
            "schema_version is missing from profile"
        ))
    elif sv != EXPECTED_SCHEMA_VERSION:
        results.append(_check_result(
            "profile", "schema_version", "warning", "warning",
            f"Machine Profile schema_version={sv}, expected={EXPECTED_SCHEMA_VERSION}"
        ))
    else:
        results.append(_check_result(
            "profile", "schema_version", "pass", "info",
            f"schema_version={sv} matches expected"
        ))

    results.append(_check_result(
        "profile", "profile_name", "pass", "info",
        f"Active profile: {profile_name} — {parsed.get('name', 'unnamed')}"
    ))

    return results


def run_section_paths(profile):
    """Check all paths in profile.paths."""
    results = []
    paths = profile.get("paths", {})
    required = profile.get("checks", {}).get("required_paths", [])

    if not paths:
        results.append(_check_result(
            "paths", "paths_section", "warning", "warning",
            "No paths defined in Machine Profile"
        ))
        return results

    for path_key, path_value in paths.items():
        exists = os.path.exists(path_value)
        is_required = path_key in required

        if exists:
            results.append(_check_result(
                "paths", path_key, "pass", "info",
                f"{path_value} exists"
            ))
        elif is_required:
            results.append(_check_result(
                "paths", path_key, "fail", "error",
                f"Required path missing: {path_value}"
            ))
        else:
            results.append(_check_result(
                "paths", path_key, "warning", "warning",
                f"Path not found: {path_value}"
            ))

    return results


def run_section_binaries(profile):
    """Check binaries in profile.binaries."""
    results = []
    binaries = profile.get("binaries", {})
    required = profile.get("checks", {}).get("required_binaries", [])

    if not binaries:
        results.append(_check_result(
            "binaries", "binaries_section", "warning", "warning",
            "No binaries defined in Machine Profile"
        ))
        return results

    for bin_key, bin_path in binaries.items():
        is_required = bin_key in required

        # If absolute path, check directly; otherwise use shutil.which
        if os.path.isabs(bin_path):
            found = os.path.isfile(bin_path) and os.access(bin_path, os.X_OK)
            display = bin_path
        else:
            found = shutil.which(bin_path) is not None
            display = shutil.which(bin_path) or bin_path

        if found:
            results.append(_check_result(
                "binaries", bin_key, "pass", "info",
                f"{display} found"
            ))
        elif is_required:
            results.append(_check_result(
                "binaries", bin_key, "fail", "error",
                f"Required binary not found: {bin_path}"
            ))
        else:
            results.append(_check_result(
                "binaries", bin_key, "warning", "warning",
                f"Binary not found: {bin_path}"
            ))

    return results


def run_section_ports(profile):
    """Check ports in profile.ports."""
    results = []
    ports = profile.get("ports", {})
    required = profile.get("checks", {}).get("required_ports", [])

    if not ports:
        return results

    # App port — always pass if we're running (the app is responding)
    app_port = ports.get("app")
    if app_port:
        results.append(_check_result(
            "ports", "app", "pass", "info",
            f"App running on port {app_port}"
        ))

    # Ollama port — check if local_ollama is enabled
    ollama_port = ports.get("ollama")
    local_ollama = profile.get("providers", {}).get("local_ollama", {})
    if ollama_port and local_ollama.get("available"):
        import urllib.request
        try:
            url = f"http://127.0.0.1:{ollama_port}"
            urllib.request.urlopen(url, timeout=2)
            results.append(_check_result(
                "ports", "ollama", "pass", "info",
                f"Ollama reachable on port {ollama_port}"
            ))
        except Exception:
            results.append(_check_result(
                "ports", "ollama", "warning", "warning",
                f"Ollama not reachable on port {ollama_port}"
            ))

    # Expected children — warning only
    children = ports.get("expected_children", {})
    for child_name, child_port in children.items():
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect(("127.0.0.1", child_port))
            sock.close()
            results.append(_check_result(
                "ports", child_name, "pass", "info",
                f"Port {child_port} ({child_name}) is responding"
            ))
        except Exception:
            results.append(_check_result(
                "ports", child_name, "warning", "warning",
                f"Port {child_port} ({child_name}) is not responding"
            ))

    return results


def run_section_secrets(profile):
    """Check env keys defined in providers. Never returns secret values."""
    results = []
    providers = profile.get("providers", {})

    for pkey, pdata in providers.items():
        env_key = pdata.get("env_key")
        available = pdata.get("available", False)

        if not env_key:
            continue

        if not available:
            results.append(_check_result(
                "secrets", env_key, "skip", "info",
                f"Provider '{pkey}' is disabled — skipping {env_key}"
            ))
            continue

        if os.environ.get(env_key):
            results.append(_check_result(
                "secrets", env_key, "pass", "info",
                f"Env key {env_key} found"
            ))
        else:
            results.append(_check_result(
                "secrets", env_key, "warning", "warning",
                f"Env key {env_key} not found"
            ))

    if not results:
        results.append(_check_result(
            "secrets", "secrets_section", "pass", "info",
            "No secrets to check"
        ))

    return results


def run_section_tmux(profile):
    """Check tmux if capabilities.tmux=true.

    Uses the tmux binary from Machine Profile, falling back to 'tmux' on PATH.
    """
    results = []
    capabilities = profile.get("capabilities", {})

    if not capabilities.get("tmux"):
        results.append(_check_result(
            "tmux", "tmux_capability", "skip", "info",
            "tmux capability disabled in Machine Profile"
        ))
        return results

    # Use binary from Machine Profile, fall back to 'tmux'
    tmux_bin = profile.get("binaries", {}).get("tmux", "tmux")
    if os.path.isabs(tmux_bin):
        tmux_path = tmux_bin if (os.path.isfile(tmux_bin) and os.access(tmux_bin, os.X_OK)) else None
    else:
        tmux_path = shutil.which(tmux_bin)

    if not tmux_path:
        results.append(_check_result(
            "tmux", "tmux_binary", "fail", "error",
            f"tmux binary not found: {tmux_bin}"
        ))
        return results

    results.append(_check_result(
        "tmux", "tmux_binary", "pass", "info",
        f"tmux found: {tmux_path}"
    ))

    # Check tmux sessions
    try:
        result = subprocess.run(
            [tmux_path, "list-sessions"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            sessions = [l.split(":")[0] for l in result.stdout.strip().split("\n") if l]
            results.append(_check_result(
                "tmux", "tmux_sessions", "pass", "info",
                f"{len(sessions)} session(s): {', '.join(sessions[:10])}"
            ))
        else:
            results.append(_check_result(
                "tmux", "tmux_sessions", "warning", "info",
                "No tmux sessions running"
            ))
    except Exception as e:
        results.append(_check_result(
            "tmux", "tmux_sessions", "warning", "warning",
            f"Could not list tmux sessions: {e}"
        ))

    return results


def run_section_ollama(profile):
    """Check Ollama if local_ollama is available.

    Uses the ollama binary from Machine Profile, falling back to 'ollama' on PATH.
    Endpoint check uses /api/tags instead of root endpoint.
    """
    results = []
    capabilities = profile.get("capabilities", {})
    local_ollama = profile.get("providers", {}).get("local_ollama", {})

    if not capabilities.get("local_ollama") and not local_ollama.get("available"):
        results.append(_check_result(
            "ollama", "ollama_capability", "skip", "info",
            "Ollama capability disabled in Machine Profile"
        ))
        return results

    # Check endpoint via /api/tags
    endpoint = local_ollama.get("endpoint", "http://127.0.0.1:11434")
    tags_url = endpoint.rstrip("/") + "/api/tags"
    import urllib.request
    try:
        urllib.request.urlopen(tags_url, timeout=2)
        results.append(_check_result(
            "ollama", "ollama_endpoint", "pass", "info",
            f"Ollama reachable at {endpoint}"
        ))
    except Exception:
        severity = "error" if local_ollama.get("available") else "warning"
        results.append(_check_result(
            "ollama", "ollama_endpoint", "fail", severity,
            f"Ollama not reachable at {endpoint}"
        ))
        # Endpoint failed — skip model check
        return results

    # Check models using binary from Machine Profile
    models = local_ollama.get("models", [])
    if not models:
        results.append(_check_result(
            "ollama", "ollama_models", "pass", "info",
            "No models configured to check"
        ))
        return results

    # Use ollama binary from Machine Profile
    ollama_bin = profile.get("binaries", {}).get("ollama", "ollama")
    if os.path.isabs(ollama_bin):
        ollama_path = ollama_bin if (os.path.isfile(ollama_bin) and os.access(ollama_bin, os.X_OK)) else None
    else:
        ollama_path = shutil.which(ollama_bin)

    if not ollama_path:
        results.append(_check_result(
            "ollama", "ollama_binary", "warning", "warning",
            f"ollama binary not found: {ollama_bin} — cannot check models"
        ))
        return results

    try:
        result = subprocess.run(
            [ollama_path, "list"], capture_output=True, text=True, timeout=10
        )
        pulled = result.stdout if result.returncode == 0 else ""
    except Exception:
        pulled = ""

    for model in models:
        if model in pulled:
            results.append(_check_result(
                "ollama", model, "pass", "info",
                f"Model {model} is pulled"
            ))
        else:
            results.append(_check_result(
                "ollama", model, "warning", "warning",
                f"Model {model} not pulled"
            ))

    return results


def run_section_providers(profile):
    """Check provider availability."""
    results = []
    providers = profile.get("providers", {})

    if not providers:
        results.append(_check_result(
            "providers", "providers_section", "warning", "warning",
            "No providers defined in Machine Profile"
        ))
        return results

    available_count = 0
    for pkey, pdata in providers.items():
        available = pdata.get("available", False)
        model_count = len(pdata.get("models", []))
        has_endpoint = bool(pdata.get("endpoint"))
        has_env_key = bool(pdata.get("env_key"))

        if available:
            available_count += 1
            results.append(_check_result(
                "providers", pkey, "pass", "info",
                f"Provider '{pkey}' available — {model_count} model(s)"
            ))
        else:
            results.append(_check_result(
                "providers", pkey, "skip", "info",
                f"Provider '{pkey}' disabled"
            ))

    if available_count == 0:
        results.append(_check_result(
            "providers", "provider_availability", "warning", "warning",
            "No providers available — flows cannot be started"
        ))

    return results


def run_healthcheck(profile, section=None):
    """Run all healthchecks or a single section.

    Args:
        profile: dict from config.get_machine_profile() — may be empty {}
        section: optional section name to run only that check

    Returns:
        dict with profile metadata, summary, and checks list
    """
    profile_path = config.get_machine_profile_path()
    metadata = config.get_machine_profile_metadata()

    if section is not None and section not in VALID_SECTIONS:
        raise ValueError(f"Unknown section '{section}'. Valid: {', '.join(VALID_SECTIONS)}")

    sections_to_run = [section] if section else VALID_SECTIONS

    all_checks = []
    for sec in sections_to_run:
        if sec == "profile":
            all_checks.extend(run_section_profile(profile, profile_path))
        elif sec == "paths":
            all_checks.extend(run_section_paths(profile))
        elif sec == "binaries":
            all_checks.extend(run_section_binaries(profile))
        elif sec == "ports":
            all_checks.extend(run_section_ports(profile))
        elif sec == "secrets":
            all_checks.extend(run_section_secrets(profile))
        elif sec == "tmux":
            all_checks.extend(run_section_tmux(profile))
        elif sec == "ollama":
            all_checks.extend(run_section_ollama(profile))
        elif sec == "providers":
            all_checks.extend(run_section_providers(profile))

    summary = {
        "passed": sum(1 for c in all_checks if c["status"] == "pass"),
        "warnings": sum(1 for c in all_checks if c["status"] == "warning"),
        "failed": sum(1 for c in all_checks if c["status"] == "fail"),
    }

    return {
        "profile": {
            "name": metadata.get("name"),
            "filename": metadata.get("active_profile"),
            "schema_version": metadata.get("schema_version"),
        },
        "summary": summary,
        "checks": all_checks,
    }
```

- [ ] **Step 2: Valider syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/system_healthcheck.py
```

- [ ] **Step 3: Test med tom profil**

```bash
cd /home/svend/DPMtF-WebUI && python3 -c "
from scripts.system_healthcheck import run_healthcheck
import json
result = run_healthcheck({})
print(json.dumps(result['summary'], indent=2))
print('Checks:', len(result['checks']))
"
```

Forventet: viser warning om ingen Machine Profile, summary med warnings.

- [ ] **Step 4: Commit**

```bash
git add scripts/system_healthcheck.py
git commit -m "[trade] Opret healthcheck motor til Machine Profile"
```

---

### Task 5: Tilføj API endpoints til app.py

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `scripts/system_healthcheck.py` — `run_healthcheck()`
- Consumes: `config.py` — `get_machine_profile()`, `get_machine_profile_metadata()`
- Produces:
  - `GET /api/system/machine-profile` → `{active_profile, exists, name, ...}`
  - `GET /api/system/healthcheck` → `{profile, summary, checks: [...]}`
  - `GET /api/system/healthcheck/{section}` → `{profile, summary, checks: [...]}`

- [ ] **Step 1: Find indsættelsespunkt i app.py**

Find et passende sted efter de eksisterende bridge-v2 endpoints. Søg efter den sidste `@app.` definition:

```bash
grep -n "^@app\.\|^# ──\|^# --" /home/svend/DPMtF-WebUI/app.py | tail -20
```

- [ ] **Step 2: Tilføj imports øverst i app.py (hvis ikke allerede til stede)**

Tilføj efter de eksisterende bridge_lib imports:

```python
# Machine Profile healthcheck (Fase 1)
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from system_healthcheck import run_healthcheck
```

- [ ] **Step 3: Tilføj GET /api/system/machine-profile**

```python
@app.get("/api/system/machine-profile")
async def system_machine_profile():
    """Return safe metadata about the active Machine Profile.

    Never returns secrets, paths, or raw profile data.
    """
    try:
        metadata = config.get_machine_profile_metadata()
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read Machine Profile: {e}",
        )
```

- [ ] **Step 4: Tilføj GET /api/system/healthcheck**

```python
@app.get("/api/system/healthcheck")
async def system_healthcheck():
    """Run all Machine Profile healthchecks.

    Returns structured results with status and severity per check.
    Never blocks existing functionality.
    """
    try:
        profile = config.get_machine_profile()
        result = run_healthcheck(profile)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Healthcheck failed: {e}",
        )
```

- [ ] **Step 5: Tilføj GET /api/system/healthcheck/{section}**

```python
@app.get("/api/system/healthcheck/{section}")
async def system_healthcheck_section(section: str):
    """Run a single section of Machine Profile healthchecks.

    Valid sections: profile, paths, binaries, ports, secrets, tmux, ollama, providers
    """
    try:
        profile = config.get_machine_profile()
        result = run_healthcheck(profile, section=section)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Healthcheck failed: {e}",
        )
```

- [ ] **Step 6: Valider syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/app.py
```

- [ ] **Step 7: Test endpoints (kræver kørende app)**

```bash
curl -s http://127.0.0.1:9130/api/system/machine-profile | python3 -m json.tool
curl -s http://127.0.0.1:9130/api/system/healthcheck | python3 -m json.tool
curl -s http://127.0.0.1:9130/api/system/healthcheck/paths | python3 -m json.tool
curl -s http://127.0.0.1:9130/api/system/healthcheck/unknown
```

Forventet: Første to returnerer JSON, `paths` returnerer checks, `unknown` returnerer 400.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "[trade] Tilføj Machine Profile API endpoints — healthcheck + metadata"
```

---

## Fase 1C — Frontend System Setup

### Task 6: Tilføj System Setup panel

**Files:**
- Modify: `static/js/dpmtf-app.js`
- Modify: `templates/index.html` (hvis HTML-anker nødvendigt)

**Interfaces:**
- Consumes: `GET /api/system/machine-profile`, `GET /api/system/healthcheck`, `GET /api/system/healthcheck/{section}`
- Produces: Read-only System Setup panel under Setup

- [ ] **Step 1: Tilføj HTML-container i index.html**

Find Setup-sektionen i `templates/index.html` og tilføj et nyt panel:

```html
<!-- System Setup Panel (Machine Profile) -->
<div id="system-setup-panel" class="dpmtf-panel dpmtf-hidden">
  <h3 data-slot="system_setup_title">System Setup</h3>
  <div id="system-setup-content"></div>
</div>
```

- [ ] **Step 2: Tilføj JavaScript funktioner i dpmtf-app.js**

Tilføj efter Bridge Setup Panel sektionen (omkring linje 3316):

```javascript
/* ── 12. System Setup Panel (Machine Profile) ────────── */

var _systemSetupSections = [
  "profile", "paths", "binaries", "ports",
  "secrets", "tmux", "ollama", "providers"
];

function loadSystemSetup() {
  var container = document.getElementById("system-setup-content");
  if (!container) return;
  clear(container);

  // Header: machine name + profile + status
  fetch("/api/system/machine-profile")
    .then(function (res) { return res.json(); })
    .then(function (meta) {
      renderSystemSetupHeader(container, meta);
      renderSystemSetupButtons(container);
      renderSystemSetupCheckContainer(container);
    })
    .catch(function (err) {
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      container.appendChild(errP);
    });
}

function renderSystemSetupHeader(container, meta) {
  var headerDiv = el("div", "dpmtf-system-setup-header");

  if (!meta.exists) {
    var noProfile = el("p", "dpmtf-warning");
    noProfile.textContent = lbl("system_setup_no_profile",
      "Ingen maskinprofil konfigureret. " +
      "Opret profiles/machine.local.json eller sæt DPMTF_MACHINE_PROFILE i .env. " +
      "Eksisterende DPMtF-funktionalitet er uændret.");
    headerDiv.appendChild(noProfile);
    container.appendChild(headerDiv);
    return;
  }

  // Show parse_error if present
  if (meta.parse_error) {
    var parseErr = el("p", "dpmtf-error");
    parseErr.textContent = lbl("system_setup_parse_error", "JSON-fejl i profil") +
      ": " + (meta.parse_error || "");
    headerDiv.appendChild(parseErr);
  }

  var infoLines = [
    lbl("system_setup_machine", "Maskine") + ": " + (meta.name || "ukendt"),
    lbl("system_setup_profile", "Profil") + ": " + (meta.active_profile || ""),
    lbl("system_setup_schema", "Schema") + ": v" + (meta.schema_version || "?"),
  ];

  infoLines.forEach(function (line) {
    var p = el("p", "dpmtf-small");
    p.textContent = line;
    headerDiv.appendChild(p);
  });

  container.appendChild(headerDiv);
}

function renderSystemSetupButtons(container) {
  var btnDiv = el("div", "dpmtf-btn-group");

  var allBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  allBtn.textContent = lbl("system_setup_run_all_checks", "Kør alle checks");
  allBtn.onclick = function () { runSystemCheck(null); };
  btnDiv.appendChild(allBtn);

  _systemSetupSections.forEach(function (sec) {
    var btn = el("button", "dpmtf-btn dpmtf-btn-secondary");
    btn.textContent = lbl("system_setup_run_" + sec, "Kør " + sec);
    btn.onclick = function () { runSystemCheck(sec); };
    btnDiv.appendChild(btn);
  });

  container.appendChild(btnDiv);
}

function renderSystemSetupCheckContainer(container) {
  var checkDiv = el("div", "dpmtf-system-setup-checks");
  checkDiv.id = "system-setup-checks";

  var summaryP = el("p", "dpmtf-small dpmtf-muted");
  summaryP.id = "system-setup-summary";
  summaryP.textContent = lbl("system_setup_ready", "Klar. Klik på en check-knap for at køre.");
  checkDiv.appendChild(summaryP);

  var listDiv = el("div", "dpmtf-check-list");
  listDiv.id = "system-setup-check-list";
  checkDiv.appendChild(listDiv);

  container.appendChild(checkDiv);
}

function runSystemCheck(section) {
  var listDiv = document.getElementById("system-setup-check-list");
  var summaryP = document.getElementById("system-setup-summary");
  if (!listDiv || !summaryP) return;

  clear(listDiv);
  summaryP.textContent = lbl("system_setup_running", "Kører checks...");

  var url = "/api/system/healthcheck";
  if (section) {
    url += "/" + encodeURIComponent(section);
  }

  fetch(url)
    .then(function (res) {
      if (!res.ok) {
        return res.json().then(function (err) {
          throw new Error(err.detail || "Healthcheck failed");
        });
      }
      return res.json();
    })
    .then(function (data) {
      renderSystemCheckResults(listDiv, summaryP, data);
    })
    .catch(function (err) {
      summaryP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
    });
}

function renderSystemCheckResults(listDiv, summaryP, data) {
  var summary = data.summary || {};
  summaryP.textContent =
    lbl("system_setup_status", "Status") + ": " +
    (summary.passed || 0) + " bestået / " +
    (summary.warnings || 0) + " advarsler / " +
    (summary.failed || 0) + " fejlet";

  var checks = data.checks || [];
  if (!checks.length) {
    var emptyP = el("p", "dpmtf-muted");
    emptyP.textContent = lbl("system_setup_no_checks", "Ingen checks returneret");
    listDiv.appendChild(emptyP);
    return;
  }

  checks.forEach(function (check) {
    var row = el("div", "dpmtf-check-row");

    // Status icon
    var icon = el("span", "dpmtf-check-icon");
    if (check.status === "pass") {
      icon.textContent = "✅";  // ✅
      icon.className += " dpmtf-check-pass";
    } else if (check.status === "warning") {
      icon.textContent = "⚠️";  // ⚠️
      icon.className += " dpmtf-check-warning";
    } else if (check.status === "fail") {
      icon.textContent = "❌";  // ❌
      icon.className += " dpmtf-check-fail";
    } else {
      icon.textContent = "⏭️";  // ⏭️ skip
      icon.className += " dpmtf-check-skip";
    }
    row.appendChild(icon);

    // Name
    var nameSpan = el("span", "dpmtf-check-name");
    nameSpan.textContent = check.name;
    row.appendChild(nameSpan);

    // Message
    var msgSpan = el("span", "dpmtf-check-message");
    msgSpan.textContent = check.message;
    row.appendChild(msgSpan);

    listDiv.appendChild(row);
  });
}
```

- [ ] **Step 3: Registrér System Setup i buildPanelStructure**

Find `buildPanelStructure()` funktionen (omkring linje 131). Tilføj `loadSystemSetup` kald i setup-sektionen:

I `buildPanelStructure()`, efter de eksisterende setup-paneler, tilføj:

```javascript
// Efter loadBridgeSetup() kaldet:
if (typeof loadSystemSetup === "function") loadSystemSetup();
```

- [ ] **Step 4: Valider JavaScript syntaks**

```bash
node --check /home/svend/DPMtF-WebUI/static/js/dpmtf-app.js
```

- [ ] **Step 5: Commit**

```bash
git add static/js/dpmtf-app.js templates/index.html
git commit -m "[trade] Tilføj System Setup panel til frontend — Machine Profile healthcheck UI"
```

---

## Fase 1D — i18n og governance

### Task 7: Tilføj i18n labels til init_db.py

**Files:**
- Modify: `scripts/init_db.py`

**Interfaces:**
- Produces: Seed data for System Setup UI labels i både `en-US` og `da-DK`

- [ ] **Step 1: Find eksisterende label seed data mønster**

```bash
grep -n "INSERT INTO ui_labels\|INSERT OR IGNORE INTO ui_labels" /home/svend/DPMtF-WebUI/scripts/init_db.py | head -5
```

Find et passende sted at indsætte nye labels — efter de eksisterende bridge labels.

- [ ] **Step 2: Tilføj ui_labels seed data**

```python
# System Setup — Machine Profile labels (Fase 1)
cursor.executemany(
    """INSERT OR IGNORE INTO ui_labels (label_key, default_text)
       VALUES (?, ?)""",
    [
        ("system_setup_title", "System Setup"),
        ("system_setup_run_all_checks", "Run All Checks"),
        ("system_setup_machine_profile", "Machine Profile"),
        ("system_setup_model_providers", "Model Providers"),
        ("system_setup_runtime_config", "Role Runtime Config"),
        ("system_setup_path_checks", "Path Checks"),
        ("system_setup_port_checks", "Port Checks"),
        ("system_setup_secrets_check", "Secrets Check"),
        ("system_setup_tmux_check", "Tmux Session Check"),
        ("system_setup_ollama_check", "Ollama Model Check"),
        ("system_setup_migration", "Migration"),
        ("system_setup_no_profile",
         "No Machine Profile configured. "
         "Create profiles/machine.local.json or set DPMTF_MACHINE_PROFILE in .env. "
         "Existing DPMtF functionality is unchanged."),
        ("system_setup_existing_unchanged",
         "Existing DPMtF functionality is unchanged."),
        ("system_setup_machine", "Machine"),
        ("system_setup_profile", "Profile"),
        ("system_setup_schema", "Schema"),
        ("system_setup_status", "Status"),
        ("system_setup_ready", "Ready. Click a check button to run."),
        ("system_setup_running", "Running checks..."),
        ("system_setup_no_checks", "No checks returned"),
        ("system_setup_run_profile", "Run profile"),
        ("system_setup_run_paths", "Run paths"),
        ("system_setup_run_binaries", "Run binaries"),
        ("system_setup_run_ports", "Run ports"),
        ("system_setup_run_secrets", "Run secrets"),
        ("system_setup_run_tmux", "Run tmux"),
        ("system_setup_run_ollama", "Run ollama"),
        ("system_setup_run_providers", "Run providers"),
        ("system_setup_parse_error", "JSON parse error in profile"),
    ],
)
```

- [ ] **Step 3: Tilføj ui_label_translations seed data (da-DK)**

```python
# System Setup — Danish translations
cursor.executemany(
    """INSERT OR IGNORE INTO ui_label_translations (label_key, locale, translated_text)
       VALUES (?, ?, ?)""",
    [
        ("system_setup_title", "da-DK", "Systemopsætning"),
        ("system_setup_run_all_checks", "da-DK", "Kør alle checks"),
        ("system_setup_machine_profile", "da-DK", "Maskinprofil"),
        ("system_setup_model_providers", "da-DK", "Modeludbydere"),
        ("system_setup_runtime_config", "da-DK", "Runtime-konfiguration"),
        ("system_setup_path_checks", "da-DK", "Sti-checks"),
        ("system_setup_port_checks", "da-DK", "Port-checks"),
        ("system_setup_secrets_check", "da-DK", "Hemmeligheds-check"),
        ("system_setup_tmux_check", "da-DK", "Tmux Session-check"),
        ("system_setup_ollama_check", "da-DK", "Ollama Model-check"),
        ("system_setup_migration", "da-DK", "Migrering"),
        ("system_setup_no_profile", "da-DK",
         "Ingen maskinprofil konfigureret. "
         "Opret profiles/machine.local.json eller sæt DPMTF_MACHINE_PROFILE i .env. "
         "Eksisterende DPMtF-funktionalitet er uændret."),
        ("system_setup_existing_unchanged", "da-DK",
         "Eksisterende DPMtF-funktionalitet er uændret."),
        ("system_setup_machine", "da-DK", "Maskine"),
        ("system_setup_profile", "da-DK", "Profil"),
        ("system_setup_schema", "da-DK", "Schema"),
        ("system_setup_status", "da-DK", "Status"),
        ("system_setup_ready", "da-DK", "Klar. Klik på en check-knap for at køre."),
        ("system_setup_running", "da-DK", "Kører checks..."),
        ("system_setup_no_checks", "da-DK", "Ingen checks returneret"),
        ("system_setup_run_profile", "da-DK", "Kør profil"),
        ("system_setup_run_paths", "da-DK", "Kør stier"),
        ("system_setup_run_binaries", "da-DK", "Kør binaries"),
        ("system_setup_run_ports", "da-DK", "Kør porte"),
        ("system_setup_run_secrets", "da-DK", "Kør hemmeligheder"),
        ("system_setup_run_tmux", "da-DK", "Kør tmux"),
        ("system_setup_run_ollama", "da-DK", "Kør ollama"),
        ("system_setup_run_providers", "da-DK", "Kør udbydere"),
        ("system_setup_parse_error", "da-DK", "JSON-fejl i profil"),
    ],
)
```

- [ ] **Step 4: Valider syntaks og kør init_db**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py
python3 /home/svend/DPMtF-WebUI/scripts/init_db.py
```

Forventet: ingen fejl, idempotent (kan køres flere gange).

- [ ] **Step 5: Commit**

```bash
git add scripts/init_db.py
git commit -m "[trade] Tilføj i18n labels for System Setup — Machine Profile UI"
```

---

### Task 8: Governance docs (allerede udført)

Governance-dokumenterne `11_SCOPE.md`, `20_GATES.md`, og `17_DATABASE.md` er allerede opdateret i commit `65b3472`.

- [x] **Step 1: Verificer at governance docs er committed**

```bash
git log --oneline -3
```

Forventet: `65b3472 [trade] Opdater governance docs for Machine Profile Fase 1 — SCOPE, GATES, DATABASE`

---

## Verifikation — alle tests

Efter alle tasks er implementeret, kør disse tests:

- [ ] **Test 1: App starter uden profiles/ mappe**

```bash
# Midlertidigt omdøb profiles/ og genstart
mv profiles profiles.bak
curl -s http://127.0.0.1:9130/api/health
# Forventet: {"status": "healthy"}
mv profiles.bak profiles
```

- [ ] **Test 2: App starter uden Machine Profile fil**

```bash
curl -s http://127.0.0.1:9130/api/system/machine-profile | python3 -m json.tool
# Forventet: exists=false
```

- [ ] **Test 3: Invalid JSON crasher ikke — metadata viser parse_error**

```bash
echo "not json" > profiles/machine.local.json
curl -s http://127.0.0.1:9130/api/system/machine-profile | python3 -m json.tool
# Forventet: exists=true, parse_error udfyldt, name=null, schema_version=null
curl -s http://127.0.0.1:9130/api/system/healthcheck/profile | python3 -m json.tool
# Forventet: section=profile, status=fail, severity=error, message indeholder "invalid JSON"
rm profiles/machine.local.json
```

- [ ] **Test 4: Healthcheck returnerer warning uden profil**

```bash
curl -s http://127.0.0.1:9130/api/system/healthcheck | python3 -m json.tool
# Forventet: summary.warnings > 0, første check er profile warning
```

- [ ] **Test 5: Path check med AI-PC profil**

```bash
cp profiles/machine.ai-pc.example.json profiles/machine.ai-pc.json
curl -s http://127.0.0.1:9130/api/system/healthcheck/paths | python3 -m json.tool
# Forventet: project_root og bridge_dir er pass
```

- [ ] **Test 6: Binary check**

```bash
curl -s http://127.0.0.1:9130/api/system/healthcheck/binaries | python3 -m json.tool
# Forventet: python og tmux er pass
```

- [ ] **Test 7: Secrets returnerer aldrig værdier**

```bash
curl -s http://127.0.0.1:9130/api/system/healthcheck/secrets | python3 -m json.tool
# Forventet: ingen secret values i output — kun "found" eller "not found"
```

- [ ] **Test 8: Ukendt section giver 400**

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9130/api/system/healthcheck/invalid
# Forventet: 400
```

- [ ] **Test 9: Frontend validering**

```bash
node --check /home/svend/DPMtF-WebUI/static/js/dpmtf-app.js
# Forventet: ingen output (success)
```

- [ ] **Test 10: Python validering**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/app.py
python3 -m py_compile /home/svend/DPMtF-WebUI/config.py
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/system_healthcheck.py
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py
# Forventet: ingen output (success)
```

---

## Stopregel — verificér før commit

Før hver commit, verificér at kun tilladte filer er ændret:

```bash
git diff --name-only HEAD
```

Tilladte filer i Fase 1:

```
profiles/.gitkeep
profiles/machine.local.example.json
profiles/machine.ai-pc.example.json
.gitignore
config.py
scripts/system_healthcheck.py
app.py
static/js/dpmtf-app.js
templates/index.html
scripts/init_db.py
docs/governance-templates-v2/11_SCOPE.md
docs/governance-templates-v2/20_GATES.md
docs/governance-templates-v2/17_DATABASE.md
docs/superpowers/specs/2026-06-30-machine-profile-design.md
docs/superpowers/plans/2026-06-30-machine-profile-phase1.md
```

Hvis andre filer ændres → **STOP**. Rapporter hvorfor.

Særligt stop hvis ændrede filer eller diffs berører:

```
database migrations for bridge_roles
database migrations for bridge_flow_steps
start_cmd_suffix
tmux injection scripts
deliverable_dir resolution
flow execution
role start/stop commands
```

Bemærk: Fase 1 tilføjer legitimt tmux healthcheck — dette er tilladt fordi det kun er read-only status, ikke tmux injection.

