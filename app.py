from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import sqlite3
from fastapi import HTTPException

app = FastAPI(title="DPMtF WebUI")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database path
DB_PATH = "databases/dpmtf.db"

# Fallback locale for i18n
FALLBACK_LOCALE = "en-US"


def _resolve_ui_label_text(label_row, locale):
    """Resolve translated text for a single ui_label row with fallback chain.

    Fallback order: requested locale -> en-US -> default_text -> label_key.
    Returns a plain string.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    label_id = label_row["label_id"]
    default_text = label_row["default_text"]
    label_key = label_row["label_key"]

    # Try requested locale translation
    if locale:
        cursor.execute(
            "SELECT translated_text FROM ui_label_translations "
            "WHERE label_id = ? AND locale = ? AND is_active = 1",
            (label_id, locale),
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]

    # Fallback to en-US translation
    if locale != FALLBACK_LOCALE:
        cursor.execute(
            "SELECT translated_text FROM ui_label_translations "
            "WHERE label_id = ? AND locale = ? AND is_active = 1",
            (label_id, FALLBACK_LOCALE),
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]

    # Fallback to default_text
    if default_text:
        conn.close()
        return default_text

    # Last resort: return the key itself
    conn.close()
    return label_key


def get_ui_label_by_key(label_key, locale="en-US"):
    """Look up a single active ui_label by label_key and resolve its text.

    Fallback chain: requested locale -> en-US -> default_text -> label_key.
    Returns a plain string.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT label_id, label_key, label_domain, default_text, description, is_active "
        "FROM ui_labels WHERE label_key = ? AND is_active = 1",
        (label_key,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return label_key

    label_row = {
        "label_id": row[0],
        "label_key": row[1],
        "label_domain": row[2],
        "default_text": row[3],
        "description": row[4],
        "is_active": bool(row[5]),
    }
    conn.close()
    return _resolve_ui_label_text(label_row, locale)


def get_ui_labels_for_domain(label_domain, locale="en-US"):
    """Return a dict of label_key -> resolved text for all active labels in a domain.

    Uses the same fallback chain per label. Sorted by label_id for determinism.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT label_id, label_key, label_domain, default_text, description, is_active "
        "FROM ui_labels WHERE label_domain = ? AND is_active = 1 "
        "ORDER BY label_id",
        (label_domain,),
    )

    result = {}
    for row in cursor.fetchall():
        label_row = {
            "label_id": row[0],
            "label_key": row[1],
            "label_domain": row[2],
            "default_text": row[3],
            "description": row[4],
            "is_active": bool(row[5]),
        }
        result[label_row["label_key"]] = _resolve_ui_label_text(label_row, locale)

    conn.close()
    return result


# Allowed classifications
ALLOWED_CLASSIFICATIONS = ["unknown", "starter", "advanced", "project_specific", "debug", "skip"]

# Default app profiles
DEFAULT_APP_PROFILES = [
    {"name": "Minimal Starter App", "description": "Basic starter profile with essential panels"},
    {"name": "Pipeline App", "description": "Pipeline-focused profile"},
    {"name": "Operational Dashboard App", "description": "Operational dashboard profile"},
    {"name": "Full Reference App", "description": "Complete reference profile"},
    {"name": "Custom Selected Panels", "description": "Custom panel selection"}
]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return HTMLResponse(content=open("templates/index.html").read())

@app.get("/api/health")
async def health_check():
    database_exists = os.path.exists(DB_PATH)
    return {
        "status": "healthy" if database_exists else "unhealthy",
        "app": "DPMtF WebUI",
        "database_path": DB_PATH,
        "database_exists": database_exists
    }

@app.get("/api/panels")
async def get_panels():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fp.id, fp.source_file, fp.panel_key, fp.panel_title, fp.html_id, fp.sort_order, fp.raw_opening_tag,
               pc.classification
        FROM frontend_panels fp
        LEFT JOIN panel_classifications pc ON fp.id = pc.panel_id
        ORDER BY fp.sort_order
    """)

    panels = []
    for row in cursor.fetchall():
        panels.append({
            "id": row[0],
            "source_file": row[1],
            "panel_key": row[2],
            "panel_title": row[3],
            "html_id": row[4],
            "sort_order": row[5],
            "raw_opening_tag": row[6],
            "classification": row[7]
        })

    conn.close()
    return {"panels": panels}

