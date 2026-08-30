"""BridgeV002 HTTP API router — moved verbatim from app.py (Spor I + J).

Pure refactor: every endpoint function, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location and the decorator prefix (`@app.X` →
`@router.X`) changed.

Endpoints (30 total):
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
  POST   /api/bridge-v2/flows/{flow_key}/dispatch
  GET    /api/bridge-v2/flows/{flow_key}/trace
  GET    /api/bridge-v2/flows/{flow_key}/steps/{step_key}/execution-config
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
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

# Ensure scripts/bridgeV002/ is on sys.path so the top-level `bridge_lib`
# import resolves. This mirrors what app.py does at its module top;
# duplicating it here keeps routers/bridge.py self-contained. The job-queue
# paths are added here too, once — they used to be inserted inside the async
# handlers, which grew sys.path by three entries per request.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (_PROJECT_ROOT / "scripts" / "bridgeV002",
           _PROJECT_ROOT / "scripts",
           _PROJECT_ROOT / "scripts" / "job_queue",
           _PROJECT_ROOT / "scripts" / "python-runtime"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from attach_tmux import VIEWER_SESSION_PREFIX  # noqa: E402
# One import path only: `from scripts.bridgeV002.bridge_lib import ...`
# beside this used to load the SAME file as a second module object with
# its own state.
from bridge_lib import (  # noqa: E402
    _bridgev002_tables_exist,
    get_next_id_for_flow,
    list_conventions_from_db,
    list_flows_from_db,
    list_roles_from_db,
    list_scripts_from_db,
    load_flow_from_db,
    load_role_from_db,
    resolve_convention_from_db,
)
import runtime_owner  # noqa: E402
import dispatch  # noqa: E402

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402

router = APIRouter(prefix="/api/bridge-v2", tags=["bridge"])


logger = logging.getLogger(__name__)


class DispatchIntent(str, Enum):
    """The CLOSED set of dispatch intents the intent API accepts.

    The client names an INTENT (what it wants done), never a path, a
    target, a script, or a command. Each member maps 1:1 to an existing
    ``dispatch`` signal function, which is called verbatim; the router
    derives every path/target server-side. Adding a member here is a
    deliberate, explicit change — the enum is never driven by the client.
    """

    SIGNAL_SEND = "signal_send"
    SIGNAL_COMPLETE = "signal_complete"
    SIGNAL_ESCALATION = "signal_escalation"
    SIGNAL_ANSWER = "signal_answer"


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


def _with_viewer_session(flow: dict) -> dict:
    """Annotate a flow row with the tmux viewer session attach_tmux.py builds.

    The name is derived from attach_tmux.VIEWER_SESSION_PREFIX rather than
    spelled out here or in the frontend, so the UI cannot drift from the
    script that actually creates the session.
    """
    flow = dict(flow)
    flow["viewer_session"] = f"{VIEWER_SESSION_PREFIX}{flow.get('flow_key', '')}"
    return flow


@router.get("/flows")
async def bridge_v2_list_flows():
    """Return all active BridgeV002 flows from database."""
    try:
        flows = [_with_viewer_session(f) for f in list_flows_from_db(get_db_path())]
        return {"flows": flows, "count": len(flows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridge flows: {e}")


@router.get("/flows/{flow_key}")
async def bridge_v2_get_flow(flow_key: str):
    """Return a BridgeV002 flow definition and its steps from database."""
    try:
        flow_data = load_flow_from_db(flow_key, get_db_path())
        return {
            "flow": _with_viewer_session(flow_data["flow"]),
            "steps": flow_data["steps"],
            "step_count": len(flow_data["steps"]),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load bridge flow: {e}")


@router.get("/flows/{flow_key}/steps/{step_key}/execution-config")
async def bridge_v2_get_step_execution_config(flow_key: str, step_key: str):
    """Return the unified resolver's dict for (flow_key, step_key) verbatim.

    Run 008 / handoff 033 (D4, spec section 18): the explainability
    endpoint. The resolver computes every dimension (governance / model /
    harness / implementation_mode) WITH its source_level (step / role
    default / system); this endpoint exposes that dict over HTTP so the
    operator never has to infer why a value was selected.

    Contract (handoff 033, D4a):
        * Resolves via execution_config.resolve_execution_config(flow_key,
          step_key, db_path=get_db_path()) -- the SINGLE resolver. No
          re-implementation of any precedence, no direct column reads.
        * Returns the resolver dict EXACTLY -- all 13 keys (flow_key,
          step_key, from_role, to_role, governance_file,
          governance_source_level, model_source, model_alias,
          model_source_level, harness_source, harness_profile,
          harness_source_level, implementation_mode). JSON null for a
          None field is fine (it is the dict's own value, not a
          reformatting).
        * 404 (not 500) when the flow_key does not exist (mirrors the
          existing GET /steps/{flow_key} 404 behavior for the flow).
        * 404 when the step_key does not exist for that flow (the
          resolver raises a clear ValueError naming both flow_key and
          step_key; we forward that message verbatim).

    db_path is sourced from get_db_path() (the same DB the surrounding
    endpoints use, including the test fixture monkey-patch). This
    keeps the endpoint and the resolver from silently reading different
    databases.
    """
    db_path = get_db_path()
    # Flow check first -- mirrors the GET /steps/{flow_key} behavior:
    # flow-not-found 404 uses a flow-shaped message, step-not-found 404
    # uses the resolver's message (which already names both keys).
    try:
        load_flow_from_db(flow_key, db_path)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")
    try:
        from execution_config import resolve_execution_config
        return resolve_execution_config(flow_key, step_key, db_path=db_path)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
             model_source, model_alias,
             harness_source, harness_profile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        flow_key, data["step_key"], data["from_role"], data["to_role"],
        deliverable_dir, deliverable_pattern,
        data.get("pre_dispatch_script"), data.get("post_dispatch_script"),
        error_msg, rule_key, max_so + 1,
        int(data.get("auto_chain_to_next", 0)),
        int(data.get("validation_required", 0)),
        data.get("model_source"),
        data.get("model_alias"),
        data.get("harness_source"),
        data.get("harness_profile"),
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
        "model_source": "model_source",
        "model_alias": "model_alias",
        "harness_source": "harness_source",
        "harness_profile": "harness_profile",
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
        cursor.execute("""
            INSERT INTO bridge_roles
            (role_key, tmux_session,
             setup_script, teardown_script, deliver_error_msg, enter_command,
             config_dir,
             default_model_source, default_model_alias,
             default_harness_source, default_harness_profile,
             trade_mcp_push_mode, max_output_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["role_key"],
            data["tmux_session"],
            data.get("setup_script"),
            data.get("teardown_script"),
            data.get("deliver_error_msg"),
            data.get("enter_command", "default"),
            data.get("config_dir"),
            data.get("default_model_source"),
            data.get("default_model_alias"),
            data.get("default_harness_source"),
            data.get("default_harness_profile"),
            data.get("trade_mcp_push_mode"),
            data.get("max_output_tokens"),
        ))
    else:
        # Role exists (active or soft-deleted) — reactivate/update it
        row = dict(existing) if not isinstance(existing, dict) else dict(existing)
        sets = []
        params = []
        for field in ["tmux_session",
                      "setup_script", "teardown_script",
                      "deliver_error_msg", "enter_command",
                      "config_dir", "default_model_source", "default_model_alias",
                      "default_harness_source", "default_harness_profile",
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
        "tmux_session",
        "setup_script", "teardown_script", "deliver_error_msg", "is_active",
        "governance_file",
        "role_type",  # G1: allow frontend to change role type (agent/human)
        "enter_command",  # H150: per-role Enter key configuration
        "config_dir",  # OpenCode config directory override
        "default_model_source", "default_model_alias",  # V3A: Model Allocator source / alias
        "default_harness_source", "default_harness_profile",  # Run 038 D1: harness fields
        "trade_mcp_push_mode", "max_output_tokens",  # Migration 004: runtime config
        "workdir_mode",  # Migration 023: coding-session working directory
        # 2026-08-30 alignment: previously DB-only fields, now frontend-editable
        # so allocator wiring is a UI action, not direct SQL.
        "allocator_client",           # Migration 008: model-allocator client adapter
        "execution_target",           # Migration 029: which machine runs the role
        "fresh_session_command",      # Migration 009: session reset before injection
        "codex_fresh_context_policy", # Migration 069: codex restart-based context release
    ]
    if "workdir_mode" in data and data["workdir_mode"] not in ("target_project", "father"):
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"workdir_mode must be 'target_project' or 'father', got {data['workdir_mode']!r}",
        )
    if "codex_fresh_context_policy" in data:
        policy = (data["codex_fresh_context_policy"] or "").strip()
        if policy and policy not in ("off", "work_unit"):
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=(
                    f"codex_fresh_context_policy must be 'off', 'work_unit' "
                    f"or empty for inherit, got {policy!r}"
                ),
            )
        data["codex_fresh_context_policy"] = policy or None
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

    # A flow's target project must exist before it is stored: dispatch sends
    # roles there, and a role pointed at a missing directory silently reviews
    # whatever repository its session happens to be sitting in.
    if "target_project_path" in data:
        target = (data["target_project_path"] or "").strip()
        if target and not os.path.isdir(target):
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Target project path '{target}' does not exist. "
                    f"Leave it empty for flows that operate on this project."
                ),
            )
        data["target_project_path"] = target or None

    # implementation_mode (Deterministic Patcher, spec sections 41-42):
    # only values the resolver accepts may be stored — an invalid row
    # raises ValueError inside dispatch and stops the chain. Empty/None
    # means NULL = inherit (falls through to the global default 'direct').
    if "implementation_mode" in data:
        mode = (data["implementation_mode"] or "").strip()
        if mode and mode not in ("direct", "deterministic_patch"):
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid implementation_mode '{mode}'. Allowed: "
                    f"'direct', 'deterministic_patch', or empty for inherit."
                ),
            )
        data["implementation_mode"] = mode or None

    # artifact_root (two-flow spec §2): free text, NO directory validation —
    # an artifact root may name a workspace the first run will create.
    # Empty/whitespace means NULL = "the flow key is the root" (the resolver's
    # fallback). Mirrors target_project_path's normalize-to-NULL shape, minus
    # the isdir gate.
    if "artifact_root" in data:
        root = (data["artifact_root"] or "").strip()
        data["artifact_root"] = root or None

    # ui_category (migration 088): which flows panel the card renders in.
    if "ui_category" in data:
        category = (data["ui_category"] or "").strip()
        if category not in ("standard", "experimental"):
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid ui_category '{category}'. "
                    f"Allowed: 'standard', 'experimental'."
                ),
            )
        data["ui_category"] = category

    updatable = [
        "name", "description", "step_order", "is_default", "is_active",
        "auto_complete_enabled", "use_machine_profile", "target_project_path",
        "artifact_root",
        "implementation_mode",
        "ui_category",
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
            capture_output=True, text=True, timeout=310
        )

        # Rebuild the flow viewer so `tmux attach -t flow-<key>` shows the
        # sessions just started. Starting clients often follows a session
        # recreation, which silently breaks the viewer's linked windows --
        # the Human then attaches to dead panes and cannot tell a working
        # chain from a stalled one. That ambiguity is the viewer's whole
        # reason to exist, so the rebuild lives here rather than in anyone's
        # memory. Best-effort: a viewer failure must not fail the start.
        try:
            viewer_script = os.path.join(
                os.environ.get("DPMTF_PROJECT_ROOT", config.get_project_root()),
                "scripts", "bridgeV002", "attach_tmux.py"
            )
            subprocess.run(
                ["python3", viewer_script, flow_key],
                capture_output=True, text=True, timeout=30
            )
        except Exception:
            pass

        if result.returncode == 0:
            return {
                "status": "ok",
                "message": result.stdout.strip() or f"No roles with model_allocator for '{flow_key}'",
            }
        else:
            raise HTTPException(status_code=500, detail=result.stderr.strip())

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="start_coding timed out after 310s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flows/{flow_key}/dispatch")
async def bridge_v2_dispatch_handoff(flow_key: str, request: Request):
    """Spawn dispatch.py to send a handoff between two roles in a flow.

    Body (JSON): {"from_role": str, "to_role": str, "id": str (optional)}.

    The endpoint validates the flow and the two roles against the
    database BEFORE spawning the subprocess. The bridge chain is LIVE
    in tmux on this machine, so a real dispatch fired by a buggy
    validator would inject a prompt into a live role session —
    validation order is part of the contract.

    Decision order, exactly:
      a. flow_key not in bridge_flows → 404, no subprocess spawned.
      b. from_role or to_role not in bridge_roles → 422 with a detail
         naming the offending role(s), no subprocess spawned.
      c. Otherwise spawn dispatch.py with --signal-send and exactly
         the validated values (plus --id only when ``id`` was
         provided), timeout 300 seconds.
      d. The subprocess RAN at all: HTTP 200 with
         {"status": "ok" if returncode==0 else "dispatch_error",
          "exit_code": <verbatim>, "stdout": <verbatim>,
          "stderr": <verbatim>}. A non-zero dispatch exit MUST be
         visible in the 200 body — never a silent success, never a
         swallowed stderr.
      e. TimeoutExpired or spawn failure → HTTP 500 with the error
         text.

    --signal-send is the only verb. The Human explicitly decided
    against exposing --signal-complete / --signal-escalation /
    --signal-answer through this endpoint.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Body must be JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Body must be a JSON object")

    from_role = payload.get("from_role")
    to_role = payload.get("to_role")
    handoff_id = payload.get("id")
    if not isinstance(from_role, str) or not from_role:
        raise HTTPException(status_code=422, detail="from_role is required (str)")
    if not isinstance(to_role, str) or not to_role:
        raise HTTPException(status_code=422, detail="to_role is required (str)")
    if handoff_id is not None and (not isinstance(handoff_id, str) or not handoff_id):
        raise HTTPException(status_code=422, detail="id must be a non-empty str when provided")

    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {exc}")

    try:
        # (a) Flow must exist.
        flow_row = conn.execute(
            "SELECT 1 FROM bridge_flows WHERE flow_key = ? AND is_active = 1",
            (flow_key,),
        ).fetchone()
        if flow_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Flow '{flow_key}' not found in bridge_flows",
            )

        # (b) Both roles must exist.
        missing = []
        for role_key in (from_role, to_role):
            row = conn.execute(
                "SELECT 1 FROM bridge_roles "
                "WHERE role_key = ? AND is_active = 1",
                (role_key,),
            ).fetchone()
            if row is None:
                missing.append(role_key)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Unknown role(s): " + ", ".join(missing)
                ),
            )
    finally:
        conn.close()

    # (c) Spawn dispatch.py. The script path is resolved via the same
    # project-root pattern the neighbouring endpoints use, so the
    # reviewer's TG8 ("no hardcoded /home/svend paths") stays green.
    try:
        script_path = os.path.join(
            os.environ.get("DPMTF_PROJECT_ROOT", config.get_project_root()),
            "scripts", "bridgeV002", "dispatch.py",
        )
        argv = [
            "python3", script_path,
            "--db-flow", flow_key,
            "--signal-send",
            "--from-role", from_role,
            "--to-role", to_role,
        ]
        if handoff_id is not None:
            argv.extend(["--id", handoff_id])

        completed = subprocess.run(
            argv,
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"dispatch.py timed out after 300s "
                f"(stdout={exc.stdout!r}, stderr={exc.stderr!r})"
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"dispatch.py failed to start: {exc}")

    # (d) Verbatim result body. A non-zero exit code is the dispatch
    # script's own verdict — the route does not interpret it, only
    # surfaces it.
    return {
        "status": "ok" if completed.returncode == 0 else "dispatch_error",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


@router.post("/flows/{flow_key}/intent")
async def bridge_v2_flow_intent(flow_key: str, request: Request):
    """Closed, enum-based intent API over the BridgeV002 dispatch signals.

    Body (JSON):
      {
        "intent": "signal_send" | "signal_complete" |
                  "signal_escalation" | "signal_answer",   # closed enum
        "from_role": str,          # required
        "to_role": str,            # required for send/escalation/answer
        "step_key": str,           # required for signal_complete
        "id": str,                 # optional; server allocates if omitted
        "force": bool              # optional, signal_complete only
      }

    Contract:
      - ``intent`` is the CLOSED ``DispatchIntent`` enum — any other value
        is a 422 and nothing is dispatched.
      - The client supplies NO paths and NO targets. ``bridge_dir`` is
        derived server-side (``dispatch._bridge_dir()``) and the target
        project path is derived inside the signal function it calls.
      - Each intent maps 1:1 to the existing ``dispatch.signal_*`` function
        and calls it VERBATIM — there is no reimplementation of dispatch
        logic and no new orchestration semantics (no auto-chain, no retry,
        no reading of results).
      - Idempotency/receipts are preserved because the signal functions own
        the id counter, the duplicate-delivery guard, the job record and
        the trace.log entry; the explicit-id normalization mirrors
        ``dispatch.main()`` and the missing-id case allocates from the
        flow's own counter.
      - The signal functions are CLI-oriented and print to stdout; in this
        in-process surface that output goes to the server log rather than
        being captured, matching the existing subprocess endpoints' effect
        of surfacing dispatch output for the operator.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Body must be JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Body must be a JSON object")

    # Closed enum: exactly one of the four intents, never a free-form string.
    raw_intent = payload.get("intent")
    if not isinstance(raw_intent, str) or not raw_intent:
        raise HTTPException(status_code=422, detail="intent is required (str)")
    try:
        intent = DispatchIntent(raw_intent)
    except ValueError:
        allowed = ", ".join(member.value for member in DispatchIntent)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown intent {raw_intent!r}; allowed intents: {allowed}",
        )

    from_role = payload.get("from_role")
    if not isinstance(from_role, str) or not from_role:
        raise HTTPException(status_code=422, detail="from_role is required (str)")

    to_role = payload.get("to_role")
    step_key = payload.get("step_key")

    # signal_complete addresses the next role via the step; every other
    # intent names its target role explicitly (mirrors dispatch.py's CLI).
    if intent is DispatchIntent.SIGNAL_COMPLETE:
        if not isinstance(step_key, str) or not step_key:
            raise HTTPException(
                status_code=422,
                detail="step_key is required for intent 'signal_complete'",
            )
    else:
        if not isinstance(to_role, str) or not to_role:
            raise HTTPException(
                status_code=422,
                detail=f"to_role is required for intent '{intent.value}'",
            )

    handoff_id = payload.get("id")
    if handoff_id is not None and (not isinstance(handoff_id, str) or not handoff_id):
        raise HTTPException(status_code=422, detail="id must be a non-empty str when provided")

    force = payload.get("force", False)
    if not isinstance(force, bool):
        raise HTTPException(status_code=422, detail="force must be a bool when provided")

    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {exc}")

    try:
        # (a) Flow must exist.
        flow_row = conn.execute(
            "SELECT 1 FROM bridge_flows WHERE flow_key = ? AND is_active = 1",
            (flow_key,),
        ).fetchone()
        if flow_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Flow '{flow_key}' not found in bridge_flows",
            )

        # (b) Referenced roles must exist.
        missing = []
        for role_key in (from_role, to_role):
            if role_key is None:
                continue
            row = conn.execute(
                "SELECT 1 FROM bridge_roles WHERE role_key = ? AND is_active = 1",
                (role_key,),
            ).fetchone()
            if row is None:
                missing.append(role_key)
        if missing:
            raise HTTPException(
                status_code=422,
                detail="Unknown role(s): " + ", ".join(missing),
            )
    finally:
        conn.close()

    # Server-side path derivation — the client never supplies these.
    bridge_dir = dispatch._bridge_dir()

    # Idempotency/receipts: normalize an explicit id exactly as dispatch's
    # CLI does (strip a non-numeric suffix), else allocate from the flow's
    # own counter. The signal function still owns the duplicate-delivery
    # guard, the counter bump and the job/trace records.
    if handoff_id:
        match = re.match(r"^(\d+)", handoff_id)
        if match and match.group(1) != handoff_id:
            handoff_id = match.group(1)
    else:
        handoff_id = f"{get_next_id_for_flow(flow_key, db_path=db_path):03d}"

    # Verbatim reuse: the closed intent maps to the existing signal function.
    if intent is DispatchIntent.SIGNAL_SEND:
        ok = dispatch.signal_send(flow_key, from_role, to_role, handoff_id, bridge_dir)
    elif intent is DispatchIntent.SIGNAL_ESCALATION:
        ok = dispatch.signal_escalation(flow_key, from_role, to_role, handoff_id, bridge_dir)
    elif intent is DispatchIntent.SIGNAL_ANSWER:
        ok = dispatch.signal_answer(flow_key, from_role, to_role, handoff_id, bridge_dir)
    else:  # SIGNAL_COMPLETE
        ok = dispatch.signal_complete(
            flow_key, step_key, from_role, handoff_id, bridge_dir, force=force
        )

    result = {
        "status": "ok" if ok else "dispatch_error",
        "intent": intent.value,
        "flow_key": flow_key,
        "handoff_id": handoff_id,
        "from_role": from_role,
    }
    if intent is DispatchIntent.SIGNAL_COMPLETE:
        result["step_key"] = step_key
    else:
        result["to_role"] = to_role
    return result


