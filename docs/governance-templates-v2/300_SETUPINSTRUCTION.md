# 300 — SETUP INSTRUCTIONS

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines how to configure DPMtF-WebUI with BridgeV002 when moving the system
to a new PC or setting up a fresh development environment. Covers platform
requirements, config file editing, database initialization, and flow setup.

**BridgeV002 replaces the legacy claude-bridge entirely.** All role-to-role
communication is database-driven via `dispatch.py`. No hardcoded session names,
no manual tmux setup, no `bridge.py`.

## When to Use

- **First-time setup** on a new machine.
- **PC migration** — moving DPMtF from one computer to another.
- **Path changes** — when project directories move to a different location.
- **After `/clear`:** Reference for environment reconstruction.

---

## Platform Support

### Linux (Primary — Fully Supported)

All DPMtF components run natively on Linux:

| Component | Requirement | Install |
|-----------|-------------|---------|
| Python 3.12+ | app.py, dispatch.py, config.py | `sudo apt install python3` (Ubuntu/Debian) |
| tmux | BridgeV002 session transport | `sudo apt install tmux` (Ubuntu/Debian) |
| Ollama | Local model runtime (optional — cloud models also supported) | `curl -fsSL https://ollama.com/install.sh \| sh` |
| Git | Version control | `sudo apt install git` |
| pip packages | FastAPI, uvicorn | `pip install -r requirements.txt` |

**Tested on:** Ubuntu 24.04+, Debian 12+, Linux Mint 22+.

### macOS (Supported — Requires Homebrew)

All components work on macOS with Homebrew-installed dependencies:

```bash
brew install python@3.12 tmux git ollama
```

**Caveats:**
- Paths use `/Users/<username>/` instead of `/home/<username>/`.
- `os.path.expanduser("~")` resolves correctly on macOS — config.py getters
  adapt automatically.

### Windows (WSL2 Required)

DPMtF does **not** run natively on Windows. tmux has no native Windows port.
**Windows Subsystem for Linux 2 (WSL2)** is required:

```powershell
# In PowerShell (Admin):
wsl --install -d Ubuntu-24.04
```

Once WSL2 is running, follow the Linux instructions inside the WSL2 terminal.
All project files must reside inside the WSL2 filesystem
(`/home/<username>/...`), not on Windows drives (`/mnt/c/...`).

---

## Configuration Files

Three files control all configurable values. Edit these when moving to a new PC.

### dpmtf.ini — App Configuration

**Location:** `<project_root>/dpmtf.ini`
**Committed to git:** Yes (contains defaults, no secrets).

```ini
[app]
port = 9130              # Server port — change if port is in use
host = 0.0.0.0           # Bind address — 0.0.0.0 for all interfaces
default_locale = en-US   # Default i18n locale

[database]
path = databases/dpmtf.db   # Relative to project root

[paths]
project_root = /home/<you>/DPMtF-WebUI    # ← CHANGE THIS on new PC
governance_dir = docs/governance-templates-v2
log_dir = logs
exports_dir = exports

[projects]
father_project = DPMtF-WebUI
child_projects = ENO                        # Comma-separated for multiple
reference_projects = ai-pc-resource-webui-v3
```

**What to change on a new PC:**

| Key | Example old | Example new |
|-----|-------------|-------------|
| `project_root` | `/home/svend/DPMtF-WebUI` | `/home/alice/DPMtF-WebUI` |
| `port` | `9130` | `9130` (change only if port conflict) |

> **Note:** `bridge_dir` is no longer in `dpmtf.ini`. Bridge paths are
> controlled by `DPMTF_BRIDGE_DIR` in `.env` (see below).

### .env — Secrets & Infrastructure

**Location:** `<project_root>/.env`
**Committed to git:** **NEVER** — contains secrets. In `.gitignore`.

```ini
# BridgeV002 infrastructure
DPMTF_BRIDGE_DIR=/home/<you>/flows     # ← CHANGE THIS on new PC

# Optional: Telegram notifications (legacy — may be removed)
DPMTF_TELEGRAM_BOT_TOKEN=...
DPMTF_TELEGRAM_CHAT_ID=...
```

