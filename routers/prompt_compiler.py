"""Prompt Compiler router (Phase 2F/2H/2I/2I-v2 + Prompt Sequences + UI labels).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` -> `@router.X`).

Endpoints moved:
  GET    /api/prompt-sequences
  POST   /api/prompt-sequences
  GET    /api/prompt-sequences/{sequence_id}/steps
  POST   /api/prompt-sequences/{sequence_id}/steps
  POST   /api/prompt-sequences/{sequence_id}/steps/{step_id}/status
  GET    /api/prompt-sequences/{sequence_id}/next-prompt
  GET    /api/prompt-sequences/{sequence_id}/generated-prompts
  POST   /api/prompt-sequences/{sequence_id}/steps/{step_id}/generated-prompts
  GET    /api/generated-prompts
  POST   /api/app-profiles/{profile_id}/draft-prompt-sequence
  GET    /api/ui-label-registry
  GET    /api/ui-labels/{label_domain}
  GET    /api/prompt-runs
  POST   /api/prompt-runs
  GET    /api/prompt-hirates
  GET    /api/implementation-patterns
  GET    /api/implementation-patterns/{pattern_id}/runs
  GET    /api/prompt-templates
  POST   /api/prompt-templates
  GET    /api/prompt-templates/{template_key}
  PUT    /api/prompt-templates/{template_key}
  GET    /api/prompt-compiler-fields
  POST   /api/prompt-compiler-fields
  POST   /api/prompt-compiler-field-options
  POST   /api/prompt-compiler/compile
  POST   /api/prompt-compiler/assign-handoff-id
  POST   /api/prompt-compiler/dispatch
  GET    /api/prompt-templates/{template_key}/hitrate

The prompt_compiler endpoints use module-level helpers that lived in
app.py at lines 81 (_resolve_ui_label_text), 159 (get_ui_labels_for_domain),
2421 (_load_knowledge_fragment), 1887 (_next_pattern_id), and 1898
(_update_pattern_hitrate). These helpers were used ONLY by prompt_compiler
endpoints (verified via grep — no other usage in app.py) and have
been moved here.

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1) — this preserves the test fixture's monkeypatch
of `app.DB_PATH` and avoids circular imports at module top-level.

A few compile/assign-handoff-id/dispatch endpoints depend on the
BridgeV002 DB helpers (load_flow_from_db, load_role_from_db,
get_next_id_for_flow, build_step_payload) — these are imported via
the same sys.path insert + bridge_lib import pattern as in app.py.
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

# Ensure scripts/bridgeV002/ is on sys.path so the bridge_lib imports
# below resolve. Mirrors app.py.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "bridgeV002"))

from bridge_lib import (  # noqa: E402
    get_next_id_for_flow,
    load_flow_from_db,
    load_role_from_db,
)
from dispatch import build_step_payload  # noqa: E402

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402


router = APIRouter(tags=["prompt_compiler"])


logger = logging.getLogger(__name__)


# ── Module-level helpers (moved verbatim from app.py) ────────────────


def _resolve_ui_label_text(label_row, locale):
    """Resolve translated text for a single ui_label row with fallback chain."""
    label_key = label_row["label_key"]
    default_text = label_row["default_text"]
    translations = label_row.get("translations") or {}
    if locale in translations:
        return translations[locale]
    if "en-US" in translations:
        return translations["en-US"]
    if default_text:
        return default_text
    return label_key


def get_ui_labels_for_domain(label_domain: str, locale: str = "en-US") -> dict:
    """Resolve labels for a domain via the full 4-layer i18n architecture."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.slot_key, l.label_key, l.default_text,
               COALESCE(t_en.translated_text, l.default_text, l.label_key) AS text_en,
               COALESCE(t_req.translated_text, t_en.translated_text, l.default_text, l.label_key) AS text_req
        FROM ui_text_slots s
        JOIN ui_text_slot_labels sl ON s.slot_key = sl.slot_key
        JOIN ui_labels l ON sl.label_key = l.label_key
        LEFT JOIN ui_label_translations t_en ON l.label_id = t_en.label_id AND t_en.locale = 'en-US'
        LEFT JOIN ui_label_translations t_req ON l.label_id = t_req.label_id AND t_req.locale = ?
        WHERE l.label_domain = ?
    """, (locale, label_domain))

    labels = {}
    for row in cursor.fetchall():
        r = dict(row)
        labels[r["slot_key"]] = r["text_req"] if r["text_req"] else r["text_en"]

    conn.close()
    return labels


def _next_pattern_id(cursor) -> str:
    """Generate the next pattern ID in sequence PAT-0001, PAT-0002, ..."""
    cursor.execute("SELECT MAX(pattern_id) FROM implementation_patterns")
    row = cursor.fetchone()
    if row and row[0]:
        num = int(row[0].split("-")[1]) + 1
    else:
        num = 1
    return f"PAT-{num:04d}"


def _update_pattern_hitrate(cursor, pattern_id: str, data: dict) -> None:
    """Update hitrate aggregate and best_model for a pattern."""
    success = data["success"]
    duration = data.get("duration_seconds")
    idle = data.get("idle_seconds")
    model = data.get("model_used") or data.get("model_type")

    cursor.execute("""
        UPDATE implementation_patterns SET
            total_runs = total_runs + 1,
            successful_runs = successful_runs + ?,
            rolling_success_rate = CAST(successful_runs + ? AS REAL) / (total_runs + 1),
            avg_duration_seconds = CASE
                WHEN ? IS NOT NULL THEN
                    CAST((avg_duration_seconds * total_runs + ?) AS REAL) / (total_runs + 1)
                ELSE avg_duration_seconds END,
            avg_idle_seconds = CASE
                WHEN ? IS NOT NULL THEN
                    CAST((avg_idle_seconds * total_runs + ?) AS REAL) / (total_runs + 1)
                ELSE avg_idle_seconds END,
            last_used_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE pattern_id = ?
    """, (
        success, success,
        duration, duration,
        idle, idle,
        pattern_id,
    ))

    if model:
        cursor.execute("""
            UPDATE implementation_patterns SET best_model = (
                SELECT model_used FROM prompt_runs
                WHERE pattern_id = ? AND success = 1
                GROUP BY model_used
                ORDER BY COUNT(*) DESC
                LIMIT 1
            )
            WHERE pattern_id = ?
        """, (pattern_id, pattern_id))


def _load_knowledge_fragment(filename):
    """Load a knowledge fragment file and return cleaned content."""
    frag_dir = os.path.join(
        config.get_project_root(),
        config.get_governance_dir(),
        "knowledge-fragments"
    )
    filepath = os.path.join(frag_dir, filename)
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.split("\n")
    cleaned = [line for line in lines if not line.startswith("> **")]
    result = "\n".join(cleaned)
    result = result.lstrip("\n")

    lines = result.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            lines.pop(i)
            if i < len(lines) and lines[i].strip() == "":
                lines.pop(i)
            break

    result = "\n".join(lines)
    result = result.replace("{{project_root}}", config.get_project_root())
    return result


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── prompt_sequences_get_list ──

@router.get("/api/prompt-sequences")
async def get_prompt_sequences():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, goal, status, created_at, updated_at
        FROM prompt_sequences
        ORDER BY created_at DESC
    """)

    sequences = []
    for row in cursor.fetchall():
        sequences.append({
            "id": row[0],
            "name": row[1],
            "goal": row[2],
            "status": row[3],
            "created_at": row[4],
            "updated_at": row[5]
        })

    # Get counts
    cursor.execute("SELECT COUNT(*) FROM prompt_sequences")
    sequence_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM prompt_sequence_steps")
    total_step_count = cursor.fetchone()[0]

    conn.close()
    return {"sequences": sequences, "sequence_count": sequence_count, "total_step_count": total_step_count}

# ── prompt_sequences_post_create ──

@router.post("/api/prompt-sequences")
async def create_prompt_sequence(sequence_data: dict):
    # Validate required fields
    name = sequence_data.get("name")
    if not name or name.strip() == "":
        raise HTTPException(status_code=400, detail="Name is required")

    goal = sequence_data.get("goal", "")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Insert new sequence
    cursor.execute("""
        INSERT INTO prompt_sequences (name, goal, status)
        VALUES (?, ?, 'planned')
    """, (name, goal))

    sequence_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "sequence_id": sequence_id,
        "name": name,
        "goal": goal
    }