@router.get("/flows/{flow_key}/trace")
async def bridge_v2_flow_trace(
    flow_key: str,
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maximum number of entries to return; out-of-range is FastAPI's 422.",
    ),
):
    """Return the last `limit` trace.log entries that belong to a flow.

    The bridge trace log is flow-wide and append-only: it carries
    every flow's and every era's rows mixed together, including
    same-``handoff_id`` rows from other flows. Filtering is
    field-based — substring matching is an auto-fail (past incidents
    charged a rejection to the wrong role because ``"review01SG"``
    appeared inside ``"imple01SG->review01SG"``).

    Decision order, exactly:
      a. flow_key not in bridge_flows (is_active=1, parameterized
         SQL) → 404.
      b. Build the flow's role set from bridge_flow_steps (every
         from_role and to_role value, is_active=1, parameterized).
         An empty set is not an error — it just yields an empty
         feed.
      c. Read {config.get_bridge_dir()}/trace.log — the getter
         called at request time, so a test that sets
         DPMTF_BRIDGE_DIR via monkeypatch.setenv before the call
         gets the fixture path. File missing → 200 with empty
         entries.
      d. Parse each line by FIELD-SPLITTING (split " | " with
         maxsplit=5 → exactly 6 fields; split parts[1] on "->" →
         exactly 2 non-empty names). Empty lines and lines starting
         with "#" are skipped. The 5-field pre-2025 era is dropped
         by the len(parts) < 6 guard; the unicode-arrow era
         ("L→C", "INIT") is dropped by the 2-name guard. " | "
         inside the message stays intact because of maxsplit=5.
      e. Include the entry ONLY if BOTH from_role and to_role are
         in the flow's role set. handoff_id plays no part in the
         filter (the same-id-other-flow test pins this).
      f. Return {"flow_key": flow_key, "entries": <the last
         `limit` matching entries, in file order — oldest first>}.

    The endpoint is read-only: no write to trace.log, no
    subprocess, no DB write. The two SELECTs are the only DB
    traffic.
    """
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {exc}")

    try:
        # (a) Flow must exist (and be active).
        flow_row = conn.execute(
            "SELECT 1 FROM bridge_flows WHERE flow_key = ? AND is_active = 1",
            (flow_key,),
        ).fetchone()
        if flow_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Flow '{flow_key}' not found in bridge_flows",
            )

        # (b) Build the flow's role set from bridge_flow_steps.
        role_rows = conn.execute(
            "SELECT from_role, to_role FROM bridge_flow_steps "
            "WHERE flow_key = ? AND is_active = 1",
            (flow_key,),
        ).fetchall()
        role_set = set()
        for row in role_rows:
            for value in row:
                if isinstance(value, str) and value:
                    role_set.add(value)
    finally:
        conn.close()

    # (c) Read the trace log via the getter at request time so
    # monkeypatch.setenv("DPMTF_BRIDGE_DIR", ...) is honoured by
    # every test invocation.
    bridge_dir = config.get_bridge_dir()
    log_path = os.path.join(bridge_dir, "trace.log")

    if not os.path.isfile(log_path):
        return {"flow_key": flow_key, "entries": []}

    try:
        with open(log_path, "r", encoding="utf-8") as handle:
            raw_text = handle.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"trace.log read failed: {exc}")

    # (d)+(e) Parse line-by-line, field-split, filter on the role set.
    # No substring matching anywhere in this path.
    entries: list[dict] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(" | ", 5)
        if len(parts) < 6:
            continue
        timestamp, direction, handoff_id, event, _mode, message = parts
        direction_names = direction.split("->", 1)
        if len(direction_names) != 2:
            continue
        from_role, to_role = direction_names
        if not from_role or not to_role:
            continue
        if from_role not in role_set or to_role not in role_set:
            continue
        entries.append({
            "timestamp": timestamp,
            "from_role": from_role,
            "to_role": to_role,
            "handoff_id": handoff_id,
            "event": event,
            "message": message,
        })

    # (f) Last `limit` matching entries, in file order (oldest first
    # within the returned slice). The O3 feed is newest-last so the
    # UI can append the next batch in place.
    return {"flow_key": flow_key, "entries": entries[-limit:]}


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


