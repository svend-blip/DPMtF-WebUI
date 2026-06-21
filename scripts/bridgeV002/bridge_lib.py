#!/usr/bin/env python3
"""
BridgeV002 core library — reads config from INI files, provides lookup functions.
No hardcoded role names or paths. All driven by configuration files.
"""
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import configparser
import os
import re
import sqlite3

import config


def resolve_placeholders(text, bridge_dir=None, project_root=None):
    """Replace {BRIDGE_DIR}, {PROJECT_ROOT}, {SCRIPTS_DIR} in config values."""
    if bridge_dir is None:
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR") or config.get_bridge_base_path()
    if project_root is None:
        project_root = os.environ.get(
            "DPMTF_PROJECT_ROOT"
        ) or config.get_project_root()

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


def get_next_id_for_flow(flow_key, db_path=None):
    """Return the next handoff ID for a specific flow, auto-incrementing.

    Uses bridge_id_counters table — completely independent of file system
    or legacy bridge directories. Flow-isolated: each flow has its own
    counter. One atomic SELECT + UPDATE per call.

    Args:
        flow_key: The flow key (e.g. 'strict_review', 'heavy').
        db_path: Optional path to SQLite database. Defaults to config.get_db_path().

    Returns:
        int — the next ID, or 1 if counter row did not exist (auto-created).
    """
    if db_path is None:
        import config as _config
        db_path = _config.get_db_path()

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Try to read existing counter
        cursor.execute(
            "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
            (flow_key,)
        )
        row = cursor.fetchone()

        if row and row[0]:
            new_id = row[0]
            cursor.execute(
                "UPDATE bridge_id_counters SET next_id = next_id + 1 WHERE flow_key = ?",
                (flow_key,)
            )
        else:
            # Auto-create counter at 1 for unknown flows
            try:
                cursor.execute(
                    "INSERT INTO bridge_id_counters (flow_key, next_id) VALUES (?, 1)",
                    (flow_key,)
                )
            except sqlite3.IntegrityError:
                # Race condition: another call created it between SELECT and INSERT.
                # Fall back to reading it now.
                cursor.execute(
                    "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
                    (flow_key,)
                )
                row2 = cursor.fetchone()
                new_id = row2[0] if row2 else 1

            cursor.execute(
                "UPDATE bridge_id_counters SET next_id = next_id + 1 WHERE flow_key = ?",
                (flow_key,)
            )

        conn.commit()
        return new_id
    except sqlite3.OperationalError:
        # Table doesn't exist yet — safe fallback
        return 1
    finally:
        conn.close()


def ensure_subdir(bridge_dir, subdir):
    """Ensure a deliverable directory exists.

    Creates the directory if it doesn't exist and returns the full path.
    """
    path = os.path.join(bridge_dir, subdir)
    os.makedirs(path, exist_ok=True)
    return path


def _bridgev002_tables_exist(db_path=None):
    """Check if bridge_roles, bridge_flows, bridge_flow_steps tables exist.

    Returns True only if all three tables are present in the database.
    Used to determine whether DB-backed functions are available.
    """
    if db_path is None:
        db_path = config.get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table in ["bridge_roles", "bridge_flows", "bridge_flow_steps"]:
            result = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not result:
                conn.close()
                return False
        conn.close()
        return True
    except sqlite3.Error:
        return False


