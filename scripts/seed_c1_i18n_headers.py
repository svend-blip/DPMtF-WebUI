"""C-1 seed: add 15 new i18n labels for table headers + card titles in dpmtf-app.js.

DB-safety: this script ONLY does parameterized INSERT OR IGNORE / INSERT OR
REPLACE. It does NOT DROP, DELETE, or CREATE TABLE. The script is
idempotent and safe to re-run.

New slot_keys (15 total):
  Bridge th-headers (11): lbl_bridge_th_{panel,slot,type,label_key,
    label_text,method,path,dataset,table,script,purpose}
  System h4-headers (4):  lbl_system_h4_{validation,platform,
    claude_sessions,workflow_loop}

Each label gets seed in en-US, da-DK, de-DE, sv-SE (matching the
existing init_db.py translation pattern).

Handoff 45: Fase C-1 of the Optimization Roadmap (hygiene).
"""
import sqlite3

DB_PATH = "databases/dpmtf.db"

# (slot_key, description) — for ui_text_slots
SLOTS = [
    ("lbl_bridge_th_panel", "Bridge roles table — Panel column header"),
    ("lbl_bridge_th_slot", "Bridge roles table — Slot column header"),
    ("lbl_bridge_th_type", "Bridge roles table — Type column header"),
    ("lbl_bridge_th_label_key", "Bridge labels table — Key column header"),
    ("lbl_bridge_th_label_text", "Bridge labels table — Text column header"),
    ("lbl_bridge_th_method", "Bridge endpoints table — Method column header"),
    ("lbl_bridge_th_path", "Bridge endpoints table — Path column header"),
    ("lbl_bridge_th_purpose", "Bridge endpoints table — Purpose column header"),
    ("lbl_bridge_th_dataset", "Bootstrap dataset table — Dataset column header"),
    ("lbl_bridge_th_table", "Bootstrap dataset table — Table column header"),
    ("lbl_bridge_th_script", "Bootstrap dataset table — Script column header"),
    ("lbl_system_h4_validation", "System section — Validation card title"),
    ("lbl_system_h4_platform", "System section — Platform card title"),
    ("lbl_system_h4_claude_sessions", "System section — Claude Code Sessions card title"),
    ("lbl_system_h4_workflow_loop", "System section — Workflow P→I→V Loop card title"),
]

# (label_id, label_key, label_domain, default_text, description) — for ui_labels
# label_id: uses LBL-10XXXXX range to avoid collision (highest existing = LBL-1000354)
LABELS = [
    # Bridge th headers
    ("LBL-1000355", "lbl_bridge_th_panel", "main", "Panel", "Bridge roles table Panel header"),
    ("LBL-1000356", "lbl_bridge_th_slot", "main", "Slot", "Bridge roles table Slot header"),
    ("LBL-1000357", "lbl_bridge_th_type", "main", "Type", "Bridge roles table Type header"),
    ("LBL-1000358", "lbl_bridge_th_label_key", "main", "Key", "Bridge labels table Key header"),
    ("LBL-1000359", "lbl_bridge_th_label_text", "main", "Text", "Bridge labels table Text header"),
    ("LBL-1000360", "lbl_bridge_th_method", "main", "Method", "Bridge endpoints Method header"),
    ("LBL-1000361", "lbl_bridge_th_path", "main", "Path", "Bridge endpoints Path header"),
    ("LBL-1000362", "lbl_bridge_th_purpose", "main", "Purpose", "Bridge endpoints Purpose header"),
    ("LBL-1000363", "lbl_bridge_th_dataset", "main", "Dataset", "Bootstrap dataset Dataset header"),
    ("LBL-1000364", "lbl_bridge_th_table", "main", "Table", "Bootstrap dataset Table header"),
    ("LBL-1000365", "lbl_bridge_th_script", "main", "Script", "Bootstrap dataset Script header"),
    # System h4 headers
    ("LBL-1000366", "lbl_system_h4_validation", "system_setup", "Validation", "System section Validation card title"),
    ("LBL-1000367", "lbl_system_h4_platform", "system_setup", "Platform", "System section Platform card title"),
    ("LBL-1000368", "lbl_system_h4_claude_sessions", "system_setup", "Claude Code Sessions", "System section Claude Code Sessions card title"),
    ("LBL-1000369", "lbl_system_h4_workflow_loop", "system_setup", "Workflow \u2014 P\u2192I\u2192V Loop", "System section Workflow PIV Loop card title"),
]

# (slot_key, label_key) — for ui_text_slot_labels
SLOT_LABEL_LINKS = [(s[0], s[0]) for s in SLOTS]