@router.post("/flows/{flow_key}/stop-servers")
async def bridge_v2_stop_servers_for_flow(flow_key: str):
    """Stop all model servers (llama.cpp, SGLang) used by a flow's roles."""
    db_path = config.get_db_path()
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="Database not found")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Get unique model aliases for this flow's roles
        rows = conn.execute(
            """SELECT DISTINCT br.role_key, br.default_model_alias,
                      br.execution_target
               FROM bridge_flow_steps bfs
               JOIN bridge_roles br ON br.role_key IN (bfs.from_role, bfs.to_role)
               WHERE bfs.flow_key = ? AND br.default_model_source = 'model_allocator'
                 AND br.default_model_alias IS NOT NULL""",
            (flow_key,)
        ).fetchall()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # A remote role's server runs on ITS machine, and Father's stored alias
    # for it can be stale — the worker resolves role→alias against its own
    # roles.yaml (that indirection is the allocator's whole design). So the
    # stop is executed on the worker, resolving there: stopping Father's
    # alias name locally stopped nothing while the worker's llama.cpp kept
    # the card.
    remote_roles = [(r["role_key"], r["execution_target"]) for r in rows
                    if (r["execution_target"] or "").strip()]
    aliases = [r["default_model_alias"] for r in rows
               if not (r["execution_target"] or "").strip()]

    stopped = []
    errors = []

    # Harness resources DPMtF started for this flow and therefore owns. Stop
    # only what is recorded in the ownership registry — never by executable
    # name, never an externally started process. One-shot codex exec / DSH
    # headless invocations carry no row and so require no shutdown here.
    try:
        for resource_id in runtime_owner.stop_owned_harness_processes(flow_key):
            stopped.append("harness:" + resource_id)
    except Exception as exc:
        errors.append("harness sweep: " + str(exc))

    if not aliases and not remote_roles:
        if errors:
            return {"status": "partial", "message": "Errors: " + "; ".join(errors),
                    "stopped": stopped, "errors": errors}
        if stopped:
            return {"status": "ok", "message": "Stopped harness processes: " + ", ".join(stopped),
                    "stopped": stopped}
        return {"status": "ok", "message": "No model servers to stop for flow '" + flow_key + "'", "stopped": []}

    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts", "model-allocator",
    )

    for role_key, target in remote_roles:
        # Resolved ON the worker, stopped ON the worker. The script goes via
        # stdin (`bash -ls`) rather than as an argument — the day's quoting
        # lesson: every nesting level is a place for the command to break.
        script = (
            f"a=$(model-allocator resolve --role {role_key} "
            "--client opencode 2>/dev/null "
            "| sed -n 's/.*\"alias\": \"\\([^\"]*\\)\".*/\\1/p' | head -1)\n"
            'if [ -n "$a" ]; then\n'
            '  model-allocator stop --alias "$a" && echo "stopped:$a"\n'
            "else\n"
            '  echo "no-alias"\n'
            "fi\n"
        )
        try:
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                 target, "bash -ls"],
                input=script, capture_output=True, text=True, timeout=60,
            )
            out = (result.stdout or "").strip()
            if "stopped:" in out:
                stopped.append(f"{target}:{out.split('stopped:')[-1].strip()}")
            else:
                errors.append(f"{role_key}@{target}: "
                              f"{(result.stderr or out or 'no output')[:120]}")
        except subprocess.TimeoutExpired:
            errors.append(f"{role_key}@{target}: timeout")

    for alias in aliases:
        try:
            result = subprocess.run(
                [allocator_script, "stop", "--alias", alias],
                capture_output=True, text=True, timeout=45
            )
            if result.returncode == 0:
                stopped.append(alias)
            else:
                errors.append(alias + ": " + (result.stderr.strip()[:200] if result.stderr else "unknown error"))
        except subprocess.TimeoutExpired:
            errors.append(alias + ": timed out")
        except Exception as e:
            errors.append(alias + ": " + str(e))

    if errors:
        return {
            "status": "partial",
            "message": "Stopped: " + ", ".join(stopped) + ". Errors: " + "; ".join(errors),
            "stopped": stopped,
            "errors": errors,
        }
    return {
        "status": "ok",
        "message": "Stopped servers: " + ", ".join(stopped),
        "stopped": stopped,
    }


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


