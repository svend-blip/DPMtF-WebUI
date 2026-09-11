"""Test migration 107: knowledge storage schema and retrieval log.

GOAL-DRAFT-002. Three properties the contract names are proven here:

1. the migration applies to a FRESH temp database,
2. it applies IDEMPOTENTLY a second time,
3. it EXPOSES the required columns.

Plus the two properties the contract's reviewer duties check by reading the
SQL: the statements are non-destructive, and the retrieval log is
append-oriented.

Everything runs against a temporary database under pytest's ``tmp_path``. The
production database at ``databases/dpmtf.db`` is never opened by this file —
the migration under test is applied to it by ``scripts/init_db.py``, not here.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

import migrate  # noqa: E402

MIGRATION_NAME = "107_knowledge_tables.sql"
MIGRATION_PATH = PROJECT_ROOT / "scripts" / "db" / MIGRATION_NAME

KNOWLEDGE_TABLES = {
    "knowledge_indexes",
    "knowledge_exclusions",
    "knowledge_retrieval_log",
}

REQUIRED_COLUMNS = {
    "knowledge_indexes": {
        "id", "scope", "provider", "location", "document_count", "status",
        "updated_at",
    },
    "knowledge_exclusions": {
        "id", "scope", "pattern", "kind", "enabled", "created_at",
    },
    "knowledge_retrieval_log": {
        "id", "provider", "scope", "query", "result_count", "sources",
        "retrieved_token_count", "retrieval_duration_ms", "agent_role",
        "run_id", "handoff_id", "created_at",
    },
}


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _strip_comments(sql: str) -> str:
    """Drop ``--`` line comments so a destructive-keyword scan reads statements.

    The migration's own header explains, in prose, that it contains no DROP,
    no DELETE and no ALTER. Scanning that prose for those words would match the
    explanation, not the SQL, so the comments go first.
    """
    return "\n".join(
        line.split("--", 1)[0] for line in sql.splitlines()
    )


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Column names of one table.

    `pragma_table_info()` is the table-valued form, which takes the table name
    as a bound parameter; the `PRAGMA table_info(x)` statement form cannot, so
    reading a schema would otherwise need string interpolation in SQL.
    """
    return {row[0] for row in conn.execute(
        "SELECT name FROM pragma_table_info(?)", (table,))}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    return {row["name"] for row in rows}


def _apply_file_only(db_path: str) -> None:
    """Apply just this migration's SQL to an empty database.

    Proves the file is self-contained: it depends on no earlier table, so a
    fresh install and a re-apply both run it the same way.
    """
    conn = _connect(db_path)
    try:
        conn.executescript(_migration_sql())
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def built_db(tmp_path_factory):
    """One database built the way a new installation builds it.

    Module-scoped deliberately: building it applies every migration under
    ``scripts/db/``, which costs seconds, and what each test below needs is a
    database in that state -- not its own private full build.
    """
    db_path = str(tmp_path_factory.mktemp("knowledge107") / "fresh.db")
    result = migrate.run_migrations(db_path)
    assert MIGRATION_NAME in result["applied"], (
        f"{MIGRATION_NAME} was not applied to a fresh database; "
        f"applied {len(result['applied'])} migration(s)")
    return db_path


@pytest.fixture
def fresh_db(built_db, tmp_path):
    """A private copy of the freshly-migrated database, for one test.

    Most tests write rows and a few assert on counts, so they must not share
    the module's build. Copying a migrated file is near-free; rebuilding it is
    not.
    """
    copy = str(tmp_path / "knowledge.db")
    shutil.copyfile(built_db, copy)
    return copy


# ── 1. applies to a fresh temp DB ────────────────────────────────────────

def test_migration_is_discoverable_by_the_runner():
    """The filename matches the runner's pattern and owns its number.

    Deliberately NOT an assertion that 107 is the last migration: the next
    draft in this series adds 108, and a test that goes red because a later
    migration legitimately landed would be a false failure charged to the
    wrong run. What must hold permanently is that the runner sees this file at
    all, and that its number is unique -- two files numbered 107 would apply in
    text order and quietly change this one's position.
    """
    names = [p.name for p in migrate._discover_migrations()]
    assert MIGRATION_NAME in names
    same_number = [n for n in names if n.split("_", 1)[0] == "107"]
    assert same_number == [MIGRATION_NAME], (
        f"migration number 107 is not unique: {same_number}")
    assert names == sorted(names), "discovery must stay in filename order"


