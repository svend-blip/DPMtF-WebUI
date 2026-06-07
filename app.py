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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)