# Machine Profile Fase 2A — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afkobl `start_cmd_suffix` ved at indføre logiske felter (runtime, provider, model) på roller og `build_start_command()` der oversætter via Machine Profile. Per-flow aktivering via `use_machine_profile`.

**Architecture:** 4 nye database-kolonner (idempotente). Nyt `command_builder.py` med 5 faste builders + command object renderer. `start_coding.py` ændres kun til at vælge mellem legacy og Machine Profile kommando. Frontend får flow-checkbox og rolle-dropdowns.

**Tech Stack:** Python 3 (FastAPI), JavaScript (vanilla), SQLite

## Global Constraints

- **Stopregel:** Må IKKE fjerne `start_cmd_suffix`, massemigrere flows, ændre tmux/prompt/flow execution ud over valg af startkommando
- Alle schemaændringer skal være idempotente (`PRAGMA table_info` check før `ALTER TABLE`)
- `use_machine_profile` default = 0 for alle eksisterende flows
- `default_runtime`, `default_provider`, `default_model` er nullable, default NULL
- Når `use_machine_profile=1`: ingen skjult fallback til `start_cmd_suffix` ved fejl
- `auth_token` må kun være `"ollama"` i command object — andre værdier behandles som secrets
- Cloud secrets (OPENROUTER_API_KEY, ANTHROPIC_API_KEY) må aldrig indgå i command object
- `default_model` ikke i model-liste → warning, ikke error (Fase 2A)
- Frontend: `use_machine_profile` checkbox kun enabled når Machine Profile findes, er valid JSON, og schema_version matcher
- Python: `python3 -m py_compile` før færdigmeldelse
- JavaScript: `node --check` før færdigmeldelse
- Ingen `shell=True` i Python execution

---

### Task 1: Idempotente database-kolonner

**Files:**
- Modify: `scripts/init_db.py`

**Interfaces:**
- Produces: `bridge_flows.use_machine_profile` (INTEGER DEFAULT 0), `bridge_roles.default_runtime` (TEXT), `bridge_roles.default_provider` (TEXT), `bridge_roles.default_model` (TEXT)

- [ ] **Step 1: Tilføj column_exists() hjælpefunktion**

Find en passende placering i `init_db.py` (før schemaændringerne) og tilføj:

```python
def _column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table (idempotent schema helper)."""
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)
```

- [ ] **Step 2: Tilføj use_machine_profile på bridge_flows**

Find sektionen hvor `auto_complete_enabled` blev tilføjet (omkring linje 4294) og tilføj efter:

```python
# Machine Profile Fase 2A — use_machine_profile on bridge_flows
if not _column_exists(cursor, "bridge_flows", "use_machine_profile"):
    cursor.execute("""
        ALTER TABLE bridge_flows ADD COLUMN use_machine_profile INTEGER DEFAULT 0
    """)
```

- [ ] **Step 3: Tilføj default_runtime, default_provider, default_model på bridge_roles**

```python
# Machine Profile Fase 2A — logical runtime fields on bridge_roles
if not _column_exists(cursor, "bridge_roles", "default_runtime"):
    cursor.execute("""
        ALTER TABLE bridge_roles ADD COLUMN default_runtime TEXT DEFAULT NULL
    """)

if not _column_exists(cursor, "bridge_roles", "default_provider"):
    cursor.execute("""
        ALTER TABLE bridge_roles ADD COLUMN default_provider TEXT DEFAULT NULL
    """)

if not _column_exists(cursor, "bridge_roles", "default_model"):
    cursor.execute("""
        ALTER TABLE bridge_roles ADD COLUMN default_model TEXT DEFAULT NULL
    """)
```

- [ ] **Step 4: Seed default-felter for eksisterende roller**

Udfyld `default_runtime`, `default_provider`, `default_model` baseret på de 20 analyserede `start_cmd_suffix` mønstre. Brug `UPDATE ... WHERE ... AND default_runtime IS NULL` for idempotens:

```python
# Seed default_runtime/default_provider/default_model from analyzed patterns
# Only sets NULL fields — never overwrites manually configured values
cursor.executemany(
    """UPDATE bridge_roles
       SET default_runtime = ?, default_provider = ?, default_model = ?
       WHERE role_key = ? AND default_runtime IS NULL""",
    [
        # Claude + local_ollama
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "archi01"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "archi01cloud"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "archi01pay"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "trend01_trade"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "risk01_trade"),
        # Claude + cloud_ollama
        ("claude", "cloud_ollama", "deepseek-v4-pro:cloud", "market01_trade"),
        # Claude + local_ollama (27b)
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "review01"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "review01cloud"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "review01pay"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "learn01_trade"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "score01_trade"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "sim01_trade"),
        # Claude + local_ollama (35b-a3b)
        ("claude", "local_ollama", "qwen3.6:35b-a3b", "review02"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b", "review02cloud"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b", "review02pay"),
        # OpenCode + local_ollama
        ("opencode", "local_ollama", "qwen3.6-27b-coder:latest", "imple01"),
        ("opencode", "local_ollama", "qwen3.6:27b-q4_K_M", "review01_trade"),
        # OpenCode + openrouter
        ("opencode", "openrouter", "z-ai/glm-5.2", "review01_trade"),  # overrides above — handled manually
        # OpenCode + cloud (minimax)
        ("opencode", "openrouter", "minimax/MiniMax-M3", "analyst01_trade"),
        ("opencode", "openrouter", "minimax/MiniMax-M3", "imple01pay"),
        # Freebuff
        ("freebuff", None, "freebuff-default", "imple01cloud"),
    ],
)
```

Bemærk: `review01_trade` har to entries — den sidste vinder pga `WHERE default_runtime IS NULL`. Hvis den allerede er seedet, opdateres den ikke. Implementer skal verificere den korrekte værdi for `review01_trade` (OpenCode + openrouter + z-ai/glm-5.2 ifølge databasen).

- [ ] **Step 5: Valider og kør**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py
python3 /home/svend/DPMtF-WebUI/scripts/init_db.py
```

Forventet: "Database initialized successfully!" — idempotent, ingen fejl.

- [ ] **Step 6: Verificer kolonner**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "PRAGMA table_info(bridge_flows);" | grep use_machine_profile
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "PRAGMA table_info(bridge_roles);" | grep -E "default_runtime|default_provider|default_model"
```

Forventet: 4 kolonner vises.

- [ ] **Step 7: Commit**

```bash
git add scripts/init_db.py
git commit -m "[trade] Tilføj idempotente Machine Profile runtime kolonner — use_machine_profile på flows, default_runtime/provider/model på roller"
```

---

### Task 2: Opret command_builder.py

**Files:**
- Create: `scripts/bridgeV002/command_builder.py`

**Interfaces:**
- Produces:
  - `build_start_command(runtime, provider, model, role_key, machine_profile) -> dict` — returnerer command object
  - `render_tmux_shell_string(command_object) -> str` — renderer command object til tmux-safe shell-string
  - `SUPPORTED_COMMAND_BUILDERS: dict` — registry over understøttede kombinationer

- [ ] **Step 1: Opret scripts/bridgeV002/command_builder.py**

