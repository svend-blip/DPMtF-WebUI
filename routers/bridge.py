"""BridgeV002 HTTP API router — moved verbatim from app.py (Spor I + J).

Pure refactor: every endpoint function, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location and the decorator prefix (`@app.X` →
`@router.X`) changed.

Endpoints (27 total):
  GET    /api/bridge-v2/status
  GET    /api/bridge-v2/roles
  GET    /api/bridge-v2/roles/{role_key}
  POST   /api/bridge-v2/roles
  PUT    /api/bridge-v2/roles/{role_key}
  POST   /api/bridge-v2/roles/{role_key}/rename
  DELETE /api/bridge-v2/roles/{role_key}
  GET    /api/bridge-v2/flows
  GET    /api/bridge-v2/flows/{flow_key}
  POST   /api/bridge-v2/flows
  PUT    /api/bridge-v2/flows/{flow_key}
  DELETE /api/bridge-v2/flows/{flow_key}
  POST   /api/bridge-v2/flows/{flow_key}/start-tmux
  POST   /api/bridge-v2/flows/{flow_key}/start-coding
  POST   /api/bridge-v2/flows/{flow_key}/stop-tmux
  POST   /api/bridge-v2/flows/{flow_key}/attach-tmux
  GET    /api/bridge-v2/steps/{flow_key}
  POST   /api/bridge-v2/steps/{flow_key}
  PUT    /api/bridge-v2/steps/{flow_key}/{step_id}
  DELETE /api/bridge-v2/steps/{flow_key}/{step_id}
  GET    /api/bridge-v2/scripts
  GET    /api/bridge-v2/conventions
  POST   /api/bridge-v2/conventions
  PATCH  /api/bridge-v2/conventions/{rule_key}
  GET    /api/bridge-v2/governance-files
  POST   /api/bridge-v2/export
  POST   /api/bridge-v2/db-backup
"""

import io
import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

# Ensure scripts/bridgeV002/ is on sys.path so the top-level `bridge_lib`
# import resolves. This mirrors what app.py does at its module top;
# duplicating it here keeps routers/bridge.py self-contained.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "bridgeV002"))

from bridge_lib import (  # noqa: E402
    _bridgev002_tables_exist,
    list_flows_from_db,
    list_roles_from_db,
    load_flow_from_db,
    load_role_from_db,
)
from scripts.bridgeV002.bridge_lib import (  # noqa: E402
    list_conventions_from_db,
    list_scripts_from_db,
    resolve_convention_from_db,
)

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402

router = APIRouter(prefix="/api/bridge-v2", tags=["bridge"])


logger = logging.getLogger(__name__)


# ── Spor I: BridgeV002 Database Integration API ────────────────


@router.get("/status")
async def bridge_v2_status():
    """Check whether BridgeV002 database tables are available."""
    tables_exist = _bridgev002_tables_exist(get_db_path())
    return {
        "available": tables_exist,
        "tables": ["bridge_roles", "bridge_flows", "bridge_flow_steps"] if tables_exist else [],
    }


