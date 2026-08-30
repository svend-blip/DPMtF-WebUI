"""Panels router (panel CRUD, classifications, groups, structure, selections).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints (10 total):
  GET    /api/panels
  POST   /api/panels/{panel_id}/classification
  GET    /api/app-profiles/{profile_id}/panels
  POST   /api/app-profiles/{profile_id}/panels/{panel_id}
  GET    /api/user-panel-groups
  POST   /api/user-panel-groups
  GET    /api/panel-structure
  POST   /api/panel-structure/subgroup-state
  GET    /api/reusable-panel-selections
  GET    /api/v2-panel-requirements

The panel endpoints use three module-level constants that lived in
app.py at lines 210 (ALLOWED_CLASSIFICATIONS) and 951-952
(VALID_PANEL_GROUPS, VALID_PANEL_STATES). These constants were used
ONLY by panel endpoints (verified via grep — no other usage in
app.py), so they have been moved here with no external impact.

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1) — this preserves the test fixture's monkeypatch
of `app.DB_PATH` and avoids circular imports at module top-level.
"""

import json
import logging
import os
import sqlite3

from fastapi import APIRouter, HTTPException, Request

from routers.shared import get_db_path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["panels"])


# ── Panel data constants (moved verbatim from app.py) ────────────────

# Valid user panel groups + states (user-panel-groups endpoints)
VALID_PANEL_GROUPS = {"daily", "journals", "reports", "periodic", "setup", "job-queue", "allocator", "experimental"}
VALID_PANEL_STATES = {"expanded", "collapsed"}


# ── Endpoints ────────────────
#
# The panel-classification subsystem (GET /api/panels, POST
# /api/panels/{id}/classification, GET/POST /api/app-profiles/{id}/panels)
# was removed 2026-08-30: frontend_panels and panel_classifications have
# been empty since the subsystem was scaffolded, and nothing in static/,
# templates/, or mcp-light ever called the endpoints. The tables stay
# (DB-safety rule — no destructive schema changes for dead code); the
# reusable-panel-selections and v2-panel-requirements registries below hold
# real rows and remain served.


@router.get("/api/user-panel-groups")
async def get_user_panel_groups():
    """Return the current user's panel group collapse/expand states.

    Identifies user via os.getlogin(). Falls back to 'default'.
    Returns empty groups object if no data or database unavailable.
    """
    try:
        user_id = os.getlogin()
    except Exception:
        user_id = "default"

    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT group_name, state, is_visible FROM user_panel_groups WHERE user_id = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        groups = {}
        for row in rows:
            groups[row["group_name"]] = {
                "state": row["state"],
                "is_visible": bool(row["is_visible"]),
            }
        return {"user_id": user_id, "groups": groups}
    except Exception:
        try:
            conn.close()
        except Exception as exc:
            logger.warning("TBD: failed to close user-panel-groups connection: %s", exc)
        return {"user_id": user_id, "groups": {}}


@router.post("/api/user-panel-groups")
async def set_user_panel_group(request: Request):
    """Store a panel group collapse/expand state for the current user.

    Body (JSON): {"group_name": "journals", "state": "collapsed"}
    """
    data = await request.json()
    group_name = data.get("group_name", "").strip()
    state = data.get("state", "").strip()
    is_visible = data.get("is_visible", 1)

    if not group_name:
        raise HTTPException(status_code=400, detail="Missing required field: group_name")
    if group_name not in VALID_PANEL_GROUPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_name: {group_name}. Must be one of: {', '.join(sorted(VALID_PANEL_GROUPS))}",
        )
    if not state:
        raise HTTPException(status_code=400, detail="Missing required field: state")
    if state not in VALID_PANEL_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Must be one of: {', '.join(sorted(VALID_PANEL_STATES))}",
        )

    try:
        user_id = os.getlogin()
    except Exception:
        user_id = "default"

    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (user_id, group_name, state, is_visible))
        conn.commit()
        conn.close()
        return {"user_id": user_id, "group_name": group_name, "state": state, "status": "stored"}
    except Exception as exc:
        logger.error("Failed to store panel group state for %s: %s", group_name, exc)
        raise HTTPException(status_code=500, detail=f"Failed to store panel group state: {exc}")


