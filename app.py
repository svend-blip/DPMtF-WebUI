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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)