@app.post("/api/panels/{panel_id}/classification")
async def update_panel_classification(panel_id: int, classification_data: dict):
    # Validate classification
    classification = classification_data.get("classification")
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(status_code=400, detail="Invalid classification value")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if panel exists
    cursor.execute("SELECT id FROM frontend_panels WHERE id = ?", (panel_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Panel not found")

    # Update or insert classification
    cursor.execute("SELECT id FROM panel_classifications WHERE panel_id = ?", (panel_id,))
    existing = cursor.fetchone()

    if existing:
        # Update existing classification
        cursor.execute("""
            UPDATE panel_classifications
            SET classification = ?, updated_at = CURRENT_TIMESTAMP
            WHERE panel_id = ?
        """, (classification, panel_id))
    else:
        # Insert new classification
        cursor.execute("""
            INSERT INTO panel_classifications (panel_id, classification)
            VALUES (?, ?)
        """, (panel_id, classification))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "panel_id": panel_id,
        "classification": classification
    }

@app.get("/api/app-profiles")
async def get_app_profiles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get profiles with panel counts
    cursor.execute("""
        SELECT ap.id, ap.name, ap.description, ap.created_at,
               COUNT(appp.panel_id) as included_panel_count
        FROM app_profiles ap
        LEFT JOIN app_profile_panels appp ON ap.id = appp.profile_id
        GROUP BY ap.id, ap.name, ap.description, ap.created_at
        ORDER BY
            CASE ap.name
                WHEN 'Minimal Starter App' THEN 1
                WHEN 'Pipeline App' THEN 2
                WHEN 'Operational Dashboard App' THEN 3
                WHEN 'Full Reference App' THEN 4
                WHEN 'Custom Selected Panels' THEN 5
                ELSE 6
            END
    """)

    profiles = []
    for row in cursor.fetchall():
        profiles.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "created_at": row[3],
            "included_panel_count": row[4]
        })

    conn.close()
    return {"profiles": profiles}

@app.post("/api/app-profiles/defaults")
async def create_default_profiles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if default profiles already exist
    cursor.execute("SELECT COUNT(*) FROM app_profiles")
    count = cursor.fetchone()[0]

    if count == 0:
        # Insert default profiles
        for profile in DEFAULT_APP_PROFILES:
            cursor.execute("""
                INSERT INTO app_profiles (name, description)
                VALUES (?, ?)
            """, (profile["name"], profile["description"]))

        conn.commit()
        conn.close()
        return {"status": "success", "message": "Default profiles created"}
    else:
        conn.close()
        return {"status": "success", "message": "Default profiles already exist"}

