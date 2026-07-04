"""System router (health, user prefs, layout, phase status, platform, system/*).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (14 total):
  GET    /
  GET    /api/health
  GET    /api/user-language
  POST   /api/user-language
  GET    /api/available-languages
  GET    /api/user-preferences
  POST   /api/user-preferences
  GET    /api/phase-status
  GET    /api/frontend-layout
  GET    /api/endpoint-runtime-status
  GET    /api/platform
  GET    /api/system/machine-profile
  GET    /api/system/healthcheck
  GET    /api/system/healthcheck/{section}

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1) — this preserves the test fixture's monkeypatch
of `app.DB_PATH` and avoids circular imports at module top-level.
"""

import logging
import os
import platform
import sqlite3
import sys
from pathlib import Path

# Ensure scripts/ is on sys.path for platform_adapter (mirrors app.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402


router = APIRouter(tags=["system"])


logger = logging.getLogger(__name__)


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── GET / ──

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return HTMLResponse(content=open("templates/index.html").read())


# ── GET /api/health ──

@router.get("/api/health")
async def health_check():
    database_exists = os.path.exists(get_db_path())
    status = "healthy" if database_exists else "unhealthy"
    logger.info("Health check: %s (db_path=%s)", status, get_db_path())
    return {
        "status": status,
        "app": "DPMtF WebUI",
        "database_path": get_db_path(),
        "database_exists": database_exists
    }


# ── GET /api/user-language ──

