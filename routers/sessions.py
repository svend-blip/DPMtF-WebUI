"""Sessions router (Claude Code sessions, workflow runs, comparison runs).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (8 total):
  GET    /api/sessions
  GET    /api/sessions/current
  POST   /api/sessions
  PUT    /api/sessions/{session_id}
  POST   /api/workflow/start
  PUT    /api/workflow/{run_id}/status
  GET    /api/workflow/runs
  GET    /api/comparison-runs

The `_compile_prompt_internal` helper function (used by
/api/workflow/start) was moved here from app.py.

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


def _compile_prompt_internal(
    template_key: str,
    project_path: str,
    phase_id: str,
    params: dict,
) -> str:
    """Compile a prompt from a template without making HTTP calls.

    Uses governance-v2 XML format, same as compile_prompt() above.
    Maps legacy parameters to new field names.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM prompt_templates
        WHERE template_key = ? AND is_active = 1
    """, (template_key,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return f"Error: Template '{template_key}' not found"
    template = dict(row)

    # Load compiler fields for reference
    cursor.execute("""
        SELECT * FROM prompt_compiler_fields
        WHERE is_active = 1
        ORDER BY section, sort_order
    """)
    cursor.fetchall()
    conn.close()

    # Map legacy params to governance-v2 field names
    goal = params.get("goal", phase_id)
    constraints = params.get("constraints", [])
    if isinstance(constraints, str):
        constraints = [c.strip() for c in constraints.split("\n") if c.strip()]

    allowed_files = params.get("allowed_files", [])
    if isinstance(allowed_files, str):
        allowed_files = [f.strip() for f in allowed_files.split("\n")
                        if f.strip()]

    validation_commands = params.get("validation_commands", [])
    if isinstance(validation_commands, str):
        validation_commands = (
            [c.strip() for c in validation_commands.split("\n")
             if c.strip()]
        )

    handoff_id = params.get("handoff_id", "???")
    father_project = params.get("father_project", "DPMtF-WebUI")
    is_migration = params.get("is_migration", False)
    target_session = params.get("target_session", "claude_implementer")

    # Derive role from session name
    if "implementer" in target_session.lower():
        governance_role_file = "03_IMPLEMENTOR.md"
        role_name = "Implementor"
    elif "architect" in target_session.lower():
        governance_role_file = "02_ARCHITECT.md"
        role_name = "Architect"
    elif "review" in target_session.lower():
        governance_role_file = "04_REVIEW.md"
        role_name = "Review"
    else:
        governance_role_file = "03_IMPLEMENTOR.md"
        role_name = "Implementor"

    # ── Generate XML output (same structure as compile_prompt) ──
    lines = []
    lines.append(
        f"<role>You are {role_name} in the DPMtF governance loop. "
        "Your role is defined"
    )
    lines.append(
        f"in {config.get_project_root()}"
        f"/{config.get_governance_dir()}/{governance_role_file}."
    )
    lines.append("Read it now before proceeding.</role>")
    lines.append("")
    lines.append(f"<handoff_id>{handoff_id}</handoff_id>")
    lines.append("")
    lines.append(f"<project>{project_path}</project>")
    lines.append("")
    lines.append("<context>")
    lines.append(f"Human has approved scope for phase {phase_id}.")
    lines.append(
        f"Scope is defined in "
        f"{project_path}/docs/dpmtf/11_SCOPE.md."
    )
    lines.append("Father project: " + father_project + ".")
    lines.append("</context>")
    lines.append("")
    lines.append("<governance>")
    lines.append("Read and apply these governance files BEFORE starting:")
    lines.append(
        f"- {config.get_project_root()}"
        f"/{config.get_governance_dir()}/12_CODING_STANDARD.md"
    )
    lines.append(
        f"- {config.get_project_root()}"
        f"/{config.get_governance_dir()}/16_FILE_ACCESS.md"
    )
    lines.append("")
    lines.append("Key rules extracted:")
    for c in constraints[:4]:
        lines.append(f"- {c}")
    if not constraints:
        lines.append(
            "- NO innerHTML for dynamic content "
            "— use createElement()/textContent."
        )
        lines.append(
            "- ALL user-facing text MUST use lbl(key, fallback)."
        )
        lines.append(
            "- Python: py_compile before signaling completion, "
            "parameterized SQL."
        )
        lines.append("- DO NOT COMMIT.")
    lines.append("</governance>")
    lines.append("")
    lines.append("<task>")
    lines.append(goal)
    lines.append("")
    lines.append("Execute the implementation as described above.")
    lines.append("")
    lines.append(
        "When ALL steps are complete, execute the bridge signal:"
    )
    lines.append("")
    lines.append(f"1. Write result file to "
                 f"{config.get_bridge_dir()}/implementertoreview/"
                 f"{handoff_id}-result.md")
    lines.append("</task>")
    lines.append("")
    lines.append("<scope>")
    lines.append("Files you MAY modify:")
    for fa in allowed_files:
        lines.append(f"- {fa}")
    if not allowed_files:
        lines.append("- (none specified — Review should verify)")
    lines.append("</scope>")
    lines.append("")
    lines.append("<validation>")
    for i, cmd in enumerate(validation_commands, 1):
        lines.append(f"{i}. {cmd}")
    if not validation_commands:
        lines.append("1. python3 -m py_compile app.py — must pass")
        lines.append(
            "2. node --check static/js/*.js — must pass for each"
            " modified file"
        )
    lines.append("</validation>")
    lines.append("")
    lines.append("<constraint>")
    lines.append("DO NOT COMMIT. Leave all changes unstaged.")
    lines.append(f"Target session: {target_session} (role: {role_name}).")
    if screenshot_required:
        lines.append(
            "CAPTURE SCREENSHOT before signaling completion."
        )
    lines.append("</constraint>")

    return "\n".join(lines)


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


@router.post("/api/workflow/start")
async def start_workflow(request: Request):
    """Compile a prompt and start a workflow run through the P→I→V loop.

    Body (JSON):
      phase_key       — phase to execute (required)
      target_project  — project path (required)
      template_key    — template to use (default: tpl_implementation_small)
      params          — template parameters (goal, constraints, etc.)
      session_id      — Claude Code session ID (optional)
    """
    data = await request.json()
    required = ["phase_key", "target_project"]
    for field in required:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    template_key = data.get("template_key", "tpl_implementation_small")
    params = data.get("params", {})

    # Compile prompt directly (avoid HTTP call to self)
    prompt_text = _compile_prompt_internal(
        template_key,
        data["target_project"],
        data["phase_key"],
        params,
    )

    # Create workflow run
    import uuid
    run_id = f"WF-{uuid.uuid4().hex[:8].upper()}"

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workflow_runs
        (run_id, phase_key, target_project, template_key,
         prompt_text, session_id, status)
        VALUES (?, ?, ?, ?, ?, ?, 'prompt_compiled')
    """, (
        run_id,
        data["phase_key"],
        data["target_project"],
        template_key,
        prompt_text,
        data.get("session_id"),
    ))
    conn.commit()
    conn.close()

    return {
        "status": "prompt_compiled",
        "run_id": run_id,
        "phase_key": data["phase_key"],
        "prompt": prompt_text,
        "next_step": "Copy prompt to Claude Code session → implement → validate → update status",
    }


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


