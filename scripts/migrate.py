"""DPMtF-WebUI — versioned SQL migration runner (Fase E-2).

Discovers scripts/db/*.sql migration files, applies pending migrations in
numeric order, and records them in schema_migrations. Idempotent and safe
to re-run.

    python3 scripts/migrate.py             apply what is pending
    python3 scripts/migrate.py --status    list what is pending; change nothing
    python3 scripts/migrate.py --help

Only the bare invocation (optionally with --db) writes to the database.
"""

import argparse
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
    """Migration files in apply order — sorted by the WHOLE filename.

    Two consequences worth knowing before adding a file here:

    1. A migration must be numbered after every migration whose columns it
       writes. `025_llama_sg_flow.sql` was originally `005_`, and it inserts
       allocator_client (added by 008), fresh_session_command (009) and
       workdir_mode (023). Existing databases never noticed, because they had
       applied 001-024 before the file was written. Every fresh install died
       on it. Number by dependency, not by when you wrote it.

    2. Duplicate numbers sort by the text after the number, so
       `007_job_queue_tables` runs before `007_remove_deprecated_columns`.
       That order is correct and already applied everywhere. Do not renumber
       them to tidy up: `schema_migrations` tracks a migration by filename, so
       a rename makes it pending again — and re-running a migration that
       rebuilds tables to drop columns is not a no-op.
    """
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


def baseline_migration() -> str | None:
    """Filename of the first migration: the schema the seeds were written for."""
    migrations = _discover_migrations()
    return migrations[0].name if migrations else None


def is_fresh(db_path: str | None = None) -> bool:
    """True when the database does not exist yet or holds no table at all.

    Asking never creates the file. A fresh database is the one case where
    init_db.py must seed BEFORE the data migrations run: the live database
    had its rows first and was changed by each migration, and a migration
    that reads or updates seeded rows does nothing when there are none.
    """
    target_db = db_path or config.get_db_path()
    if not Path(target_db).is_file():
        return True
    conn = sqlite3.connect(f"file:{Path(target_db).resolve()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
    finally:
        conn.close()
    return row[0] == 0


def _dir_exists(path: str) -> bool:
    return os.path.isdir(path)


def clear_missing_target_paths(db_path: str | None = None) -> list[tuple[str, str]]:
    """Clear bridge_flows.target_project_path where the directory is not here.

    For a FRESH install only (init_db.py decides). Several flow migrations
    write the target paths of the machine they were written on. There they are
    right; on any other machine bridge_lib refuses every dispatch of those
    flows with "targets project path ..., which does not exist". A flow with
    no target works in Father, and the path is set in the flow editor.

    Never run this on an existing database: a path that is missing right now
    (an unmounted disk, a repository being moved) is the installation's own.

    Returns the (flow_key, path) pairs that were cleared.
    """
    target_db = db_path or config.get_db_path()
    conn = sqlite3.connect(target_db)
    try:
        rows = conn.execute(
            "SELECT flow_key, target_project_path FROM bridge_flows "
            "WHERE COALESCE(TRIM(target_project_path), '') != ''"
        ).fetchall()
        cleared = [(flow_key, path) for flow_key, path in rows if not _dir_exists(path.strip())]
        conn.executemany(
            "UPDATE bridge_flows SET target_project_path = NULL, updated_at = datetime('now') "
            "WHERE flow_key = ?",
            [(flow_key,) for flow_key, _ in cleared],
        )
        conn.commit()
    finally:
        conn.close()
    return cleared


def run_migrations(db_path: str | None = None, stop_after: str | None = None) -> dict:
    """Apply pending SQL migrations and return a summary.

    Args:
        db_path: Optional DB path override. Defaults to config.get_db_path().
        stop_after: Optional migration filename; pending migrations are
            applied up to and including it, and the rest are left pending.
            init_db.py uses it on a fresh database to apply the baseline,
            seed, and only then apply everything else.

    Returns:
        dict with keys: applied (list[str]), skipped (int), db_path (str).

    Raises:
        RuntimeError: if a migration fails (after rollback).
    """
    target_db = db_path or config.get_db_path()
    Path(target_db).parent.mkdir(parents=True, exist_ok=True)

    migrations = _discover_migrations()
    if stop_after is not None:
        names = [m.name for m in migrations]
        if stop_after not in names:
            raise RuntimeError(f"stop_after names no migration: {stop_after}")
        migrations = migrations[: names.index(stop_after) + 1]
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


def pending_migrations(db_path: str | None = None) -> dict:
    """What run_migrations would apply, without applying or creating anything.

    The database is opened read-only. One that does not exist yet, or that
    predates schema_migrations, has everything pending — and is left exactly
    as it was found: no file is created and no bookkeeping table is added.
    """
    target_db = db_path or config.get_db_path()
    migrations = _discover_migrations()
    already_applied: set[str] = set()
    if Path(target_db).is_file():
        conn = sqlite3.connect(f"file:{Path(target_db).resolve()}?mode=ro", uri=True)
        try:
            already_applied = _applied_migrations(conn)
        finally:
            conn.close()
    pending = [m.name for m in migrations if m.name not in already_applied]
    return {"pending": pending, "applied": len(migrations) - len(pending), "db_path": target_db}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="migrate.py",
        description=(
            "Apply the pending SQL migrations under scripts/db/ to the DPMtF "
            "database, in filename order, recording each in schema_migrations. "
            "Run without arguments to apply; --status only looks."
        ),
    )
    parser.add_argument(
        "--status", action="store_true",
        help="list the pending migrations and exit; the database is opened "
             "read-only and nothing is created or changed",
    )
    parser.add_argument(
        "--db", metavar="PATH", default=None,
        help="database file to use instead of the configured one",
    )
    # argparse exits 0 on --help and 2 on anything it does not know — before
    # any of the code below runs, which is the point: until 2026-09-20 main()
    # ignored argv, so `migrate.py --help` (or a typo) applied every pending
    # migration to the live database.
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.status:
        report = pending_migrations(args.db)
        print(
            f"{len(report['pending'])} pending, {report['applied']} already applied. "
            f"DB: {report['db_path']}"
        )
        for name in report["pending"]:
            print(f"  - {name}")
        return 0

    summary = run_migrations(args.db)
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