```python
"""Machine Profile Fase 2A — Command builder for role start commands.

Translates logical role fields (runtime, provider, model) into concrete
start commands using Machine Profile configuration.

Returns structured command objects — never raw shell strings directly.
Renderer handles tmux-safe shell string conversion.
"""

import os
import shlex


def build_start_command(runtime, provider, model, role_key, machine_profile):
    """Build a start command object from logical role fields + Machine Profile.

    Args:
        runtime: str — which program starts the role (claude, opencode, freebuff)
        provider: str or None — where the model comes from (local_ollama, openrouter, ...)
        model: str — which model to use
        role_key: str — the role's unique key (for config_dir resolution)
        machine_profile: dict — from config.get_machine_profile()

    Returns:
        dict with keys: cwd (str), env (dict), argv (list[str])

    Raises:
        ValueError: if runtime/provider combination is unsupported,
                    if required fields are missing,
                    if required binaries are not found in Machine Profile
    """
    # Validate required fields
    if not runtime:
        raise ValueError(
            f"Role {role_key} has use_machine_profile flow enabled "
            f"but missing default_runtime"
        )
    if not provider and runtime != "freebuff":
        raise ValueError(
            f"Role {role_key} has use_machine_profile flow enabled "
            f"but missing default_provider"
        )
    if not model:
        raise ValueError(
            f"Role {role_key} has use_machine_profile flow enabled "
            f"but missing default_model"
        )

    # Look up builder
    builder_key = (runtime, provider if provider else None)
    builder = SUPPORTED_COMMAND_BUILDERS.get(builder_key)
    if builder is None:
        raise ValueError(
            f"Unsupported runtime/provider combination: {runtime}/{provider}"
        )

    return builder(runtime, provider, model, role_key, machine_profile)


# ── Builder registry ──────────────────────────────────────────


SUPPORTED_COMMAND_BUILDERS = {}


def _register(runtime, provider):
    """Decorator to register a builder function."""
    def decorator(func):
        SUPPORTED_COMMAND_BUILDERS[(runtime, provider)] = func
        return func
    return decorator


# ── Individual builders ───────────────────────────────────────


def _resolve_binary(binary_ref, binaries, runtime_name):
    """Resolve a binary_ref from Machine Profile binaries section.

    Returns absolute path if available, or the ref itself for PATH lookup.
    Raises ValueError if binary is not found and not on PATH.
    """
    binary_path = binaries.get(binary_ref, binary_ref)
    if os.path.isabs(binary_path):
        if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
            return binary_path
        raise ValueError(f"Runtime binary not found: {binary_path}")
    # Non-absolute — assume on PATH (validated by healthcheck)
    return binary_path


def _get_provider_config(provider_key, providers):
    """Get provider config, raising if not found."""
    if provider_key not in providers:
        raise ValueError(
            f"Provider not configured in Machine Profile: {provider_key}"
        )
    return providers[provider_key]


def _get_runtime_config(runtime_key, runtimes):
    """Get runtime config, returning empty dict if not found."""
    return runtimes.get(runtime_key, {})


@_register("claude", "local_ollama")
@_register("claude", "cloud_ollama")
def build_claude_ollama_command(runtime, provider, model, role_key, mp):
    """Build Claude + Ollama (local or cloud) command."""
    binaries = mp.get("binaries", {})
    providers = mp.get("providers", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    claude_bin = _resolve_binary("claude", binaries, "claude")
    provider_cfg = _get_provider_config(provider, providers)
    runtime_cfg = _get_runtime_config("claude", runtimes)

    endpoint = provider_cfg.get("endpoint", "http://127.0.0.1:11434")
    auth_token = provider_cfg.get("auth_token", "ollama")

    # Security: only "ollama" token is allowed in command object
    if auth_token != "ollama":
        raise ValueError(
            f"auth_token for provider '{provider}' is not 'ollama' — "
            f"cannot include in command object. Use environment variable instead."
        )

    env = dict(runtime_cfg.get("default_env", {}))
    env["ANTHROPIC_BASE_URL"] = endpoint
    env["ANTHROPIC_AUTH_TOKEN"] = auth_token

    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": env,
        "argv": [claude_bin, "--model", model],
    }


@_register("opencode", "local_ollama")
def build_opencode_ollama_command(runtime, provider, model, role_key, mp):
    """Build OpenCode + local Ollama command."""
    binaries = mp.get("binaries", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    config_dir = f"{config_base}/{role_key}"

    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": {
            "OPENCODE_CONFIG_DIR": config_dir,
            "OPENCODE_CONFIG": f"{config_dir}/opencode.json",
        },
        "argv": [opencode_bin, "--model", f"ollama/{model}"],
    }


@_register("opencode", "openrouter")
def build_opencode_openrouter_command(runtime, provider, model, role_key, mp):
    """Build OpenCode + OpenRouter command.

    OpenRouter API key comes from environment — NOT included in command object.
    """
    binaries = mp.get("binaries", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    config_dir = f"{config_base}/{role_key}"

    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": {
            "OPENCODE_CONFIG_DIR": config_dir,
            "OPENCODE_CONFIG": f"{config_dir}/opencode.json",
        },
        "argv": [opencode_bin, "--model", f"openrouter/{model}"],
    }


@_register("freebuff", None)
def build_freebuff_command(runtime, provider, model, role_key, mp):
    """Build Freebuff command. Freebuff is a runtime, not a provider."""
    binaries = mp.get("binaries", {})
    paths = mp.get("paths", {})

    freebuff_bin = _resolve_binary("freebuff", binaries, "freebuff")
    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": {},
        "argv": [freebuff_bin],
    }


# ── Renderer ──────────────────────────────────────────────────


def render_tmux_shell_string(command_object):
    """Render a command object to a tmux-safe shell string.

    Builds: cd <cwd> && ENV=value ... binary --arg ...

    Uses shlex.quote() for safe shell quoting.
    Never uses shell=True internally.

    Args:
        command_object: dict with cwd, env, argv

    Returns:
        str — shell command string safe for tmux send-keys
    """
    parts = []

    # cd to working directory
    cwd = command_object.get("cwd", "")
    if cwd:
        parts.append(f"cd {shlex.quote(cwd)}")

    # Environment variables
    for key, value in command_object.get("env", {}).items():
        parts.append(f"{key}={shlex.quote(str(value))}")

    # Command and arguments
    argv = command_object.get("argv", [])
    if argv:
        parts.append(" ".join(shlex.quote(arg) for arg in argv))

    return " && ".join(parts) if parts else ""
```

