# 300 — SETUP INSTRUCTIONS

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines how to configure DPMtF-WebUI and claude-bridge when moving the system
to a new PC or setting up a fresh development environment. Covers platform
requirements, config file editing, and tmux session setup.

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
| Python 3.12+ | app.py, bridge.py, config.py | `sudo apt install python3` (Ubuntu/Debian) |
| tmux | 3-layer bridge communication | `sudo apt install tmux` (Ubuntu/Debian) |
| Git | Version control | `sudo apt install git` |
| pip packages | FastAPI, uvicorn, python-dotenv | `pip install -r requirements.txt` |

**Tested on:** Ubuntu 24.04+, Debian 12+, Linux Mint 22+.

### macOS (Supported — Requires Homebrew)

All components work on macOS with Homebrew-installed dependencies:

```bash
# Install prerequisites
brew install python@3.12 tmux git

# Verify tmux version (must be >= 3.3)
tmux -V
```

**Caveats:**
- Paths use `/Users/<username>/` instead of `/home/<username>/`.
- `os.path.expanduser("~")` resolves correctly on macOS — config.py getters
  adapt automatically.
- Default file permissions may differ; `chmod` if bridge.py is not executable.

### Windows (WSL2 Required)

DPMtF does **not** run natively on Windows. The bridge architecture depends on
`tmux`, which has no native Windows port. **Windows Subsystem for Linux 2 (WSL2)**
is required:

```powershell
# In PowerShell (Admin):
wsl --install -d Ubuntu-24.04
```

Once WSL2 is running, follow the Linux instructions above inside the WSL2
terminal. All project files must reside inside the WSL2 filesystem
(`/home/<username>/...`), not on Windows drives (`/mnt/c/...`).

**Why WSL2 is mandatory:**
- `tmux` requires a Unix PTY (pseudo-terminal) — unavailable on native Windows.
- `bridge.py` uses `tmux send-keys` for inter-session communication.
- The 3-layer governance loop (implementer ↔ review ↔ architect) depends on
  persistent tmux sessions.

**Alternatives that do NOT work:**
- Cygwin / MSYS2 — tmux support is incomplete and unstable.
- Docker — tmux inside containers requires `--privileged` mode and host PTY access.
- GitHub Codespaces / cloud VM — works but requires always-on connectivity.

---

## Configuration Files

Two files control all configurable values. Edit these when moving to a new PC.

### dpmtf.ini — App Configuration

**Location:** `<project_root>/dpmtf.ini`
**Commited to git:** Yes (contains defaults, no secrets).

```ini
[app]
port = 9130              # Server port — change if port is in use
host = 0.0.0.0           # Bind address — 0.0.0.0 for all interfaces
default_locale = en-US   # Default i18n locale

[database]
path = databases/dpmtf.db   # Relative to project root

[paths]
project_root = /home/svend/DPMtF-WebUI    # ← CHANGE THIS on new PC
bridge_dir = /home/svend/claude-bridge     # ← CHANGE THIS on new PC
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
| `bridge_dir` | `/home/svend/claude-bridge` | `/home/alice/claude-bridge` |
| `port` | `9130` | `9130` (change only if port conflict) |

### .env — Secrets & Infrastructure

**Location:** `<project_root>/.env`
**Commited to git:** **NEVER** — contains secrets. In `.gitignore`.

```ini
# Secrets (existing — do NOT commit)
DPMTF_TELEGRAM_BOT_TOKEN=...
DPMTF_TELEGRAM_CHAT_ID=...
DPMTF_CLAUDE_TMUX_SESSION=...