def load_role_from_db(role_name, db_path=None):
    """Load a single role's configuration from bridge_roles table.

    Args:
        role_name: The role_key to look up (e.g. 'architect', 'implementer')
        db_path: Optional path to SQLite database. Uses config.get_db_path() if not given.

    Returns:
        dict with keys matching bridge_roles columns, plus resolved start_cmd.
        Keys: role_key, tmux_session, start_cmd, model_type, cloud_model,
              ollama_model, setup_script, teardown_script, deliver_error_msg,
              is_active, created_at, updated_at

    Raises:
        ValueError: If table doesn't exist or role not found.
    """
    if not _bridgev002_tables_exist(db_path):
        raise ValueError(
            f"BridgeV002 database tables not found at '{db_path}' "
            f"(or not yet created by init_db.py)"
        )

    if db_path is None:
        db_path = config.get_db_path()

    project_root = _find_project_root()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT * FROM bridge_roles WHERE role_key = ? AND is_active = 1",
        (role_name,)
    ).fetchone()

    if not row:
        conn.close()
        raise ValueError(f"Active role '{role_name}' not found in bridge_roles")

    role = dict(row)

    # Resolve placeholders in start_cmd, setup_script, teardown_script
    for field in ["start_cmd", "setup_script", "teardown_script"]:
        if role[field] is not None:
            role[field] = resolve_placeholders(
                role[field], project_root=project_root
            )

    conn.close()
    return role


def load_flow_from_db(flow_name, db_path=None):
    """Load a flow definition and its steps from database tables.

    Args:
        flow_name: The flow_key to look up (e.g. 'heavy', 'simplified')
        db_path: Optional path to SQLite database. Uses config.get_db_path() if not given.

    Returns:
        dict with two keys:
            'flow': dict from bridge_flows row (flow_key, name, description,
                     step_order, is_default, is_active, created_at, updated_at)
            'steps': list of dicts from bridge_flow_steps rows, sorted by sort_order.
                     Each step dict has: id, flow_key, step_key, from_role, to_role,
                     deliverable_dir, deliverable_pattern, pre_dispatch_script,
                     post_dispatch_script, error_msg, sort_order, is_active

    Raises:
        ValueError: If table doesn't exist or flow not found.
    """
    if not _bridgev002_tables_exist(db_path):
        raise ValueError(
            f"BridgeV002 database tables not found at '{db_path}' "
            f"(or not yet created by init_db.py)"
        )

    if db_path is None:
        db_path = config.get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Load flow definition
    row = cursor.execute(
        "SELECT * FROM bridge_flows WHERE flow_key = ? AND is_active = 1",
        (flow_name,)
    ).fetchone()

    if not row:
        conn.close()
        raise ValueError(f"Active flow '{flow_name}' not found in bridge_flows")

    flow = dict(row)

    # Load active steps for this flow, ordered by sort_order
    steps = []
    for step_row in cursor.execute(
        "SELECT * FROM bridge_flow_steps "
        "WHERE flow_key = ? AND is_active = 1 "
        "ORDER BY sort_order ASC",
        (flow_name,)
    ):
        steps.append(dict(step_row))

    conn.close()
    return {"flow": flow, "steps": steps}