- [ ] **Step 2: Valider syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/command_builder.py
```

- [ ] **Step 3: Test med AI-PC profil**

```bash
cp /home/svend/DPMtF-WebUI/profiles/machine.ai-pc.example.json /home/svend/DPMtF-WebUI/profiles/machine.local.json

python3 -c "
import json, sys
sys.path.insert(0, '/home/svend/DPMtF-WebUI/scripts/bridgeV002')
from command_builder import build_start_command, render_tmux_shell_string

with open('/home/svend/DPMtF-WebUI/profiles/machine.local.json') as f:
    mp = json.load(f)

# Test 1: Claude + local_ollama
cmd = build_start_command('claude', 'local_ollama', 'qwen3.6:35b-a3b-64k', 'archi01', mp)
print('Test 1 — Claude + local_ollama:')
print('  argv:', cmd['argv'])
print('  env keys:', list(cmd['env'].keys()))
assert 'ANTHROPIC_BASE_URL' in cmd['env']
assert cmd['argv'][0].endswith('claude')
print('  shell:', render_tmux_shell_string(cmd)[:80], '...')
print('  PASS')

# Test 2: OpenCode + openrouter
cmd = build_start_command('opencode', 'openrouter', 'z-ai/glm-5.2', 'review01_trade', mp)
print('Test 2 — OpenCode + openrouter:')
assert 'openrouter/z-ai/glm-5.2' in cmd['argv']
assert 'OPENROUTER_API_KEY' not in str(cmd)
print('  PASS')

# Test 3: Freebuff
cmd = build_start_command('freebuff', None, 'freebuff-default', 'imple01cloud', mp)
print('Test 3 — Freebuff:')
assert len(cmd['env']) == 0
assert 'freebuff' in cmd['argv'][0]
print('  PASS')

# Test 4: Unsupported combination
try:
    build_start_command('claude', 'openrouter', 'test', 'test', mp)
    print('Test 4 — FAIL: should have raised')
except ValueError as e:
    print('Test 4 — Unsupported:', str(e)[:60])
    print('  PASS')

print('All tests passed!')
"

rm /home/svend/DPMtF-WebUI/profiles/machine.local.json
```

Forventet: Alle 4 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/bridgeV002/command_builder.py
git commit -m "[trade] Opret command_builder.py — build_start_command() + 5 builders + renderer"
```

---

### Task 3: Opdater start_coding.py

**Files:**
- Modify: `scripts/bridgeV002/start_coding.py`

**Interfaces:**
- Consumes: `command_builder.build_start_command()`, `command_builder.render_tmux_shell_string()`, `config.get_machine_profile()`
- Produces: `start_coding.py` vælger mellem legacy `start_cmd_suffix` og Machine Profile kommando baseret på `flow.use_machine_profile`

- [ ] **Step 1: Tilføj import af command_builder og config**

I toppen af `start_coding.py`, efter de eksisterende imports:

```python
# Machine Profile Fase 2A — command builder
from command_builder import build_start_command, render_tmux_shell_string  # noqa: E402
```

- [ ] **Step 2: Tilføj load_flow_from_db til get_flow_roles**

`get_flow_roles()` skal også returnere `use_machine_profile` fra flowet. Opdater SQL i `get_flow_roles()`:

Find funktionen `get_flow_roles()` (omkring linje 28). Tilføj en separat query til at hente flowets `use_machine_profile`:

```python
def get_flow_machine_profile_flag(db_path, flow_key):
    """Return use_machine_profile flag for a flow (0 or 1)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT use_machine_profile FROM bridge_flows WHERE flow_key = ?",
        (flow_key,)
    ).fetchone()
    conn.close()
    if row:
        return row["use_machine_profile"] or 0
    return 0
```

- [ ] **Step 3: Opdater main() til at bruge Machine Profile**

I `main()`, efter at have hentet `roles`, tilføj logik til at tjekke `use_machine_profile`:

Find linjen hvor `roles = get_flow_roles(...)` kaldes. Efter denne linje, tilføj:

```python
# Machine Profile Fase 2A — check if flow uses Machine Profile
use_machine_profile = get_flow_machine_profile_flag(db_path, args.flow_key)
machine_profile = {}
if use_machine_profile:
    machine_profile = config_mod.get_machine_profile()
    if not machine_profile:
        print("WARNING: flow.use_machine_profile=1 but no Machine Profile found.")
        print("  Create profiles/machine.local.json or set DPMTF_MACHINE_PROFILE in .env.")
        print("  Falling back to legacy start_cmd_suffix for this run.")
        use_machine_profile = False
```

- [ ] **Step 4: Opdater run_cmd_in_session kaldet**

I løkken over roller, erstat det eksisterende `run_cmd_in_session` kald med Machine Profile logik. Find linjen:

```python
ok = run_cmd_in_session(
    session_name,
    role["start_cmd"],
    bridge_dir,
    project_root,
    start_cmd_suffix=role.get("start_cmd_suffix"),
    target_project=project_root,
)
```

Erstat med:

```python
if use_machine_profile:
    # Build command from Machine Profile
    try:
        cmd_obj = build_start_command(
            runtime=role.get("default_runtime"),
            provider=role.get("default_provider"),
            model=role.get("default_model"),
            role_key=role["role_key"],
            machine_profile=machine_profile,
        )
        # Check model against provider model list (warning only in Fase 2A)
        provider_key = role.get("default_provider")
        if provider_key and provider_key in machine_profile.get("providers", {}):
            provider_models = machine_profile["providers"][provider_key].get("models", [])
            if provider_models and role.get("default_model") not in provider_models:
                print(f"  WARNING: model '{role.get('default_model')}' not in "
                      f"Machine Profile provider '{provider_key}' model list")

        cmd_str = render_tmux_shell_string(cmd_obj)
        print(f"  Machine Profile: {cmd_str}")
        cmd = ["tmux", "send-keys", "-t", session_name, cmd_str, "Enter"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        ok = result.returncode == 0
    except ValueError as e:
        print(f"  ERROR building Machine Profile command: {e}")
        errors.append(role["role_key"])
        continue
else:
    # Legacy path — unchanged
    ok = run_cmd_in_session(
        session_name,
        role["start_cmd"],
        bridge_dir,
        project_root,
        start_cmd_suffix=role.get("start_cmd_suffix"),
        target_project=project_root,
    )
```

- [ ] **Step 5: Valider syntaks**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/bridgeV002/start_coding.py
git commit -m "[trade] Opdater start_coding.py til Machine Profile — vælg mellem legacy og build_start_command() baseret på flow.use_machine_profile"
```

---

### Task 4: Frontend — flow checkbox + rolle dropdowns

**Files:**
- Modify: `static/js/dpmtf-app.js`
- Modify: `templates/index.html` (hvis nødvendigt for nye form-felter)

**Interfaces:**
- Consumes: `GET /api/system/machine-profile` (til at tjekke om Machine Profile findes)
- Produces: Flow-formular med `use_machine_profile` checkbox, rolle-formular med `default_runtime`, `default_provider`, `default_model` dropdowns

- [ ] **Step 1: Tilføj use_machine_profile checkbox i flow-formularen**

Find flow-formularens render/update funktion i `dpmtf-app.js`. Tilføj checkbox efter eksisterende felter:

```javascript
// Machine Profile Fase 2A — use_machine_profile checkbox
var mpCheckbox = el("input", null);
mpCheckbox.type = "checkbox";
mpCheckbox.id = "bridge-input-use-machine-profile";
mpCheckbox.checked = data.use_machine_profile === 1;

var mpLabel = el("label", "dpmtf-label");
mpLabel.textContent = lbl("lbl_bridge_use_machine_profile", "Brug Machine Profile til startkommandoer");
mpLabel.htmlFor = "bridge-input-use-machine-profile";

// Check if Machine Profile is available and valid
fetch("/api/system/machine-profile")
  .then(function (res) { return res.json(); })
  .then(function (meta) {
    if (!meta.exists) {
      mpCheckbox.disabled = true;
      var helpText = el("p", "dpmtf-small dpmtf-muted");
      helpText.textContent = lbl("lbl_mp_missing",
        "Machine Profile mangler — opret profil i System Setup før aktivering.");
      mpLabel.appendChild(helpText);
    } else if (meta.parse_error) {
      mpCheckbox.disabled = true;
      var helpText = el("p", "dpmtf-small dpmtf-muted");
      helpText.textContent = lbl("lbl_mp_parse_error",
        "Machine Profile har JSON-fejl — ret profilen før aktivering.");
      mpLabel.appendChild(helpText);
    } else if (meta.schema_version !== 1) {
      mpCheckbox.disabled = true;
      var helpText = el("p", "dpmtf-small dpmtf-muted");
      helpText.textContent = lbl("lbl_mp_schema_mismatch",
        "Machine Profile schema_version matcher ikke — opdater profilen før aktivering.");
      mpLabel.appendChild(helpText);
    }
  })
  .catch(function () {
    mpCheckbox.disabled = true;
  });

