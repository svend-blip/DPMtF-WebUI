"""Central configuration for {PROJECT_NAME}.

Single source of truth for all configurable values.
Paths, ports, model names, project references MUST come from here.
Hardcoding /home/svend/... anywhere else is an auto-fail in validation.

Sources (in priority order):
1. Environment variables (secrets, infrastructure)
2. dpmtf.ini (app-config)
3. Hardcoded fallbacks (last resort, for development only)
"""

import os
import configparser
from pathlib import Path

# ── .env loading ────────────────────────────────────────────────

def _load_env():
    """Load .env file into os.environ. Manual loader — no dependencies."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

_load_env()

# ── .ini loading ────────────────────────────────────────────────

_ini_path = Path(__file__).resolve().parent / "dpmtf.ini"
_config = configparser.ConfigParser()
if _ini_path.exists():
    _config.read(_ini_path, encoding="utf-8")

# ── Getter functions ────────────────────────────────────────────

def get_db_path() -> str:
    """Database path. .ini [database] path, or fallback."""
    return _config.get("database", "path", fallback="databases/{DATABASE}")

def get_bridge_dir() -> str:
    """Bridge directory. Env var DPMTF_BRIDGE_DIR, or .ini [paths] bridge_dir, or fallback."""
    env = os.environ.get("DPMTF_BRIDGE_DIR")
    if env:
        return env
    return _config.get("paths", "bridge_dir", fallback="/home/svend/claude-bridge")

def get_project_root() -> str:
    """Project root directory. .ini [paths] project_root, or derived from this file's location."""
    configured = _config.get("paths", "project_root", fallback=None)
    if configured:
        return configured
    return str(Path(__file__).resolve().parent)

def get_governance_dir() -> str:
    """Governance docs directory (relative to project root)."""
    return _config.get("paths", "governance_dir", fallback="docs/dpmtf")

def get_governance_dir_abs() -> str:
    """Governance docs directory (absolute path)."""
    return str(Path(get_project_root()) / get_governance_dir())

def get_father_project() -> str:
    """Father project name."""
    return _config.get("projects", "father_project", fallback="DPMtF-WebUI")

def get_father_governance_dir() -> str:
    """Father project's governance directory (absolute path).

    Returns path to DPMtF-WebUI/docs/governance-templates-v2/
    where all structural governance files live.
    Child projects reference these, not maintain copies.
    """
    father_root = "{FATHER_PROJECT_ROOT}"
    return str(Path(father_root) / "docs" / "governance-templates-v2")

def get_child_projects() -> list:
    """Child project names (comma-separated in .ini)."""
    raw = _config.get("projects", "child_projects", fallback="")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_reference_projects() -> list:
    """Reference project names (comma-separated in .ini)."""
    raw = _config.get("projects", "reference_projects", fallback="")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_port() -> int:
    """Server port."""
    try:
        return _config.getint("app", "port")
    except (ValueError, KeyError):
        return 5000

def get_host() -> str:
    """Server host."""
    return _config.get("app", "host", fallback="0.0.0.0")

def get_default_locale() -> str:
    """Default locale for i18n."""
    return _config.get("app", "default_locale", fallback="en-US")

def get_log_dir() -> str:
    """Log directory (relative to project root)."""
    return _config.get("paths", "log_dir", fallback="logs")

def get_exports_dir() -> str:
    """Exports directory (relative to project root)."""
    return _config.get("paths", "exports_dir", fallback="exports")

# ── Bridge session names (env vars with defaults) ───────────────

def get_review_session() -> str:
    return os.environ.get("DPMTF_REVIEW_SESSION", "claude_review")

def get_implementer_session() -> str:
    return os.environ.get("DPMTF_IMPLEMENTER_SESSION", "claude_implementer")

def get_architect_session() -> str:
    return os.environ.get("DPMTF_ARCHITECT_SESSION", "claude_architect")
