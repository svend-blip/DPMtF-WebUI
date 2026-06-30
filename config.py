"""Central configuration for DPMtF-WebUI.

Single source of truth for all configurable values.
Paths, ports, model names, project references MUST come from here.
Hardcoding /home/svend/... anywhere else is an auto-fail in validation.

Sources (in priority order):
1. Environment variables (secrets, infrastructure)
2. dpmtf.ini (app-config)
3. Hardcoded fallbacks (last resort, for development only)
"""

import json
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
    return _config.get("database", "path", fallback="databases/dpmtf.db")

def get_bridge_dir() -> str:
    """Bridge directory. Env var DPMTF_BRIDGE_DIR, or .ini [paths] bridge_dir, or fallback."""
    env = os.environ.get("DPMTF_BRIDGE_DIR")
    if env:
        return env
    return _config.get("paths", "bridge_dir", fallback="/home/svend/flows")

def get_bridge_base_path() -> str:
    """Bridge base path. .ini [bridge] base_path, or fallback to project_root/flows."""
    configured = _config.get("bridge", "base_path", fallback=None)
    if configured:
        return configured
    return str(Path(get_project_root()) / "flows")


def get_project_root() -> str:
    """Project root directory. .ini [paths] project_root, or derived from this file's location."""
    configured = _config.get("paths", "project_root", fallback=None)
    if configured:
        return configured
    return str(Path(__file__).resolve().parent)

def get_governance_dir() -> str:
    """Governance docs directory (relative to project root)."""
    return _config.get("paths", "governance_dir", fallback="docs/governance-templates-v2")

def get_governance_dir_abs() -> str:
    """Governance docs directory (absolute path)."""
    return str(Path(get_project_root()) / get_governance_dir())

def get_father_project() -> str:
    """Father project name."""
    return _config.get("projects", "father_project", fallback="DPMtF-WebUI")

def get_child_projects() -> list:
    """Child project names (comma-separated in .ini)."""
    raw = _config.get("projects", "child_projects", fallback="ENO")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_reference_projects() -> list:
    """Reference project names (comma-separated in .ini)."""
    raw = _config.get("projects", "reference_projects", fallback="ai-pc-resource-webui-v3")
    return [p.strip() for p in raw.split(",") if p.strip()]

def get_port() -> int:
    """Server port."""
    return _config.getint("app", "port", fallback=9130)

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

def get_trade_inbox_dir() -> str:
    """Absolute path to Trade Cockpit inbox directory for JSON output."""
    return os.environ.get("DPMTF_TRADE_INBOX", "/home/svend/trade-ui/inbox/pending")


# ── Machine Profile (Fase 1) ──────────────────────────────────────

def get_machine_profile_path() -> str:
    """Return resolved path to active Machine Profile.

    Reads DPMTF_MACHINE_PROFILE from env, falls back to machine.local.json.
    Returns the absolute path whether or not the file exists.
    """
    profile_name = os.environ.get("DPMTF_MACHINE_PROFILE", "machine.local.json")
    return os.path.join(get_project_root(), "profiles", profile_name)


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
