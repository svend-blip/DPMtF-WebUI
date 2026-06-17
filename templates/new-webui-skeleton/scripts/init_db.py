"""{PROJECT_NAME} — Database initialization and seed script.

Creates the 7 essential tables every DPMtF-governed WebUI needs:
  - i18n: ui_text_slots, ui_text_slot_labels, ui_labels, ui_label_translations
  - Panel structure: user_panel_groups, panel_subgroups, panel_subgroup_mappings

Seeds essential labels in da-DK, en-US, de-DE, and sv-SE locales.
Idempotent — safe to re-run (INSERT OR IGNORE/REPLACE).
"""

import sqlite3
from pathlib import Path
from config import get_db_path

DB_PATH = get_db_path()
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ── i18n Tables ───────────────────────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_text_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_text_slot_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key TEXT NOT NULL,
    label_key TEXT NOT NULL,
    label_domain TEXT NOT NULL DEFAULT 'main',
    UNIQUE(slot_key, label_key)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_key TEXT UNIQUE NOT NULL,
    default_text TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ui_label_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_key TEXT NOT NULL,
    locale TEXT NOT NULL,
    translation TEXT NOT NULL,
    UNIQUE(label_key, locale)
)
""")

# ── Panel Structure Tables ────────────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_panel_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    group_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'expanded',
    is_visible INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, group_name)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subgroup_key TEXT UNIQUE NOT NULL,
    group_name TEXT NOT NULL,
    title_en TEXT NOT NULL DEFAULT '',
    title_da TEXT NOT NULL DEFAULT '',
    is_visible INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS panel_subgroup_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subgroup_key TEXT NOT NULL,
    slot_key TEXT NOT NULL,
    UNIQUE(subgroup_key, slot_key)
)
""")

# ── Seed: UI Labels ───────────────────────────────────

labels_seed = [
    # (label_key, default_text, description)
    ("lbl_page_title", "{PROJECT_TITLE}", "Page title"),
    ("lbl_heading_main", "{PROJECT_TITLE}", "Main heading"),
    ("pg_daily", "\U0001f4cb Daily", "Daily panel group"),
    ("pg_journals", "\U0001f4d3 Journals", "Journals panel group"),
    ("pg_reports", "\U0001f4ca Reports", "Reports panel group"),
    ("pg_periodic", "↻ Periodic", "Periodic panel group"),
    ("pg_setup", "⚙️ Setup", "Setup panel group"),
    ("lbl_status_loading", "Loading...", "Loading status"),
    ("lbl_status_error_prefix", "Error: ", "Error prefix"),
    ("lbl_lang_selector", "Language", "Language selector label"),
]

