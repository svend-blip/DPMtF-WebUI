#!/usr/bin/env python3
"""
BridgeV002 core library — reads config from INI files, provides lookup functions.
No hardcoded role names or paths. All driven by configuration files.
"""
import configparser
import os
import re
from pathlib import Path


def resolve_placeholders(text, bridge_dir=None, project_root=None):
    """Replace {BRIDGE_DIR}, {PROJECT_ROOT}, {SCRIPTS_DIR} in config values."""
    if bridge_dir is None:
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge"))
    if project_root is None:
        project_root = os.environ.get(
            "DPMTF_PROJECT_ROOT"
        ) or str(Path(__file__).resolve().parent.parent)

    replacements = {
        "{BRIDGE_DIR}": bridge_dir,
        "{PROJECT_ROOT}": project_root,
        "{SCRIPTS_DIR}": f"{project_root}/scripts/bridgeV002",
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text


def _find_project_root():
    """Locate the DPMtF-WebUI project root directory."""
    if "DPMTF_PROJECT_ROOT" in os.environ:
        return os.environ["DPMTF_PROJECT_ROOT"]
    script_parent = Path(__file__).resolve().parent.parent
    if (script_parent / "docs" / "bridgeV002").is_dir():
        return str(script_parent)
    return str(Path.home() / "DPMtF-WebUI")


def load_bridge_config(bridge_dir=None):
    """Load bridgeV002.ini and resolve all placeholders.

    Searches multiple locations: project docs/bridgeV002/, then ~/.bridge/.
    Returns dict of resolved section/key/value pairs.
    """
    config = configparser.ConfigParser()
    project_root = _find_project_root() or os.environ.get("DPMTF_PROJECT_ROOT")

    search_paths = [
        os.path.join(project_root, "docs", "bridgeV002", "bridgeV002.ini"),
        os.path.expanduser("~/.bridge/bridgeV002.ini"),
    ]

    loaded = False
    for path in search_paths:
        if os.path.exists(path):
            config.read(path)
            loaded = True
            break

    if not loaded:
        raise FileNotFoundError(
            "bridgeV002.ini not found in any search location: " + str(search_paths)
        )

    resolved = {}
    for section in config.sections():
        resolved[section] = {}
        raw = dict(config[section])
        placeholders_resolved = False
        for key, val in raw.items():
            if "{BRIDGE_DIR}" in val or "{PROJECT_ROOT}" in val or "{SCRIPTS_DIR}" in val:
                resolved[section][key] = resolve_placeholders(
                    val, bridge_dir=bridge_dir, project_root=project_root
                )
                placeholders_resolved = True
            else:
                resolved[section][key] = val

    return resolved


def _find_ini_file(base_dir, filename):
    """Search for an INI file in the given directory and ~/.bridge equivalent."""
    candidates = [
        os.path.join(base_dir, filename),
        os.path.expanduser(os.path.join("~/.bridge", filename)),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"{filename} not found in {base_dir} or ~/.bridge/"
    )


def load_role_config(role_name, bridge_dir=None, project_root=None):
    """Load a single role's configuration by name from roles/default.ini.

    Returns dict with resolved placeholders.
    """
    if project_root is None:
        project_root = _find_project_root() or os.environ.get("DPMTF_PROJECT_ROOT")

    raw_project_root = project_root

    roles_dir_env = os.environ.get(
        "DPMTF_ROLES_DIR",
        os.path.join(project_root, "docs", "bridgeV002", "roles"),
    )

    config = configparser.ConfigParser()
    try:
        ini_path = _find_ini_file(roles_dir_env, "default.ini")
        config.read(ini_path)
    except FileNotFoundError:
        pass

    section = f"role:{role_name}"
    if section in config:
        role = {}
        for key, val in config[section].items():
            role[key] = resolve_placeholders(
                val, bridge_dir=bridge_dir, project_root=raw_project_root
            )
        return role

    raise ValueError(f"Role '{role_name}' not found in roles/default.ini")


def load_flow_config(flow_name, project_root=None):
    """Load a flow definition by name from flows/ directory.

    Returns dict of all sections with their key/value pairs.
    """
    if project_root is None:
        project_root = _find_project_root() or os.environ.get("DPMTF_PROJECT_ROOT")

    raw_project_root = project_root

    flows_dir_env = os.environ.get(
        "DPMTF_FLOWS_DIR",
        os.path.join(project_root, "docs", "bridgeV002", "flows"),
    )

    config = configparser.ConfigParser()
    try:
        ini_path = _find_ini_file(flows_dir_env, f"{flow_name}.ini")
        config.read(ini_path)
    except FileNotFoundError:
        pass

    result = {}
    for section in config.sections():
        raw_dict = dict(config[section])
        placeholders_found = any(
            p in v for v in raw_dict.values()
            for p in ["{BRIDGE_DIR}", "{PROJECT_ROOT}", "{SCRIPTS_DIR}"]
        )
        if placeholders_found:
            result[section] = {
                k: resolve_placeholders(v, project_root=raw_project_root)
                for k, v in raw_dict.items()
            }
        else:
            result[section] = raw_dict

    if result:
        return result

    raise ValueError(
        f"Flow '{flow_name}' not found in flows/ directory"
    )


def get_next_id(bridge_dir=None):
    """Find next available handoff ID across all bridge subdirectories.

    Scans standard deliverable directories for existing numbered files
    and returns max + 1, or 1 if no files found.
    """
    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge")
        )

    existing = set()
    id_pattern = re.compile(r"(\d+)-[\w]+\.md$")

    for dirname in [
        "reviewtoarchitect",
        "architecttoreview",
        "reviewtoimplementor",
        "implementertoreview",
    ]:
        dir_path = os.path.join(bridge_dir, dirname)
        if os.path.isdir(dir_path):
            for fname in os.listdir(dir_path):
                m = id_pattern.match(fname)
                if m:
                    try:
                        existing.add(int(m.group(1)))
                    except ValueError:
                        pass

    return max(existing) + 1 if existing else 1


def ensure_subdir(bridge_dir, subdir):
    """Ensure a deliverable directory exists.

    Creates the directory if it doesn't exist and returns the full path.
    """
    path = os.path.join(bridge_dir, subdir)
    os.makedirs(path, exist_ok=True)
    return path


if __name__ == "__main__":
    print("BridgeV002 core library")
    bridge_config = load_bridge_config()
    print(f"Loaded config sections: {list(bridge_config.keys())}")
    for role in ["architect", "implementer"]:
        rc = load_role_config(role)
        print(f"Role '{role}': session={rc.get('tmux_session')}")
    nid = get_next_id()
    print(f"Next handoff ID: {nid}")