@router.get("/roles")
async def bridge_v2_list_roles():
    """Return all active BridgeV002 roles from database."""
    try:
        roles = list_roles_from_db(get_db_path())
        return {"roles": roles, "count": len(roles)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge roles: {e}")


@router.get("/roles/{role_key}")
async def bridge_v2_get_role(role_key: str):
    """Return a single BridgeV002 role configuration from database."""
    try:
        role = load_role_from_db(role_key, get_db_path())
        return {"role": role}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load bridge role: {e}")


@router.get("/flows")
async def bridge_v2_list_flows():
    """Return all active BridgeV002 flows from database."""
    try:
        flows = list_flows_from_db(get_db_path())
        return {"flows": flows, "count": len(flows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge flows: {e}")


@router.get("/flows/{flow_key}")
async def bridge_v2_get_flow(flow_key: str):
    """Return a BridgeV002 flow definition and its steps from database."""
    try:
        flow_data = load_flow_from_db(flow_key, get_db_path())
        return {"flow": flow_data["flow"], "steps": flow_data["steps"], "step_count": len(flow_data["steps"])}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load bridge flow: {e}")


@router.get("/scripts")
async def bridge_v2_list_scripts():
    """Return all active BridgeV002 scripts from database."""
    try:
        scripts = list_scripts_from_db(get_db_path())
        return {"scripts": scripts, "count": len(scripts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge scripts: {e}")


@router.get("/conventions")
async def bridge_v2_list_conventions():
    """Return all convention rules from database."""
    try:
        conventions = list_conventions_from_db(get_db_path())
        return {"conventions": conventions, "count": len(conventions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge conventions: {e}")


@router.post("/conventions")
async def bridge_v2_create_convention(request: Request):
    """Create a new BridgeV002 convention rule."""
    data = await request.json()
    required = ["rule_key", "step_type", "dir_template", "pattern_template"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT rule_key FROM bridge_convention_rules WHERE rule_key = ?",
        (data["rule_key"],)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail=f"Convention '{data['rule_key']}' already exists")

    cursor.execute("""
        INSERT INTO bridge_convention_rules
        (rule_key, step_type, dir_template, pattern_template, error_template,
         prompt_template, content_template, validation_schema, rule_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["rule_key"],
        data["step_type"],
        data["dir_template"],
        data["pattern_template"],
        data.get("error_template", ""),
        data.get("prompt_template", ""),
        data.get("content_template", ""),
        data.get("validation_schema", ""),
        data.get("rule_type", "generic"),
    ))
    conn.commit()
    conn.close()
    return {"status": "created", "rule_key": data["rule_key"]}


@router.patch("/conventions/{rule_key}")
async def bridge_v2_patch_convention(rule_key: str, request: Request):
    """Patch a convention rule — only the fields provided are updated."""
    data = await request.json()
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute(
        "SELECT rule_key FROM bridge_convention_rules WHERE rule_key = ?",
        (rule_key,)
    )
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Convention '{rule_key}' not found")

    updatable = [
        "content_template",
        "validation_schema",
        "rule_type",
    ]
    sets = []
    params = []
    for field in updatable:
        if field in data:
            sets.append(f"{field} = ?")
            params.append(data[field])

    if not sets:
        conn.close()
        return {"status": "no changes", "rule_key": rule_key}

    params.append(rule_key)
    cursor.execute(
        f"UPDATE bridge_convention_rules SET {', '.join(sets)} WHERE rule_key = ?",
        params,
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "rule_key": rule_key}


@router.get("/steps/{flow_key}")
async def bridge_v2_list_steps(flow_key: str):
    """Return all steps for a flow, with available roles/conventions/scripts for dropdowns."""
    try:
        flows = list_flows_from_db(get_db_path())
        flow_keys = [f["flow_key"] for f in flows]
        if flow_key not in flow_keys:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")

        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        steps_rows = cursor.execute(
            "SELECT * FROM bridge_flow_steps WHERE flow_key = ? ORDER BY sort_order ASC",
            (flow_key,)
        ).fetchall()
        steps = [dict(r) for r in steps_rows]

        roles_data = list_roles_from_db(get_db_path())
        role_keys = [r["role_key"] for r in roles_data]
        conventions_data = list_conventions_from_db(get_db_path())
        scripts_data = list_scripts_from_db(get_db_path())

        conn.close()
        return {
            "steps": steps,
            "count": len(steps),
            "flow_key": flow_key,
            "available_roles": role_keys,
            "available_conventions": conventions_data,
            "available_scripts": scripts_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge steps: {e}")


@router.post("/steps/{flow_key}")
async def bridge_v2_create_step(request: Request, flow_key: str):
    """Create a new step for the given flow."""
    data = await request.json()
    required = ["step_key", "from_role", "to_role"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    flows = list_flows_from_db(get_db_path())
    if flow_key not in [fl["flow_key"] for fl in flows]:
        raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM bridge_flow_steps WHERE flow_key = ? AND step_key = ?",
        (flow_key, data["step_key"])
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"Step '{data['step_key']}' already exists in flow '{flow_key}'")

    # Auto-reactivate from/to roles if soft-deleted
    for role_field in ["from_role", "to_role"]:
        cursor.execute(
            "SELECT is_active FROM bridge_roles WHERE role_key = ?",
            (data[role_field],)
        )
        existing_role = cursor.fetchone()
        if existing_role and not existing_role["is_active"]:
            cursor.execute(
                "UPDATE bridge_roles SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE role_key = ?",
                (data[role_field],)
            )

    deliverable_dir = data.get("deliverable_dir", None)
    deliverable_pattern = data.get("deliverable_pattern", None)
    error_msg = data.get("error_msg", None)
    rule_key = data.get("rule_key", None)

    if rule_key:
        convention = resolve_convention_from_db(rule_key, get_db_path())
        if convention and "rule_key" in convention:
            deliverable_dir = convention.get("dir_template", deliverable_dir)
            deliverable_pattern = convention.get("pattern_template", deliverable_pattern)
            error_msg = convention.get("error_template", error_msg)

    result = cursor.execute(
        "SELECT MAX(sort_order) as max_so FROM bridge_flow_steps WHERE flow_key = ?",
        (flow_key,)
    ).fetchone()
    max_so = result["max_so"] if result["max_so"] is not None else 0

    cursor.execute("""
        INSERT INTO bridge_flow_steps
            (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern,
             pre_dispatch_script, post_dispatch_script, error_msg, rule_key, sort_order,
             auto_chain_to_next, validation_required,
             runtime_override, provider_override, model_override,
             model_source, model_alias)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        flow_key, data["step_key"], data["from_role"], data["to_role"],
        deliverable_dir, deliverable_pattern,
        data.get("pre_dispatch_script"), data.get("post_dispatch_script"),
        error_msg, rule_key, max_so + 1,
        int(data.get("auto_chain_to_next", 0)),
        int(data.get("validation_required", 0)),
        data.get("runtime_override"),
        data.get("provider_override"),
        data.get("model_override"),
        data.get("model_source"),
        data.get("model_alias"),
    ))
    new_id = cursor.lastrowid
    conn.commit()

    row = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ?", (new_id,)
    ).fetchone()
    conn.close()
    return {"step": dict(row), "created": True}


@router.put("/steps/{flow_key}/{step_id}")
async def bridge_v2_update_step(request: Request, flow_key: str, step_id: int):
    """Update a step. Supports partial updates — only provided fields are changed."""
    data = await request.json()
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ? AND flow_key = ?",
        (step_id, flow_key)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in flow '{flow_key}'")

    existing = dict(row)
    updates = []
    params = []

    field_map = {
        "from_role": "from_role",
        "to_role": "to_role",
        "deliverable_dir": "deliverable_dir",
        "deliverable_pattern": "deliverable_pattern",
        "pre_dispatch_script": "pre_dispatch_script",
        "post_dispatch_script": "post_dispatch_script",
        "error_msg": "error_msg",
        "sort_order": "sort_order",
        "auto_chain_to_next": "auto_chain_to_next",
        "validation_required": "validation_required",
        "runtime_override": "runtime_override",
        "provider_override": "provider_override",
        "model_override": "model_override",
        "model_source": "model_source",
        "model_alias": "model_alias",
    }

    for field, column in field_map.items():
        if field in data:
            updates.append(f"{column} = ?")
            params.append(data[field])

    if "rule_key" in data and data["rule_key"] != existing.get("rule_key"):
        rule_key_val = data["rule_key"]
        convention = resolve_convention_from_db(rule_key_val, get_db_path()) if rule_key_val else None

        updates.append("rule_key = ?")
        params.append(rule_key_val)

        if convention and "rule_key" in convention:
            if "deliverable_dir" not in data and convention.get("dir_template"):
                updates.append("deliverable_dir = ?")
                params.append(convention["dir_template"])
            if "deliverable_pattern" not in data and convention.get("pattern_template"):
                updates.append("deliverable_pattern = ?")
                params.append(convention["pattern_template"])
            if "error_msg" not in data and convention.get("error_template"):
                updates.append("error_msg = ?")
                params.append(convention["error_template"])

    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No valid fields to update")

    params.append(step_id)
    params.append(flow_key)
    cursor.execute(
        f"UPDATE bridge_flow_steps SET {', '.join(updates)} WHERE id = ? AND flow_key = ?",
        params,
    )
    conn.commit()

    updated = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ?", (step_id,)
    ).fetchone()
    conn.close()
    return {"step": dict(updated), "updated": True}


@router.delete("/steps/{flow_key}/{step_id}")
async def bridge_v2_delete_step(flow_key: str, step_id: int):
    """Hard-delete a step."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT * FROM bridge_flow_steps WHERE id = ? AND flow_key = ?",
        (step_id, flow_key)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in flow '{flow_key}'")

    deleted = dict(row)
    cursor.execute(
        "DELETE FROM bridge_flow_steps WHERE id = ? AND flow_key = ?",
        (step_id, flow_key)
    )
    if cursor.rowcount == 0:
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
    conn.commit()
    conn.close()
    return {"deleted": True, "step": deleted}


# ── Spor J: BridgeV002 CRUD API ────────────────


@router.post("/roles")
async def bridge_v2_create_role(request: Request):
    """Create a new BridgeV002 role configuration."""
    data = await request.json()
    required = ["role_key", "tmux_session"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT * FROM bridge_roles WHERE role_key = ?",
        (data["role_key"],)
    ).fetchone()

    if not existing:
        model_type = data.get("model_type", "ollama")
        cursor.execute("""
            INSERT INTO bridge_roles
            (role_key, tmux_session, model_type, cloud_model, ollama_model,
             setup_script, teardown_script, deliver_error_msg, enter_command,
             default_runtime, default_provider, default_model, config_dir,
             default_model_source, default_model_alias,
             trade_mcp_push_mode, max_output_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["role_key"],
            data["tmux_session"],
            model_type,
            data.get("cloud_model"),
            data.get("ollama_model"),
            data.get("setup_script"),
            data.get("teardown_script"),
            data.get("deliver_error_msg"),
            data.get("enter_command", "default"),
            data.get("default_runtime"),
            data.get("default_provider"),
            data.get("default_model"),
            data.get("config_dir"),
            data.get("default_model_source"),
            data.get("default_model_alias"),
            data.get("trade_mcp_push_mode"),
            data.get("max_output_tokens"),
        ))
    else:
        # Role exists (active or soft-deleted) — reactivate/update it
        row = dict(existing) if not isinstance(existing, dict) else dict(existing)
        model_type = row["model_type"] if not data.get("model_type") else data["model_type"]
        sets = []
        params = []
        for field in ["tmux_session", "model_type", "cloud_model",
                      "ollama_model", "setup_script", "teardown_script",
                      "deliver_error_msg", "enter_command",
                      "default_runtime", "default_provider", "default_model",
                      "config_dir", "default_model_source", "default_model_alias",
                      "trade_mcp_push_mode", "max_output_tokens"]:
            if field in data:
                sets.append(f"{field} = ?")
                params.append(data[field])
        # Always reactivate if it was soft-deleted
        if not row.get("is_active"):
            sets.append("is_active = 1")
        sets.append("updated_at = datetime('now')")
        cursor.execute(
            f"UPDATE bridge_roles SET {', '.join(sets)} WHERE role_key = ?",
            params + [data["role_key"]],
        )

    conn.commit()
    return {"status": "created", "role_key": data["role_key"]} if not existing else {"status": "updated", "role_key": data["role_key"]}


@router.put("/roles/{role_key}")
async def bridge_v2_update_role(role_key: str, request: Request):
    """Update a BridgeV002 role configuration. Only provided fields are updated."""
    data = await request.json()

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role_key FROM bridge_roles WHERE role_key = ?",
        (role_key,)
    )
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Role '{role_key}' not found")

    updatable = [
        "tmux_session", "model_type", "cloud_model", "ollama_model",
        "setup_script", "teardown_script", "deliver_error_msg", "is_active",
        "governance_file",
        "role_type",  # G1: allow frontend to change role type (agent/human)
        "enter_command",  # H150: per-role Enter key configuration
        "default_runtime", "default_provider", "default_model",  # Machine Profile Fase 2A
        "config_dir",  # Machine Profile Fase 2A — OpenCode config directory override
        "default_model_source", "default_model_alias",  # V3A: Model Allocator source / alias
        "trade_mcp_push_mode", "max_output_tokens",  # Migration 004: runtime config
    ]
    sets = []
    params = []
    for field in updatable:
        if field in data:
            sets.append(f"{field} = ?")
            params.append(data[field])

    if not sets:
        conn.close()
        return {"status": "no changes", "role_key": role_key}

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(role_key)

    cursor.execute(
        f"UPDATE bridge_roles SET {', '.join(sets)} WHERE role_key = ?",
        params,
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "role_key": role_key}


@router.post("/roles/{role_key}/rename")
async def bridge_v2_rename_role(role_key: str, request: Request):
    """Rename a bridge role (change role_key). Atomic operation."""
    data = await request.json()
    new_role_key = data.get("new_role_key", "").strip()

    if not new_role_key or new_role_key == role_key:
        raise HTTPException(status_code=400, detail="No change made — invalid new role key")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM bridge_roles WHERE role_key = ?", (role_key,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Role '{role_key}' not found")

        cursor.execute(
            "SELECT role_key FROM bridge_roles WHERE role_key = ?", (new_role_key,)
        )
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=409, detail=f"Role '{new_role_key}' already exists")

        dependents = 0
        try:
            from_count = cursor.execute(
                "SELECT COUNT(*) FROM bridge_flow_steps WHERE from_role = ?", (role_key,)
            ).fetchone()[0]
            to_count = cursor.execute(
                "SELECT COUNT(*) FROM bridge_flow_steps WHERE to_role = ?", (role_key,)
            ).fetchone()[0]
            dependents = from_count + to_count

            if dependents:
                cursor.execute(
                    "UPDATE bridge_flow_steps SET from_role = ?, updated_at = CURRENT_TIMESTAMP WHERE from_role = ?",
                    (new_role_key, role_key)
                )
                cursor.execute(
                    "UPDATE bridge_flow_steps SET to_role = ?, updated_at = CURRENT_TIMESTAMP WHERE to_role = ?",
                    (new_role_key, role_key)
                )
        except sqlite3.OperationalError as exc:
            logger.warning("TBD: bridge_flow_steps table not available for role rename: %s", exc)

        cursor.execute(
            "UPDATE bridge_roles SET role_key = ?, updated_at = CURRENT_TIMESTAMP WHERE role_key = ?",
            (new_role_key, role_key)
        )
        conn.commit()

        return {
            "status": "renamed",
            "old_role_key": role_key,
            "new_role_key": new_role_key,
            "dependents": dependents,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Rename failed: {str(e)}")
    finally:
        conn.close()


@router.delete("/roles/{role_key}")
async def bridge_v2_delete_role(role_key: str):
    """Soft-delete a BridgeV002 role (set is_active=0)."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role_key FROM bridge_roles WHERE role_key = ?",
        (role_key,)
    )
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Role '{role_key}' not found")

    cursor.execute(
        "UPDATE bridge_roles SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE role_key = ?",
        (role_key,)
    )

    cursor.execute(
        "UPDATE bridge_flow_steps SET is_active = 0 "
        "WHERE (from_role = ? OR to_role = ?) AND is_active = 1",
        (role_key, role_key)
    )

    conn.commit()
    conn.close()
    return {"status": "deleted", "role_key": role_key}


@router.get("/governance-files")
async def bridge_v2_list_governance_files():
    """List all .md files in the governance-templates-v2 directory (disk-read)."""
    gov_dir = config.get_governance_dir_abs()
    if not gov_dir or not os.path.isdir(gov_dir):
        return {"files": []}
    files = sorted(
        f for f in os.listdir(gov_dir) if f.lower().endswith(".md")
    )
    return {"files": files}


@router.post("/flows")
async def bridge_v2_create_flow(request: Request):
    """Create a new BridgeV002 flow definition with optional steps."""
    data = await request.json()
    required = ["flow_key", "name"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute(
        "SELECT flow_key FROM bridge_flows WHERE flow_key = ?",
        (data["flow_key"],)
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"Flow '{data['flow_key']}' already exists")

    is_default = data.get("is_default", 0)

    if is_default:
        cursor.execute(
            "UPDATE bridge_flows SET is_default = 0 WHERE is_default = 1"
        )

    use_mp = data.get("use_machine_profile", 0)
    if use_mp not in (0, 1):
        use_mp = 0

    cursor.execute("""
        INSERT INTO bridge_flows (flow_key, name, description, step_order, is_default, use_machine_profile)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["flow_key"],
        data["name"],
        data.get("description"),
        data.get("step_order"),
        is_default,
        use_mp,
    ))

    step_count = 0
    steps = data.get("steps", [])
    for i, step in enumerate(steps):
        if "from_role" not in step or "to_role" not in step:
            continue
        cursor.execute("""
            INSERT INTO bridge_flow_steps
            (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern,
             pre_dispatch_script, post_dispatch_script, error_msg, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["flow_key"],
            step.get("step_key", f"step_{i+1}"),
            step["from_role"],
            step["to_role"],
            step.get("deliverable_dir"),
            step.get("deliverable_pattern"),
            step.get("pre_dispatch_script"),
            step.get("post_dispatch_script"),
            step.get("error_msg"),
            i + 1,
        ))
        step_count += 1

    conn.commit()
    conn.close()
    return {"status": "created", "flow_key": data["flow_key"], "steps_added": step_count}


@router.put("/flows/{flow_key}")
async def bridge_v2_update_flow(flow_key: str, request: Request):
    """Update a BridgeV002 flow definition. Only provided fields are updated."""
    data = await request.json()

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute(
        "SELECT flow_key FROM bridge_flows WHERE flow_key = ?",
        (flow_key,)
    )
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")

    updatable = [
        "name", "description", "step_order", "is_default", "is_active",
        "auto_complete_enabled", "use_machine_profile",
    ]
    sets = []
    params = []
    for field in updatable:
        if field in data:
            sets.append(f"{field} = ?")
            params.append(data[field])

    if not sets:
        conn.close()
        return {"status": "no changes", "flow_key": flow_key}

    if data.get("is_default"):
        cursor.execute(
            "UPDATE bridge_flows SET is_default = 0 WHERE is_default = 1"
        )

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(flow_key)

    cursor.execute(
        f"UPDATE bridge_flows SET {', '.join(sets)} WHERE flow_key = ?",
        params,
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "flow_key": flow_key}


@router.delete("/flows/{flow_key}")
async def bridge_v2_delete_flow(flow_key: str):
    """Hard-delete a BridgeV002 flow (only if it has no steps)."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check flow exists
    cursor.execute("SELECT * FROM bridge_flows WHERE flow_key = ?", (flow_key,))
    flow = cursor.fetchone()
    if not flow:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")

    # Check step count — only allow deletion if 0 steps remain
    cursor.execute("SELECT COUNT(*) as cnt FROM bridge_flow_steps WHERE flow_key = ?", (flow_key,))
    step_count = cursor.fetchone()[0]

    if step_count > 0:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete flow '{flow_key}': {step_count} steps remain. Delete all steps first."
        )

    # Hard-delete the flow (no dependency cleanup needed — 0 steps)
    cursor.execute("DELETE FROM bridge_flows WHERE flow_key = ?", (flow_key,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "flow_key": flow_key}


@router.post("/flows/{flow_key}/start-tmux")
async def bridge_v2_start_tmux_for_flow(flow_key: str):
    """Start tmux sessions for all active from_roles in a BridgeV002 flow."""
    try:
        script_path = os.path.join(
            os.environ.get("DPMTF_PROJECT_ROOT", config.get_project_root()),
            "scripts", "bridgeV002", "start_tmuxflow.py"
        )

        result = subprocess.run(
            ["python3", script_path, flow_key],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return {
                "status": "ok",
                "message": result.stdout.strip() or f"All sessions exist for '{flow_key}'",
            }
        else:
            raise HTTPException(status_code=500, detail=result.stderr.strip())

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="start_tmuxflow timed out after 30s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flows/{flow_key}/start-coding")
async def bridge_v2_start_coding_for_flow(flow_key: str):
    """Start coding frontends for all roles in a BridgeV002 flow via start_coding.py."""
    try:
        script_path = os.path.join(
            os.environ.get("DPMTF_PROJECT_ROOT", config.get_project_root()),
            "scripts", "bridgeV002", "start_coding.py"
        )

        result = subprocess.run(
            ["python3", script_path, flow_key],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return {
                "status": "ok",
                "message": result.stdout.strip() or f"No roles with default_runtime for '{flow_key}'",
            }
        else:
            raise HTTPException(status_code=500, detail=result.stderr.strip())

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="start_coding timed out after 30s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flows/{flow_key}/stop-tmux")
async def bridge_v2_stop_tmux_for_flow(flow_key: str):
    """Stop all tmux sessions for a BridgeV002 flow via stop_tmuxflow.py."""
    try:
        script_path = os.path.join(
            os.environ.get("DPMTF_PROJECT_ROOT", config.get_project_root()),
            "scripts", "bridgeV002", "stop_tmuxflow.py"
        )

        result = subprocess.run(
            ["python3", script_path, flow_key],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return {
                "status": "ok",
                "message": result.stdout.strip() or f"No sessions for '{flow_key}'",
            }
        else:
            raise HTTPException(status_code=500, detail=result.stderr.strip())

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="start_tmuxflow timed out after 30s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flows/{flow_key}/attach-tmux")
async def bridge_v2_attach_tmux_for_flow(flow_key: str):
    """Attach to all tmux sessions for a BridgeV002 flow via attach_tmux.py."""
    try:
        script_path = os.path.join(
            os.environ.get("DPMTF_PROJECT_ROOT", config.get_project_root()),
            "scripts", "bridgeV002", "attach_tmux.py"
        )

        result = subprocess.run(
            ["python3", script_path, flow_key],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return {
                "status": "ok",
                "message": result.stdout.strip() or f"No sessions for '{flow_key}'",
            }
        else:
            raise HTTPException(status_code=500, detail=result.stderr.strip())

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="attach_tmux timed out after 30s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── V3A: Model Allocator proxy endpoints ───────────────────────


def _parse_allocator_validate_text(raw_output: str) -> dict:
    """Parse text output from `model-allocator validate` into structured fields."""
    status = "UNKNOWN"
    backend = None
    real_model = None
    gpu_policy = None
    warnings = []
    errors = []
    current_section = None

    lines = raw_output.splitlines()
    # First line is often the status word (OK / WARNING / ERROR).
    if lines:
        first = lines[0].strip().upper()
        if first in {"OK", "WARNING", "ERROR"}:
            status = first

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Status:"):
            status = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Backend:"):
            backend = stripped.split(":", 1)[1].strip()
        elif stripped.lower().startswith("gpu policy:"):
            gpu_policy = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Real model:") or stripped.startswith("Logical model:"):
            value = stripped.split(":", 1)[1].strip()
            if stripped.startswith("Real model:"):
                real_model = value
        elif stripped.lower().startswith("warnings:"):
            current_section = "warnings"
            content = stripped.split(":", 1)[1].strip()
            if content and content.lower() != "none":
                warnings.append(content.lstrip("- "))
            continue
        elif stripped.lower().startswith("errors:"):
            current_section = "errors"
            content = stripped.split(":", 1)[1].strip()
            if content and content.lower() != "none":
                errors.append(content.lstrip("- "))
            continue
        elif stripped and current_section:
            if stripped.lower() == "none":
                continue
            if current_section == "warnings":
                warnings.append(stripped.lstrip("- "))
            elif current_section == "errors":
                errors.append(stripped.lstrip("- "))

    return {
        "validation_status": status,
        "resolved_backend": backend,
        "resolved_real_model": real_model,
        "gpu_policy": gpu_policy,
        "warnings": warnings,
        "errors": errors,
    }


@router.get("/allocator/aliases")
async def bridge_v2_allocator_aliases(client: str):
    """List allocator aliases for a client by shelling out to model-allocator."""
    if not client:
        raise HTTPException(status_code=400, detail="client query parameter is required")

    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "list", "--client", client],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=502,
                detail=f"model-allocator list failed: {result.stderr.strip() or result.stdout.strip()}",
            )
        aliases = json.loads(result.stdout.strip())
        return {"aliases": aliases}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"model-allocator list returned invalid JSON: {exc}",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator list timed out after 30s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator list error: {exc}")