for label_key, default_text, description in labels_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_labels (label_key, default_text, description)
        VALUES (?, ?, ?)
    """, (label_key, default_text, description))

# ── Seed: Translations ────────────────────────────────

translations_seed = [
    # (label_key, locale, translation)
    # da-DK
    ("lbl_page_title", "da-DK", "{PROJECT_TITLE}"),
    ("lbl_heading_main", "da-DK", "{PROJECT_TITLE}"),
    ("pg_daily", "da-DK", "\U0001f4cb Daglig"),
    ("pg_journals", "da-DK", "\U0001f4d3 Journaler"),
    ("pg_reports", "da-DK", "\U0001f4ca Rapporter"),
    ("pg_periodic", "da-DK", "↻ Periodisk"),
    ("pg_setup", "da-DK", "⚙️ Opsætning"),
    ("lbl_status_loading", "da-DK", "Indlæser..."),
    ("lbl_status_error_prefix", "da-DK", "Fejl: "),
    ("lbl_lang_selector", "da-DK", "Sprog"),
    # de-DE
    ("lbl_page_title", "de-DE", "{PROJECT_TITLE}"),
    ("lbl_heading_main", "de-DE", "{PROJECT_TITLE}"),
    ("pg_daily", "de-DE", "\U0001f4cb Täglich"),
    ("pg_journals", "de-DE", "\U0001f4d3 Journale"),
    ("pg_reports", "de-DE", "\U0001f4ca Berichte"),
    ("pg_periodic", "de-DE", "↻ Periodisch"),
    ("pg_setup", "de-DE", "⚙️ Einrichtung"),
    ("lbl_status_loading", "de-DE", "Laden..."),
    ("lbl_status_error_prefix", "de-DE", "Fehler: "),
    ("lbl_lang_selector", "de-DE", "Sprache"),
    # sv-SE
    ("lbl_page_title", "sv-SE", "{PROJECT_TITLE}"),
    ("lbl_heading_main", "sv-SE", "{PROJECT_TITLE}"),
    ("pg_daily", "sv-SE", "\U0001f4cb Daglig"),
    ("pg_journals", "sv-SE", "\U0001f4d3 Journaler"),
    ("pg_reports", "sv-SE", "\U0001f4ca Rapporter"),
    ("pg_periodic", "sv-SE", "↻ Periodisk"),
    ("pg_setup", "sv-SE", "⚙️ Inställningar"),
    ("lbl_status_loading", "sv-SE", "Laddar..."),
    ("lbl_status_error_prefix", "sv-SE", "Fel: "),
    ("lbl_lang_selector", "sv-SE", "Språk"),
]

for label_key, locale, translation in translations_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_label_translations (label_key, locale, translation)
        VALUES (?, ?, ?)
    """, (label_key, locale, translation))

# ── Seed: Text Slots ──────────────────────────────────

slots_seed = [
    # (slot_key, description)
    ("lbl_page_title", "Page title"),
    ("lbl_heading_main", "Main heading"),
    ("pg_daily", "Daily panel group header"),
    ("pg_journals", "Journals panel group header"),
    ("pg_reports", "Reports panel group header"),
    ("pg_periodic", "Periodic panel group header"),
    ("pg_setup", "Setup panel group header"),
    ("lbl_status_loading", "Loading status text"),
    ("lbl_status_error_prefix", "Error message prefix"),
    ("lbl_lang_selector", "Language selector label"),
]

for slot_key, description in slots_seed:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slots (slot_key, description)
        VALUES (?, ?)
    """, (slot_key, description))

# ── Seed: Slot → Label Mappings ───────────────────────

slot_label_mappings = [
    # (slot_key, label_key, label_domain)
    ("lbl_page_title", "lbl_page_title", "main"),
    ("lbl_heading_main", "lbl_heading_main", "main"),
    ("pg_daily", "pg_daily", "main"),
    ("pg_journals", "pg_journals", "main"),
    ("pg_reports", "pg_reports", "main"),
    ("pg_periodic", "pg_periodic", "main"),
    ("pg_setup", "pg_setup", "main"),
    ("lbl_status_loading", "lbl_status_loading", "main"),
    ("lbl_status_error_prefix", "lbl_status_error_prefix", "main"),
    ("lbl_lang_selector", "lbl_lang_selector", "main"),
]

for slot_key, label_key, domain in slot_label_mappings:
    cursor.execute("""
        INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key, label_domain)
        VALUES (?, ?, ?)
    """, (slot_key, label_key, domain))

# ── Seed: Panel Groups (default state) ────────────────

group_names = ["daily", "journals", "reports", "periodic", "setup"]
for gn in group_names:
    cursor.execute("""
        INSERT OR IGNORE INTO user_panel_groups (user_id, group_name, state, is_visible)
        VALUES ('default', ?, 'expanded', 1)
    """, (gn,))

conn.commit()
conn.close()

print("Database initialized: " + DB_PATH)
print("Tables created: ui_text_slots, ui_text_slot_labels, ui_labels, ui_label_translations, user_panel_groups, panel_subgroups, panel_subgroup_mappings")
print("Seed data: 10 labels x 4 locales, 10 text slots, 5 panel groups")