form.appendChild(mpCheckbox);
form.appendChild(mpLabel);
```

- [ ] **Step 2: Tilføj default_runtime, default_provider, default_model i rolle-formularen**

Find rolle-formularens render/update funktion. Tilføj tre dropdowns efter eksisterende felter:

```javascript
// Machine Profile Fase 2A — logical runtime fields
fetch("/api/system/machine-profile")
  .then(function (res) { return res.json(); })
  .then(function (meta) {
    var disabled = !meta.exists || meta.parse_error || meta.schema_version !== 1;

    // default_runtime dropdown
    var rtLabel = el("label", "dpmtf-label");
    rtLabel.textContent = lbl("lbl_bridge_default_runtime", "default_runtime");
    var rtSelect = el("select", null);
    rtSelect.id = "bridge-input-default-runtime";
    rtSelect.disabled = disabled;
    var rtEmpty = el("option", null);
    rtEmpty.value = "";
    rtEmpty.textContent = "";
    rtSelect.appendChild(rtEmpty);
    if (!disabled) {
      // Populate from Machine Profile — runtimes are in capabilities + runtimes sections
      // For now, hardcode the 3 known runtimes (can be made dynamic later)
      ["claude", "opencode", "freebuff"].forEach(function (rt) {
        var opt = el("option", null);
        opt.value = rt;
        opt.textContent = rt;
        if (data.default_runtime === rt) opt.selected = true;
        rtSelect.appendChild(opt);
      });
    }
    form.appendChild(rtLabel);
    form.appendChild(rtSelect);

    // default_provider dropdown
    var pvLabel = el("label", "dpmtf-label");
    pvLabel.textContent = lbl("lbl_bridge_default_provider", "default_provider");
    var pvSelect = el("select", null);
    pvSelect.id = "bridge-input-default-provider";
    pvSelect.disabled = disabled;
    var pvEmpty = el("option", null);
    pvEmpty.value = "";
    pvEmpty.textContent = "";
    pvSelect.appendChild(pvEmpty);
    if (!disabled && meta.providers) {
      Object.keys(meta.providers).forEach(function (pv) {
        var opt = el("option", null);
        opt.value = pv;
        opt.textContent = pv + " (" + (meta.providers[pv].model_count || 0) + " models)";
        if (data.default_provider === pv) opt.selected = true;
        pvSelect.appendChild(opt);
      });
    }
    form.appendChild(pvLabel);
    form.appendChild(pvSelect);

    // default_model dropdown (text input for now — model lists can be large)
    var mdLabel = el("label", "dpmtf-label");
    mdLabel.textContent = lbl("lbl_bridge_default_model", "default_model");
    var mdInput = el("input", null);
    mdInput.type = "text";
    mdInput.id = "bridge-input-default-model";
    mdInput.value = data.default_model || "";
    mdInput.disabled = disabled;
    form.appendChild(mdLabel);
    form.appendChild(mdInput);
  });
