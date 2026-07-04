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
import ast
import os
import configparser
from pathlib import Path


class ConfigValidationError(Exception):
    """Raised when config.py source still contains a hardcoded user-specific path."""
    pass

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

def get_home_dir() -> str:
    """Home directory. Env var DPMTF_HOME_DIR, or $HOME."""
    return os.environ.get("DPMTF_HOME_DIR", os.path.expanduser("~"))

def get_projects_base_dir() -> str:
    """Base directory where child/reference projects live. Defaults to home dir."""
    configured = _config.get("paths", "projects_base_dir", fallback=None)
    if configured:
        return configured
    return get_home_dir()

def get_project_path(project_name: str) -> str:
    """Full path for a child or reference project."""
    return os.path.join(get_projects_base_dir(), project_name)

def get_opencode_bin() -> str:
    """Path to opencode binary. Env var DPMTF_OPENCODE_BIN, or derived from home dir."""
    configured = _config.get("paths", "opencode_bin", fallback=None)
    if configured:
        return configured
    return os.path.join(get_home_dir(), ".opencode", "bin", "opencode")

def get_bridge_dir() -> str:
    """Bridge directory. Env var DPMTF_BRIDGE_DIR, or .ini [paths] bridge_dir."""
    env = os.environ.get("DPMTF_BRIDGE_DIR")
    if env:
        return env
    configured = _config.get("paths", "bridge_dir", fallback=None)
    if configured:
        return configured
    return str(Path(get_project_root()) / "flows")

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
    configured = _config.get("paths", "trade_inbox_dir", fallback=None)
    if configured:
        return configured
    env = os.environ.get("DPMTF_TRADE_INBOX")
    if env:
        return env
    return os.path.join(get_home_dir(), "trade-ui", "inbox", "pending")


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


# ── Logging ─────────────────────────────────────────────────────

def get_logging_level() -> str:
    """Logging level. .ini [logging] level, or fallback to INFO."""
    return _config.get("logging", "level", fallback="INFO").upper()


def get_logging_file() -> str:
    """Absolute path to log file. Resolves relative path from project root."""
    file_rel = _config.get("logging", "file", fallback="logs/app.log")
    return str(Path(get_project_root()) / file_rel)


# ── System Resources — omitted card paths ────────────────────────

def get_omitted_card_paths() -> list:
    """Paths to omit from system_resources dashboard cards.

    Env var DPMTF_OMITTED_CARD_PATHS (JSON-encoded list), or default
    fallback list (paths relative to home dir).
    """
    env = os.environ.get("DPMTF_OMITTED_CARD_PATHS")
    if env:
        try:
            parsed = json.loads(env)
            if isinstance(parsed, list):
                return [str(p) for p in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
    home = get_home_dir()
    return [
        "RAM",
        "/",
        os.path.join(home, "HermesOutput"),
        os.path.join(home, "ComfyUI"),
        os.path.join(home, "ComfyUI-LTX23"),
    ]


# ── Startup Validation ──────────────────────────────────────────

# The literal hardcoded-user-path marker is assembled from string fragments
# so a static grep for the literal does not flag the validator itself.
_HARDCODED_USER_MARKER = "/" + "home" + "/" + "svend"


def validate_no_hardcoded_paths() -> None:
    """Scan config.py source for hardcoded user-specific path strings.

    Parses config.py as AST and inspects every string constant outside
    of docstrings and outside of this validator function itself.
    Raises ConfigValidationError if any hit is found.

    This catches the auto-fail pattern from CLAUDE.md sections 3 and 6:
    any application code that hardcodes the current user's home directory
    as a fallback or string literal is flagged at startup instead of
    silently shipping.

    A pure runtime check on resolved values is impractical: paths like
    get_project_root() legitimately derive from this file's location,
    which IS the user's home on the current machine. Source-code
    scanning catches the actual anti-pattern (hardcoded string in code)
    without false positives from legitimately-derived values.
    """
    config_path = Path(__file__).resolve()
    with open(config_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    skip_lines = set()

    def _add_docstring_lines(node):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                for ln in range(first.lineno, first.end_lineno + 1):
                    skip_lines.add(ln)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef, ast.Module)):
            _add_docstring_lines(node)
        if isinstance(node, ast.FunctionDef) and node.name in (
            "validate_no_hardcoded_paths", "validate_config",
        ):
            for ln in range(node.lineno, node.end_lineno + 1):
                skip_lines.add(ln)
        if isinstance(node, ast.ClassDef) and node.name == "ConfigValidationError":
            for ln in range(node.lineno, node.end_lineno + 1):
                skip_lines.add(ln)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if (_HARDCODED_USER_MARKER in node.value
                    and node.lineno not in skip_lines):
                raise ConfigValidationError(
                    f"config.py line {node.lineno}: hardcoded "
                    f"user-specific path in code: {node.value!r}"
                )


# Backwards-compatible alias for callers that referenced the prior name.
validate_config = validate_no_hardcoded_paths