# ── prompt_sequences_steps_get ──

@router.get("/api/prompt-sequences/{sequence_id}/steps")
async def get_prompt_sequence_steps(sequence_id: int):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if sequence exists
    cursor.execute("SELECT id FROM prompt_sequences WHERE id = ?", (sequence_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Sequence not found")

    cursor.execute("""
        SELECT id, step_number, step_title, target_layer, status, prompt_text, result_note, created_at, updated_at
        FROM prompt_sequence_steps
        WHERE sequence_id = ?
        ORDER BY step_number ASC
    """, (sequence_id,))

    steps = []
    for row in cursor.fetchall():
        steps.append({
            "id": row[0],
            "step_number": row[1],
            "step_title": row[2],
            "target_layer": row[3],
            "status": row[4],
            "prompt_text": row[5],
            "result_note": row[6],
            "created_at": row[7],
            "updated_at": row[8]
        })

    conn.close()
    return {"steps": steps}

# ── prompt_sequences_steps_post ──

@router.post("/api/prompt-sequences/{sequence_id}/steps")
async def create_prompt_sequence_step(sequence_id: int, step_data: dict):
    # Validate required fields
    step_title = step_data.get("step_title")
    if not step_title or step_title.strip() == "":
        raise HTTPException(status_code=400, detail="Step title is required")

    target_layer = step_data.get("target_layer")
    allowed_layers = ["skeleton", "database", "frontend", "css", "backend", "config", "tests", "docs", "verification", "other"]
    if not target_layer or target_layer not in allowed_layers:
        raise HTTPException(status_code=400, detail=f"Invalid target layer. Must be one of: {', '.join(allowed_layers)}")

    prompt_text = step_data.get("prompt_text", "")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if sequence exists
    cursor.execute("SELECT id FROM prompt_sequences WHERE id = ?", (sequence_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Get the next step number
    cursor.execute("SELECT COALESCE(MAX(step_number), 0) + 1 FROM prompt_sequence_steps WHERE sequence_id = ?", (sequence_id,))
    step_number = cursor.fetchone()[0]

    # Insert new step
    cursor.execute("""
        INSERT INTO prompt_sequence_steps (sequence_id, step_number, step_title, target_layer, status, prompt_text)
        VALUES (?, ?, ?, ?, 'planned', ?)
    """, (sequence_id, step_number, step_title, target_layer, prompt_text))

    step_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "step_id": step_id,
        "sequence_id": sequence_id,
        "step_title": step_title,
        "target_layer": target_layer,
        "prompt_text": prompt_text
    }

# ── prompt_sequences_step_status ──

@router.post("/api/prompt-sequences/{sequence_id}/steps/{step_id}/status")
async def update_prompt_sequence_step_status(sequence_id: int, step_id: int, status_data: dict):
    # Validate required fields
    status = status_data.get("status")
    allowed_statuses = ["planned", "generated", "implemented", "failed", "skipped"]
    if not status or status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}")

    result_note = status_data.get("result_note", "")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if sequence exists
    cursor.execute("SELECT id FROM prompt_sequences WHERE id = ?", (sequence_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Check if step exists and belongs to sequence
    cursor.execute("""
        SELECT id FROM prompt_sequence_steps
        WHERE id = ? AND sequence_id = ?
    """, (step_id, sequence_id))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Step not found or does not belong to sequence")

    # Update step status and result_note
    cursor.execute("""
        UPDATE prompt_sequence_steps
        SET status = ?, result_note = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, result_note, step_id))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "sequence_id": sequence_id,
        "step_id": step_id,
        "step_status": status,
        "result_note": result_note
    }

# ── prompt_sequences_next_prompt ──

@router.get("/api/prompt-sequences/{sequence_id}/next-prompt")
async def get_next_prompt_preview(sequence_id: int):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if sequence exists
    cursor.execute("SELECT id, name FROM prompt_sequences WHERE id = ?", (sequence_id,))
    sequence = cursor.fetchone()
    if not sequence:
        conn.close()
        raise HTTPException(status_code=404, detail="Sequence not found")

    sequence_name = sequence[1]

    # Find the first planned step for this sequence ordered by step_number
    cursor.execute("""
        SELECT id, step_number, step_title, target_layer, prompt_text
        FROM prompt_sequence_steps
        WHERE sequence_id = ? AND status = 'planned'
        ORDER BY step_number ASC
        LIMIT 1
    """, (sequence_id,))

    step = cursor.fetchone()
    conn.close()

    if not step:
        return {
            "status": "no_planned_steps"
        }

    step_id, step_number, step_title, target_layer, prompt_text = step

    # Generate the prompt preview
    generated_prompt = f"""Project path: {config.get_project_root()}

Sequence: {sequence_name}
Step #{step_number}: {step_title}
Target Layer: {target_layer}

Instructions:
Implement only this step.
Do not expand scope.
Do not execute unrelated changes.
Use targeted Edit/MultiEdit for existing files.
Write only for new files.
No heredocs.
Stop after verification.

Step prompt text:
{prompt_text}"""

    return {
        "status": "success",
        "sequence_id": sequence_id,
        "step_id": step_id,
        "step_number": step_number,
        "step_title": step_title,
        "target_layer": target_layer,
        "generated_prompt": generated_prompt
    }

# ── prompt_sequences_generated_prompts_get ──

@router.get("/api/prompt-sequences/{sequence_id}/generated-prompts")
async def get_generated_prompts(sequence_id: int):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if sequence exists
    cursor.execute("SELECT id FROM prompt_sequences WHERE id = ?", (sequence_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Get generated prompts for this sequence
    cursor.execute("""
        SELECT gp.id, gp.sequence_step_id, gp.prompt_text, gp.generated_at,
               pss.step_number, pss.step_title, pss.target_layer
        FROM generated_prompts gp
        JOIN prompt_sequence_steps pss ON gp.sequence_step_id = pss.id
        WHERE pss.sequence_id = ?
        ORDER BY gp.generated_at DESC
    """, (sequence_id,))

    generated_prompts = []
    for row in cursor.fetchall():
        generated_prompts.append({
            "id": row[0],
            "sequence_step_id": row[1],
            "prompt_text": row[2],
            "generated_at": row[3],
            "step_number": row[4],
            "step_title": row[5],
            "target_layer": row[6]
        })

    conn.close()
    return {"generated_prompts": generated_prompts}

# ── prompt_sequences_generated_prompts_post ──

@router.post("/api/prompt-sequences/{sequence_id}/steps/{step_id}/generated-prompts")
async def save_generated_prompt(sequence_id: int, step_id: int, prompt_data: dict):
    # Validate required fields
    generated_prompt = prompt_data.get("generated_prompt")
    if not generated_prompt or generated_prompt.strip() == "":
        raise HTTPException(status_code=400, detail="Generated prompt is required")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if sequence exists
    cursor.execute("SELECT id FROM prompt_sequences WHERE id = ?", (sequence_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Check if step exists and belongs to sequence
    cursor.execute("""
        SELECT id FROM prompt_sequence_steps
        WHERE id = ? AND sequence_id = ?
    """, (step_id, sequence_id))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Step not found or does not belong to sequence")

    # Insert generated prompt
    cursor.execute("""
        INSERT INTO generated_prompts (sequence_step_id, prompt_text)
        VALUES (?, ?)
    """, (step_id, generated_prompt))

    generated_prompt_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "generated_prompt_id": generated_prompt_id,
        "sequence_id": sequence_id,
        "step_id": step_id
    }

# ── generated_prompts_get_all ──

@router.get("/api/generated-prompts")
async def get_all_generated_prompts():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get all generated prompts with sequence and step information
    cursor.execute("""
        SELECT gp.id, gp.sequence_step_id, gp.prompt_text, gp.generated_at,
               pss.sequence_id, ps.name, pss.step_number, pss.step_title, pss.target_layer
        FROM generated_prompts gp
        JOIN prompt_sequence_steps pss ON gp.sequence_step_id = pss.id
        JOIN prompt_sequences ps ON pss.sequence_id = ps.id
        ORDER BY gp.generated_at DESC
    """)

    generated_prompts = []
    for row in cursor.fetchall():
        generated_prompts.append({
            "id": row[0],
            "sequence_step_id": row[1],
            "prompt_text": row[2],
            "generated_at": row[3],
            "sequence_id": row[4],
            "sequence_name": row[5],
            "step_number": row[6],
            "step_title": row[7],
            "target_layer": row[8]
        })

    conn.close()
    return {"generated_prompts": generated_prompts}

# ── app_profiles_draft_prompt_sequence ──

@router.post("/api/app-profiles/{profile_id}/draft-prompt-sequence")
async def create_draft_prompt_sequence(profile_id: int):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if profile exists
    cursor.execute("SELECT id, name FROM app_profiles WHERE id = ?", (profile_id,))
    profile = cursor.fetchone()
    if not profile:
        conn.close()
        raise HTTPException(status_code=404, detail="App profile not found")

    profile_name = profile[1]

    # Get panels included in this profile
    cursor.execute("""
        SELECT fp.panel_key, fp.panel_title
        FROM frontend_panels fp
        JOIN app_profile_panels appp ON fp.id = appp.panel_id
        WHERE appp.profile_id = ?
        ORDER BY fp.sort_order
    """, (profile_id,))

    included_panels = cursor.fetchall()

    # Create new prompt sequence
    sequence_name = f"Draft from {profile_name}"
    sequence_goal = f"Create a new WebUI app draft from selected panels in {profile_name}."

    cursor.execute("""
        INSERT INTO prompt_sequences (name, goal, status)
        VALUES (?, ?, 'planned')
    """, (sequence_name, sequence_goal))

    sequence_id = cursor.lastrowid

    # Define draft steps
    draft_steps = [
        {
            "step_title": "Create project skeleton",
            "target_layer": "skeleton",
            "prompt_text": "Create only the basic FastAPI project skeleton for the new app. Do not implement panel functionality yet."
        },
        {
            "step_title": "Add selected frontend panel placeholders",
            "target_layer": "frontend",
            "prompt_text": f"Add static placeholder sections for the selected app profile panels. Do not implement backend actions yet. Included panels: {', '.join([f'{p[0]} ({p[1]})' for p in included_panels]) if included_panels else 'None'}"
        },
        {
            "step_title": "Add basic CSS layout",
            "target_layer": "css",
            "prompt_text": "Add minimal CSS layout for the selected panels. Do not redesign beyond the selected structure."
        },
        {
            "step_title": "Add health endpoint",
            "target_layer": "backend",
            "prompt_text": "Add a simple /api/health endpoint for the new app."
        },
        {
            "step_title": "Add basic verification",
            "target_layer": "tests",
            "prompt_text": "Add basic verification commands or tests for app startup and health endpoint."
        },
        {
            "step_title": "Update project documentation",
            "target_layer": "docs",
            "prompt_text": "Update README or project documentation with install, start, and verification commands."
        }
    ]

    # Create steps for the sequence
    created_steps_count = 0
    for i, step in enumerate(draft_steps):
        step_number = i + 1
        cursor.execute("""
            INSERT INTO prompt_sequence_steps (sequence_id, step_number, step_title, target_layer, status, prompt_text)
            VALUES (?, ?, ?, ?, 'planned', ?)
        """, (sequence_id, step_number, step["step_title"], step["target_layer"], step["prompt_text"]))
        created_steps_count += 1

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "profile_id": profile_id,
        "sequence_id": sequence_id,
        "created_steps_count": created_steps_count
    }

# ── ui_label_registry_get ──

@router.get("/api/ui-label-registry")
async def get_ui_label_registry():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get all active ui_labels ordered by label_id
    cursor.execute("""
        SELECT label_id, label_key, label_domain, default_text, description, is_active, created_at, updated_at
        FROM ui_labels
        ORDER BY label_id
    """)

    ui_labels = []
    for row in cursor.fetchall():
        ui_labels.append({
            "label_id": row[0],
            "label_key": row[1],
            "label_domain": row[2],
            "default_text": row[3],
            "description": row[4],
            "is_active": bool(row[5]),
            "created_at": row[6],
            "updated_at": row[7]
        })

    # Get all active ui_label_translations ordered by label_id, locale
    cursor.execute("""
        SELECT label_id, locale, translated_text, is_active, created_at, updated_at
        FROM ui_label_translations
        ORDER BY label_id, locale
    """)

    ui_label_translations = []
    for row in cursor.fetchall():
        ui_label_translations.append({
            "label_id": row[0],
            "locale": row[1],
            "translated_text": row[2],
            "is_active": bool(row[3]),
            "created_at": row[4],
            "updated_at": row[5]
        })

    conn.close()
    return {
        "ui_labels": ui_labels,
        "ui_label_translations": ui_label_translations
    }

# ── ui_labels_by_domain ──

@router.get("/api/ui-labels/{label_domain}")
async def get_ui_labels_by_domain(label_domain: str, locale: str = "en-US"):
    """Return resolved labels for a domain via the full 4-layer i18n architecture.

    Traverses ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations.
    Returns {slot_key: resolved_text} so frontend data-slot attributes and lbl() calls
    resolve correctly through the slot→label mapping table.

    Fallback chain: requested locale → en-US → default_text → label_key.
    """
    labels = get_ui_labels_for_domain(label_domain, locale)
    return {
        "label_domain": label_domain,
        "locale": locale,
        "labels": labels
    }

# ── prompt_runs_get ──

@router.get("/api/prompt-runs")
async def get_prompt_runs(
    phase_key: str | None = None,
    target_project: str | None = None,
    success: int | None = None,
    template_key: str | None = None,
    execution_status: str | None = None,
    first_try_success: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List prompt runs with optional filters.

    Query params:
      phase_key        — filter by phase (e.g. "2E", "3C-14")
      target_project   — filter by project path or name
      success          — 1 for successes, 0 for failures, omit for all
      template_key     — filter by template (e.g. "tpl_implementation_small")
      execution_status — filter by status: 'completed', 'failed', 'unknown', 'sent'
      first_try_success — 1 for first-try wins, 0 for failures, omit for all
      limit            — max rows (default 50)
      offset           — pagination offset (default 0)
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where: list[str] = []
    params: list = []

    if phase_key:
        where.append("phase_key = ?")
        params.append(phase_key)
    if target_project:
        where.append("target_project LIKE ?")
        params.append(f"%{target_project}%")
    if success is not None:
        where.append("success = ?")
        params.append(success)
    if template_key:
        where.append("template_key = ?")
        params.append(template_key)
    if execution_status:
        where.append("execution_status = ?")
        params.append(execution_status)
    if first_try_success is not None:
        where.append("first_try_success = ?")
        params.append(first_try_success)

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    params.extend([limit, offset])

    cursor.execute(
        f"SELECT * FROM prompt_runs{clause} "
        "ORDER BY run_timestamp DESC LIMIT ? OFFSET ?",
        params,
    )
    rows = cursor.fetchall()
    runs = [dict(r) for r in rows]

    # Total count (without limit/offset)
    count_params = params[:-2]
    cursor.execute(
        f"SELECT COUNT(*) FROM prompt_runs{clause}",
        count_params,
    )
    total = cursor.fetchone()[0]

    conn.close()
    return {"runs": runs, "total": total, "limit": limit, "offset": offset}

# ── prompt_runs_post ──

@router.post("/api/prompt-runs")
async def create_prompt_run(request: Request):
    """Record a new prompt run and update hitrate aggregates.

    Body (JSON):
      run_id              — unique run identifier (required)
      phase_key           — phase this run belongs to (required)
      target_project      — project the prompt targeted (required)
      prompt_summary      — brief description of the prompt
      success             — 1 = success, 0 = failure (required)
      execution_status    — 'completed', 'failed', 'unknown', 'sent' (required)
      first_try_success   — 0=no, 1=yes (required when execution_status='completed')
      validation_passed   — 0=no, 1=yes (required when execution_status='completed')
      manual_corrections  — number of corrective prompts (default 0)
      template_key        — FK to prompt_templates (optional)
      duration_seconds    — execution time in seconds
      error_summary       — error description if failed
      model_used          — model that executed the prompt
      model_type          — 'local' or 'cloud' (derived from model_used if omitted)
      idle_seconds        — wait time before model started
      token_count_input   — input tokens (cloud only)
      token_count_output  — output tokens (cloud only)
      token_cost_eur      — estimated EUR cost (cloud only)
      token_cost_dkk      — estimated DKK cost (cloud only)
      file_signature      — comma-separated changed files (for pattern matching)
      constraint_set      — comma-separated constraints (for pattern matching)
      notes               — optional human notes
    """
    data = await request.json()

    required = ["run_id", "phase_key", "target_project", "success", "execution_status"]
    for field in required:
        if field not in data:
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {field}"
            )

    # Validate execution_status
    execution_status = data["execution_status"]
    if execution_status not in ("completed", "failed", "unknown", "sent"):
        raise HTTPException(
            status_code=400,
            detail="execution_status must be 'completed', 'failed', 'unknown', or 'sent'",
        )

    # Mandatory outcome fields when status is 'completed'
    if execution_status == "completed":
        if "first_try_success" not in data or data["first_try_success"] is None:
            raise HTTPException(
                status_code=400,
                detail="first_try_success is required when execution_status='completed'",
            )
        if "validation_passed" not in data or data["validation_passed"] is None:
            raise HTTPException(
                status_code=400,
                detail="validation_passed is required when execution_status='completed'",
            )

    # Derive model_type from model_used if not explicit
    model_type = data.get("model_type")
    if not model_type and data.get("model_used"):
        model_type = "cloud" if ":cloud" in data["model_used"] else "local"

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # ── Pattern matching ──────────────────────────────────────────
    pattern_id = None
    file_sig = data.get("file_signature")
    constraint_set = data.get("constraint_set")

    if file_sig and constraint_set:
        # Find existing pattern
        cursor.execute("""
            SELECT pattern_id FROM implementation_patterns
            WHERE file_signature = ? AND constraint_set = ?
        """, (file_sig, constraint_set))
        row = cursor.fetchone()
        if row:
            pattern_id = row[0]
        else:
            # Create new pattern
            pattern_id = _next_pattern_id(cursor)
            cursor.execute("""
                INSERT INTO implementation_patterns
                (pattern_id, file_signature, constraint_set, phase_key,
                 total_runs, successful_runs, rolling_success_rate,
                 best_model, avg_duration_seconds, last_used_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                pattern_id,
                file_sig,
                constraint_set,
                data["phase_key"],
                data["success"],
                1.0 if data["success"] else 0.0,
                data.get("model_used") or model_type,
                data.get("duration_seconds"),
            ))
        # Update pattern hitrate
        _update_pattern_hitrate(cursor, pattern_id, data)

    # ── Insert run ───────────────────────────────────────────────
    try:
        cursor.execute("""
            INSERT INTO prompt_runs
            (run_id, phase_key, target_project, prompt_summary, success,
             duration_seconds, error_summary, model_used, model_type,
             idle_seconds, token_count_input, token_count_output,
             token_cost_eur, token_cost_dkk, pattern_id,
             template_key, execution_status, first_try_success,
             manual_corrections, validation_passed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["run_id"],
            data["phase_key"],
            data["target_project"],
            data.get("prompt_summary"),
            data["success"],
            data.get("duration_seconds"),
            data.get("error_summary"),
            data.get("model_used"),
            model_type,
            data.get("idle_seconds"),
            data.get("token_count_input"),
            data.get("token_count_output"),
            data.get("token_cost_eur"),
            data.get("token_cost_dkk"),
            pattern_id,
            data.get("template_key"),
            execution_status,
            data.get("first_try_success"),
            data.get("manual_corrections", 0),
            data.get("validation_passed"),
            data.get("notes"),
        ))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Run ID '{data['run_id']}' already exists.",
        )

    # ── Template hitrate tracking ─────────────────────────────────
    template_key = data.get("template_key")
    if template_key and data.get("model_used"):
        is_success = data["success"]
        # Update template-level counters
        if model_type == "local":
            cursor.execute("""
                UPDATE prompt_templates SET
                    total_local_runs = total_local_runs + 1,
                    local_success_rate = CAST(
                        (local_success_rate * total_local_runs + ?) AS REAL
                    ) / (total_local_runs + 1),
                    updated_at = CURRENT_TIMESTAMP
                WHERE template_key = ?
            """, (1.0 if is_success else 0.0, template_key))
        elif model_type == "cloud":
            cursor.execute("""
                UPDATE prompt_templates SET
                    total_cloud_runs = total_cloud_runs + 1,
                    cloud_success_rate = CAST(
                        (cloud_success_rate * total_cloud_runs + ?) AS REAL
                    ) / (total_cloud_runs + 1),
                    updated_at = CURRENT_TIMESTAMP
                WHERE template_key = ?
            """, (1.0 if is_success else 0.0, template_key))

        # UPSERT template_model_hitrates
        cursor.execute("""
            INSERT INTO template_model_hitrates
            (template_key, model_used, total_runs, successful_runs,
             rolling_success_rate, avg_duration_seconds, last_run_timestamp)
            VALUES (?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(template_key, model_used) DO UPDATE SET
                total_runs = total_runs + 1,
                successful_runs = successful_runs + ?,
                rolling_success_rate = CAST(successful_runs + ? AS REAL) / (total_runs + 1),
                avg_duration_seconds = CAST(
                    (avg_duration_seconds * total_runs + ?) AS REAL
                ) / (total_runs + 1),
                last_run_timestamp = CURRENT_TIMESTAMP,
                last_updated = CURRENT_TIMESTAMP
        """, (
            template_key,
            data["model_used"],
            1.0 if is_success else 0.0,
            data.get("duration_seconds") or 0,
            is_success,
            is_success,
            data.get("duration_seconds") or 0,
        ))

    # Update phase hitrate aggregate
    cursor.execute("""
        INSERT INTO prompt_hitrates
        (phase_key, total_runs, successful_runs, rolling_success_rate,
         last_run_timestamp)
        VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(phase_key) DO UPDATE SET
            total_runs = total_runs + 1,
            successful_runs = successful_runs + ?,
            rolling_success_rate = CAST(successful_runs + ? AS REAL) / (total_runs + 1),
            last_run_timestamp = CURRENT_TIMESTAMP,
            last_updated = CURRENT_TIMESTAMP
    """, (
        data["phase_key"],
        data["success"],
        1.0 if data["success"] else 0.0,
        data["success"],
        data["success"],
    ))

    conn.commit()
    conn.close()

    return {
        "status": "recorded",
        "run_id": data["run_id"],
        "phase_key": data["phase_key"],
        "pattern_id": pattern_id,
        "template_key": template_key,
    }


def _next_pattern_id(cursor) -> str:
    """Generate the next pattern ID in sequence PAT-0001, PAT-0002, ..."""
    cursor.execute("SELECT MAX(pattern_id) FROM implementation_patterns")
    row = cursor.fetchone()
    if row and row[0]:
        num = int(row[0].split("-")[1]) + 1
    else:
        num = 1
    return f"PAT-{num:04d}"


def _update_pattern_hitrate(cursor, pattern_id: str, data: dict) -> None:
    """Update hitrate aggregate and best_model for a pattern."""
    success = data["success"]
    duration = data.get("duration_seconds")
    idle = data.get("idle_seconds")
    model = data.get("model_used") or data.get("model_type")

    # Update aggregate
    cursor.execute("""
        UPDATE implementation_patterns SET
            total_runs = total_runs + 1,
            successful_runs = successful_runs + ?,
            rolling_success_rate = CAST(successful_runs + ? AS REAL) / (total_runs + 1),
            avg_duration_seconds = CASE
                WHEN ? IS NOT NULL THEN
                    CAST((avg_duration_seconds * total_runs + ?) AS REAL) / (total_runs + 1)
                ELSE avg_duration_seconds END,
            avg_idle_seconds = CASE
                WHEN ? IS NOT NULL THEN
                    CAST((avg_idle_seconds * total_runs + ?) AS REAL) / (total_runs + 1)
                ELSE avg_idle_seconds END,
            last_used_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE pattern_id = ?
    """, (
        success, success,
        duration, duration,
        idle, idle,
        pattern_id,
    ))

    # Update best_model: set to the model with most successful runs
    if model:
        cursor.execute("""
            UPDATE implementation_patterns SET best_model = (
                SELECT model_used FROM prompt_runs
                WHERE pattern_id = ? AND success = 1
                GROUP BY model_used
                ORDER BY COUNT(*) DESC
                LIMIT 1
            )
            WHERE pattern_id = ?
        """, (pattern_id, pattern_id))

# ── prompt_hirates_get ──

@router.get("/api/prompt-hirates")
async def get_prompt_hitrates():
    """Return aggregated hitrate statistics grouped by phase_key.

    Sorted by rolling_success_rate ascending (worst first) so the
    frontend can highlight phases that need template improvement.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM prompt_hitrates
        ORDER BY rolling_success_rate ASC, total_runs DESC
    """)
    rows = cursor.fetchall()
    hitrates = [dict(r) for r in rows]

    conn.close()
    return {"hitrates": hitrates}

# ── implementation_patterns_get ──

@router.get("/api/implementation-patterns")
async def get_implementation_patterns(
    constraint_set: str | None = None,
):
    """Return implementation patterns with hitrate statistics.

    Optional filter: ?constraint_set=read-only,no-schema
    Sorted by rolling_success_rate ASC (worst first).
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if constraint_set:
        cursor.execute("""
            SELECT * FROM implementation_patterns
            WHERE constraint_set LIKE ?
            ORDER BY rolling_success_rate ASC, total_runs DESC
        """, (f"%{constraint_set}%",))
    else:
        cursor.execute("""
            SELECT * FROM implementation_patterns
            ORDER BY rolling_success_rate ASC, total_runs DESC
        """)
    rows = cursor.fetchall()
    patterns = [dict(r) for r in rows]

    conn.close()
    return {"patterns": patterns}

# ── implementation_patterns_runs_get ──

@router.get("/api/implementation-patterns/{pattern_id}/runs")
async def get_pattern_runs(pattern_id: str, limit: int = 50):
    """Return all prompt_runs linked to a specific pattern."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM prompt_runs
        WHERE pattern_id = ?
        ORDER BY run_timestamp DESC
        LIMIT ?
    """, (pattern_id, limit))
    rows = cursor.fetchall()
    runs = [dict(r) for r in rows]

    conn.close()
    return {"pattern_id": pattern_id, "runs": runs}

# ── prompt_templates_get_list ──

@router.get("/api/prompt-templates")
async def get_prompt_templates(
    suitable_for: str | None = None,
    complexity_tier: int | None = None,
    capture_source: str | None = None,
    is_active: int | None = None,
):
    """List prompt templates with optional filters.

    Query params:
      suitable_for    — filter by model compatibility: 'local', 'cloud', 'both'
      complexity_tier — filter by complexity: 1 (simple), 2 (medium), 3 (complex)
      capture_source  — filter by capture source: 'designed', 'verbatim', 'reconstructed'
      is_active       — 1 for active only, 0 for inactive, omit for all
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where: list[str] = []
    params: list = []

    if suitable_for:
        where.append("suitable_for = ?")
        params.append(suitable_for)
    if complexity_tier is not None:
        where.append("complexity_tier = ?")
        params.append(complexity_tier)
    if capture_source:
        where.append("capture_source = ?")
        params.append(capture_source)
    if is_active is not None:
        where.append("is_active = ?")
        params.append(is_active)

    clause = (" WHERE " + " AND ".join(where)) if where else ""

    cursor.execute(
        f"SELECT * FROM prompt_templates{clause} ORDER BY template_key",
        params,
    )
    rows = cursor.fetchall()
    templates = [dict(r) for r in rows]

    conn.close()
    return {"templates": templates}

# ── prompt_templates_post_create ──

@router.post("/api/prompt-templates")
async def create_prompt_template(request: Request):
    """Create a new prompt template.

    Body (JSON):
      template_key           — unique key, slug format (required)
      template_name          — human-readable name (required)
      description            — optional description
      structure_json         — template structure (required, JSON string)
      constraints_json       — default constraints (optional, JSON string)
      suitable_for           — 'local', 'cloud', or 'both' (default 'local')
      complexity_tier        — 1=simple, 2=medium, 3=complex (default 2)
      capture_source         — 'designed', 'verbatim', 'reconstructed' (default 'designed')
      avg_token_count_input  — estimated input tokens
      avg_token_count_output — estimated output tokens
      local_success_rate     — initial local success rate (default 0.0)
      cloud_success_rate     — initial cloud success rate (default 0.0)
      total_local_runs       — initial local run count (default 0)
      total_cloud_runs       — initial cloud run count (default 0)
    """
    data = await request.json()

    required = ["template_key", "template_name", "structure_json"]
    for field in required:
        if field not in data:
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {field}"
            )

    # Validate suitable_for
    suitable_for = data.get("suitable_for", "local")
    if suitable_for not in ("local", "cloud", "both"):
        raise HTTPException(
            status_code=400,
            detail="suitable_for must be 'local', 'cloud', or 'both'",
        )

    # Validate complexity_tier
    complexity_tier = data.get("complexity_tier", 2)
    if complexity_tier not in (1, 2, 3):
        raise HTTPException(
            status_code=400,
            detail="complexity_tier must be 1, 2, or 3",
        )

    # Validate capture_source
    capture_source = data.get("capture_source", "designed")
    if capture_source not in ("designed", "verbatim", "reconstructed"):
        raise HTTPException(
            status_code=400,
            detail="capture_source must be 'designed', 'verbatim', or 'reconstructed'",
        )

    # Validate structure_json is valid JSON
    try:
        structure = json.loads(data["structure_json"])
        if not isinstance(structure, dict) or "sections" not in structure:
            raise HTTPException(
                status_code=400,
                detail="structure_json must be a JSON object with a 'sections' array",
            )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="structure_json is not valid JSON",
        )

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO prompt_templates
            (template_key, template_name, description, structure_json,
             constraints_json, suitable_for, complexity_tier, capture_source,
             avg_token_count_input, avg_token_count_output,
             local_success_rate, cloud_success_rate,
             total_local_runs, total_cloud_runs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["template_key"],
            data["template_name"],
            data.get("description"),
            data["structure_json"],
            data.get("constraints_json"),
            suitable_for,
            complexity_tier,
            capture_source,
            data.get("avg_token_count_input"),
            data.get("avg_token_count_output"),
            data.get("local_success_rate", 0.0),
            data.get("cloud_success_rate", 0.0),
            data.get("total_local_runs", 0),
            data.get("total_cloud_runs", 0),
        ))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Template key '{data['template_key']}' already exists.",
        )

    conn.commit()
    conn.close()

    return {
        "status": "created",
        "template_key": data["template_key"],
    }

# ── prompt_templates_get_one ──

@router.get("/api/prompt-templates/{template_key}")
async def get_prompt_template(template_key: str):
    """Get a single template with rendered preview.

    Returns the template with structure_json parsed and a preview
    of how the template looks with placeholder values filled in.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM prompt_templates
        WHERE template_key = ? AND is_active = 1
    """, (template_key,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    template = dict(row)
    # Parse JSON fields for convenience
    try:
        template["structure"] = json.loads(template["structure_json"])
    except json.JSONDecodeError:
        template["structure"] = {"error": "Invalid JSON"}
    try:
        template["constraints"] = json.loads(template["constraints_json"] or "{}")
    except json.JSONDecodeError:
        template["constraints"] = {}

    # Generate a preview with placeholder values
    preview_parts = []
    for section in template.get("structure", {}).get("sections", []):
        label = section.get("label", "")
        if section.get("type") == "fixed":
            preview_parts.append(f"{label} {section.get('value', '')}".strip())
        elif section.get("type") == "param":
            preview_parts.append(f"{label} <{section.get('param_key', '?')}>")
        elif section.get("type") == "list":
            preview_parts.append(f"{label}")
            preview_parts.append("  - <item 1>")
            preview_parts.append("  - <item 2>")
    template["preview"] = "\n".join(preview_parts)

    conn.close()
    return template

# ── prompt_templates_put_update ──

@router.put("/api/prompt-templates/{template_key}")
async def update_prompt_template(template_key: str, request: Request):
    """Update an existing template. Only provided fields are updated."""
    data = await request.json()

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute("""
        SELECT template_key FROM prompt_templates
        WHERE template_key = ? AND is_active = 1
    """, (template_key,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    # Build SET clause from provided fields
    updatable = [
        "template_name", "description", "structure_json",
        "constraints_json", "suitable_for",
        "complexity_tier", "capture_source",
        "avg_token_count_input", "avg_token_count_output",
        "local_success_rate", "cloud_success_rate",
        "total_local_runs", "total_cloud_runs", "is_active",
    ]
    sets = []
    params = []
    for field in updatable:
        if field in data:
            sets.append(f"{field} = ?")
            params.append(data[field])

    if not sets:
        conn.close()
        return {"status": "no changes", "template_key": template_key}

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(template_key)

    cursor.execute(
        f"UPDATE prompt_templates SET {', '.join(sets)} WHERE template_key = ?",
        params,
    )
    conn.commit()
    conn.close()

    return {"status": "updated", "template_key": template_key}

# ── prompt_compiler_fields_get ──

@router.get("/api/prompt-compiler-fields")
async def get_prompt_compiler_fields():
    """Return all active compiler fields grouped by section.

    Frontend uses this to dynamically generate the compile form.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM prompt_compiler_fields
        WHERE is_active = 1
        ORDER BY section, sort_order
    """)
    rows = cursor.fetchall()

    # Attach options for select fields (handoff 015 — database-driven dropdowns)
    # Convert rows to dicts first — sqlite3.Row does not support item assignment
    fields_temp = [dict(r) for r in rows]
    for f in fields_temp:
        if f["field_type"] == "select":
            cursor.execute("""
                SELECT option_value, option_label, is_default
                FROM prompt_compiler_field_options
                WHERE field_key = ? AND is_active = 1
                ORDER BY sort_order
            """, (f["field_key"],))
            option_rows = cursor.fetchall()
            f["_options"] = [
                {
                    "value": dict(or_)["option_value"],
                    "label": dict(or_)["option_label"],
                    "default": bool(dict(or_)["is_default"]),
                }
                for or_ in option_rows
            ]

    conn.close()

    # Add options array to select fields, remove internal _options key
    for f in fields_temp:
        if f.get("_options") is not None:
            f["options"] = f.pop("_options")
        elif f["field_type"] == "select":
            f["options"] = []

    fields = fields_temp

    # Group by section
    sections = {}
    for f in fields:
        section = f["section"]
        if section not in sections:
            sections[section] = []
        sections[section].append(f)

    return {
        "fields": fields,
        "sections": sections,
        "total": len(fields),
    }

# ── prompt_compiler_fields_post ──

@router.post("/api/prompt-compiler-fields")
async def create_prompt_compiler_field(request: Request):
    """Create a new compiler field."""
    data = await request.json()
    required = ["field_key", "field_label", "field_type", "section"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prompt_compiler_fields
        (field_key, field_label, field_type, is_required, required_condition,
         section, sort_order, placeholder, help_text, default_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["field_key"],
        data["field_label"],
        data["field_type"],
        data.get("is_required", 1),
        data.get("required_condition"),
        data["section"],
        data.get("sort_order", 0),
        data.get("placeholder"),
        data.get("help_text"),
        data.get("default_value"),
    ))
    conn.commit()
    conn.close()
    return {"status": "created", "field_key": data["field_key"]}

# ── prompt_compiler_field_options_post ──

@router.post("/api/prompt-compiler-field-options")
async def create_prompt_compiler_field_option(request: Request):
    """Create a new option for a compiler select field.

    Required JSON fields: field_key, option_value, option_label.
    Optional: sort_order (default 0), is_default (default 0).
    """
    data = await request.json()
    required_fields = ["field_key", "option_value", "option_label"]
    for f in required_fields:
        if f not in data:
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {f}"
            )

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prompt_compiler_field_options
        (field_key, option_value, option_label, sort_order, is_default)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["field_key"],
        data["option_value"],
        data["option_label"],
        data.get("sort_order", 0),
        data.get("is_default", 0),
    ))
    conn.commit()
    conn.close()
    return {
        "status": "created",
        "field_key": data["field_key"],
        "option_value": data["option_value"],
    }

# ── prompt_compiler_compile ──

@router.post("/api/prompt-compiler/compile")
async def compile_prompt(request: Request):
    """Compile a simplified prompt (Spor G).

    Accepts 8 fields. Auto-generates governance, constraint, validation
    from target_session role mapping. Returns governance-v2 XML handoff format.

    If flow_key + step_key are provided, resolves deliverable path and
    BridgeV002 signal instruction from DB (replaces legacy bridge.py).
    """
    data = await request.json()

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ── Load compiler fields ─────────────────────────
    cursor.execute("""
        SELECT * FROM prompt_compiler_fields
        WHERE is_active = 1
        ORDER BY section, sort_order
    """)
    field_rows = cursor.fetchall()
    conn.close()

    # ── Validate required fields ─────
    errors = []
    deployment_strategy = data.get("deployment_strategy", "standard")
    flow_key = data.get("flow_key", "")

    # Standard + flow: only target_project and goal are required
    # (phase_key, target_session, allowed_files, forbidden_files auto-resolved)
    if deployment_strategy == "standard" and flow_key:
        required_fields = ["target_project", "goal"]
    else:
        required_fields = ["target_project", "phase_key", "goal"]

    for field_key in required_fields:
        value = data.get(field_key, "")
        if not value or value == "":
            label = field_key
            for fr in field_rows:
                if dict(fr)["field_key"] == field_key:
                    label = dict(fr)["field_label"]
                    break
            errors.append({
                "error": f"Field '{label}' must be filled in",
                "field_key": field_key,
            })

    # scope_gate_confirmed must be checked
    if not data.get("scope_gate_confirmed", False):
        errors.append({
            "error": "Du skal bekræfte at du har taget stilling til scope og gate scope",
            "field_key": "scope_gate_confirmed",
        })

    if errors:
        return JSONResponse(
            status_code=400, content={"errors": errors, "status": "incomplete"}
        )

    # ── Resolve BridgeV002 step data (if flow_key + step_key provided) ─────
    flow_key = data.get("flow_key", "")
    step_key = data.get("step_key", "")
    bridge_step_data = None  # payload dict from build_step_payload, or None

    if flow_key and step_key:
        try:
            flow_data = load_flow_from_db(flow_key, db_path=get_db_path())
        except ValueError:
            flow_data = None

        if flow_data:
            steps = flow_data["steps"]
            target_step = None
            for s in steps:
                if s.get("step_key") == step_key:
                    target_step = s
                    break

            if target_step:
                # Use placeholder "???" for ID — will be replaced at assign-handoff-id time
                bridge_step_data = build_step_payload(
                    target_step, flow_key, "???", config.get_bridge_dir()
                )

    # ── Generate prompt ─────
    handoff_id = data.get("handoff_id", "???")
    target_project = data.get("target_project", "")
    phase_key = data.get("phase_key", "")
    goal = data.get("goal", "")
    deployment_strategy = data.get("deployment_strategy", "standard")
    allowed_files = data.get("allowed_files", "")
    forbidden_files = data.get("forbidden_files", "")

    # ── Standard + BridgeV002: auto-resolve from governance ─────
    if deployment_strategy == "standard" and bridge_step_data:
        from_role_key = bridge_step_data.get("from_role", "")
        to_role_key = bridge_step_data.get("to_role", "")

        # Load to_role from DB → get governance_file, tmux_session
        # (to_role is the one who executes the prompt)
        try:
            to_role_data = load_role_from_db(to_role_key, db_path=get_db_path())
        except ValueError:
            to_role_data = None

        # Auto-resolve target_session from to_role's tmux_session
        if to_role_data:
            target_session = to_role_data.get("tmux_session", "")
            governance_file = to_role_data.get("governance_file", "")
        else:
            target_session = "claude_implementer"
            governance_file = "03_IMPLEMENTOR.md"

        # Read governance file content from disk
        gov_path = os.path.join(
            config.get_project_root(),
            config.get_governance_dir(),
            governance_file,
        )
        gov_content = ""
        if os.path.isfile(gov_path):
            with open(gov_path, "r", encoding="utf-8") as gf:
                gov_content = gf.read()

        # Extract role name from governance file (first # heading)
        role_name = to_role_key
        if gov_content:
            for line in gov_content.split("\n"):
                if line.startswith("# ") and "STRICT_REVIEW" in line:
                    role_name = line.replace("# ", "").strip()
                    break

        # ── Build deliverable path and signal command from DB ─────
        deliverable_dir_val = bridge_step_data.get("deliverable_dir", "")

        # Result path: use step's deliverable_dir (absolute path to results/)
        # For step archi01→imple01, deliverable_dir is .../handoffs, but result goes to .../results
        if deliverable_dir_val:
            result_dir = os.path.join(os.path.dirname(deliverable_dir_val), "results")
        else:
            result_dir = os.path.join(config.get_bridge_dir(), "results")
        result_path = f"{result_dir}/{{ID}}-result.md"

        signal_cmd_template = (
            f"python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py "
            f"--db-flow {flow_key} --signal-complete --from-role {to_role_key}"
        )

        # ── Assemble prompt from governance + DB ─────
        lines = []
        # <role> — from governance file reference
        lines.append(f"<role>You are {to_role_key} in the DPMtF strict_review flow.")
        lines.append(f"Your role is defined in {gov_path}.")
        lines.append("Read it now before proceeding.</role>")
        lines.append("")
        lines.append(f"<handoff_id>{handoff_id}</handoff_id>")
        lines.append("")
        lines.append(f"<project>{target_project}</project>")
        lines.append("")
        lines.append("<context>")
        lines.append(f"Human has approved scope for phase {phase_key}.")
        lines.append(f"Scope is defined in {target_project}/docs/dpmtf/11_SCOPE.md.")
        lines.append(f"Father project: {config.get_father_project()}.")
        lines.append(f"Flow: {flow_key}, Step: {step_key} ({from_role_key} → {to_role_key}).")
        lines.append("</context>")
        lines.append("")
        # <governance> — reference the flow-specific file only
        lines.append("<governance>")
        lines.append("Read and apply your role definition BEFORE starting:")
        lines.append(f"- {gov_path}")
        lines.append("")
        lines.append("Key rules from your governance file apply in full.")
        lines.append("</governance>")
        lines.append("")
        # <task> — goal + auto-generated bridge signal
        lines.append("<task>")
        lines.append(goal)
        lines.append("")
        lines.append("When ALL steps are complete, execute the bridge signal:")
        lines.append("")
        lines.append(f"1. Write result file to {result_path.replace('{ID}', handoff_id)}")
        lines.append(f"2. SIGNAL completion: {signal_cmd_template.replace('{ID}', handoff_id)}")
        lines.append("</task>")
        lines.append("")
        # <scope> — from user input + Father project protection
        lines.append("<scope>")
        lines.append("Files you MAY modify:")
        if allowed_files:
            for f in allowed_files.strip().split("\n"):
                f = f.strip()
                if f:
                    lines.append(f"- {f}")
        else:
            lines.append("- (per governance file — Review will verify)")
        lines.append("")
        lines.append("Files you MUST NOT touch:")
        if forbidden_files:
            for f in forbidden_files.strip().split("\n"):
                f = f.strip()
                if f:
                    lines.append(f"- {f}")
        lines.append(f"- {config.get_project_root()}/ (Father project)")
        lines.append("</scope>")
        lines.append("")
        # <validation> — reference governance file
        lines.append("<validation>")
        lines.append(f"Run all validation checks defined in your governance file: {gov_path}")
        lines.append("Key checks include: py_compile, node --check, innerHTML, diff scope, i18n.")
        lines.append("</validation>")
        lines.append("")
        # <constraint> — from governance
        lines.append("<constraint>")
        lines.append("DO NOT COMMIT. Leave all changes unstaged.")
        lines.append(f"Target session: {target_session} (role: {from_role_key}).")
        lines.append("Execute ALL steps in <task> — especially the signal completion command.")
        lines.append("Stop after 2 failed patching attempts — document, do not guess.")
        lines.append("</constraint>")

        prompt = "\n".join(lines)

        result_response = {
            "prompt": prompt,
            "params_used": list(data.keys()),
            "format": "governance-v2-xml",
            "target_session": target_session,
            "target_role": to_role_key,
            "bridge_flow_key": flow_key,
            "bridge_step_key": step_key,
            "deliverable_dir": deliverable_dir_val,
            "governance_file": governance_file,
            "auto_resolved": True,
        }
        return result_response

    # ── Legacy / accelerated / no-flow: existing behavior ─────
    target_session = data.get("target_session", "claude_implementer")

    # Map session to governance role
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

    # ── Determine deliverable path and signal command ─────
    if bridge_step_data:
        deliverable_dir_val = bridge_step_data.get("deliverable_dir", "implementertoreview")
        result_path = f"{config.get_bridge_dir()}/{deliverable_dir_val}/{{ID}}-result.md"
        to_role_key = bridge_step_data.get("to_role", "")
        signal_cmd_template = (
            f"python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py "
            f"--db-flow {flow_key} --signal-complete --from-role {to_role_key}"
        )
    else:
        deliverable_dir_val = "implementertoreview"
        result_path = f"{config.get_bridge_dir()}/implementertoreview/{{ID}}-result.md"
        signal_cmd_template = f"python3 {config.get_bridge_dir()}/bridge.py complete {{ID}}"

    lines = []
    lines.append(f"<role>You are {role_name} in the DPMtF governance loop. Your role is defined")
    lines.append(f"in {config.get_project_root()}/{config.get_governance_dir()}/{governance_role_file}.")
    lines.append("Read it now before proceeding.</role>")
    lines.append("")
    lines.append(f"<handoff_id>{handoff_id}</handoff_id>")
    lines.append("")
    lines.append(f"<project>{target_project}</project>")
    lines.append("")
    lines.append("<context>")
    lines.append(f"Human has approved scope for phase {phase_key}.")
    lines.append(f"Scope is defined in {target_project}/docs/dpmtf/11_SCOPE.md.")
    lines.append(f"Father project: {config.get_father_project()}.")
    if deployment_strategy:
        lines.append(f"Deployment strategy: {deployment_strategy}.")
    lines.append("</context>")
    lines.append("")
    lines.append("<governance>")
    lines.append("Read and apply these governance files BEFORE starting:")
    lines.append(f"- {config.get_project_root()}/{config.get_governance_dir()}/12_CODING_STANDARD.md")
    lines.append(f"- {config.get_project_root()}/{config.get_governance_dir()}/16_FILE_ACCESS.md")
    lines.append(f"- {config.get_project_root()}/{config.get_governance_dir()}/{governance_role_file}")
    lines.append("")
    lines.append("Key rules extracted:")
    lines.append("- NO innerHTML for dynamic content — use createElement()/textContent.")
    lines.append("- ALL user-facing text MUST use lbl(key, fallback).")
    lines.append("- Python: py_compile before signaling completion, parameterized SQL.")
    lines.append("- DO NOT COMMIT.")
    lines.append("</governance>")
    lines.append("")
    lines.append("<task>")
    lines.append(goal)
    lines.append("")
    lines.append("When ALL steps are complete, execute the bridge signal:")
    lines.append("")
    lines.append(f"1. Write result file to {result_path.replace('{ID}', handoff_id)}")
    lines.append(f"2. SIGNAL completion: {signal_cmd_template.replace('{ID}', handoff_id)}")
    lines.append("</task>")
    lines.append("")
    lines.append("<scope>")
    lines.append("Files you MAY modify:")
    if allowed_files:
        for f in allowed_files.strip().split("\n"):
            f = f.strip()
            if f:
                lines.append(f"- {f}")
    else:
        lines.append("- (none specified — Review should verify)")
    lines.append("")
    lines.append("Files you MUST NOT touch:")
    if forbidden_files:
        for f in forbidden_files.strip().split("\n"):
            f = f.strip()
            if f:
                lines.append(f"- {f}")
    lines.append(f"- {config.get_project_root()}/ (Father project)")
    lines.append("</scope>")
    lines.append("")
    lines.append("<validation>")
    lines.append("1. python3 -m py_compile <modified files> — must pass")
    lines.append("2. node --check static/js/*.js — must pass for each modified file")
    lines.append("3. grep -RIn 'innerHTML' static/ templates/ — must be empty")
    lines.append("4. git diff --stat — verify only allowed files changed")
    lines.append("</validation>")
    lines.append("")
    lines.append("<constraint>")
    lines.append("DO NOT COMMIT. Leave all changes unstaged.")
    lines.append(f"Target session: {target_session} (role: {role_name}).")
    lines.append(f"Execute ALL steps in <task> — especially the signal completion command.")
    lines.append("</constraint>")

    prompt = "\n".join(lines)

    result_response = {
        "prompt": prompt,
        "params_used": list(data.keys()),
        "format": "governance-v2-xml",
        "target_session": target_session,
        "target_role": role_name,
    }

    if bridge_step_data:
        result_response["bridge_flow_key"] = flow_key
        result_response["bridge_step_key"] = step_key
        result_response["deliverable_dir"] = bridge_step_data.get("deliverable_dir", "")

    return result_response

# ── prompt_compiler_assign_handoff_id ──

@router.post("/api/prompt-compiler/assign-handoff-id")
async def assign_handoff_id(request: Request):
    """Assign a real handoff ID to a compiled prompt and write the handoff file.

    Replaces ??? placeholders with the next available BridgeV002 handoff ID,
    writes the finalized prompt to the correct deliverable directory resolved
    from DB, and returns a BridgeV002 dispatch command.

    Body (JSON):
      prompt_text     — the compiled prompt text (may contain ??? placeholders)
      target_project  — target project path (for logging context)
      flow_key        — BridgeV002 flow key (e.g. 'strict_review')
      step_key        — BridgeV002 step key within the flow (optional)
      deliverable_dir — pre-resolved from compile_prompt (if available)
    """
    data = await request.json()
    prompt_text: str = data.get("prompt_text", "")

    if not prompt_text:
        raise HTTPException(status_code=400, detail="Missing prompt_text")

    flow_key = data.get("flow_key", "strict_review")
    step_key = data.get("step_key", "")

    # Get next handoff ID from BridgeV002 DB (replaces bridge.py next-id subprocess)
    try:
        handoff_id_raw = get_next_id_for_flow(flow_key, db_path=get_db_path())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get next ID for flow '{flow_key}': {e}",
        )

    handoff_id: str = str(handoff_id_raw)

    # Replace ??? placeholders with real ID
    finalized_prompt: str = prompt_text.replace("???", handoff_id)

    # Resolve deliverable directory and pattern from step
    # Priority: 1) DB step deliverable_dir (absolute path), 2) pre-resolved from compile, 3) default
    deliverable_dir_val = ""
    deliverable_pattern = "{ID}-handoff.md"  # default

    if flow_key and step_key:
        try:
            flow_data = load_flow_from_db(flow_key, db_path=get_db_path())
            for s in flow_data["steps"]:
                if s.get("step_key") == step_key:
                    deliverable_dir_val = s.get("deliverable_dir", "")
                    deliverable_pattern = s.get("deliverable_pattern", deliverable_pattern)
                    break
        except ValueError as exc:
            logger.warning("TBD: flow %s not found for assign-handoff-id deliverable lookup: %s", flow_key, exc)

    # Fall back to pre-resolved from compile if DB lookup didn't yield a dir
    if not deliverable_dir_val:
        deliverable_dir_val = data.get("deliverable_dir", "")

    if not deliverable_dir_val:
        # Last-resort fallback — use DPMTF_BRIDGE_DIR from environment
        bridge_base = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/flows"))
        deliverable_dir_val = f"{bridge_base}/{flow_key}/handoffs"

    # Build deliverable filename from pattern
    deliverable_file = deliverable_pattern.replace("{ID}", handoff_id)

    # Build handoff path — handle absolute vs relative deliverable_dir
    if os.path.isabs(deliverable_dir_val):
        handoff_dir = deliverable_dir_val
    else:
        handoff_dir = os.path.join(config.get_bridge_dir(), deliverable_dir_val)
    handoff_path = os.path.join(handoff_dir, deliverable_file)
    os.makedirs(handoff_dir, exist_ok=True)
    try:
        with open(handoff_path, "w") as f:
            f.write(finalized_prompt)
    except IOError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to write handoff file: {e}"
        )

    # Build BridgeV002 dispatch command from step (replaces legacy bridge.py send)
    from_role_for_send = "archi01"  # default sender
    to_role_for_send = "imple01"    # default target
    if flow_key and step_key:
        try:
            flow_data = load_flow_from_db(flow_key, db_path=get_db_path())
            for s in flow_data["steps"]:
                if s.get("step_key") == step_key:
                    from_role_for_send = s.get("from_role", from_role_for_send)
                    to_role_for_send = s.get("to_role", to_role_for_send)
                    break
        except ValueError as exc:
            logger.warning("TBD: flow %s not found for assign-handoff-id role lookup: %s", flow_key, exc)

    dispatch_command: str = (
        f"python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py "
        f"--db-flow {flow_key} --signal-send "
        f"--from-role {from_role_for_send} --to-role {to_role_for_send} "
        f"--id {handoff_id}"
    )

    return {
        "handoff_id": handoff_id,
        "handoff_path": handoff_path,
        "prompt": finalized_prompt,
        "dispatch_command": dispatch_command,
        "flow_key": flow_key,
        "from_role": from_role_for_send,
        "to_role": to_role_for_send,
        "deliverable_dir": deliverable_dir_val,
        "status": "ready_for_dispatch",
    }

# ── prompt_compiler_dispatch ──

@router.post("/api/prompt-compiler/dispatch")
async def dispatch_handoff(request: Request):
    """Run the BridgeV002 dispatcher to deliver a handoff to its target role.

    Frontend wrapper around dispatch.py signal-send. Called from the UI after
    assign-handoff-id has produced a ready dispatch command, eliminating the
    need to copy/paste the command into a terminal.

    Body (JSON):
      flow_key   — BridgeV002 flow key (e.g. 'strict_review')
      from_role  — source role key (e.g. 'archi01')
      to_role    — target role key (e.g. 'imple01')
      handoff_id — assigned handoff ID (e.g. '178')
    """
    data = await request.json()

    required_fields = ["flow_key", "from_role", "to_role", "handoff_id"]
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {field}"
            )

    flow_key = str(data["flow_key"]).strip()
    from_role = str(data["from_role"]).strip()
    to_role = str(data["to_role"]).strip()
    handoff_id = str(data["handoff_id"]).strip()

    script_path = (
        Path(config.get_project_root())
        / "scripts"
        / "bridgeV002"
        / "dispatch.py"
    )
    if not script_path.exists():
        raise HTTPException(
            status_code=500, detail=f"dispatch.py not found at {script_path}"
        )

    cmd = [
        "python3",
        str(script_path),
        "--db-flow", flow_key,
        "--signal-send",
        "--from-role", from_role,
        "--to-role", to_role,
        "--id", handoff_id,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=config.get_project_root(),
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "error": "dispatch.py timed out after 120 seconds",
                "handoff_id": handoff_id,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to execute dispatch.py: {e}",
                "handoff_id": handoff_id,
            },
        )

    output = (result.stdout or "") + (result.stderr or "")
    success = (
        result.returncode == 0
        and "ERROR" not in output
        and "send_failed" not in output
        and "✅" in output
    )

    return {
        "success": success,
        "returncode": result.returncode,
        "output": output,
        "handoff_id": handoff_id,
        "from_role": from_role,
        "to_role": to_role,
        "flow_key": flow_key,
    }

# ── prompt_templates_hitrate_get ──

@router.get("/api/prompt-templates/{template_key}/hitrate")
async def get_template_model_hitrates(template_key: str):
    """Return per-model hitrate statistics for a template.

    Enables data-driven model selection — shows which models
    perform best with this specific template.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Verify template exists
    cursor.execute("""
        SELECT template_key, template_name FROM prompt_templates
        WHERE template_key = ? AND is_active = 1
    """, (template_key,))
    template = cursor.fetchone()
    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    cursor.execute("""
        SELECT * FROM template_model_hitrates
        WHERE template_key = ?
        ORDER BY rolling_success_rate ASC
    """, (template_key,))
    rows = cursor.fetchall()
    model_hitrates = [dict(r) for r in rows]

    conn.close()
    return {
        "template_key": template_key,
        "template_name": template["template_name"],
        "model_hitrates": model_hitrates,
    }

