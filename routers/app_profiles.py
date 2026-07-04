"""App Profiles router (app profile CRUD).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (2 total):
  GET    /api/app-profiles
  POST   /api/app-profiles/defaults

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1).
"""

import sqlite3

from fastapi import APIRouter

from routers.shared import get_db_path


router = APIRouter(tags=["app_profiles"])


# ── Module-level data (moved verbatim from app.py) ────────────────


# Default app profiles
DEFAULT_APP_PROFILES = [
    {"name": "Minimal Starter App", "description": "Basic starter profile with essential panels"},
    {"name": "Pipeline App", "description": "Pipeline-focused profile"},
    {"name": "Operational Dashboard App", "description": "Operational dashboard profile"},
    {"name": "Full Reference App", "description": "Complete reference profile"},
    {"name": "Custom Selected Panels", "description": "Custom panels chosen by user"},
]


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── GET /api/app-profiles ──

@router.get("/api/app-profiles")
async def get_app_profiles():
    conn = sqlite3.connect(get_db_path())
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


# ── POST /api/app-profiles/defaults ──

@router.post("/api/app-profiles/defaults")
async def create_default_profiles():
    conn = sqlite3.connect(get_db_path())
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


