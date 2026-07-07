"""C-3 migration: drop audited dead tables from the project DB.

Handoff 46 audit verdict (2026-07-04): 8 zero-row candidate tables were
originally KEPT because several were still referenced by code.

Fase F cleanup (handoff 59) removed the Prompt Sequence and Project Plan
sub-features, making 6 tables unreferenced hard-dead code.  Those 6 tables
were dropped with 0 rows:

  - prompt_sequences
  - prompt_sequence_steps
  - generated_prompts
  - project_plans
  - projects
  - reference_projects

Fase F-2 cleanup (handoff 60) removed a second dead cluster: the legacy
prompt-run / hitrate / template / pattern / compiler-field sub-features.
A 6-agent reachability audit confirmed these 7 tables are dead (no frontend
caller, no live route, no mcp-light/bridge/scripts consumer).  They are
removed regardless of row count — most contain only seed rows or stale
dev-test rows:

  - prompt_runs
  - prompt_templates
  - prompt_hitrates
  - template_model_hitrates
  - implementation_patterns
  - prompt_compiler_fields
  - prompt_compiler_field_options

DB-safety (rule #7 in 12_CODING_STANDARD.md): the only destructive
operation is `DROP TABLE IF EXISTS`, executed only for tables that (1)
appear in SAFE_TO_DROP and (2) have no FK dependents outside the drop list.
Tables are dropped in dependency order so children are removed before
parents.  A timestamped backup is written next to the DB file before any
drops.

Permanent exclusions (NEVER-DROP): i18n 4-layer tables, all bridge_*
tables, all UI/Frontend tables, and workflow_runs.
"""

import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import config  # noqa: E402

# Tables approved for conditional drop after handoff 59 + handoff 60 cleanup.
# A table is dropped only if it has no FK dependents outside this list;
# the migration orders children before parents.  Row count is NOT a blocker
# for this approved list (some tables contain seed/dev-test rows).
SAFE_TO_DROP = [
    # Handoff 59 (prompt-sequence / project-plan cluster)
    "prompt_sequences",
    "prompt_sequence_steps",
    "generated_prompts",
    "project_plans",
    "projects",
    "reference_projects",
    # Handoff 60 (prompt-run / hitrate / template / pattern cluster)
    "prompt_runs",
    "prompt_templates",
    "prompt_hitrates",
    "template_model_hitrates",
    "implementation_patterns",
    "prompt_compiler_fields",
    "prompt_compiler_field_options",
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


def _get_row_count(cursor: sqlite3.Cursor, table: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


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

        row_count = _get_row_count(cursor, table)
        external_dependents = [
            d for d in _get_fk_references_to(cursor, table) if d not in SAFE_TO_DROP
        ]

        if not external_dependents:
            candidates.add(table)
            print(f"  select: {table} (rows={row_count})")
        else:
            print(
                f"  reject: {table} (rows={row_count}, "
                f"has external FK dependents: {external_dependents})"
            )

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