# ── Thin proxy: Test OK for allocator alias ──────────────────

@router.get("/allocator-test")
async def bridge_v2_allocator_test(alias: str, client: str = "opencode"):
    """Thin proxy: run `model-allocator validate --alias X --client Y --json`.

    Returns the validation result so the role editor's 'Test OK' button
    can show OK/Error inline without a full allocator dashboard.
    """
    import json as _json
    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts", "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "validate", "--alias", alias,
             "--client", client, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode in (0, 2):
            try:
                return _json.loads(result.stdout)
            except _json.JSONDecodeError:
                return {"validation_status": "ERROR",
                        "errors": ["Failed to parse allocator output"]}
        else:
            return {"validation_status": "ERROR",
                    "errors": [result.stderr.strip() or result.stdout.strip() or "Unknown error"]}
    except subprocess.TimeoutExpired:
        return {"validation_status": "ERROR",
                "errors": ["Allocator validate timed out after 30s"]}
    except Exception as exc:
        return {"validation_status": "ERROR",
                "errors": [str(exc)]}


@router.get("/allocator-aliases")
async def bridge_v2_allocator_aliases():
    """Alias vocabulary for the model-alias pickers.

    Thin proxy over `model-allocator list` (JSON), so the role and step
    editors can offer the aliases that actually exist instead of a blank
    text field. Free text stays possible in the UI — this is a datalist,
    not a gate.
    """
    import json as _json
    allocator_script = os.path.join(
        config.get_project_path("model-allocator"),
        "scripts", "model-allocator",
    )
    try:
        result = subprocess.run(
            [allocator_script, "list"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=502,
                detail=result.stderr.strip() or "model-allocator list failed",
            )
        rows = _json.loads(result.stdout)
        return {"aliases": [
            {"alias": r.get("alias"), "status": r.get("status"),
             "backend": r.get("backend"), "real_model": r.get("real_model")}
            for r in rows if r.get("alias")
        ]}
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="model-allocator list timed out")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/harnesses")
async def bridge_v2_harnesses():
    """The harness roster, straight from the harness-allocator package.

    Serves the vocabulary for the harness-source pickers: supported and
    experimental harnesses with their LaunchSpec mode and launch owner
    (native = harness-allocator builds the command, otherwise the
    model-allocator client adapter launches). The roster is derived, never
    duplicated here — harness-allocator is the single source of truth.
    """
    try:
        import harness as harness_mod  # scripts/bridgeV002/harness.py (sys.path above)
        ha = harness_mod._standalone()
        from harness_allocator import capabilities, launchspec, definition

        def _entry(key, tier):
            try:
                spec = launchspec.get_launch_spec(key) or {}
            except Exception:
                spec = {}
            try:
                reset = launchspec.get_reset_spec(key)
            except Exception:
                reset = None
            return {
                "harness": key,
                "tier": tier,
                "mode": spec.get("mode"),
                "launch_owner": ("harness_allocator" if definition.is_native(key)
                                 else "model_allocator"),
                "required_env": list(spec.get("required_env") or []),
                # How a live session's context is reset (item 15): the
                # declared harness fact behind the per-role
                # fresh_session_command / codex_fresh_context_policy knobs.
                "reset": reset,
            }

        return {"harnesses": (
            [_entry(k, "supported") for k in capabilities.SUPPORTED_HARNESSES]
            + [_entry(k, "experimental") for k in capabilities.EXPERIMENTAL_HARNESSES]
        )}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"harness roster unavailable: {exc}")