@router.get("/api/user-language")
async def get_user_language():
    """Return the current user's language preference.

    Identifies user via os.getlogin(). Falls back to 'default' row,
    then to hardcoded 'en-US' if table is empty.
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
            "SELECT locale FROM user_language WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return {"user_id": user_id, "locale": row["locale"]}

        cursor.execute(
            "SELECT locale FROM user_language WHERE user_id = 'default'",
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"user_id": user_id, "locale": row["locale"]}
        return {"user_id": user_id, "locale": "en-US"}
    except Exception as exc:
        logger.error("get_user_language failed: %s", exc)
        try:
            conn.close()
        except Exception as exc_close:
            logger.warning("TBD: failed to close user-language connection: %s", exc_close)
        return {"user_id": user_id, "locale": "en-US"}


# ── POST /api/user-language ──

@router.post("/api/user-language")
async def set_user_language(request: Request):
    """Store the user's language preference.

    Body (JSON): {"locale": "da-DK"}
    Validates that the locale exists in ui_label_translations.
    """
    data = await request.json()
    locale = data.get("locale", "").strip()

    if not locale:
        raise HTTPException(status_code=400, detail="Missing required field: locale")

    # Validate locale exists in translations
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM ui_label_translations WHERE locale = ? AND is_active = 1",
            (locale,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row or row[0] == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported locale: {locale}. No translations found.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("set_user_language locale validation error (continuing): %s", exc)

    try:
        user_id = os.getlogin()
    except Exception:
        user_id = "default"

    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_language (user_id, locale, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (user_id, locale))
        conn.commit()
        conn.close()
        return {"user_id": user_id, "locale": locale, "status": "stored"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store preference: {exc}")


# ── GET /api/available-languages ──

@router.get("/api/available-languages")
async def get_available_languages():
    """Return distinct locales with display names from ui_label_translations.

    The frontend uses this to populate the language dropdown dynamically.
    Adding a new locale to ui_label_translations automatically makes it
    available in the dropdown — no HTML changes needed.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT locale
        FROM ui_label_translations
        WHERE is_active = 1
        ORDER BY locale
    """)
    rows = cursor.fetchall()
    conn.close()

    # Locale display names (en-US)
    locale_names = {
        "da-DK": "Dansk",
        "en-US": "English",
        "de-DE": "Deutsch",
        "el-GR": "Ελληνικά",
        "sv-SE": "Svenska",
    }

    languages = []
    for row in rows:
        loc = row["locale"]
        languages.append({
            "locale": loc,
            "display_name": locale_names.get(loc, loc)
        })

    # Fallback if table is empty (should not happen, but safe)
    if not languages:
        languages = [
            {"locale": "en-US", "display_name": "English"},
            {"locale": "da-DK", "display_name": "Dansk"},
        ]

    return {"languages": languages}


# ── GET /api/user-preferences ──

@router.get("/api/user-preferences")
async def get_user_preferences():
    """Return all preferences for the current user."""
    try:
        user_id = os.getlogin()
    except Exception:
        user_id = "default"

    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT pref_key, pref_value FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        conn.close()
        prefs = {row["pref_key"]: row["pref_value"] for row in rows}
        return {"user_id": user_id, "preferences": prefs}
    except Exception as exc:
        logger.warning("get_user_preferences failed (returning empty): %s", exc)
        try:
            conn.close()
        except Exception as exc_close:
            logger.warning("TBD: failed to close user-preferences connection: %s", exc_close)
        return {"user_id": user_id, "preferences": {}}


# ── POST /api/user-preferences ──

@router.post("/api/user-preferences")
async def set_user_preference(request: Request):
    """Store a single user preference.

    Body (JSON): {"pref_key": "target_project", "pref_value": "<absolute project path>"}
    """
    data = await request.json()
    pref_key = data.get("pref_key", "").strip()
    pref_value = data.get("pref_value", "").strip()

    if not pref_key:
        raise HTTPException(status_code=400, detail="Missing required field: pref_key")

    try:
        user_id = os.getlogin()
    except Exception:
        user_id = "default"

    try:
        conn = sqlite3.connect(get_db_path())
        conn.execute(
            """INSERT OR REPLACE INTO user_preferences (user_id, pref_key, pref_value, updated_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (user_id, pref_key, pref_value),
        )
        conn.commit()
        conn.close()
        return {"user_id": user_id, "pref_key": pref_key, "pref_value": pref_value, "status": "stored"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store preference: {exc}")


# ── GET /api/phase-status ──

@router.get("/api/phase-status")
async def get_phase_status():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get completed phases
    cursor.execute("""
        SELECT phase_key, phase_title, phase_description, phase_state, sort_order
        FROM phase_status
        WHERE phase_state = 'completed'
        ORDER BY sort_order
    """)

    completed = []
    for row in cursor.fetchall():
        completed.append({
            "phase_key": row[0],
            "phase_title": row[1],
            "phase_description": row[2],
            "phase_state": row[3],
            "sort_order": row[4]
        })

    # Get next phase
    cursor.execute("""
        SELECT phase_key, phase_title, phase_description, phase_state, sort_order
        FROM phase_status
        WHERE phase_state = 'next'
        ORDER BY sort_order
    """)

    next_phases = []
    for row in cursor.fetchall():
        next_phases.append({
            "phase_key": row[0],
            "phase_title": row[1],
            "phase_description": row[2],
            "phase_state": row[3],
            "sort_order": row[4]
        })

    # Get planned phases (if any)
    cursor.execute("""
        SELECT phase_key, phase_title, phase_description, phase_state, sort_order
        FROM phase_status
        WHERE phase_state = 'planned'
        ORDER BY sort_order
    """)

    planned = []
    for row in cursor.fetchall():
        planned.append({
            "phase_key": row[0],
            "phase_title": row[1],
            "phase_description": row[2],
            "phase_state": row[3],
            "sort_order": row[4]
        })

    conn.close()
    return {
        "completed": completed,
        "next": next_phases,
        "planned": planned
    }


# ── GET /api/frontend-layout ──

@router.get("/api/frontend-layout")
async def get_frontend_layout():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get layout slots
    cursor.execute("""
        SELECT slot_id, slot_name, slot_description, display_order, is_active
        FROM layout_slots
        ORDER BY display_order
    """)

    layout_slots = []
    for row in cursor.fetchall():
        layout_slots.append({
            "slot_id": row[0],
            "slot_name": row[1],
            "slot_description": row[2],
            "display_order": row[3],
            "is_active": bool(row[4])
        })

    # Get layout panels
    cursor.execute("""
        SELECT panel_id, slot_id, panel_key, panel_title, panel_description, panel_type, display_order, is_active
        FROM layout_panels
        ORDER BY display_order
    """)

    layout_panels = []
    for row in cursor.fetchall():
        layout_panels.append({
            "panel_id": row[0],
            "slot_id": row[1],
            "panel_key": row[2],
            "panel_title": row[3],
            "panel_description": row[4],
            "panel_type": row[5],
            "display_order": row[6],
            "is_active": bool(row[7])
        })

    conn.close()
    return {
        "layout_slots": layout_slots,
        "layout_panels": layout_panels
    }
async def get_endpoint_registry():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get all active endpoints ordered by endpoint_id
    cursor.execute("""
        SELECT endpoint_id, endpoint_key, route_path, http_method, endpoint_purpose,
               response_shape, frontend_consumer, is_read_only, is_active, created_at, updated_at
        FROM endpoint_registry
        WHERE is_active = 1
        ORDER BY endpoint_id
    """)

    endpoints = []
    for row in cursor.fetchall():
        endpoints.append({
            "endpoint_id": row[0],
            "endpoint_key": row[1],
            "route_path": row[2],
            "http_method": row[3],
            "endpoint_purpose": row[4],
            "response_shape": row[5],
            "frontend_consumer": row[6],
            "is_read_only": bool(row[7]),
            "is_active": bool(row[8]),
            "created_at": row[9],
            "updated_at": row[10],
        })

    conn.close()
    return {"endpoint_registry": endpoints}


# ── GET /api/endpoint-runtime-status ──

@router.get("/api/endpoint-runtime-status")
async def get_endpoint_runtime_status():
    # Build in-memory map of registered FastAPI routes (late-import to avoid
    # circular dependency: app imports this router; this router must not import
    # app at module top-level).
    import app as _app
    route_map = {}
    for route in _app.app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            path = route.path
            methods = route.methods - {"HEAD", "OPTIONS"}
            if path not in route_map:
                route_map[path] = set()
            route_map[path].update(methods)

    # Query active endpoint_registry records ordered by endpoint_id
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute("""
        SELECT endpoint_id, endpoint_key, route_path, http_method
        FROM endpoint_registry
        WHERE is_active = 1
        ORDER BY endpoint_id
    """)

    runtime_status = []
    for row in cursor.fetchall():
        endpoint_id, endpoint_key, route_path, http_method = row

        # Check if route path is registered
        route_registered = route_path in route_map

        # Check if HTTP method is registered for the route
        if route_registered:
            method_registered = http_method in route_map.get(route_path, set())
        else:
            method_registered = False

        # Determine status string
        if route_registered and method_registered:
            status = "ok"
        elif not route_registered:
            status = "missing_route"
        else:
            status = "missing_method"

        runtime_status.append({
            "endpoint_id": endpoint_id,
            "endpoint_key": endpoint_key,
            "route_path": route_path,
            "http_method": http_method,
            "route_registered": route_registered,
            "method_registered": method_registered,
            "status": status,
            "check_type": "fastapi_route_registry",
        })

    conn.close()
    return {"endpoint_runtime_status": runtime_status}


# Allowed table names for safe counting in bootstrap dataset status
ALLOWED_BOOTSTRAP_TABLES = {
    "phase_status",
    "layout_slots",
    "layout_panels",
    "ui_labels",
    "ui_label_translations",
    "endpoint_registry",
    "architecture_decision_records",
    "webui_migration_targets",
    "reusable_panel_selections",
    "webui_project_skeletons",
    "v2_panel_requirements",
}


# ── GET /api/platform ──

@router.get("/api/platform")
async def get_platform_info():
    """Return current platform information.

    Uses the PlatformAdapter to report platform type, available
    tools, and sample system queries (GPU count, home dir).
    """
    from platform_adapter import get_adapter
    adapter = get_adapter()

    info = {
        "platform": adapter.get_platform_name(),
        "python_version": sys.version,
        "os_release": platform.release(),
        "home_dir": adapter.get_home_dir(),
        "path_separator": adapter.get_env_path_separator(),
    }

    # Lightweight system queries
    try:
        gpus = adapter.get_gpu_info()
        info["gpu_count"] = len(gpus)
        info["gpus"] = gpus[:2]  # First two GPUs
    except Exception:
        info["gpu_count"] = 0

    try:
        home_usage = adapter.get_disk_usage(adapter.get_home_dir())
        info["home_disk"] = home_usage
    except Exception:
        info["home_disk"] = None

    return info


# ── GET /api/system/machine-profile ──

@router.get("/api/system/machine-profile")
async def system_machine_profile():
    """Return safe metadata about the active Machine Profile.

    Never returns secrets, paths, or raw profile data.
    """
    try:
        metadata = config.get_machine_profile_metadata()
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read Machine Profile: {e}",
        )


# ── GET /api/system/healthcheck ──

@router.get("/api/system/healthcheck")
async def system_healthcheck():
    """Run all Machine Profile healthchecks.

    Returns structured results with status and severity per check.
    Never blocks existing functionality.
    """
    try:
        profile = config.get_machine_profile()
        # Late import to avoid circular dependency: scripts/system_healthcheck
        # is not part of the routers package's import graph.
        from scripts.system_healthcheck import run_healthcheck as _run_healthcheck
        result = _run_healthcheck(profile)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Healthcheck failed: {e}",
        )


# ── GET /api/system/healthcheck/{section} ──

@router.get("/api/system/healthcheck/{section}")
async def system_healthcheck_section(section: str):
    """Run a single section of Machine Profile healthchecks.

    Valid sections: profile, paths, binaries, ports, secrets, tmux, ollama, providers
    """
    try:
        profile = config.get_machine_profile()
        from scripts.system_healthcheck import run_healthcheck as _run_healthcheck
        result = _run_healthcheck(profile, section=section)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Healthcheck failed: {e}",
        )