@router.post("/allocator/validate")
async def bridge_v2_allocator_validate(request: Request):
    """Validate an allocator alias/client by shelling out to model-allocator."""
    data = await request.json()
    alias = data.get("alias")
    client = data.get("client")
    if not alias or not client:
        raise HTTPException(status_code=400, detail="alias and client are required")

    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "validate", "--alias", alias, "--client", client, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw_output = result.stdout.strip()
        parsed = {}
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            # Fallback: allocator without --json support — parse text output
            parsed = _parse_allocator_validate_text(raw_output)

        return {
            "validation_status": parsed.get("validation_status", "UNKNOWN"),
            "resolved_backend": parsed.get("resolved_backend"),
            "resolved_real_model": parsed.get("resolved_real_model"),
            "warnings": parsed.get("warnings", []),
            "errors": parsed.get("errors", []),
            "gpu_policy": parsed.get("resolved_gpu", parsed.get("gpu_policy")),
            "raw_output": raw_output,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator validate timed out after 30s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator validate error: {exc}")


@router.post("/allocator/status")
async def bridge_v2_allocator_status(request: Request):
    """Get runtime status for an allocator alias."""
    data = await request.json()
    alias = data.get("alias")
    if not alias:
        raise HTTPException(status_code=400, detail="alias is required")

    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "status", "--alias", alias],
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw_output = result.stdout.strip() or result.stderr.strip()
        parsed = {}
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            pass

        status_info = parsed.get("runtime") or parsed or {}
        return {
            "running": status_info.get("running", False),
            "reachable": parsed.get("reachable", {}).get("reachable", False),
            "model_available": parsed.get("model_available", {}).get("available", False),
            "backend": parsed.get("backend"),
            "api_base": parsed.get("api_base"),
            "pid": status_info.get("pid"),
            "port": parsed.get("port") or status_info.get("port"),
            "models": status_info.get("models", []),
            "error": status_info.get("error") or result.stderr.strip() or None,
            "raw_output": raw_output,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator status timed out after 30s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator status error: {exc}")


@router.post("/allocator/start")
async def bridge_v2_allocator_start(request: Request):
    """Warm up the backend runtime for an allocator alias."""
    data = await request.json()
    alias = data.get("alias")
    if not alias:
        raise HTTPException(status_code=400, detail="alias is required")

    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "start", "--alias", alias],
            capture_output=True,
            text=True,
            timeout=200,
        )
        raw_output = result.stdout.strip() or result.stderr.strip()
        parsed = {}
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            pass

        return {
            "started": parsed.get("started", result.returncode == 0),
            "pid": parsed.get("pid"),
            "port": parsed.get("port"),
            "error": parsed.get("error") or (result.stderr.strip() or None),
            "raw_output": raw_output,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator start timed out after 200s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator start error: {exc}")


@router.post("/allocator/stop")
async def bridge_v2_allocator_stop(request: Request):
    """Stop the backend runtime for an allocator alias."""
    data = await request.json()
    alias = data.get("alias")
    if not alias:
        raise HTTPException(status_code=400, detail="alias is required")

    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "stop", "--alias", alias],
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw_output = result.stdout.strip() or result.stderr.strip()
        parsed = {}
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            pass

        return {
            "stopped": parsed.get("stopped", result.returncode == 0),
            "error": parsed.get("error") or (result.stderr.strip() or None),
            "raw_output": raw_output,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator stop timed out after 60s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator stop error: {exc}")


def _allocator_script() -> str:
    return os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )


def _run_allocator(cmd_args: list) -> subprocess.CompletedProcess:
    """Run the allocator CLI, raising HTTPException on failure.

    A nonzero exit is treated as a validation/usage error (HTTP 400) whose
    detail is the CLI's error message (JSON {"error": ...} on stderr, or raw text).
    """
    try:
        result = subprocess.run(
            [_allocator_script()] + cmd_args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator timed out after 30s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator error: {exc}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                detail = parsed.get("error", detail)
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=400, detail=detail or "model-allocator config command failed")
    return result


@router.get("/allocator/config")
async def bridge_v2_allocator_config():
    """Return the full allocator config (aliases, roles, profiles)."""
    result = _run_allocator(["config", "show"])
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator config show returned invalid JSON: {exc}")


@router.post("/allocator/config/alias")
async def bridge_v2_allocator_set_alias(request: Request):
    data = await request.json()
    name = data.get("name")
    definition = data.get("definition")
    if not name or not isinstance(name, str) or not isinstance(definition, dict):
        raise HTTPException(status_code=400, detail="name and definition (object) are required")
    _run_allocator(["config", "set-alias", "--name", name, "--json", json.dumps(definition)])
    return {"ok": True}


@router.delete("/allocator/config/alias/{name}")
async def bridge_v2_allocator_delete_alias(name: str):
    _run_allocator(["config", "delete-alias", "--name", name])
    return {"ok": True}