**What to change on a new PC:**

| Key | Example old | Example new |
|-----|-------------|-------------|
| `DPMTF_BRIDGE_DIR` | `/home/svend/flows` | `/home/alice/flows` |

> **Note:** The legacy session variables (`DPMTF_REVIEW_SESSION`,
> `DPMTF_IMPLEMENTER_SESSION`, `DPMTF_ARCHITECT_SESSION`) are **no longer used**.
> BridgeV002 resolves session names from the database (`bridge_roles.tmux_session`).

### Shell Environment

Export `DPMTF_BRIDGE_DIR` in your shell profile so manual dispatch commands work:

```bash
echo 'export DPMTF_BRIDGE_DIR=/home/<you>/flows' >> ~/.bashrc
source ~/.bashrc
```

---

## BridgeV002 — Database-Driven Flow Setup

BridgeV002 replaces the legacy `bridge.py` + hardcoded tmux sessions entirely.
All configuration lives in the database, managed via the DPMtF web UI.

### How It Works

1. **Flows** (`bridge_flows`) — define a sequence of role-to-role steps
   (e.g., `strict_review`: archi01 → imple01 → review01 → review02 → human).
2. **Roles** (`bridge_roles`) — each role has a `tmux_session` name,
   `start_cmd` (how to launch Claude Code / OpenCode), and `ollama_model`.
3. **Steps** (`bridge_flow_steps`) — each step defines from_role, to_role,
   deliverable paths, and pre/post dispatch scripts.
4. **Conventions** (`bridge_convention_rules`) — content templates for
   handoff prompts, callback formats, and verdict structures.

### Setup Per Flow Key

Different flows require different tmux sessions. The sessions needed for a
flow are determined by the `from_role` entries in `bridge_flow_steps`.

**Example — `strict_review` flow:**

| Step | From Role | To Role | Tmux Session |
|------|-----------|---------|--------------|
| archi01-imple01 | archi01 | imple01 | archi01, imple01 |
| imple01-review01 | imple01 | review01 | imple01, review01 |
| review01-review02 | review01 | review02 | review01, review02 |
| review02-human | review02 | human | review02 |

→ **4 tmux sessions required:** `archi01`, `imple01`, `review01`, `review02`

**Other flows** (e.g., a simplified 2-role flow) would require fewer sessions.
The UI's **Start tmux** button reads the flow definition from the database
and creates exactly the sessions needed — no guessing, no hardcoding.

### Setup Steps (via Web UI)

1. Start DPMtF-WebUI: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload`
2. Open `http://localhost:9130` in a browser.
3. Go to **Setup** → **Bridge Setup** panel.
4. Verify flows, roles, steps, and conventions are configured (seed data
   from `init_db.py` provides `strict_review` defaults).
5. Click **Start tmux** for your flow — creates all required sessions.
6. Click **Start Coding** — launches Claude Code / OpenCode in each session.
7. Click **Attach tmux** — builds a viewer session (`flow-<flow_key>`)
   with one window per role. Attach with `tmux attach -t flow-<flow_key>`.

### Setup Steps (via Terminal — Alternative)

```bash
# 1. Create tmux sessions for the flow
python3 scripts/bridgeV002/start_tmuxflow.py strict_review

# 2. Launch Claude Code / OpenCode in each session
python3 scripts/bridgeV002/start_coding.py strict_review

# 3. Build viewer session
python3 scripts/bridgeV002/attach_tmux.py strict_review
tmux attach -t flow-strict_review
```

---

## Quick-Start Checklist

### Fresh Linux Install

