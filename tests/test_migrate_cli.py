"""migrate.py's command line reads its arguments.

Until 2026-09-20 `main()` ignored argv altogether: `migrate.py --help`, a
typo, anything at all, applied every pending migration to the live database
and printed the summary. The only way to learn what was pending was to apply
it. `--help` documents, `--status` lists without touching anything, an
unknown argument is refused — and none of the three opens the database for
writing.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import migrate  # noqa: E402


@pytest.fixture()
def two_migrations(tmp_path, monkeypatch):
    mig_dir = tmp_path / "db"
    mig_dir.mkdir()
    (mig_dir / "001_first.sql").write_text("CREATE TABLE first_table (id INTEGER);", encoding="utf-8")
    (mig_dir / "002_second.sql").write_text("CREATE TABLE second_table (id INTEGER);", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", mig_dir)
    # A call that reaches the real database is a test failure, not a side effect.
    monkeypatch.setattr(migrate.config, "get_db_path",
                        lambda: pytest.fail("the command line reached for the live database"))
    return tmp_path / "target.db"


def _tables(db):
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def test_help_applies_nothing(two_migrations, capsys):
    with pytest.raises(SystemExit) as exit_info:
        migrate.main(["--help", "--db", str(two_migrations)])
    assert exit_info.value.code == 0
    assert not two_migrations.exists(), "--help created the database"
    out = capsys.readouterr().out
    assert "--status" in out and "--db" in out


@pytest.mark.parametrize("argv", [["--hlep"], ["status"], ["--dry-run-please"], ["apply", "now"]])
def test_an_argument_it_does_not_know_is_refused_not_ignored(two_migrations, argv, capsys):
    with pytest.raises(SystemExit) as exit_info:
        migrate.main(argv + ["--db", str(two_migrations)])
    assert exit_info.value.code == 2
    assert not two_migrations.exists(), f"{argv} created the database"


def test_status_lists_what_is_pending_and_touches_nothing(two_migrations, capsys):
    # No database yet: everything is pending, and there is still no database.
    assert migrate.main(["--status", "--db", str(two_migrations)]) == 0
    out = capsys.readouterr().out
    assert "001_first.sql" in out and "002_second.sql" in out and "2 pending" in out
    assert not two_migrations.exists(), "--status created the database"

    # One applied by hand: --status reports the other, and changes nothing —
    # not even the bookkeeping table.
    conn = sqlite3.connect(two_migrations)
    conn.executescript(migrate.SCHEMA_MIGRATIONS_DDL)
    conn.execute("INSERT INTO schema_migrations (filename, applied_at) VALUES ('001_first.sql', 'x')")
    conn.commit()
    conn.close()
    before = two_migrations.read_bytes()
    assert migrate.main(["--status", "--db", str(two_migrations)]) == 0
    out = capsys.readouterr().out
    assert "002_second.sql" in out and "1 pending" in out
    assert "001_first.sql" not in out.split("pending")[1]
    assert two_migrations.read_bytes() == before, "--status wrote to the database"

    # A database that predates schema_migrations is read, not initialised.
    bare = two_migrations.with_name("bare.db")
    sqlite3.connect(bare).close()
    assert migrate.main(["--status", "--db", str(bare)]) == 0
    assert "schema_migrations" not in _tables(bare)


def test_no_arguments_still_applies(two_migrations, capsys):
    assert migrate.main(["--db", str(two_migrations)]) == 0
    assert {"first_table", "second_table", "schema_migrations"} <= _tables(two_migrations)
    assert "Applied 2 migration(s)" in capsys.readouterr().out
    # and --status then reports nothing pending
    assert migrate.main(["--status", "--db", str(two_migrations)]) == 0
    assert "0 pending" in capsys.readouterr().out