@router.get("/api/reusable-panel-selections")
async def get_reusable_panel_selections():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get active reusable panel selections ordered by migration_priority
    cursor.execute("""
        SELECT reusable_panel_id, target_project_key, source_project_path,
               panel_key, panel_title, source_html_id, source_panel_kind,
               selection_status, selection_reason, migration_priority,
               is_required, is_active
        FROM reusable_panel_selections
        WHERE is_active = 1
        ORDER BY migration_priority
    """)

    reusable_panel_selections = []
    for row in cursor.fetchall():
        reusable_panel_selections.append({
            "reusable_panel_id": row[0],
            "target_project_key": row[1],
            "source_project_path": row[2],
            "panel_key": row[3],
            "panel_title": row[4],
            "source_html_id": row[5],
            "source_panel_kind": row[6],
            "selection_status": row[7],
            "selection_reason": row[8],
            "migration_priority": row[9],
            "is_required": bool(row[10]),
            "is_active": bool(row[11]),
        })

    conn.close()
    return {"reusable_panel_selections": reusable_panel_selections}


@router.get("/api/v2-panel-requirements")
async def get_v2_panel_requirements():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get active v2 panel requirements ordered by panel_key, display_order
    cursor.execute("""
        SELECT requirement_id, target_project_key, panel_key, panel_title,
               card_key, card_title, card_type, display_order,
               source_reference, required_data_json, visual_requirements_json,
               behavior_requirements_json, implementation_status,
               is_required, is_active
        FROM v2_panel_requirements
        WHERE is_active = 1
        ORDER BY panel_key, display_order
    """)

    v2_panel_requirements = []
    for row in cursor.fetchall():
        record = {
            "requirement_id": row[0],
            "target_project_key": row[1],
            "panel_key": row[2],
            "panel_title": row[3],
            "card_key": row[4],
            "card_title": row[5],
            "card_type": row[6],
            "display_order": row[7],
            "source_reference": row[8],
            "required_data": json.loads(row[9]),
            "visual_requirements": json.loads(row[10]),
            "behavior_requirements": json.loads(row[11]),
            "implementation_status": row[12],
            "is_required": bool(row[13]),
            "is_active": bool(row[14]),
        }
        v2_panel_requirements.append(record)

    conn.close()
    return {"v2_panel_requirements": v2_panel_requirements}


@router.get("/api/panel-structure")
async def get_panel_structure(locale: str = "en-US"):
    """Return full panel hierarchy with subgroups, visibility, and collapse states."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT group_name, state, is_visible FROM user_panel_groups WHERE user_id = 'default'"
    )
    group_rows = {r["group_name"]: r for r in cursor.fetchall()}

    cursor.execute(
        "SELECT * FROM panel_subgroups WHERE is_visible = 1 ORDER BY sort_order"
    )
    subgroups = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM panel_subgroup_mappings")
    mappings = {}
    for r in cursor.fetchall():
        sg = r["subgroup_key"]
        if sg not in mappings:
            mappings[sg] = []
        mappings[sg].append(r["slot_key"])

    cursor.execute(
        "SELECT group_name, state FROM user_panel_groups WHERE user_id = 'default' AND group_name LIKE 'sg_%'"
    )
    subgroup_states = {r["group_name"]: r["state"] for r in cursor.fetchall()}

    group_names = ["daily", "journals", "reports", "periodic", "setup", "job-queue", "allocator", "experimental"]
    result = {}
    title_field = "title_da" if locale == "da-DK" else "title_en"

    for gn in group_names:
        gr = group_rows.get(gn)
        is_visible = gr["is_visible"] if gr else 1
        state = gr["state"] if gr else "expanded"

        group_subgroups = [sg for sg in subgroups if sg["group_name"] == gn]

        if group_subgroups:
            subgroup_list = []
            for sg in group_subgroups:
                subgroup_list.append({
                    "key": sg["subgroup_key"],
                    "title": sg[title_field],
                    "is_visible": bool(sg["is_visible"]),
                    "state": subgroup_states.get(sg["subgroup_key"], "expanded"),
                    "slots": mappings.get(sg["subgroup_key"], []),
                })
        else:
            subgroup_list = [{
                "key": f"sg_{gn}_all",
                "title": "",
                "is_visible": True,
                "state": "expanded",
                "slots": [],
            }]

        result[gn] = {
            "is_visible": bool(is_visible),
            "state": state,
            "subgroups": subgroup_list,
        }

    conn.close()
    return {"groups": result}


@router.post("/api/panel-structure/subgroup-state")
async def save_subgroup_state(request: Request):
    """Save collapse state for a panel subgroup."""
    data = await request.json()
    subgroup_key = data.get("subgroup_key")
    state = data.get("state", "expanded")

    if not subgroup_key:
        raise HTTPException(status_code=400, detail="subgroup_key required")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
        VALUES ('default', ?, ?, 1, datetime('now'))
    """, (subgroup_key, state))
    conn.commit()
    conn.close()
    return {"status": "saved", "subgroup_key": subgroup_key, "state": state}