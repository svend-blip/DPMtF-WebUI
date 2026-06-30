"""Machine Profile healthcheck engine — Phase 1 read-only validation.

Runs checks against the active Machine Profile and returns structured results.
Never modifies state. Never returns secrets. Never uses shell=True.
"""

import json
import os
import shutil
import socket
import subprocess
import urllib.request

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
    1. Profile file missing -> warning
    2. Profile file exists but JSON invalid -> fail/error
    3. Profile file exists and valid -> check schema_version etc.
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

    # App port — socket-check like expected_children
    app_port = ports.get("app")
    if app_port:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect(("127.0.0.1", app_port))
            sock.close()
            results.append(_check_result(
                "ports", "app", "pass", "info",
                f"App port {app_port} is responding"
            ))
        except Exception:
            results.append(_check_result(
                "ports", "app", "warning", "warning",
                f"App port {app_port} is not responding"
            ))

    # Ollama port — check if local_ollama is enabled
    ollama_port = ports.get("ollama")
    local_ollama = profile.get("providers", {}).get("local_ollama", {})
    if ollama_port and local_ollama.get("available"):
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
            sessions = [line.split(":")[0] for line in result.stdout.strip().split("\n") if line]
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

    Raises:
        ValueError: if section is not a valid section name
    """
    profile_path = config.get_machine_profile_path()
    metadata = config.get_machine_profile_metadata()

    if section is not None and section not in VALID_SECTIONS:
        raise ValueError(
            f"Unknown section '{section}'. Valid: {', '.join(VALID_SECTIONS)}"
        )

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