```bash
# 1. Install prerequisites
sudo apt update && sudo apt install python3 python3-pip tmux git
curl -fsSL https://ollama.com/install.sh | sh

# 2. Clone repository
git clone <repo-url> ~/DPMtF-WebUI
cd ~/DPMtF-WebUI

# 3. Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Edit config files for your paths
nano dpmtf.ini     # Change project_root
nano .env           # Change DPMTF_BRIDGE_DIR to /home/<you>/flows

# 5. Export bridge dir in shell
echo 'export DPMTF_BRIDGE_DIR=/home/<you>/flows' >> ~/.bashrc
source ~/.bashrc

# 6. Create bridge directory
mkdir -p ~/flows

# 7. Initialize database (creates tables + seed data including strict_review flow)
python3 scripts/init_db.py

# 8. Pull Ollama models (if using local models)
ollama pull qwen3.6:35b-a3b
ollama pull qwen3.6:27b-q4_K_M

# 9. Start the app
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 9130 --reload

# 10. Open http://localhost:9130 → Setup → Bridge Setup
#     Use Start tmux → Start Coding → Attach tmux buttons
```

### macOS Install

Same as Linux, but install prerequisites via Homebrew:

```bash
brew install python@3.12 tmux git ollama
# Then follow Linux steps 2-10 above.
# Paths will be /Users/<you>/... instead of /home/<you>/...
```

### Windows Install (WSL2)

```powershell
# In PowerShell (Admin):
wsl --install -d Ubuntu-24.04
# Restart, launch Ubuntu from Start Menu, then follow Linux steps 1-10.
```

---

## Validation After Setup

```bash
# 1. Config loads correctly
python3 -c "import config; print('project_root:', config.get_project_root()); print('bridge_dir:', config.get_bridge_dir())"
# Must print your actual paths, not /home/svend/...

# 2. Database is initialized with flow data
python3 -c "
import sqlite3
conn = sqlite3.connect('databases/dpmtf.db')
print('Flows:', conn.execute('SELECT COUNT(*) FROM bridge_flows').fetchone()[0])
print('Roles:', conn.execute('SELECT COUNT(*) FROM bridge_roles WHERE is_active=1').fetchone()[0])
print('Steps:', conn.execute('SELECT COUNT(*) FROM bridge_flow_steps WHERE is_active=1').fetchone()[0])
conn.close()
"

# 3. BridgeV002 dispatch works
python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --help
# Must print help text without errors

# 4. App starts and API responds
curl -s http://localhost:9130/api/health
curl -s http://localhost:9130/api/bridge-v2/status
curl -s http://localhost:9130/api/bridge-v2/flows

# 5. Tmux sessions for your flow (after clicking Start tmux in UI)
tmux list-sessions
# Must show the sessions defined in bridge_roles for your flow
```

---

## Adding a New Flow

BridgeV002 supports multiple flows. To add a new flow:

1. **Create the flow** in UI: Setup → Bridge Setup → Flows → Add Flow.
2. **Create roles** for the flow: Setup → Bridge Setup → Roles → Add Role.
   Each role needs a `tmux_session` name and `start_cmd`.
3. **Create steps** for the flow: Setup → Bridge Setup → Steps → Add Step.
   Each step defines from_role → to_role and deliverable paths.
4. **Create conventions** if the defaults don't fit: Setup → Bridge Setup →
   Conventions → Edit. Convention rules define prompt templates and
   validation schemas.

The UI exposes all CRUD operations for flows, roles, steps, and conventions.
No config files to edit, no scripts to write.

---

## Related Reference Files

| File | Use When |
|------|----------|
| [[10_PROJECT]] | Confirming project identity and port. |
| [[14_ARCHITECTURE]] | Understanding component layout and bridge architecture. |
| [[100_BRIDGE]] | BridgeV002 protocol and dispatch signals. |
| [[12_CODING_STANDARD]] | Config Lookup Pattern — mandatory config.py usage. |
| [[16_FILE_ACCESS]] | Project Root Resolution via config.py. |
| [[402_STRICT_REVIEW_ARCHI01]] | Architect role definition for strict_review flow. |
| [[403_STRICT_REVIEW_IMPLE01]] | Implementer role definition for strict_review flow. |