@app.get("/api/app-profiles/{profile_id}/panels")
async def get_profile_panels(profile_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if profile exists
    cursor.execute("SELECT id FROM app_profiles WHERE id = ?", (profile_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Profile not found")

    cursor.execute("""
        SELECT fp.id, fp.panel_key, fp.panel_title, fp.html_id,
               app_profile_panels.id IS NOT NULL as included
        FROM frontend_panels fp
        LEFT JOIN app_profile_panels ON fp.id = app_profile_panels.panel_id AND app_profile_panels.profile_id = ?
        ORDER BY fp.sort_order
    """, (profile_id,))

    panels = []
    for row in cursor.fetchall():
        panels.append({
            "id": row[0],
            "panel_key": row[1],
            "panel_title": row[2],
            "html_id": row[3],
            "included": bool(row[4])
        })

    conn.close()
    return {"panels": panels}

@app.post("/api/app-profiles/{profile_id}/panels/{panel_id}")
async def update_profile_panel_membership(profile_id: int, panel_id: int, membership_data: dict):
    # Validate membership_data
    include = membership_data.get("include")
    if include is None:
        raise HTTPException(status_code=400, detail="Include parameter is required")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if profile exists
    cursor.execute("SELECT id FROM app_profiles WHERE id = ?", (profile_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Profile not found")

    # Check if panel exists
    cursor.execute("SELECT id FROM frontend_panels WHERE id = ?", (panel_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Panel not found")

    # Update or insert membership
    cursor.execute("SELECT id FROM app_profile_panels WHERE profile_id = ? AND panel_id = ?", (profile_id, panel_id))
    existing = cursor.fetchone()

    if include:
        if not existing:
            # Insert new membership
            cursor.execute("""
                INSERT INTO app_profile_panels (profile_id, panel_id)
                VALUES (?, ?)
            """, (profile_id, panel_id))
    else:
        if existing:
            # Delete existing membership
            cursor.execute("DELETE FROM app_profile_panels WHERE profile_id = ? AND panel_id = ?", (profile_id, panel_id))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "profile_id": profile_id,
        "panel_id": panel_id,
        "included": include
    }

# Prompt Sequence Planner endpoints
@app.get("/api/prompt-sequences")
async def get_prompt_sequences():
    conn = sqlite3.connect(DB_PATH)
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

@app.post("/api/prompt-sequences")
async def create_prompt_sequence(sequence_data: dict):
    # Validate required fields
    name = sequence_data.get("name")
    if not name or name.strip() == "":
        raise HTTPException(status_code=400, detail="Name is required")

    goal = sequence_data.get("goal", "")

    conn = sqlite3.connect(DB_PATH)
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

@app.get("/api/prompt-sequences/{sequence_id}/steps")
async def get_prompt_sequence_steps(sequence_id: int):
    conn = sqlite3.connect(DB_PATH)
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

@app.post("/api/prompt-sequences/{sequence_id}/steps")
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

    conn = sqlite3.connect(DB_PATH)
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

@app.post("/api/prompt-sequences/{sequence_id}/steps/{step_id}/status")
async def update_prompt_sequence_step_status(sequence_id: int, step_id: int, status_data: dict):
    # Validate required fields
    status = status_data.get("status")
    allowed_statuses = ["planned", "generated", "implemented", "failed", "skipped"]
    if not status or status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}")

    result_note = status_data.get("result_note", "")

    conn = sqlite3.connect(DB_PATH)
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

@app.get("/api/prompt-sequences/{sequence_id}/next-prompt")
async def get_next_prompt_preview(sequence_id: int):
    conn = sqlite3.connect(DB_PATH)
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
    generated_prompt = f"""Project path: /home/svend/DPMtF-WebUI

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

@app.get("/api/prompt-sequences/{sequence_id}/generated-prompts")
async def get_generated_prompts(sequence_id: int):
    conn = sqlite3.connect(DB_PATH)
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

@app.post("/api/prompt-sequences/{sequence_id}/steps/{step_id}/generated-prompts")
async def save_generated_prompt(sequence_id: int, step_id: int, prompt_data: dict):
    # Validate required fields
    generated_prompt = prompt_data.get("generated_prompt")
    if not generated_prompt or generated_prompt.strip() == "":
        raise HTTPException(status_code=400, detail="Generated prompt is required")

    conn = sqlite3.connect(DB_PATH)
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

@app.get("/api/generated-prompts")
async def get_all_generated_prompts():
    conn = sqlite3.connect(DB_PATH)
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

@app.get("/api/phase-status")
async def get_phase_status():
    conn = sqlite3.connect(DB_PATH)
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

@app.get("/api/frontend-layout")
async def get_frontend_layout():
    conn = sqlite3.connect(DB_PATH)
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

@app.post("/api/app-profiles/{profile_id}/draft-prompt-sequence")
async def create_draft_prompt_sequence(profile_id: int):
    conn = sqlite3.connect(DB_PATH)
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

@app.get("/api/ui-label-registry")
async def get_ui_label_registry():
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/ui-labels/{label_domain}")
async def get_ui_labels_by_domain(label_domain: str, locale: str = "en-US"):
    labels = get_ui_labels_for_domain(label_domain, locale)
    return {
        "label_domain": label_domain,
        "locale": locale,
        "labels": labels
    }


@app.get("/api/endpoint-registry")
async def get_endpoint_registry():
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/endpoint-runtime-status")
async def get_endpoint_runtime_status():
    # Build in-memory map of registered FastAPI routes
    route_map = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            path = route.path
            methods = route.methods - {"HEAD", "OPTIONS"}
            if path not in route_map:
                route_map[path] = set()
            route_map[path].update(methods)

    # Query active endpoint_registry records ordered by endpoint_id
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/bootstrap-dataset-status")
async def get_bootstrap_dataset_status():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get active bootstrap_dataset_registry records ordered by dataset_id
    cursor.execute("""
        SELECT dataset_id, dataset_key, table_name, min_expected_count,
               is_required, is_active
        FROM bootstrap_dataset_registry
        WHERE is_active = 1
        ORDER BY dataset_id
    """)

    bootstrap_status = []
    for row in cursor.fetchall():
        dataset_id, dataset_key, table_name, min_expected_count, is_required, is_active = row

        # Safe table-name handling: only count if the name is an allowed identifier
        if table_name not in ALLOWED_BOOTSTRAP_TABLES:
            bootstrap_status.append({
                "dataset_id": dataset_id,
                "dataset_key": dataset_key,
                "table_name": table_name,
                "min_expected_count": min_expected_count,
                "actual_count": None,
                "is_required": bool(is_required),
                "is_active": bool(is_active),
                "status": "missing_table",
            })
            continue

        # Verify the table exists in sqlite_schema
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        if not cursor.fetchone():
            bootstrap_status.append({
                "dataset_id": dataset_id,
                "dataset_key": dataset_key,
                "table_name": table_name,
                "min_expected_count": min_expected_count,
                "actual_count": None,
                "is_required": bool(is_required),
                "is_active": bool(is_active),
                "status": "missing_table",
            })
            continue

        # Count records in the referenced table
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        actual_count = cursor.fetchone()[0]

        if actual_count >= min_expected_count:
            status = "ok"
        else:
            status = "below_minimum"

        bootstrap_status.append({
            "dataset_id": dataset_id,
            "dataset_key": dataset_key,
            "table_name": table_name,
            "min_expected_count": min_expected_count,
            "actual_count": actual_count,
            "is_required": bool(is_required),
            "is_active": bool(is_active),
            "status": status,
        })

    conn.close()
    return {"bootstrap_dataset_status": bootstrap_status}


@app.get("/api/architecture-decision-records")
async def get_architecture_decision_records():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get active ADRs ordered by adr_id
    cursor.execute("""
        SELECT adr_id, adr_key, adr_title, decision_status,
               decision_context, decision_text, consequences,
               related_phase_key, is_active
        FROM architecture_decision_records
        WHERE is_active = 1
        ORDER BY adr_id
    """)

    architecture_decision_records = []
    for row in cursor.fetchall():
        architecture_decision_records.append({
            "adr_id": row[0],
            "adr_key": row[1],
            "adr_title": row[2],
            "decision_status": row[3],
            "decision_context": row[4],
            "decision_text": row[5],
            "consequences": row[6],
            "related_phase_key": row[7],
            "is_active": bool(row[8]),
        })

    conn.close()
    return {"architecture_decision_records": architecture_decision_records}


@app.get("/api/webui-migration-targets")
async def get_webui_migration_targets():
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/reusable-panel-selections")
async def get_reusable_panel_selections():
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/webui-project-skeletons")
async def get_webui_project_skeletons():
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/v2-panel-requirements")
async def get_v2_panel_requirements():
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/project-plans")
async def get_project_plans():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pp.id, pp.project_name, pp.target_folder, pp.app_port, pp.app_profile_id, pp.prompt_sequence_id, pp.notes, pp.status, pp.created_at,
               ap.name as app_profile_name, ps.name as prompt_sequence_name
        FROM project_plans pp
        LEFT JOIN app_profiles ap ON pp.app_profile_id = ap.id
        LEFT JOIN prompt_sequences ps ON pp.prompt_sequence_id = ps.id
        ORDER BY pp.created_at DESC
    """)

    project_plans = []
    for row in cursor.fetchall():
        project_plans.append({
            "id": row[0],
            "project_name": row[1],
            "target_folder": row[2],
            "app_port": row[3],
            "app_profile_id": row[4],
            "prompt_sequence_id": row[5],
            "notes": row[6],
            "status": row[7],
            "created_at": row[8],
            "app_profile_name": row[9],
            "prompt_sequence_name": row[10]
        })

    conn.close()
    return {"project_plans": project_plans}

@app.post("/api/project-plans")
async def create_project_plan(project_data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Validate required fields
    project_name = project_data.get("project_name")
    target_folder = project_data.get("target_folder")

    if not project_name or project_name.strip() == "":
        conn.close()
        raise HTTPException(status_code=400, detail="Project name is required")

    if not target_folder or target_folder.strip() == "":
        conn.close()
        raise HTTPException(status_code=400, detail="Target folder is required")

    # Validate target folder path
    if not target_folder.startswith("/"):
        conn.close()
        raise HTTPException(status_code=400, detail="Target folder must be an absolute path")

    if target_folder == "/":
        conn.close()
        raise HTTPException(status_code=400, detail="Target folder cannot be root directory")

    if target_folder == "/home/svend":
        conn.close()
        raise HTTPException(status_code=400, detail="Target folder cannot be /home/svend")

    if ".." in target_folder:
        conn.close()
        raise HTTPException(status_code=400, detail="Target folder cannot contain '..'")

    # Validate app_port if provided
    app_port = project_data.get("app_port")
    if app_port is not None:
        if not isinstance(app_port, int) or app_port < 1024 or app_port > 65535:
            conn.close()
            raise HTTPException(status_code=400, detail="App port must be between 1024 and 65535")

    # Validate app_profile_id if provided
    app_profile_id = project_data.get("app_profile_id")
    if app_profile_id is not None:
        cursor.execute("SELECT id FROM app_profiles WHERE id = ?", (app_profile_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="App profile not found")

    # Validate prompt_sequence_id if provided
    prompt_sequence_id = project_data.get("prompt_sequence_id")
    if prompt_sequence_id is not None:
        cursor.execute("SELECT id FROM prompt_sequences WHERE id = ?", (prompt_sequence_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Prompt sequence not found")

    # Create project plan
    cursor.execute("""
        INSERT INTO project_plans (project_name, target_folder, app_port, app_profile_id, prompt_sequence_id, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        project_name,
        target_folder,
        app_port,
        app_profile_id,
        prompt_sequence_id,
        project_data.get("notes", "")
    ))

    project_plan_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "project_plan_id": project_plan_id
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)