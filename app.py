from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import sys
import platform
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

@app.get("/api/user-language")
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
        conn = sqlite3.connect(DB_PATH)
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
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return {"user_id": user_id, "locale": "en-US"}

@app.post("/api/user-language")
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
        conn = sqlite3.connect(DB_PATH)
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
    except Exception:
        pass

    try:
        user_id = os.getlogin()
    except Exception:
        user_id = "default"

    try:
        conn = sqlite3.connect(DB_PATH)
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

VALID_PANEL_GROUPS = {"daily", "journals", "reports", "periodic", "setup"}
VALID_PANEL_STATES = {"expanded", "collapsed"}


@app.get("/api/user-panel-groups")
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
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT group_name, state FROM user_panel_groups WHERE user_id = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        groups = {}
        for row in rows:
            groups[row["group_name"]] = row["state"]
        return {"user_id": user_id, "groups": groups}
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return {"user_id": user_id, "groups": {}}


@app.post("/api/user-panel-groups")
async def set_user_panel_group(request: Request):
    """Store a panel group collapse/expand state for the current user.

    Body (JSON): {"group_name": "journals", "state": "collapsed"}
    """
    data = await request.json()
    group_name = data.get("group_name", "").strip()
    state = data.get("state", "").strip()

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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (user_id, group_name, state))
        conn.commit()
        conn.close()
        return {"user_id": user_id, "group_name": group_name, "state": state, "status": "stored"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store panel group state: {exc}")

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

@app.post("/api/phases/sync-from-git")
async def sync_phases_from_git():
    """Manually sync phase status based on git sync state.

    Checks git_sync_status for all projects. If all tracked projects
    have unpushed_commits = 0 and last_push_success = 1, advances phases.
    Otherwise returns current state without changes.

    Returns what was advanced (if anything).
    """
    conn = sqlite3.connect(DB_PATH)
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

# ---------------------------------------------------------------------------
# Phase 2F — Hitrate Scoring endpoints
# ---------------------------------------------------------------------------


@app.get("/api/prompt-runs")
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
    conn = sqlite3.connect(DB_PATH)
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


@app.post("/api/prompt-runs")
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

    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/prompt-hirates")
async def get_prompt_hitrates():
    """Return aggregated hitrate statistics grouped by phase_key.

    Sorted by rolling_success_rate ascending (worst first) so the
    frontend can highlight phases that need template improvement.
    """
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/implementation-patterns")
async def get_implementation_patterns(
    constraint_set: str | None = None,
):
    """Return implementation patterns with hitrate statistics.

    Optional filter: ?constraint_set=read-only,no-schema
    Sorted by rolling_success_rate ASC (worst first).
    """
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/implementation-patterns/{pattern_id}/runs")
async def get_pattern_runs(pattern_id: str, limit: int = 50):
    """Return all prompt_runs linked to a specific pattern."""
    conn = sqlite3.connect(DB_PATH)
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


# ---------------------------------------------------------------------------
# Phase 2H — Prompt Template Manager endpoints
# ---------------------------------------------------------------------------


@app.get("/api/prompt-templates")
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
    conn = sqlite3.connect(DB_PATH)
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


@app.post("/api/prompt-templates")
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

    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/prompt-templates/{template_key}")
async def get_prompt_template(template_key: str):
    """Get a single template with rendered preview.

    Returns the template with structure_json parsed and a preview
    of how the template looks with placeholder values filled in.
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


@app.put("/api/prompt-templates/{template_key}")
async def update_prompt_template(template_key: str, request: Request):
    """Update an existing template. Only provided fields are updated."""
    data = await request.json()

    conn = sqlite3.connect(DB_PATH)
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


# ---------------------------------------------------------------------------
# Phase 2I — Local Prompt Compiler
# ---------------------------------------------------------------------------


@app.post("/api/prompt-templates/{template_key}/compile")
async def compile_prompt(template_key: str, request: Request):
    """Compile a prompt from a template with provided parameters.

    Body (JSON):
      project_path   — target project path (replaces {project_path})
      phase_id       — phase key (replaces {phase_id})
      goal           — what this prompt should achieve
      constraints    — list of constraint strings
      implementation — implementation target description
      allowed_files  — list of allowed file paths
      validation_commands — list of validation shell commands
      scope          — scope description (for brainstorm)
      deliverable    — deliverable description (for brainstorm)
      <any other key> — replaces {key} in template sections
    """
    data = await request.json()

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
        raise HTTPException(status_code=404, detail="Template not found")

    template = dict(row)
    conn.close()

    try:
        structure = json.loads(template["structure_json"])
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Template structure is invalid JSON")

    # Build the prompt by processing each section
    lines = []
    for section in structure.get("sections", []):
        label = section.get("label", "")
        sec_type = section.get("type", "fixed")

        if sec_type == "fixed":
            value = section.get("value", "")
            # Replace {placeholders} in value
            for key, val in data.items():
                value = value.replace("{" + key + "}", str(val))
            if label and value:
                lines.append(f"{label} {value}".strip())
            elif label:
                lines.append(label)
            elif value:
                lines.append(value)

        elif sec_type == "param":
            param_key = section.get("param_key", "")
            value = data.get(param_key, f"<{param_key}>")
            lines.append(f"{label} {value}")

        elif sec_type == "list":
            param_key = section.get("param_key", "")
            items = data.get(param_key, [])
            if not isinstance(items, list):
                items = [str(items)]
            lines.append(label)
            for item in items:
                lines.append(f"  - {item}")

    prompt_text = "\n".join(lines)

    return {
        "template_key": template_key,
        "template_name": template["template_name"],
        "suitable_for": template["suitable_for"],
        "prompt": prompt_text,
        "params_used": list(data.keys()),
    }


# ── Phase 2H Redesign: Template Model Hitrates ───────────────────────


@app.get("/api/prompt-templates/{template_key}/hitrate")
async def get_template_model_hitrates(template_key: str):
    """Return per-model hitrate statistics for a template.

    Enables data-driven model selection — shows which models
    perform best with this specific template.
    """
    conn = sqlite3.connect(DB_PATH)
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


# ---------------------------------------------------------------------------
# Phase 2J — Validation Automation
# ---------------------------------------------------------------------------


@app.post("/api/validate")
async def run_validation(request: Request):
    """Run validation rules against a project and return a structured report.

    Body (JSON):
      target_project  — project path or key (required)
      phase_key       — phase being validated (optional)
      rule_keys       — list of rule keys to run, or ["all"] (default)
      diff_content    — pre-provided diff output (optional, avoids shelling out)

    Only runs read-only diagnostic commands (grep, git diff, syntax checks).
    No destructive operations. Records results in validation_runs and
    validation_results tables.
    """
    data = await request.json()

    target = data.get("target_project")
    if not target:
        raise HTTPException(status_code=400, detail="Missing target_project")

    rule_keys = data.get("rule_keys", ["all"])
    phase_key = data.get("phase_key")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch rules
    if "all" in rule_keys:
        cursor.execute("""
            SELECT * FROM validation_rules WHERE is_active = 1 ORDER BY rule_key
        """)
    else:
        placeholders = ",".join("?" for _ in rule_keys)
        cursor.execute(f"""
            SELECT * FROM validation_rules
            WHERE rule_key IN ({placeholders}) AND is_active = 1
            ORDER BY rule_key
        """, rule_keys)
    rules = [dict(r) for r in cursor.fetchall()]

    if not rules:
        conn.close()
        return {"status": "no rules matched", "results": []}

    # Generate run_id
    import uuid
    run_id = f"VALRUN-{uuid.uuid4().hex[:8].upper()}"

    # Run each rule
    results = []
    passed_count = 0
    failed_count = 0

    for rule in rules:
        cmd = rule["command"]
        result = {"rule_key": rule["rule_key"], "rule_name": rule["rule_name"],
                  "command": cmd, "passed": 0, "actual_output": "", "notes": ""}

        try:
            # Safety: only allow read-only commands
            dangerous = ["rm ", ">", "$(", "`", "sudo", "kill", "fuser",
                         "DELETE", "DROP", "ALTER", "INSERT", "UPDATE",
                         "pip install", "npm install", "nohup", "&"]
            if any(d in cmd for d in dangerous):
                result["notes"] = "Blocked: command contains potentially destructive operations"
                results.append(result)
                failed_count += 1
                continue

            # Run command in the target project directory
            import subprocess
            proc = subprocess.run(
                cmd, shell=True, cwd=target,
                capture_output=True, text=True, timeout=30,
            )
            output = (proc.stdout + proc.stderr).strip()
            result["actual_output"] = output[:2000]  # Truncate

            # Determine pass/fail
            # Exit code 0 = pass. expected_output is documentation for humans.
            if proc.returncode == 0:
                result["passed"] = 1
                passed_count += 1
            else:
                result["passed"] = 0
                result["notes"] = f"Exit code {proc.returncode}"
                failed_count += 1

        except subprocess.TimeoutExpired:
            result["notes"] = "Command timed out after 30s"
            failed_count += 1
        except Exception as exc:
            result["notes"] = f"Error: {str(exc)[:200]}"
            failed_count += 1

        results.append(result)

    # Record run
    total = len(rules)
    verdict = "PASS" if failed_count == 0 else ("PASS WITH NOTES" if failed_count <= 1 else "FAIL")
    cursor.execute("""
        INSERT INTO validation_runs
        (run_id, phase_key, target_project, overall_verdict,
         rules_total, rules_passed, rules_failed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, phase_key, target, verdict, total, passed_count, failed_count))

    # Record per-rule results
    for r in results:
        cursor.execute("""
            INSERT INTO validation_results
            (run_id, rule_key, passed, actual_output, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (run_id, r["rule_key"], r["passed"],
              r["actual_output"][:500], r["notes"][:500]))

    conn.commit()
    conn.close()

    return {
        "run_id": run_id,
        "target_project": target,
        "phase_key": phase_key,
        "verdict": verdict,
        "rules_total": total,
        "rules_passed": passed_count,
        "rules_failed": failed_count,
        "results": results,
    }


@app.get("/api/validation-runs")
async def get_validation_runs(limit: int = 20):
    """Return recent validation runs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM validation_runs
        ORDER BY run_timestamp DESC LIMIT ?
    """, (limit,))
    runs = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"runs": runs}


@app.get("/api/validation-rules")
async def get_validation_rules():
    """Return all active validation rules."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM validation_rules
        WHERE is_active = 1
        ORDER BY rule_key
    """)
    rules = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"rules": rules}


# ---------------------------------------------------------------------------
# Phase 2K — Git Sync Management
# ---------------------------------------------------------------------------


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


@app.get("/api/git/status")
async def get_git_status(project_key: str | None = None):
    """Return git sync status for tracked projects.

    If project_key is provided, returns status for that project only.
    Otherwise returns all tracked projects.

    This is a read-only status check. It does NOT perform git operations.
    Actual commit/push remain manual (Claude Code or Svend).
    """
    conn = sqlite3.connect(DB_PATH)
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


@app.post("/api/git/operations")
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

    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/git/operations")
async def get_git_operations(limit: int = 20):
    """Return recent git operations."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM git_operations
        ORDER BY operation_timestamp DESC LIMIT ?
    """, (limit,))
    ops = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"operations": ops}


# ---------------------------------------------------------------------------
# Phase 2L — Platform Adapter Framework
# ---------------------------------------------------------------------------


@app.get("/api/platform")
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


# ---------------------------------------------------------------------------
# Phase 2M — Local Claude Code Session Manager
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
async def get_sessions(limit: int = 20):
    """List recent Claude Code sessions."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM claude_sessions
        ORDER BY started_at DESC LIMIT ?
    """, (limit,))
    sessions = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"sessions": sessions}


@app.get("/api/sessions/current")
async def get_current_session():
    """Return the currently active Claude Code session, if any."""
    conn = sqlite3.connect(DB_PATH)
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


@app.post("/api/sessions")
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

    conn = sqlite3.connect(DB_PATH)
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


@app.put("/api/sessions/{session_id}")
async def update_session(session_id: str, request: Request):
    """Update a session (stop, update activity timestamp, add notes).

    Body (JSON):
      status   — 'active', 'idle', or 'stopped'
      notes    — optional notes to append
    """
    data = await request.json()

    conn = sqlite3.connect(DB_PATH)
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


# ---------------------------------------------------------------------------
# Phase 2N — Prompt→Implementer→Validator loop
# ---------------------------------------------------------------------------


def _compile_prompt_internal(
    template_key: str,
    project_path: str,
    phase_id: str,
    params: dict,
) -> str:
    """Compile a prompt from a template without making HTTP calls.

    Uses the same logic as POST /api/prompt-templates/{key}/compile
    but operates directly on the database.
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
    conn.close()

    try:
        structure = json.loads(template["structure_json"])
    except json.JSONDecodeError:
        return "Error: Template structure is invalid JSON"

    # Merge params with defaults
    data = {
        "project_path": project_path,
        "phase_id": phase_id,
        "goal": params.get("goal", phase_id),
        "constraints": params.get("constraints", []),
        "implementation": params.get("implementation", ""),
        "allowed_files": params.get("allowed_files", []),
        "validation_commands": params.get("validation_commands", []),
    }
    # Add any extra params
    for k, v in params.items():
        if k not in data:
            data[k] = v

    lines = []
    for section in structure.get("sections", []):
        label = section.get("label", "")
        sec_type = section.get("type", "fixed")

        if sec_type == "fixed":
            value = section.get("value", "")
            for key, val in data.items():
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                value = value.replace("{" + key + "}", str(val))
            if label and value:
                lines.append(f"{label} {value}".strip())
            elif label:
                lines.append(label)
            elif value:
                lines.append(value)

        elif sec_type == "param":
            param_key = section.get("param_key", "")
            value = data.get(param_key, f"<{param_key}>")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"{label} {value}")

        elif sec_type == "list":
            param_key = section.get("param_key", "")
            items = data.get(param_key, [])
            if not isinstance(items, list):
                items = [str(items)]
            lines.append(label)
            for item in items:
                lines.append(f"  - {item}")

    return "\n".join(lines)


@app.post("/api/workflow/start")
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

    conn = sqlite3.connect(DB_PATH)
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


@app.put("/api/workflow/{run_id}/status")
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

    conn = sqlite3.connect(DB_PATH)
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


@app.get("/api/workflow/runs")
async def get_workflow_runs(limit: int = 20):
    """List recent workflow runs with status."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM workflow_runs
        ORDER BY started_at DESC LIMIT ?
    """, (limit,))
    runs = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"runs": runs}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)