@router.get("/ui-links")
async def bridge_v2_ui_links():
    """Companion web UI URLs from config — ports are data, never hardcoded JS."""
    return {
        "allocator_web_url": config.get_allocator_web_url(),
        "harness_web_url": config.get_harness_web_url(),
    }


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

# ── Job Queue endpoints ──────────────────────────────────────────

@router.post("/jobs")
async def bridge_v2_create_job(request: Request):
    """Create a job in DRAFT state."""
    from job_queue.models import JobRepository

    data = await request.json()
    required = ["flow_key", "role_key", "goal", "target_project"]
    for field in required:
        if not data.get(field):
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")

    repo = JobRepository()
    try:
        job_id = repo.create_job(
            flow_key=data["flow_key"],
            role_key=data["role_key"],
            goal=data["goal"],
            target_project=data["target_project"],
            allocator_alias=data.get("allocator_alias", ""),
            step_key=data.get("step_key", ""),
            priority=data.get("priority", 0),
            idempotency_key=data.get("idempotency_key", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"job_id": job_id, "status": "DRAFT"}


@router.put("/jobs/{job_id}/approve")
async def bridge_v2_approve_job(job_id: str):
    from job_queue.models import JobRepository, IllegalTransitionError

    repo = JobRepository()
    try:
        repo.transition(job_id, "AWAITING_APPROVAL", actor="human")
        repo.transition(job_id, "APPROVED", actor="human")
    except IllegalTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"job_id": job_id, "status": "APPROVED"}


