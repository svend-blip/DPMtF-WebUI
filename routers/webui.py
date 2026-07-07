"""WebUI Factory router (migration targets, skeletons, create-webui).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (4 total):
  GET    /api/webui-migration-targets
  GET    /api/webui-project-skeletons
  POST   /api/create-webui/initialize
  POST   /api/create-webui/start

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1).
"""

import logging
import os
import sqlite3
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402


router = APIRouter(tags=["webui"])


logger = logging.getLogger(__name__)


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── GET /api/webui-migration-targets ──

@router.get("/api/webui-migration-targets")
async def get_webui_migration_targets():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get active migration targets ordered by target_id
    cursor.execute("""
        SELECT target_id, target_project_key, target_project_name,
               target_project_path, target_port, target_status,
               source_project_path, migration_strategy,
               related_adr_id, notes, is_active
        FROM webui_migration_targets
        WHERE is_active = 1
        ORDER BY target_id
    """)

    webui_migration_targets = []
    for row in cursor.fetchall():
        webui_migration_targets.append({
            "target_id": row[0],
            "target_project_key": row[1],
            "target_project_name": row[2],
            "target_project_path": row[3],
            "target_port": row[4],
            "target_status": row[5],
            "source_project_path": row[6],
            "migration_strategy": row[7],
            "related_adr_id": row[8],
            "notes": row[9],
            "is_active": bool(row[10]),
        })

    conn.close()
    return {"webui_migration_targets": webui_migration_targets}


# ── GET /api/webui-project-skeletons ──

@router.get("/api/webui-project-skeletons")
async def get_webui_project_skeletons():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get active skeleton records ordered by skeleton_id
    cursor.execute("""
        SELECT skeleton_id, target_project_key, target_project_path,
               target_port, skeleton_status, created_files_json,
               server_start_command, health_endpoint, notes, is_active
        FROM webui_project_skeletons
        WHERE is_active = 1
        ORDER BY skeleton_id
    """)

    webui_project_skeletons = []
    for row in cursor.fetchall():
        webui_project_skeletons.append({
            "skeleton_id": row[0],
            "target_project_key": row[1],
            "target_project_path": row[2],
            "target_port": row[3],
            "skeleton_status": row[4],
            "created_files_json": row[5],
            "server_start_command": row[6],
            "health_endpoint": row[7],
            "notes": row[8],
            "is_active": bool(row[9]),
        })

    conn.close()
    return {"webui_project_skeletons": webui_project_skeletons}


# ── POST /api/create-webui/initialize ──

@router.post("/api/create-webui/initialize")
async def create_webui_initialize(request: Request):
    """Run initialize_new_webui.py to create a new WebUI project.

    Body (JSON):
      name  — project name (lowercase, hyphenated, max 10 chars recommended)
      port  — port number (9132-9199)
      title — project title (displayed in page title and heading)
    """
    data = await request.json()

    # Validate required fields
    for field in ["name", "port", "title"]:
        if field not in data or not str(data[field]).strip():
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    name = str(data["name"]).strip()
    port = int(data["port"])
    title = str(data["title"]).strip()

    # Validate port range
    if port < 9132 or port > 9199:
        raise HTTPException(status_code=400, detail=f"Port must be in range 9132-9199")

    # Run initialize_new_webui.py
    script_path = Path(config.get_project_root()) / "scripts" / "initialize_new_webui.py"
    result = subprocess.run(
        ["python3", str(script_path), "--name", name, "--port", str(port), "--title", title],
        capture_output=True, text=True,
        cwd=config.get_project_root(),
        timeout=120,
    )

    if result.returncode != 0:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "detail": result.stderr or result.stdout or "Unknown error",
            },
        )

    project_dir = str(Path.home() / name)

    return {
        "success": True,
        "output": result.stdout,
        "project_dir": project_dir,
        "port": port,
    }


# ── POST /api/create-webui/start ──

@router.post("/api/create-webui/start")
async def create_webui_start(request: Request):
    """Start uvicorn for a newly created WebUI project.

    Body (JSON):
      project_dir — absolute path to the project directory
      port        — port number the project was initialized with
    """
    data = await request.json()

    for field in ["project_dir", "port"]:
        if field not in data or not str(data[field]).strip():
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    project_dir = str(data["project_dir"]).strip()
    port = int(data["port"])

    # Verify project directory exists
    if not Path(project_dir).exists():
        raise HTTPException(status_code=400, detail=f"Project directory not found: {project_dir}")

    # Verify uvicorn exists
    uvicorn_path = Path(project_dir) / ".venv" / "bin" / "uvicorn"
    if not uvicorn_path.exists():
        raise HTTPException(status_code=400, detail=f"uvicorn not found at {uvicorn_path}")

    # Start uvicorn as detached background process
    subprocess.Popen(
        [str(uvicorn_path), "app:app", "--host", "0.0.0.0", "--port", str(port)],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    url = f"http://localhost:{port}/"

    return {
        "success": True,
        "url": url,
        "message": f"Server started on port {port}",
    }


