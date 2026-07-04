"""Git router (git operations + phase sync from git).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (4 total):
  POST   /api/phases/sync-from-git
  GET    /api/git/status
  POST   /api/git/operations
  GET    /api/git/operations

The `_advance_phase_on_push` helper function (used by sync-from-git
and POST git/operations) was moved here from app.py.

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1).
"""

import logging
import os
import sqlite3
import subprocess

from fastapi import APIRouter, HTTPException, Request

from routers.shared import get_db_path


router = APIRouter(tags=["git"])


logger = logging.getLogger(__name__)


# ── Module-level helpers (moved verbatim from app.py) ────────────────


def _advance_phase_on_push(cursor):
    """Advance phase status when a successful push occurs.

    Moves all 'next' phases to 'completed', and promotes the first
    'planned' phase (by sort_order) to 'next'.

    Uses the caller's cursor — caller is responsible for commit/close.
    """
    # Find all current 'next' phases
    cursor.execute(
        "SELECT phase_key FROM phase_status WHERE phase_state = 'next'"
    )
    next_phases = [row[0] for row in cursor.fetchall()]

    # Mark them as completed
    for phase_key in next_phases:
        cursor.execute(
            "UPDATE phase_status SET phase_state = 'completed',"
            " updated_at = datetime('now') WHERE phase_key = ?",
            (phase_key,),
        )

    # Find first planned phase and promote to next
    cursor.execute(
        "SELECT phase_key FROM phase_status WHERE phase_state = 'planned'"
        " ORDER BY sort_order LIMIT 1"
    )
    first_planned = cursor.fetchone()
    if first_planned:
        cursor.execute(
            "UPDATE phase_status SET phase_state = 'next',"
            " updated_at = datetime('now') WHERE phase_key = ?",
            (first_planned[0],),
        )

    return {
        "advanced": next_phases,
        "new_next": [first_planned[0]] if first_planned else [],
    }


# ── Endpoints (moved verbatim from app.py) ────────────────


@router.post("/api/phases/sync-from-git")
async def sync_phases_from_git():
    """Manually sync phase status based on git sync state.

    Checks git_sync_status for all projects. If all tracked projects
    have unpushed_commits = 0 and last_push_success = 1, advances phases.
    Otherwise returns current state without changes.

    Returns what was advanced (if anything).
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check git sync status
    cursor.execute("SELECT * FROM git_sync_status")
    projects = [dict(r) for r in cursor.fetchall()]

    # Determine if we should advance
    can_advance = len(projects) > 0
    for p in projects:
        if p.get("unpushed_commits", 0) > 0 or not p.get("last_push_success"):
            can_advance = False
            break

    if not can_advance:
        conn.close()
        return {
            "advanced": [],
            "new_next": [],
            "unchanged": [],
            "reason": "Unpushed commits exist or no successful push recorded.",
        }

    # Use the same cursor for phase advancement (avoid DB lock)
    result = _advance_phase_on_push(cursor)

    # Get remaining planned phases
    cursor.execute(
        "SELECT phase_key FROM phase_status WHERE phase_state = 'planned'"
        " ORDER BY sort_order"
    )
    unchanged = [row[0] for row in cursor.fetchall()]
    conn.close()

    return {
        "advanced": result["advanced"],
        "new_next": result["new_next"],
        "unchanged": unchanged,
    }


@router.get("/api/git/status")
async def get_git_status(project_key: str | None = None):
    """Return git sync status for tracked projects.

    If project_key is provided, returns status for that project only.
    Otherwise returns all tracked projects.

    This is a read-only status check. It does NOT perform git operations.
    Actual commit/push remain manual (Claude Code or Svend).
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if project_key:
        cursor.execute("""
            SELECT * FROM git_sync_status WHERE project_key = ?
        """, (project_key,))
    else:
        cursor.execute("""
            SELECT * FROM git_sync_status ORDER BY project_key
        """)
    rows = cursor.fetchall()
    statuses = [dict(r) for r in rows]

    # Enrich with live git info if project path exists
    import subprocess
    import os
    for s in statuses:
        path = s.get("project_path", "")
        if os.path.isdir(os.path.join(path, ".git")):
            try:
                # Count unpushed commits
                proc = subprocess.run(
                    ["git", "-C", path, "log", "origin/master..master", "--oneline"],
                    capture_output=True, text=True, timeout=5,
                )
                commits = [l for l in proc.stdout.strip().split("\n") if l]
                s["unpushed_commits"] = len(commits)
                s["unpushed_list"] = commits[:10]

                # Last commit
                proc = subprocess.run(
                    ["git", "-C", path, "log", "-1", "--format=%h %s"],
                    capture_output=True, text=True, timeout=5,
                )
                s["last_commit"] = proc.stdout.strip()

                # Branch
                proc = subprocess.run(
                    ["git", "-C", path, "branch", "--show-current"],
                    capture_output=True, text=True, timeout=5,
                )
                s["branch"] = proc.stdout.strip()
            except Exception:
                pass

    conn.close()
    return {"projects": statuses}


@router.post("/api/git/operations")
async def record_git_operation(request: Request):
    """Record a git operation that happened externally.

    This does NOT perform git operations — it only records them.
    Actual commit/push are done manually by Claude Code or Svend.

    Body (JSON):
      project_key    — which project (required)
      operation_type — 'commit' or 'push' (required)
      details        — commit message or push summary
      success        — 1 = success, 0 = failure (default 1)
      error_log      — error output if failed
      operator       — who performed the operation
    """
    data = await request.json()
    required = ["project_key", "operation_type"]
    for field in required:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    import uuid
    op_id = f"GITOP-{uuid.uuid4().hex[:8].upper()}"

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO git_operations
        (operation_id, project_key, operation_type, details,
         success, error_log, operator)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        op_id,
        data["project_key"],
        data["operation_type"],
        data.get("details"),
        data.get("success", 1),
        data.get("error_log"),
        data.get("operator", "Claude Code"),
    ))

    phase_result = None
    if data["operation_type"] == "push" and data.get("success", 1):
        # Update sync status
        cursor.execute("""
            INSERT INTO git_sync_status
            (project_key, project_path, branch, unpushed_commits,
             last_push_timestamp, last_push_success)
            VALUES (?, ?, 'master', 0, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(project_key) DO UPDATE SET
                unpushed_commits = 0,
                last_push_timestamp = CURRENT_TIMESTAMP,
                last_push_success = 1,
                updated_at = CURRENT_TIMESTAMP
        """, (data["project_key"], data.get("project_path", "")))

        # Advance phase status on successful push
        phase_result = _advance_phase_on_push(cursor)

    conn.commit()
    conn.close()

    result = {"status": "recorded", "operation_id": op_id}
    if phase_result is not None:
        result["phases_advanced"] = phase_result
    return result


@router.get("/api/git/operations")
async def get_git_operations(limit: int = 20):
    """Return recent git operations."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM git_operations
        ORDER BY operation_timestamp DESC LIMIT ?
    """, (limit,))
    ops = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"operations": ops}