def test_number_follows_the_previous_last_migration():
    """107 is one past 106, the last migration that existed before this run.

    A gap in 001..107 would mean a migration was renumbered or deleted --
    schema_migrations tracks by filename, so a rename makes it pending again
    and a re-run of a table-rebuilding migration is not a no-op.
    """
    numbers = sorted(int(p.name.split("_", 1)[0])
                     for p in migrate.MIGRATIONS_DIR.glob("*.sql"))
    assert 106 in numbers, "expected 106 in the migration history"
    assert numbers.count(107) == 1, "migration number 107 must appear exactly once"
    for wanted in range(1, 108):
        assert wanted in numbers, f"migration number {wanted:03d} is missing"


def test_applies_to_fresh_database(fresh_db):
    conn = _connect(fresh_db)
    try:
        assert KNOWLEDGE_TABLES <= _table_names(conn)
        logged = conn.execute(
            "SELECT filename FROM schema_migrations WHERE filename = ?",
            (MIGRATION_NAME,),
        ).fetchone()
        assert logged is not None, "runner did not record the migration"
    finally:
        conn.close()


def test_file_is_self_contained(tmp_path):
    """The SQL alone creates exactly the three knowledge tables and nothing else."""
    db_path = str(tmp_path / "solo.db")
    _apply_file_only(db_path)
    conn = _connect(db_path)
    try:
        created = _table_names(conn) - {"sqlite_sequence"}
        assert created == KNOWLEDGE_TABLES, (
            f"migration created unexpected tables: {created - KNOWLEDGE_TABLES}")
    finally:
        conn.close()


def test_no_seed_rows(tmp_path):
    """Schema only: the migration must not insert data of its own."""
    db_path = str(tmp_path / "seed_check.db")
    _apply_file_only(db_path)
    conn = _connect(db_path)
    try:
        # Literal statements, not an interpolated table name: SQLite cannot
        # bind one, and the project rule is no string-built SQL.
        counts = {
            "knowledge_indexes": conn.execute(
                "SELECT COUNT(*) FROM knowledge_indexes").fetchone()[0],
            "knowledge_exclusions": conn.execute(
                "SELECT COUNT(*) FROM knowledge_exclusions").fetchone()[0],
            "knowledge_retrieval_log": conn.execute(
                "SELECT COUNT(*) FROM knowledge_retrieval_log").fetchone()[0],
        }
        assert set(counts) == KNOWLEDGE_TABLES
        seeded = {t: n for t, n in counts.items() if n}
        assert not seeded, f"migration seeded rows: {seeded}"
    finally:
        conn.close()


# ── 2. applies idempotently a second time ────────────────────────────────

def test_second_run_does_not_reapply(fresh_db):
    """The runner skips it the second time (schema_migrations tracking)."""
    second = migrate.run_migrations(fresh_db)
    assert MIGRATION_NAME not in second["applied"], (
        "migration was applied twice by the runner")
    conn = _connect(fresh_db)
    try:
        assert KNOWLEDGE_TABLES <= _table_names(conn)
    finally:
        conn.close()


def test_sql_reapplies_without_error(fresh_db):
    """The statements themselves are re-runnable: IF NOT EXISTS, not tracking.

    The runner's skip is only half of idempotency. The other half is what
    happens when the file is executed against a database that already has the
    tables — a manual re-run, or another process bootstrapping concurrently.
    """
    before = _connect(fresh_db)
    try:
        indexes_before = _index_names(before)
    finally:
        before.close()

    _apply_file_only(fresh_db)
    _apply_file_only(fresh_db)

    after = _connect(fresh_db)
    try:
        assert KNOWLEDGE_TABLES <= _table_names(after)
        assert _index_names(after) == indexes_before, (
            "re-apply changed the index set")
    finally:
        after.close()


def test_reapply_preserves_existing_rows(fresh_db):
    """Idempotent means the data survives, not only that no error is raised."""
    conn = _connect(fresh_db)
    try:
        conn.execute(
            "INSERT INTO knowledge_indexes (scope, provider, location, "
            "document_count, status) VALUES (?, ?, ?, ?, ?)",
            ("dpmtf-webui", "none", "knowledge_index/dpmtf-webui", 3, "ready"),
        )
        conn.execute(
            "INSERT INTO knowledge_exclusions (scope, pattern, kind, enabled) "
            "VALUES (?, ?, ?, ?)",
            ("dpmtf-webui", "node_modules", "path", 1),
        )
        conn.execute(
            "INSERT INTO knowledge_retrieval_log (provider, scope, query, "
            "result_count, sources, retrieved_token_count, "
            "retrieval_duration_ms, agent_role, run_id, handoff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("none", "dpmtf-webui", "migration idempotency", 1, '["a.py"]',
             120, 7, "imple01", "002", "001"),
        )
        conn.commit()
    finally:
        conn.close()

    _apply_file_only(fresh_db)

    conn = _connect(fresh_db)
    try:
        index_row = conn.execute(
            "SELECT provider, document_count, status FROM knowledge_indexes "
            "WHERE scope = ?", ("dpmtf-webui",),
        ).fetchone()
        assert index_row is not None, "re-apply dropped the index row"
        assert index_row["provider"] == "none"
        assert index_row["document_count"] == 3
        assert index_row["status"] == "ready"
        assert conn.execute(
            "SELECT COUNT(*) FROM knowledge_exclusions").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM knowledge_retrieval_log").fetchone()[0] == 1
    finally:
        conn.close()


