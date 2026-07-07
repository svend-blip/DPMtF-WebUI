"""DPMtF-WebUI — versioned SQL migration runner (Fase E-2).

Discovers scripts/db/*.sql migration files, applies pending migrations in
numeric order, and records them in schema_migrations. Idempotent and safe
to re-run.
"""

import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so 'import config' works
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent / "db"

SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    applied_at TEXT NOT NULL
);
"""

_MIGRATION_FILENAME_RE = re.compile(r"^\d{3}_.+\.sql$")


def _discover_migrations() -> list[Path]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    files = [
        p for p in MIGRATIONS_DIR.iterdir()
        if p.is_file() and _MIGRATION_FILENAME_RE.match(p.name)
    ]
    return sorted(files, key=lambda p: p.name)


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    try:
        rows = conn.execute(
            "SELECT filename FROM schema_migrations"
        ).fetchall()
        return {row[0] for row in rows}
    except sqlite3.OperationalError:
        # schema_migrations does not exist yet.
        return set()


def run_migrations(db_path: str | None = None) -> dict:
    """Apply pending SQL migrations and return a summary.

    Args:
        db_path: Optional DB path override. Defaults to config.get_db_path().

    Returns:
        dict with keys: applied (list[str]), skipped (int), db_path (str).

    Raises:
        RuntimeError: if a migration fails (after rollback).
    """
    target_db = db_path or config.get_db_path()
    Path(target_db).parent.mkdir(parents=True, exist_ok=True)

    migrations = _discover_migrations()
    applied: list[str] = []

    conn = sqlite3.connect(target_db)
    try:
        conn.executescript(SCHEMA_MIGRATIONS_DDL)
        already_applied = _applied_migrations(conn)

        for migration in migrations:
            if migration.name in already_applied:
                continue

            sql = migration.read_text(encoding="utf-8")
            try:
                conn.execute("BEGIN")
                conn.executescript(sql)
                conn.execute(
                    """
                    INSERT INTO schema_migrations (filename, applied_at)
                    VALUES (?, ?)
                    """,
                    (
                        migration.name,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
                applied.append(migration.name)
            except Exception as exc:
                conn.rollback()
                raise RuntimeError(
                    f"Migration {migration.name} failed: {exc}"
                ) from exc
    finally:
        conn.close()

    skipped = len(migrations) - len(applied)
    return {"applied": applied, "skipped": skipped, "db_path": target_db}


def main() -> int:
    summary = run_migrations()
    print(
        f"Applied {len(summary['applied'])} migration(s), "
        f"skipped {summary['skipped']} already-applied. "
        f"DB: {summary['db_path']}"
    )
    for name in summary["applied"]:
        print(f"  + {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
