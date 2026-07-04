"""Governance router (ADRs — Architecture Decision Records).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definition.
Only the code location moved and the decorator prefix changed
(`@app.X` -> `@router.X`).

Endpoints moved:
  GET    /api/architecture-decision-records

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1) — this preserves the test fixture's monkeypatch
of `app.DB_PATH` and avoids circular imports at module top-level.
"""

import sqlite3

from fastapi import APIRouter

from routers.shared import get_db_path


router = APIRouter(tags=["governance"])


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── architecture_decision_records_get ──

@router.get("/api/architecture-decision-records")
async def get_architecture_decision_records():
    conn = sqlite3.connect(get_db_path())
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

