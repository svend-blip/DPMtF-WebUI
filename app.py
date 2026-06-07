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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)