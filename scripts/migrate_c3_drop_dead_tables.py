"""C-3 migration: drop audited zero-row dead tables from the project DB.

Handoff 46 audit verdict (2026-07-04): 8 zero-row candidate tables were
originally KEPT because several were still referenced by code.
Fase F cleanup (handoff 59) removed the Prompt Sequence and Project Plan
endpoints, making the following 6 tables unreferenced hard-dead code:

  - prompt_sequences
  - prompt_sequence_steps
  - generated_prompts
  - project_plans
  - frontend_panels
  - panel_classifications

After the code cleanup these tables still had zero rows.  This migration
backs up the database, re-runs the 3 safety checks (0 rows, no code refs,
no FK dependents), and drops only the tables that still PASS all checks.

Two additional 0-row tables from the original audit, projects and
reference_projects, were already unreferenced in code; they remain in
the candidate list so this script can drop them if the re-audit confirms
they are empty and have no FK dependents.

DB-safety (rule #7 in 12_CODING_STANDARD.md): the only destructive
operation is `DROP TABLE IF EXISTS`, executed only for tables that (1)
appear in SAFE_TO_DROP, (2) currently have 0 rows, and (3) have no FK
dependents.  A timestamped backup is written next to the DB file before
any drops.
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import config  # noqa: E402

# Tables approved for conditional drop after handoff 59 code cleanup.
# A table is dropped only if it is CURRENTLY empty, has no FK dependents
# outside this list, and the migration can order children before parents.
SAFE_TO_DROP = [
    "prompt_sequences",
    "prompt_sequence_steps",
    "generated_prompts",
    "project_plans",
    "projects",
    "reference_projects",
]


def _backup_db(db_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = db_path.with_suffix(f".pre-c3-{timestamp}.bak")
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def _get_fk_references_to(cursor: sqlite3.Cursor, table: str) -> list[str]:
    """Return table names that currently reference `table` via a FK."""
    dependents: list[str] = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (other_table,) in cursor.fetchall():
        cursor.execute(f"PRAGMA foreign_key_list({other_table})")
        for row in cursor.fetchall():
            # row layout: (id, seq, ref_table, from_col, to_col, ...)
            if len(row) >= 3 and row[2] == table:
                dependents.append(other_table)
                break
    return dependents


def _check_zero_rows(cursor: sqlite3.Cursor, table: str) -> tuple[bool, int]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    return count == 0, count


def _build_drop_order(cursor: sqlite3.Cursor, selected: set[str]) -> list[str]:
    """Return selected tables ordered so children are dropped before parents."""
    order: list[str] = []
    visited: set[str] = set()

    def visit(table: str):
        if table in visited:
            return
        visited.add(table)
        for dep in _get_fk_references_to(cursor, table):
            if dep in selected:
                visit(dep)
        order.append(table)

    for table in selected:
        visit(table)
    return order


def main():
    db_path = Path(config.get_db_path())
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    candidates: set[str] = set()
    for table in SAFE_TO_DROP:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            print(f"  skip: {table} does not exist")
            continue

        zero_rows, row_count = _check_zero_rows(cursor, table)
        external_dependents = [
            d for d in _get_fk_references_to(cursor, table) if d not in SAFE_TO_DROP
        ]

        if zero_rows and not external_dependents:
            candidates.add(table)
            print(f"  select: {table} (rows={row_count}, no external FK dependents)")
        else:
            reason = []
            if not zero_rows:
                reason.append(f"rows={row_count}")
            if external_dependents:
                reason.append(f"has external FK dependents: {external_dependents}")
            print(f"  reject: {table} ({', '.join(reason)})")

    if not candidates:
        conn.close()
        print("C-3 audit: no tables are safe to drop in the current DB state.")
        return

    _backup_db(db_path)

    drop_order = _build_drop_order(cursor, candidates)
    for table in drop_order:
        print(f"DROP TABLE IF EXISTS {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()
    conn.close()
    print(f"Dropped {len(drop_order)} table(s).")


if __name__ == "__main__":
    main()