# ── 3. required columns are exposed ──────────────────────────────────────

@pytest.mark.parametrize("table", sorted(REQUIRED_COLUMNS))
def test_required_columns_present(fresh_db, table):
    conn = _connect(fresh_db)
    try:
        present = _columns(conn, table)
    finally:
        conn.close()
    missing = REQUIRED_COLUMNS[table] - present
    assert not missing, f"{table} is missing columns: {sorted(missing)}"


def test_retrieval_log_observability_columns(fresh_db):
    """The eight fields addendum §8 names are all on the log, and typed so a
    retrieval can actually be recorded."""
    conn = _connect(fresh_db)
    try:
        types = {
            row[1]: row[2].upper()
            for row in conn.execute("PRAGMA table_info(knowledge_retrieval_log)")
        }
    finally:
        conn.close()

    for field in ("provider", "scope", "query", "sources", "agent_role",
                  "run_id", "handoff_id"):
        assert types.get(field, "").startswith("TEXT"), (
            f"{field} should be TEXT, got {types.get(field)!r}")
    for field in ("result_count", "retrieved_token_count",
                  "retrieval_duration_ms"):
        assert types.get(field, "").startswith("INTEGER"), (
            f"{field} should be INTEGER, got {types.get(field)!r}")


# ── Constraints the contract's shape requires ────────────────────────────

def test_index_scope_is_unique(fresh_db):
    """One row per repository scope (addendum §4's logical separation)."""
    conn = _connect(fresh_db)
    try:
        conn.execute(
            "INSERT INTO knowledge_indexes (scope, provider) VALUES (?, ?)",
            ("harness-allocator", "none"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO knowledge_indexes (scope, provider) VALUES (?, ?)",
                ("harness-allocator", "none"),
            )
    finally:
        conn.close()


def test_index_defaults_are_usable(fresh_db):
    """A provider may register a scope without knowing counts or paths yet."""
    conn = _connect(fresh_db)
    try:
        conn.execute(
            "INSERT INTO knowledge_indexes (scope, provider) VALUES (?, ?)",
            ("flowrunner", "none"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT location, document_count, status, updated_at "
            "FROM knowledge_indexes WHERE scope = ?",
            ("flowrunner",),
        ).fetchone()
        assert row["location"] == ""
        assert row["document_count"] == 0
        assert row["status"] == "unknown"
        assert row["updated_at"], "updated_at must default to a timestamp"
    finally:
        conn.close()


def test_exclusions_are_per_scope_and_typed(fresh_db):
    """kind carries the three exclusion modes; scope keeps them separate."""
    conn = _connect(fresh_db)
    try:
        for scope, pattern, kind in (
            ("dpmtf-webui", "venv", "path"),
            ("dpmtf-webui", ".env", "name"),
            ("dpmtf-webui", "BEGIN PRIVATE KEY", "content"),
            ("model-allocator", "venv", "path"),
        ):
            conn.execute(
                "INSERT INTO knowledge_exclusions (scope, pattern, kind) "
                "VALUES (?, ?, ?)",
                (scope, pattern, kind),
            )
        conn.commit()

        # Same pattern, different scope: allowed, because exclusions are
        # repository-specific.
        assert conn.execute(
            "SELECT COUNT(*) FROM knowledge_exclusions").fetchone()[0] == 4
        # Same scope and pattern twice: refused (UNIQUE(scope, pattern)).
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO knowledge_exclusions (scope, pattern, kind) "
                "VALUES (?, ?, ?)",
                ("dpmtf-webui", "venv", "path"),
            )
        # An exclusion kind outside the contract's vocabulary: refused.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO knowledge_exclusions (scope, pattern, kind) "
                "VALUES (?, ?, ?)",
                ("dpmtf-webui", "elsewhere", "regex"),
            )
    finally:
        conn.close()


