"""Sessions router (Claude Code sessions, workflow runs, comparison runs).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (7 total):
  GET    /api/sessions
  GET    /api/sessions/current
  POST   /api/sessions
  PUT    /api/sessions/{session_id}
  PUT    /api/workflow/{run_id}/status
  GET    /api/workflow/runs
  GET    /api/comparison-runs

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1).
DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1).
"""

import logging
import sqlite3
import uuid

from fastapi import APIRouter, HTTPException, Request

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402


router = APIRouter(tags=["sessions"])


logger = logging.getLogger(__name__)


# ── Module-level helpers (moved verbatim from app.py) ────────────────


# ── Endpoints (moved verbatim from app.py) ────────────────


@router.get("/api/sessions")
async def get_sessions(limit: int = 20):
    """List recent Claude Code sessions."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM claude_sessions
        ORDER BY started_at DESC LIMIT ?
    """, (limit,))
    sessions = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"sessions": sessions}


@router.get("/api/sessions/current")
async def get_current_session():
    """Return the currently active Claude Code session, if any."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM claude_sessions
        WHERE status = 'active'
        ORDER BY started_at DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        return {"active": True, "session": dict(row)}
    return {"active": False, "session": None}


@router.post("/api/sessions")
async def create_session(request: Request):
    """Record a new Claude Code session (started manually by Svend).

    Body (JSON):
      model_used      — model name (e.g. 'qwen36-27b-q4km:latest')
      project_context — which project is being worked on
      notes           — optional notes
    """
    data = await request.json()
    import uuid

    session_id = f"CS-{uuid.uuid4().hex[:8].upper()}"

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO claude_sessions
        (session_id, model_used, project_context, status, notes)
        VALUES (?, ?, ?, 'active', ?)
    """, (
        session_id,
        data.get("model_used"),
        data.get("project_context"),
        data.get("notes"),
    ))
    conn.commit()
    conn.close()

    return {"status": "recorded", "session_id": session_id}


@router.put("/api/sessions/{session_id}")
async def update_session(session_id: str, request: Request):
    """Update a session (stop, update activity timestamp, add notes).

    Body (JSON):
      status   — 'active', 'idle', or 'stopped'
      notes    — optional notes to append
    """
    data = await request.json()

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute("""
        SELECT session_id FROM claude_sessions WHERE session_id = ?
    """, (session_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    if "status" in data:
        cursor.execute("""
            UPDATE claude_sessions SET
                status = ?,
                last_activity_at = CURRENT_TIMESTAMP,
                ended_at = CASE WHEN ? = 'stopped' THEN CURRENT_TIMESTAMP ELSE ended_at END
            WHERE session_id = ?
        """, (data["status"], data["status"], session_id))
    else:
        cursor.execute("""
            UPDATE claude_sessions SET
                last_activity_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        """, (session_id,))

    if "notes" in data and data["notes"]:
        cursor.execute("""
            UPDATE claude_sessions SET
                notes = COALESCE(notes, '') || ? || '; '
            WHERE session_id = ?
        """, (data["notes"], session_id))

    conn.commit()
    conn.close()

    return {"status": "updated", "session_id": session_id}


@router.put("/api/workflow/{run_id}/status")
async def update_workflow_status(run_id: str, request: Request):
    """Update workflow run status as it progresses through the loop.

    Body (JSON):
      status            — 'implementing', 'validating', 'done', 'failed'
      validation_run_id — validation run ID (when status='validating')
      hitrate_run_id    — prompt run ID (when status='done')
      notes             — optional notes
    """
    data = await request.json()
    if "status" not in data:
        raise HTTPException(status_code=400, detail="Missing status")

    valid_statuses = ["prompt_compiled", "implementing", "validating", "done", "failed"]
    if data["status"] not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute("SELECT run_id FROM workflow_runs WHERE run_id = ?", (run_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Workflow run not found")

    updates = ["status = ?"]
    params = [data["status"]]

    if data.get("validation_run_id"):
        updates.append("validation_run_id = ?")
        params.append(data["validation_run_id"])
    if data.get("hitrate_run_id"):
        updates.append("hitrate_run_id = ?")
        params.append(data["hitrate_run_id"])
    if data.get("notes"):
        updates.append("notes = COALESCE(notes, '') || ? || '; '")
        params.append(data["notes"])
    if data["status"] in ("done", "failed"):
        updates.append("completed_at = CURRENT_TIMESTAMP")

    params.append(run_id)
    cursor.execute(
        f"UPDATE workflow_runs SET {', '.join(updates)} WHERE run_id = ?",
        params,
    )
    conn.commit()
    conn.close()

    return {"status": "updated", "run_id": run_id, "new_status": data["status"]}


@router.get("/api/workflow/runs")
async def get_workflow_runs(limit: int = 20):
    """List recent workflow runs with status."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM workflow_runs
        ORDER BY started_at DESC LIMIT ?
    """, (limit,))
    runs = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"runs": runs}


@router.get("/api/comparison-runs")
async def get_comparison_runs(
    complexity_tier: int | None = None,
    winner: str | None = None,
    task_type: str | None = None,
    limit: int = 20
):
    """List comparison runs with optional filters."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM comparison_runs WHERE 1=1"
    params = []

    if complexity_tier is not None:
        query += " AND complexity_tier = ?"
        params.append(complexity_tier)
    if winner is not None:
        query += " AND winner = ?"
        params.append(winner)
    if task_type is not None:
        query += " AND task_type = ?"
        params.append(task_type)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    comparisons = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"comparisons": comparisons}


