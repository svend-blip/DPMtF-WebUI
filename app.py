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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)