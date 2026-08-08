"""i18n label helpers — find-or-create instead of create-per-slot.

Slot keys are unique by design, but labels are meant to be SHARED: when
several slots present the same text and help text, they map to ONE label
(the 4-layer architecture explicitly allows many slots per label). In
practice generation created a new label per slot, which is why duplicate
labels exist at all. Every programmatic label creation goes through
``find_or_create_label`` so an identical label is reused instead of
duplicated.

Usage (in init_db.py-style seeds and Python migrations):

    from scripts.i18n_lib import find_or_create_label, map_slot

    label_key = find_or_create_label(
        cursor,
        label_key_hint="lbl_save_button",
        default_text="Save",
        description="Generic save button",
        translations={
            "en-US": "Save", "da-DK": "Gem",
            "de-DE": "Speichern", "es-ES": "Guardar",
        },
    )
    map_slot(cursor, "panel_x_save_btn", label_key)

The four locales are MANDATORY (12_CODING_STANDARD.md); a missing one is
a ValueError here, not a silent gap discovered by a reviewer later.
"""
from __future__ import annotations

import sqlite3

MANDATORY_LOCALES = ("en-US", "da-DK", "de-DE", "es-ES")


def find_or_create_label(
    cursor: sqlite3.Cursor,
    label_key_hint: str,
    default_text: str,
    description: str,
    translations: dict[str, str],
    label_domain: str = "main",
) -> str:
    """Return the label_key for (default_text, description) — existing if an
    identical active label exists, otherwise newly created with all four
    mandatory locales.

    Reuse matches on default_text + description (case-insensitive). The
    hint is only used when a NEW label is created; on reuse the existing
    key is returned and the caller maps its slot to that.
    """
    missing = [loc for loc in MANDATORY_LOCALES if not (translations.get(loc) or "").strip()]
    if missing:
        raise ValueError(
            f"Label '{label_key_hint}' is missing mandatory locale(s): "
            f"{', '.join(missing)} — all of {', '.join(MANDATORY_LOCALES)} are required"
        )

    row = cursor.execute(
        """SELECT label_key, label_id FROM ui_labels
           WHERE lower(default_text) = lower(?)
             AND lower(COALESCE(description, '')) = lower(COALESCE(?, ''))
             AND is_active = 1
           ORDER BY id LIMIT 1""",
        (default_text.strip(), (description or "").strip()),
    ).fetchone()
    if row:
        return row[0]

    label_id = _next_label_id(cursor)
    cursor.execute(
        """INSERT INTO ui_labels
           (label_id, label_key, label_domain, default_text, description,
            is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
        (label_id, label_key_hint, label_domain, default_text.strip(),
         (description or "").strip()),
    )
    for locale in MANDATORY_LOCALES:
        cursor.execute(
            """INSERT INTO ui_label_translations
               (label_id, locale, translated_text, is_active,
                created_at, updated_at)
               VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))""",
            (label_id, locale, translations[locale].strip()),
        )
    return label_key_hint


def map_slot(cursor: sqlite3.Cursor, slot_key: str, label_key: str,
             slot_description: str = "") -> None:
    """Idempotently register a slot and map it to a label."""
    cursor.execute(
        """INSERT OR IGNORE INTO ui_text_slots
           (slot_key, description, created_at, updated_at)
           VALUES (?, ?, datetime('now'), datetime('now'))""",
        (slot_key, slot_description),
    )
    cursor.execute(
        """INSERT OR REPLACE INTO ui_text_slot_labels
           (slot_key, label_key, created_at)
           VALUES (?, ?, datetime('now'))""",
        (slot_key, label_key),
    )


def _next_label_id(cursor: sqlite3.Cursor) -> str:
    """Allocate the next LBL-<n> id after the current numeric maximum."""
    row = cursor.execute(
        """SELECT MAX(CAST(SUBSTR(label_id, 5) AS INTEGER))
           FROM ui_labels WHERE label_id LIKE 'LBL-%'"""
    ).fetchone()
    next_num = (row[0] or 1000000) + 1
    return f"LBL-{next_num}"