# (label_id, locale, translated_text) — for ui_label_translations
TRANSLATIONS = [
    # lbl_bridge_th_panel
    ("LBL-1000355", "en-US", "Panel"),
    ("LBL-1000355", "da-DK", "Panel"),
    ("LBL-1000355", "de-DE", "Panel"),
    ("LBL-1000355", "sv-SE", "Panel"),
    # lbl_bridge_th_slot
    ("LBL-1000356", "en-US", "Slot"),
    ("LBL-1000356", "da-DK", "Slot"),
    ("LBL-1000356", "de-DE", "Slot"),
    ("LBL-1000356", "sv-SE", "Slot"),
    # lbl_bridge_th_type
    ("LBL-1000357", "en-US", "Type"),
    ("LBL-1000357", "da-DK", "Type"),
    ("LBL-1000357", "de-DE", "Typ"),
    ("LBL-1000357", "sv-SE", "Typ"),
    # lbl_bridge_th_label_key
    ("LBL-1000358", "en-US", "Key"),
    ("LBL-1000358", "da-DK", "Nøgle"),
    ("LBL-1000358", "de-DE", "Schlüssel"),
    ("LBL-1000358", "sv-SE", "Nyckel"),
    # lbl_bridge_th_label_text
    ("LBL-1000359", "en-US", "Text"),
    ("LBL-1000359", "da-DK", "Tekst"),
    ("LBL-1000359", "de-DE", "Text"),
    ("LBL-1000359", "sv-SE", "Text"),
    # lbl_bridge_th_method
    ("LBL-1000360", "en-US", "Method"),
    ("LBL-1000360", "da-DK", "Metode"),
    ("LBL-1000360", "de-DE", "Methode"),
    ("LBL-1000360", "sv-SE", "Metod"),
    # lbl_bridge_th_path
    ("LBL-1000361", "en-US", "Path"),
    ("LBL-1000361", "da-DK", "Sti"),
    ("LBL-1000361", "de-DE", "Pfad"),
    ("LBL-1000361", "sv-SE", "Sökväg"),
    # lbl_bridge_th_purpose
    ("LBL-1000362", "en-US", "Purpose"),
    ("LBL-1000362", "da-DK", "Formål"),
    ("LBL-1000362", "de-DE", "Zweck"),
    ("LBL-1000362", "sv-SE", "Syfte"),
    # lbl_bridge_th_dataset
    ("LBL-1000363", "en-US", "Dataset"),
    ("LBL-1000363", "da-DK", "Datasæt"),
    ("LBL-1000363", "de-DE", "Datensatz"),
    ("LBL-1000363", "sv-SE", "Dataset"),
    # lbl_bridge_th_table
    ("LBL-1000364", "en-US", "Table"),
    ("LBL-1000364", "da-DK", "Tabel"),
    ("LBL-1000364", "de-DE", "Tabelle"),
    ("LBL-1000364", "sv-SE", "Tabell"),
    # lbl_bridge_th_script
    ("LBL-1000365", "en-US", "Script"),
    ("LBL-1000365", "da-DK", "Skript"),
    ("LBL-1000365", "de-DE", "Skript"),
    ("LBL-1000365", "sv-SE", "Skript"),
    # lbl_system_h4_validation
    ("LBL-1000366", "en-US", "Validation"),
    ("LBL-1000366", "da-DK", "Validering"),
    ("LBL-1000366", "de-DE", "Validierung"),
    ("LBL-1000366", "sv-SE", "Validering"),
    # lbl_system_h4_platform
    ("LBL-1000367", "en-US", "Platform"),
    ("LBL-1000367", "da-DK", "Platform"),
    ("LBL-1000367", "de-DE", "Plattform"),
    ("LBL-1000367", "sv-SE", "Plattform"),
    # lbl_system_h4_claude_sessions
    ("LBL-1000368", "en-US", "Claude Code Sessions"),
    ("LBL-1000368", "da-DK", "Claude Code-sessioner"),
    ("LBL-1000368", "de-DE", "Claude Code-Sitzungen"),
    ("LBL-1000368", "sv-SE", "Claude Code-sessioner"),
    # lbl_system_h4_workflow_loop
    ("LBL-1000369", "en-US", "Workflow \u2014 P\u2192I\u2192V Loop"),
    ("LBL-1000369", "da-DK", "Workflow \u2014 P\u2192I\u2192V-l\u00f8kke"),
    ("LBL-1000369", "de-DE", "Workflow \u2014 P\u2192I\u2192V-Schleife"),
    ("LBL-1000369", "sv-SE", "Workflow \u2014 P\u2192I\u2192V-slinga"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. ui_text_slots
    for slot_key, description in SLOTS:
        cursor.execute(
            "INSERT OR IGNORE INTO ui_text_slots (slot_key, description) "
            "VALUES (?, ?)",
            (slot_key, description),
        )

    # 2. ui_labels
    for label_id, label_key, label_domain, default_text, description in LABELS:
        cursor.execute(
            "INSERT OR IGNORE INTO ui_labels "
            "(label_id, label_key, label_domain, default_text, description, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (label_id, label_key, label_domain, default_text, description),
        )

    # 3. ui_text_slot_labels
    for slot_key, label_key in SLOT_LABEL_LINKS:
        cursor.execute(
            "INSERT OR IGNORE INTO ui_text_slot_labels (slot_key, label_key) "
            "VALUES (?, ?)",
            (slot_key, label_key),
        )

    # 4. ui_label_translations
    for label_id, locale, translated_text in TRANSLATIONS:
        cursor.execute(
            "INSERT OR REPLACE INTO ui_label_translations "
            "(label_id, locale, translated_text, is_active) "
            "VALUES (?, ?, ?, 1)",
            (label_id, locale, translated_text),
        )

    conn.commit()

    # Verify counts
    cursor.execute(
        "SELECT COUNT(*) FROM ui_text_slots WHERE slot_key LIKE 'lbl_bridge_th_%' "
        "OR slot_key LIKE 'lbl_system_h4_%'"
    )
    slots_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM ui_labels WHERE label_id LIKE 'LBL-10003%'"
    )
    labels_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM ui_text_slot_labels "
        "WHERE slot_key LIKE 'lbl_bridge_th_%' OR slot_key LIKE 'lbl_system_h4_%'"
    )
    links_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM ui_label_translations WHERE label_id LIKE 'LBL-10003%'"
    )
    translations_count = cursor.fetchone()[0]

    conn.close()

    print(f"Seed complete:")
    print(f"  ui_text_slots: {slots_count} new/updated")
    print(f"  ui_labels: {labels_count} new/updated")
    print(f"  ui_text_slot_labels: {links_count} new/updated")
    print(f"  ui_label_translations: {translations_count} new/updated")


if __name__ == "__main__":
    main()