@router.get("/jobs")
async def bridge_v2_list_jobs(status: str = None, flow_key: str = None):
    from job_queue.models import JobRepository

    repo = JobRepository()
    jobs = repo.list_jobs(status=status, flow_key=flow_key)
    return {"jobs": [j.__dict__ for j in jobs], "count": len(jobs)}


@router.get("/jobs/{job_id}")
async def bridge_v2_get_job(job_id: str):
    from job_queue.models import JobRepository

    repo = JobRepository()
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    events = repo.get_events(job_id)
    return {"job": job.__dict__, "events": events}


@router.post("/jobs/{job_id}/cancel")
async def bridge_v2_cancel_job(job_id: str):
    from job_queue.models import JobRepository, IllegalTransitionError

    repo = JobRepository()
    try:
        repo.transition(job_id, "CANCELLED", actor="human")
    except IllegalTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"job_id": job_id, "status": "CANCELLED"}


@router.post("/jobs/scheduler/tick")
async def bridge_v2_scheduler_tick():
    from job_queue.scheduler import Scheduler

    sched = Scheduler()
    result = sched.tick()
    return result


# ── Handoff Compiler endpoint ─────────────────────────────────────

@router.post("/jobs/compile")
async def bridge_v2_compile_handoff(request: Request):
    """Compile an approved goal into bounded execution jobs.

    Body: {goal, flow_key, role_key, target_project, model_context_window}
    Returns: {jobs: [...], count: N}
    """
    from handoff_compiler import compile_handoff, create_jobs_from_compiled
    from job_queue.models import JobRepository
    from context_fit_spike import evaluate_fit

    data = await request.json()
    required = ["goal", "flow_key", "role_key", "target_project"]
    for field in required:
        if not data.get(field):
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")

    # Default context window: 131072 (will be overridden by allocator in production)
    model_ctx = data.get("model_context_window", 131072)

    compiled = compile_handoff(
        goal=data["goal"],
        flow_key=data["flow_key"],
        role_key=data["role_key"],
        target_project=data["target_project"],
        model_context_window=model_ctx,
    )

    # Create jobs in the queue
    repo = JobRepository()
    job_ids = create_jobs_from_compiled(
        repo, compiled,
        allocator_alias=data.get("allocator_alias", ""),
    )

    return {
        "jobs": [{"job_id": jid, "goal": c.goal, "context_fit_state": c.context_fit_state,
                   "is_continuation": c.is_continuation}
                  for jid, c in zip(job_ids, compiled)],
        "count": len(job_ids),
    }
