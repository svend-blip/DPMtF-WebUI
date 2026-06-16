"""{PROJECT_TITLE} — Minimal FastAPI backend.

Provides the core endpoints every DPMtF-governed WebUI needs:
  - Health check
  - i18n label resolution (4-layer architecture)
  - Available languages
  - Panel structure (visibility, collapse state, subgroups)
  - Static file serving

Domain-specific endpoints are added by the implementer.
"""

import os
import sqlite3
import config
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="{PROJECT_TITLE}")

DB_PATH = config.get_db_path()

# ── Static files ──────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

# Mount after explicit routes to avoid conflicts
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Health ────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    database_exists = os.path.exists(DB_PATH)
    return {
        "status": "healthy" if database_exists else "unhealthy",
        "app": "{PROJECT_TITLE}",
        "database_path": DB_PATH,
        "database_exists": database_exists,
    }


# ── i18n ──────────────────────────────────────────────

def get_ui_labels_for_domain(domain: str, locale: str) -> dict:
    """Resolve labels via 4-layer i18n architecture.

    ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations.
    Fallback chain: requested locale → en-US → default_text → label_key.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.slot_key, l.label_key, l.default_text,
               COALESCE(t_en.translation, l.default_text, l.label_key) AS text_en,
               COALESCE(t_req.translation, t_en.translation, l.default_text, l.label_key) AS text_req
        FROM ui_text_slots s
        JOIN ui_text_slot_labels sl ON s.slot_key = sl.slot_key
        JOIN ui_labels l ON sl.label_key = l.label_key
        LEFT JOIN ui_label_translations t_en ON l.label_key = t_en.label_key AND t_en.locale = 'en-US'
        LEFT JOIN ui_label_translations t_req ON l.label_key = t_req.label_key AND t_req.locale = ?
        WHERE sl.label_domain = ?
    """, (locale, domain))

    labels = {}
    for row in cursor.fetchall():
        r = dict(row)
        labels[r["slot_key"]] = r["text_req"] if r["text_req"] else r["text_en"]

    conn.close()
    return labels


@app.get("/api/ui-labels/{label_domain}")
async def get_ui_labels(label_domain: str, locale: str = "en-US"):
    """Return resolved labels for a domain."""
    labels = get_ui_labels_for_domain(label_domain, locale)
    return {
        "label_domain": label_domain,
        "locale": locale,
        "labels": labels,
    }


@app.get("/api/available-languages")
async def get_available_languages():
    """Return list of available locales from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT locale FROM ui_label_translations
        UNION
        SELECT 'en-US' AS locale
        ORDER BY locale
    """)
    locales = [dict(r)["locale"] for r in cursor.fetchall()]
    conn.close()

    # Map locale codes to human-readable labels
    locale_labels = {
        "en-US": "English",
        "da-DK": "Dansk",
        "de-DE": "Deutsch",
        "sv-SE": "Svenska",
    }

    return {
        "languages": [
            {"locale": loc, "label": locale_labels.get(loc, loc)}
            for loc in locales
        ]
    }


# ── Panel Structure ───────────────────────────────────

@app.get("/api/panel-structure")
async def get_panel_structure(locale: str = "en-US"):
    """Return full panel hierarchy with subgroups, visibility, and collapse states."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT group_name, state, is_visible FROM user_panel_groups WHERE user_id = 'default'"
    )
    group_rows = {r["group_name"]: r for r in cursor.fetchall()}

    cursor.execute(
        "SELECT * FROM panel_subgroups WHERE is_visible = 1 ORDER BY sort_order"
    )
    subgroups = [dict(r) for r in cursor.fetchall()]

    # Slot mappings for subgroups
    cursor.execute("SELECT * FROM panel_subgroup_mappings")
    mappings = {}
    for r in cursor.fetchall():
        sg = r["subgroup_key"]
        if sg not in mappings:
            mappings[sg] = []
        mappings[sg].append(r["slot_key"])

    # Subgroup collapse states
    cursor.execute(
        "SELECT group_name, state FROM user_panel_groups WHERE user_id = 'default' AND group_name LIKE 'sg_%'"
    )
    subgroup_states = {r["group_name"]: r["state"] for r in cursor.fetchall()}

    group_names = ["daily", "journals", "reports", "periodic", "setup"]
    result = {}
    title_field = "title_da" if locale == "da-DK" else "title_en"

    for gn in group_names:
        gr = group_rows.get(gn)
        is_visible = gr["is_visible"] if gr else 1
        state = gr["state"] if gr else "expanded"

        group_subgroups = [sg for sg in subgroups if sg["group_name"] == gn]

        if group_subgroups:
            subgroup_list = []
            for sg in group_subgroups:
                subgroup_list.append({
                    "key": sg["subgroup_key"],
                    "title": sg[title_field],
                    "is_visible": bool(sg["is_visible"]),
                    "state": subgroup_states.get(sg["subgroup_key"], "expanded"),
                    "slots": mappings.get(sg["subgroup_key"], []),
                })
        else:
            subgroup_list = [{
                "key": f"sg_{gn}_all",
                "title": "",
                "is_visible": True,
                "state": "expanded",
                "slots": [],
            }]

        result[gn] = {
            "is_visible": bool(is_visible),
            "state": state,
            "subgroups": subgroup_list,
        }

    conn.close()
    return {"groups": result}


@app.post("/api/panel-structure/subgroup-state")
async def save_subgroup_state(request: Request):
    """Save collapse state for a panel subgroup."""
    data = await request.json()
    subgroup_key = data.get("subgroup_key")
    state = data.get("state", "expanded")

    if not subgroup_key:
        raise HTTPException(status_code=400, detail="subgroup_key required")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
        VALUES ('default', ?, ?, 1, datetime('now'))
    """, (subgroup_key, state))
    conn.commit()
    conn.close()
    return {"status": "saved", "subgroup_key": subgroup_key, "state": state}


@app.post("/api/panel-structure/group-state")
async def save_group_state(request: Request):
    """Save collapse state for a panel group."""
    data = await request.json()
    group_name = data.get("group_name")
    state = data.get("state", "expanded")

    if not group_name:
        raise HTTPException(status_code=400, detail="group_name required")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_panel_groups (user_id, group_name, state, is_visible, updated_at)
        VALUES ('default', ?, ?, 1, datetime('now'))
    """, (group_name, state))
    conn.commit()
    conn.close()
    return {"status": "saved", "group_name": group_name, "state": state}