def test_exclusion_enabled_flag_defaults_on_and_switches_off(fresh_db):
    conn = _connect(fresh_db)
    try:
        conn.execute(
            "INSERT INTO knowledge_exclusions (scope, pattern, kind) "
            "VALUES (?, ?, ?)",
            ("dpmtf-webui", "logs", "path"),
        )
        conn.commit()
        default = conn.execute(
            "SELECT enabled FROM knowledge_exclusions WHERE pattern = ?",
            ("logs",),
        ).fetchone()["enabled"]
        assert default == 1, "a new rule must be active by default"

        conn.execute(
            "UPDATE knowledge_exclusions SET enabled = 0 WHERE pattern = ?",
            ("logs",),
        )
        conn.commit()
        row = conn.execute(
            "SELECT enabled FROM knowledge_exclusions WHERE pattern = ?",
            ("logs",),
        ).fetchone()
        assert row["enabled"] == 0
        # A rule switched off is still a rule — disabled, not deleted.
        assert conn.execute(
            "SELECT COUNT(*) FROM knowledge_exclusions").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE knowledge_exclusions SET enabled = 2 WHERE pattern = ?",
                ("logs",),
            )
    finally:
        conn.close()


def test_retrieval_log_is_append_only(fresh_db):
    """Two identical retrievals are two rows — the §8 comparison counts them."""
    conn = _connect(fresh_db)
    try:
        for _ in range(3):
            conn.execute(
                "INSERT INTO knowledge_retrieval_log "
                "(provider, scope, query, result_count, sources, "
                "retrieved_token_count, retrieval_duration_ms, agent_role, "
                "run_id, handoff_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("leann", "dpmtf-webui", "migration runner", 2,
                 '["scripts/migrate.py"]', 240, 15, "review01", "002", "001"),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT id, created_at FROM knowledge_retrieval_log "
            "WHERE query = ? ORDER BY id",
            ("migration runner",),
        ).fetchall()
        assert len(rows) == 3, "duplicate retrievals must each keep a row"
        assert len({row["id"] for row in rows}) == 3
    finally:
        conn.close()


def test_retrieval_log_minimal_insert_is_recorded(fresh_db):
    """Only the three identity fields are mandatory; the rest default."""
    conn = _connect(fresh_db)
    try:
        conn.execute(
            "INSERT INTO knowledge_retrieval_log (provider, scope, query) "
            "VALUES (?, ?, ?)",
            ("none", "simple-harness", "scope isolation"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT result_count, sources, retrieved_token_count, "
            "retrieval_duration_ms, agent_role, run_id, handoff_id, created_at "
            "FROM knowledge_retrieval_log WHERE scope = ?",
            ("simple-harness",),
        ).fetchone()
        assert row["result_count"] == 0
        assert row["sources"] == "[]"
        assert row["retrieved_token_count"] == 0
        assert row["retrieval_duration_ms"] == 0
        assert row["agent_role"] is None
        assert row["run_id"] is None
        assert row["handoff_id"] is None
        assert row["created_at"], "created_at must default to a timestamp"
    finally:
        conn.close()


# ── Non-destructive by construction ──────────────────────────────────────

def test_sql_is_non_destructive():
    """No DROP, DELETE, TRUNCATE, UPDATE, INSERT or ALTER in the statements."""
    statements = _strip_comments(_migration_sql()).upper()
    for keyword in ("DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT",
                    "UPDATE", "REPLACE"):
        assert not re.search(rf"\b{keyword}\b", statements), (
            f"migration contains a destructive/seed statement: {keyword}")


def test_every_create_table_is_guarded():
    """CREATE TABLE without IF NOT EXISTS is not re-runnable."""
    sql = _strip_comments(_migration_sql())
    creates = re.findall(r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS)?", sql,
                         re.IGNORECASE)
    assert len(creates) == 3, f"expected 3 CREATE TABLE statements, got {len(creates)}"
    assert all(guard for guard in creates), (
        "a CREATE TABLE lacks IF NOT EXISTS, so a re-apply would fail")
    indexes = re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(IF\s+NOT\s+EXISTS)?",
                         sql, re.IGNORECASE)
    assert indexes, "expected at least one index"
    assert all(guard for guard in indexes), (
        "a CREATE INDEX lacks IF NOT EXISTS, so a re-apply would fail")


def test_no_transaction_control_and_no_absolute_paths():
    """migrate.py wraps each file in a transaction; nested BEGIN breaks it."""
    sql = _migration_sql()
    statements = _strip_comments(sql)
    assert not re.search(r"\bBEGIN\b|\bCOMMIT\b", statements, re.IGNORECASE), (
        "migration must not carry its own BEGIN/COMMIT — migrate.py wraps it")
    assert "/home/" not in sql, "migration must not name a machine path"


def test_existing_schema_is_untouched(fresh_db):
    """Applying the migration leaves the pre-existing tables alone."""
    conn = _connect(fresh_db)
    try:
        before = _table_names(conn)
        assert "bridge_roles" in before, (
            "fixture DB should already carry the baseline schema")
    finally:
        conn.close()

    _apply_file_only(fresh_db)

    conn = _connect(fresh_db)
    try:
        after = _table_names(conn)
    finally:
        conn.close()
    assert before <= after, f"migration removed tables: {before - after}"