def list_roles_from_db(db_path=None):
    """List all active roles from bridge_roles table.

    Returns:
        list of dicts, one per active role, ordered by role_key.
    """
    if not _bridgev002_tables_exist(db_path):
        return []

    if db_path is None:
        db_path = config.get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM bridge_roles WHERE is_active = 1 ORDER BY role_key"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_flows_from_db(db_path=None):
    """List all active flows from bridge_flows table.

    Returns:
        list of dicts, one per active flow, with is_default flag, ordered by flow_key.
    """
    if not _bridgev002_tables_exist(db_path):
        return []

    if db_path is None:
        db_path = config.get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM bridge_flows WHERE is_active = 1 ORDER BY flow_key"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_scripts_from_db(db_path=None):
    """List all active scripts from bridge_scripts table.

    Returns:
        list of dicts, one per active script, ordered by script_key.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM bridge_scripts WHERE is_active = 1 ORDER BY script_key"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def list_conventions_from_db(db_path=None):
    """List all convention rules from bridge_convention_rules table.

    Returns:
        list of dicts, one per rule, ordered by rule_key.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM bridge_convention_rules ORDER BY rule_key"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def resolve_convention_from_db(rule_key, db_path=None):
    """Resolve a single convention rule by key.

    Args:
        rule_key: The convention key (e.g. 'handoff', 'callback', 'verdict')
        db_path: Optional path to SQLite database. Uses config.get_db_path() if not given.

    Returns:
        dict with keys: rule_key, step_type, dir_template, pattern_template,
                       error_template, prompt_template

    Raises:
        ValueError: If rule_key not found.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM bridge_convention_rules WHERE rule_key = ?",
            (rule_key,)
        ).fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Convention rule '{rule_key}' not found in bridge_convention_rules")
        result = dict(row)
        conn.close()
        return result
    except sqlite3.OperationalError:
        return {}


def resolve_content_template_from_db(rule_key, db_path=None):
    """Resolve the content template for a convention rule.

    Looks up the content_template column from bridge_convention_rules.
    If the template contains placeholder tokens ({handoff_id}, {source_role},
    {next_role}), they are returned as-is for caller-side interpolation.

    Args:
        rule_key: The convention key (e.g. 'callback', 'handoff', 'verdict')
        db_path: Optional path to SQLite database.

    Returns:
        str with the content template, or empty string if not set / column missing.
    """
    if db_path is None:
        db_path = config.get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content_template FROM bridge_convention_rules WHERE rule_key = ?",
            (rule_key,)
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
        return ""
    except sqlite3.OperationalError:
        return ""


def validate_deliverable_against_schema(file_path, rule_key, db_path=None):
    """Validate that a deliverable file contains required XML sections.

    Reads the convention rule's validation_schema JSON array and checks
    that each listed XML tag (e.g. '<role>', '<task>') appears at least
    once in the file content.

    Args:
        file_path: Absolute path to the deliverable .md file.
        rule_key: The convention key whose schema should be used.
        db_path: Optional path to SQLite database.

    Returns:
        dict with keys:
            'valid': bool — True if all required sections present
            'missing': list[str] — tags found in schema but absent from file
            'checked': list[str] — tags that were checked
    """
    if db_path is None:
        db_path = config.get_db_path()

    result = {"valid": False, "missing": [], "checked": []}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT validation_schema FROM bridge_convention_rules WHERE rule_key = ?",
            (rule_key,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            result["valid"] = True
            return result

        import json
        required_tags = json.loads(row[0])
        result["checked"] = list(required_tags)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        missing = []
        for tag in required_tags:
            if tag not in content:
                missing.append(tag)

        result["missing"] = missing
        result["valid"] = len(missing) == 0
        return result
    except (sqlite3.OperationalError, FileNotFoundError, json.JSONDecodeError):
        result["valid"] = False
        result["missing"] = ["<validation-error>"]
        return result


if __name__ == "__main__":
    print("BridgeV002 core library")
    bridge_config = load_bridge_config()
    print(f"Loaded config sections: {list(bridge_config.keys())}")
    for role in ["architect", "implementer"]:
        rc = load_role_config(role)
        print(f"Role '{role}': session={rc.get('tmux_session')}")
    nid = get_next_id()
    print(f"Next handoff ID: {nid}")

    # Database-backed functions (Spor I)
    if _bridgev002_tables_exist():
        print("\nDatabase-backed lookup:")
        for role in ["architect", "implementer"]:
            try:
                rc = load_role_from_db(role)
                print(f"  DB role '{role}': session={rc.get('tmux_session')}, model_type={rc.get('model_type')}")
            except ValueError as e:
                print(f"  DB role '{role}': NOT FOUND ({e})")

        try:
            fl = load_flow_from_db("heavy")
            print(f"  DB flow 'heavy': {len(fl['steps'])} steps")
            for s in fl["steps"]:
                print(f"    {s['step_key']}: {s['from_role']} -> {s['to_role']}")
        except ValueError as e:
            print(f"  DB flow 'heavy': NOT FOUND ({e})")

        roles = list_roles_from_db()
        flows = list_flows_from_db()
        print(f"\n  Total active roles: {len(roles)}")
        print(f"  Total active flows: {len(flows)}")
    else:
        print("\nDatabase tables not found — run init_db.py first")