```

- [ ] **Step 3: Opdater save-funktioner til at inkludere nye felter**

I flow save-funktionen, tilføj:

```javascript
if (document.getElementById("bridge-input-use-machine-profile")) {
  body.use_machine_profile = document.getElementById("bridge-input-use-machine-profile").checked ? 1 : 0;
}
```

I rolle save-funktionen, tilføj:

```javascript
var rtEl = document.getElementById("bridge-input-default-runtime");
var pvEl = document.getElementById("bridge-input-default-provider");
var mdEl = document.getElementById("bridge-input-default-model");
if (rtEl) body.default_runtime = rtEl.value || null;
if (pvEl) body.default_provider = pvEl.value || null;
if (mdEl) body.default_model = mdEl.value || null;
```

- [ ] **Step 4: Valider JavaScript**

```bash
node --check /home/svend/DPMtF-WebUI/static/js/dpmtf-app.js
```

- [ ] **Step 5: Commit**

```bash
git add static/js/dpmtf-app.js
git commit -m "[trade] Tilføj Machine Profile frontend — use_machine_profile checkbox på flow, default_runtime/provider/model på rolle"
```

---

### Task 5: i18n labels

**Files:**
- Modify: `scripts/init_db.py`

**Interfaces:**
- Produces: Seed data for nye UI labels i `en-US` og `da-DK`

- [ ] **Step 1: Tilføj ui_labels**

Find `ui_labels_data` listen og tilføj før `]`:

```python
    # ── Machine Profile Fase 2A — flow/role labels ──
    ("LBL-1000346", "lbl_bridge_use_machine_profile", "main", "Use Machine Profile for start commands", "Checkbox label for enabling Machine Profile on a flow"),
    ("LBL-1000347", "lbl_bridge_default_runtime", "main", "default_runtime", "Label for default runtime field on role form"),
    ("LBL-1000348", "lbl_bridge_default_provider", "main", "default_provider", "Label for default provider field on role form"),
    ("LBL-1000349", "lbl_bridge_default_model", "main", "default_model", "Label for default model field on role form"),
    ("LBL-1000350", "lbl_mp_missing", "main", "Machine Profile missing — create profile in System Setup before activating.", "Help text when Machine Profile file is missing"),
    ("LBL-1000351", "lbl_mp_parse_error", "main", "Machine Profile has JSON error — fix profile before activating.", "Help text when Machine Profile JSON is invalid"),
    ("LBL-1000352", "lbl_mp_schema_mismatch", "main", "Machine Profile schema_version mismatch — update profile before activating.", "Help text when Machine Profile schema_version does not match"),
```

- [ ] **Step 2: Tilføj ui_label_translations (da-DK)**

Find `ui_label_translations_data` listen og tilføj før `]`:

```python
    # ── Machine Profile Fase 2A — Danish translations ──
    ("LBL-1000346", "da-DK", "Brug Machine Profile til startkommandoer"),
    ("LBL-1000347", "da-DK", "default_runtime"),
    ("LBL-1000348", "da-DK", "default_provider"),
    ("LBL-1000349", "da-DK", "default_model"),
    ("LBL-1000350", "da-DK", "Machine Profile mangler — opret profil i System Setup før aktivering."),
    ("LBL-1000351", "da-DK", "Machine Profile har JSON-fejl — ret profilen før aktivering."),
    ("LBL-1000352", "da-DK", "Machine Profile schema_version matcher ikke — opdater profilen før aktivering."),
```

- [ ] **Step 3: Valider og kør**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py
python3 /home/svend/DPMtF-WebUI/scripts/init_db.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/init_db.py
git commit -m "[trade] Tilføj i18n labels for Machine Profile Fase 2A — flow checkbox + rolle dropdowns"
```

---

### Task 6: Opdater governance docs

**Files:**
- Modify: `docs/governance-templates-v2/11_SCOPE.md`
- Modify: `docs/governance-templates-v2/20_GATES.md`

- [ ] **Step 1: Opdater 11_SCOPE.md**

Erstat Machine Profile Fase 1 scope med Fase 2A:

```markdown
## Aktivt scope — Machine Profile Fase 2A

### Inden for scope

- `bridge_flows.use_machine_profile` kolonne (idempotent)
- `bridge_roles.default_runtime`, `default_provider`, `default_model` kolonner (idempotent)
- `scripts/bridgeV002/command_builder.py` — `build_start_command()` + 5 builders + renderer
- `start_coding.py` ændring — vælg mellem legacy og Machine Profile kommando
- Frontend: `use_machine_profile` checkbox på flow, `default_runtime/provider/model` på rolle
- i18n labels for nye UI-elementer

### Uden for scope

- Fjernelse af `start_cmd_suffix`
- Massemigrering af alle flows
- `command_templates` i Machine Profile
- `runtime_commands` database-tabel
- Flow-role overrides (Fase 2B)
- Ændring af tmux/prompt/flow execution ud over valg af startkommando
```

- [ ] **Step 2: Opdater 20_GATES.md**

Tilføj:

```markdown
### GATE-M6: Machine Profile Activation

TRIGGER: User enables use_machine_profile on a flow.

QUESTION: "Er Machine Profile valid og mindst én provider available?"

CONSEQUENCE:
  - Hvis Machine Profile mangler → checkbox disabled, kan ikke aktiveres
  - Hvis JSON invalid → checkbox disabled, kan ikke aktiveres
  - Hvis schema_version mismatch → checkbox disabled, kan ikke aktiveres
  - Hvis ingen provider available → advarsel men tillader aktivering

### GATE-M7: No Silent Fallback

TRIGGER: Flow har use_machine_profile=1 men build_start_command() fejler.

QUESTION: "Skal fejlen rapporteres og rollen stoppes?"

CONSEQUENCE:
  - Fejl skal være synlig — ingen skjult fallback til start_cmd_suffix
  - Rollen startes ikke
  - Fejlbesked logges
```

- [ ] **Step 3: Commit**

```bash
git add docs/governance-templates-v2/11_SCOPE.md docs/governance-templates-v2/20_GATES.md
git commit -m "[trade] Opdater governance docs for Machine Profile Fase 2A"
```

---

## Verifikation — alle tests

- [ ] **Test 1: Kolonner eksisterer og er idempotente**

```bash
python3 /home/svend/DPMtF-WebUI/scripts/init_db.py
# Forventet: "Database initialized successfully!" — ingen fejl ved gentaget kørsel
```

- [ ] **Test 2: build_start_command() med AI-PC profil**

```bash
cp /home/svend/DPMtF-WebUI/profiles/machine.ai-pc.example.json /home/svend/DPMtF-WebUI/profiles/machine.local.json
python3 -c "
import json, sys
sys.path.insert(0, '/home/svend/DPMtF-WebUI/scripts/bridgeV002')
from command_builder import build_start_command, render_tmux_shell_string
with open('/home/svend/DPMtF-WebUI/profiles/machine.local.json') as f:
    mp = json.load(f)
# Claude + local_ollama
cmd = build_start_command('claude', 'local_ollama', 'qwen3.6:35b-a3b-64k', 'test', mp)
assert 'ANTHROPIC_BASE_URL' in cmd['env']
# OpenCode + openrouter
cmd = build_start_command('opencode', 'openrouter', 'z-ai/glm-5.2', 'test', mp)
assert 'openrouter/z-ai/glm-5.2' in cmd['argv']
assert 'OPENROUTER_API_KEY' not in str(cmd)
# Freebuff
cmd = build_start_command('freebuff', None, 'freebuff-default', 'test', mp)
assert len(cmd['env']) == 0
# Unsupported
try:
    build_start_command('claude', 'openrouter', 'test', 'test', mp)
    assert False, 'should have raised'
except ValueError:
    pass
print('All command builder tests passed!')
"
rm /home/svend/DPMtF-WebUI/profiles/machine.local.json
```

- [ ] **Test 3: Python validering**

```bash
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/init_db.py
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/command_builder.py
python3 -m py_compile /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
python3 -m py_compile /home/svend/DPMtF-WebUI/app.py
```

- [ ] **Test 4: JavaScript validering**

```bash
node --check /home/svend/DPMtF-WebUI/static/js/dpmtf-app.js
```

- [ ] **Test 5: use_machine_profile default = 0**

```bash
sqlite3 /home/svend/DPMtF-WebUI/databases/dpmtf.db "SELECT flow_key, use_machine_profile FROM bridge_flows;"
# Forventet: alle flows viser 0 eller tom (NULL)
```

- [ ] **Test 6: No-runtime-diff**

```bash
git diff --name-only HEAD~6..HEAD
# Forventet: kun tilladte filer — scripts/init_db.py, scripts/bridgeV002/command_builder.py, scripts/bridgeV002/start_coding.py, static/js/dpmtf-app.js, docs/governance-templates-v2/*
```

---

## Stopregel — verificér før hver commit

```bash
git diff --name-only HEAD
```

Tilladte filer i Fase 2A:

```
scripts/init_db.py
scripts/bridgeV002/command_builder.py
scripts/bridgeV002/start_coding.py
static/js/dpmtf-app.js
templates/index.html
docs/governance-templates-v2/11_SCOPE.md
docs/governance-templates-v2/20_GATES.md
docs/superpowers/specs/2026-06-30-machine-profile-phase2-design.md
docs/superpowers/plans/2026-06-30-machine-profile-phase2.md
```

Hvis andre filer ændres → **STOP**. Rapporter hvorfor.

Bekræft i færdigmelding:

```
start_cmd_suffix ikke fjernet
Ingen massemigrering
Ingen ændring af tmux injection
Ingen ændring af prompt injection
Ingen ændring af deliverable_dir resolution
Ingen ændring af flow execution logic ud over valg af startkommando
```