@router.post("/allocator/config/role")
async def bridge_v2_allocator_set_role(request: Request):
    data = await request.json()
    name = data.get("name")
    definition = data.get("definition")
    if not name or not isinstance(name, str) or not isinstance(definition, dict):
        raise HTTPException(status_code=400, detail="name and definition (object) are required")
    _run_allocator(["config", "set-role", "--name", name, "--json", json.dumps(definition)])
    return {"ok": True}


@router.delete("/allocator/config/role/{name}")
async def bridge_v2_allocator_delete_role(name: str):
    _run_allocator(["config", "delete-role", "--name", name])
    return {"ok": True}


@router.post("/export")
async def bridge_v2_export(request: Request):
    """Export BridgeV002 configuration as JSON for backup/restoration."""
    try:
        data = await request.json()
        export_type = data.get("type", "all")
    except Exception:
        export_type = "all"

    result = {}
    if export_type in ("all", "roles"):
        try:
            roles = list_roles_from_db(get_db_path())
            result["roles"] = roles
        except Exception:
            result["roles"] = []

    if export_type in ("all", "flows"):
        try:
            flows_list = list_flows_from_db(get_db_path())
            flow_details = []
            for flow in flows_list:
                try:
                    fd = load_flow_from_db(flow["flow_key"], get_db_path())
                    flow_details.append(fd)
                except Exception:
                    flow_details.append({"flow": flow, "steps": []})
            result["flows"] = flow_details
        except Exception:
            result["flows"] = []

    if export_type == "all":
        all_steps = []
        try:
            flows_to_check = list_flows_from_db(get_db_path())
            for flow in flows_to_check:
                try:
                    fd = load_flow_from_db(flow["flow_key"], get_db_path())
                    for s in (fd.get("steps") or []):
                        s["flow_key"] = flow["flow_key"]
                        all_steps.append(s)
                except Exception as exc:
                    logger.warning("TBD: failed to load flow %s for export: %s", flow.get("flow_key"), exc)
        except Exception as exc:
            logger.warning("TBD: failed to list flows for export: %s", exc)
        result["all_steps"] = all_steps

    return {"export_type": export_type, "data": result}


@router.post("/db-backup")
async def bridge_v2_db_backup():
    """Create a full SQLite database backup and stream it as a downloadable file.

    Opens the source database in read-only mode via URI so the running app's
    write connection is not blocked. The backup is materialized in memory
    using SQLite's online backup API and then serialized to bytes.
    """
    try:
        raw_path = get_db_path()
        db_abs = raw_path if os.path.isabs(raw_path) else str(Path(raw_path).resolve())

        src_conn = sqlite3.connect(f"file:{db_abs}?mode=ro", uri=True)
        dst_conn = sqlite3.connect(":memory:")
        try:
            src_conn.backup(dst_conn)
            data = dst_conn.serialize()
        finally:
            try:
                dst_conn.close()
            except Exception as exc:
                logger.warning("TBD: failed to close in-memory db-backup destination: %s", exc)
            try:
                src_conn.close()
            except Exception as exc:
                logger.warning("TBD: failed to close db-backup source connection: %s", exc)

        app_name = config.get_father_project() or "dpmtf-webui"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{app_name}_{timestamp}.db.bak"

        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-DB-Backup-Source": db_abs,
                "X-DB-Backup-Size": str(len(data)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database backup failed: {e}")