# Bridge infrastructure (added Spor A — 2026-06-16)
DPMTF_BRIDGE_DIR=/home/svend/claude-bridge     # ← CHANGE THIS on new PC
DPMTF_REVIEW_SESSION=claude_review
DPMTF_IMPLEMENTER_SESSION=claude_implementer
DPMTF_ARCHITECT_SESSION=claude_architect
```

**What to change on a new PC:**

| Key | Example old | Example new |
|-----|-------------|-------------|
| `DPMTF_BRIDGE_DIR` | `/home/svend/claude-bridge` | `/home/alice/claude-bridge` |
| `DPMTF_TELEGRAM_BOT_TOKEN` | (old token) | (new bot token from @BotFather) |
| `DPMTF_TELEGRAM_CHAT_ID` | (old chat ID) | (new chat ID) |

**Session names** (`DPMTF_REVIEW_SESSION`, etc.) normally stay the same unless
you have naming conflicts with existing tmux sessions.

### Environment Variable Fallback

If `DPMTF_BRIDGE_DIR` is not set in the shell environment AND not in `.env`,
bridge.py falls back to `~/.dpmtf/bridge`. To avoid this, either:

1. **Set in `.env`** (loaded by config.py when DPMtF-WebUI runs).
2. **Export in shell profile** (`~/.bashrc`):
   ```bash
   export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge
   ```
3. **Both** — `.env` for the web app, shell export for direct bridge.py CLI use.

**Recommendation:** Do both. The `.env` file covers the web app. The shell
export covers manual `bridge.py send` / `bridge.py complete` commands run
directly in the terminal.

---

## Tmux Session Setup

The governance loop requires three persistent tmux sessions:

| Session Name | Role | Model | Purpose |
|-------------|------|-------|---------|
| `claude_implementer` | Implementor | Local (Ollama) | Code execution |
| `claude_review` | Review | Cloud (cheap) | Validation & dispatch |
| `claude_architect` | Architect | Cloud (capable) | Design & escalation |

### Create Sessions

```bash
# Create three named sessions (detached)
tmux new-session -d -s claude_implementer
tmux new-session -d -s claude_review
tmux new-session -d -s claude_architect
```

### Verify Sessions

```bash
tmux list-sessions
# Expected output:
# claude_architect: 1 windows (created ...)
# claude_implementer: 1 windows (created ...)
# claude_review: 1 windows (created ...)
```

### Start Claude Code in Each Session

```bash
# In each tmux session, start Claude Code:
tmux attach -t claude_implementer
# Inside: claude (or your Claude Code launch command)

tmux attach -t claude_review
# Inside: claude

tmux attach -t claude_architect
# Inside: claude
```

Detach from a session with `Ctrl+B, D`.

### Session Names in Config

If you use different session names, update them in `.env`:

```ini
DPMTF_REVIEW_SESSION=my_review_session
DPMTF_IMPLEMENTER_SESSION=my_implementer_session
DPMTF_ARCHITECT_SESSION=my_architect_session
```

---

## Quick-Start Checklist

### Fresh Linux Install

```bash
# 1. Install prerequisites
sudo apt update && sudo apt install python3 python3-pip tmux git

# 2. Clone repository
git clone <repo-url> ~/DPMtF-WebUI
cd ~/DPMtF-WebUI

# 3. Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Edit config files for your paths
nano dpmtf.ini     # Change project_root, bridge_dir
nano .env           # Change DPMTF_BRIDGE_DIR, tokens

# 5. Export bridge dir in shell (for CLI bridge.py calls)
echo 'export DPMTF_BRIDGE_DIR=/home/<you>/claude-bridge' >> ~/.bashrc
source ~/.bashrc

# 6. Create bridge directory
mkdir -p ~/claude-bridge/reviewtoimplementor
mkdir -p ~/claude-bridge/implementertoreview
mkdir -p ~/claude-bridge/reviewtoarchitect
mkdir -p ~/claude-bridge/architecttoreview

# 7. Copy bridge.py to bridge directory
cp /path/to/bridge.py ~/claude-bridge/

# 8. Initialize database
python3 scripts/init_db.py

# 9. Create tmux sessions
tmux new-session -d -s claude_implementer
tmux new-session -d -s claude_review
tmux new-session -d -s claude_architect

# 10. Start the app
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130
```

### macOS Install

Same as Linux, but install prerequisites via Homebrew:

```bash
# 1. Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install prerequisites
brew install python@3.12 tmux git

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

Run these checks to verify the setup is correct:

```bash
# 1. Config loads correctly
python3 -c "import sys; sys.path.insert(0,'.'); import config; print(config.get_project_root()); print(config.get_bridge_dir())"
# Must print your actual paths, not /home/svend/...

# 2. Database is initialized
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute('SELECT COUNT(*) FROM ui_labels').fetchone()[0])"
# Must print a positive number

# 3. Bridge.py works
python3 ~/claude-bridge/bridge.py next-id
# Must print a number without errors

# 4. Tmux sessions exist
tmux list-sessions
# Must show claude_implementer, claude_review, claude_architect

# 5. App starts
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130 &
sleep 2
curl -s http://localhost:9130/api/health || echo "Health check failed"
```

---

## Related Reference Files

| File | Use When |
|------|----------|
| [[10_PROJECT]] | Confirming project identity and port. |
| [[14_ARCHITECTURE]] | Understanding component layout and bridge architecture. |
| [[100_BRIDGE]] | Bridge protocol details and tmux communication. |
| [[12_CODING_STANDARD]] | Config Lookup Pattern — mandatory config.py usage. |
| [[16_FILE_ACCESS]] | Project Root Resolution via config.py. |

---
