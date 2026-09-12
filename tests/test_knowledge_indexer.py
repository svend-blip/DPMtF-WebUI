"""Tests for the provider-neutral knowledge indexer.

These tests exercise ``knowledge.indexer`` against a temporary repository
and a throwaway SQLite database. The project database at
``databases/dpmtf.db`` is never written: each test creates its own fixture
DB under ``tmp_path`` and monkeypatches the indexer's ``config.get_db_path``
getter so the indexer reads the fixture instead of the live store.
"""

import json
import sqlite3

from knowledge import indexer

_EXCLUSION_SCHEMA = """
CREATE TABLE knowledge_exclusions (
    scope TEXT NOT NULL,
    pattern TEXT NOT NULL,
    kind TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
)
"""


def _create_fixture_db(db_path, rows):
    """Create a throwaway SQLite DB with the knowledge_exclusions schema."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_EXCLUSION_SCHEMA)
        conn.executemany(
            "INSERT INTO knowledge_exclusions (scope, pattern, kind, enabled) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _create_fixture_repo(repo):
    """Create the GOAL work-item-2 fixture repository.

    ``README.md`` is the only file that must be emitted. The other files
    exercise default name, suffix, directory, and content exclusions.
    """
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=abc\n", encoding="utf-8")
    (repo / "private.pem").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEAu7fakekeymaterialfortestonly\n"
        "-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "dep.txt").write_text("dep\n", encoding="utf-8")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "cached.cpython-312.pyc").write_bytes(
        b"\x00\x01\x02"
    )
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02")


def _patch_db(monkeypatch, db_path):
    """Point the indexer at the fixture DB without touching project config."""
    monkeypatch.setattr("config.get_db_path", lambda: str(db_path))


def _read_manifest(path):
    """Parse a JSONL manifest into a list of records."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_only_source_file_is_emitted(tmp_path, monkeypatch):
    """The fixture repo emits exactly README.md when no repo rules exist."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _create_fixture_repo(repo)

    db = tmp_path / "fixture.db"
    _create_fixture_db(db, [])
    _patch_db(monkeypatch, db)

    out = tmp_path / "manifest.jsonl"
    assert (
        indexer.main(
            ["--repo", str(repo), "--scope", "test", "--out", str(out)]
        )
        == 0
    )

    records = _read_manifest(out)
    paths = {record["path"] for record in records}
    assert paths == {"README.md"}


def test_scope_and_path_recorded_verbatim(tmp_path, monkeypatch):
    """The emitted record carries the requested scope and exact record keys."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _create_fixture_repo(repo)

    db = tmp_path / "fixture.db"
    _create_fixture_db(db, [])
    _patch_db(monkeypatch, db)

    out = tmp_path / "manifest.jsonl"
    assert (
        indexer.main(
            ["--repo", str(repo), "--scope", "test", "--out", str(out)]
        )
        == 0
    )

    records = _read_manifest(out)
    assert len(records) == 1
    record = records[0]
    assert record["scope"] == "test"
    assert record["path"] == "README.md"
    assert record["content"] == "hello\n"
    assert record["size_bytes"] == 6
    assert set(record) == {
        "scope",
        "path",
        "content",
        "size_bytes",
        "indexed_at",
    }


def test_per_scope_exclusion_rows_are_honored(tmp_path, monkeypatch):
    """Enabled repo-specific rows apply only to their own scope."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / "skipme.txt").write_text("skip\n", encoding="utf-8")
    (repo / "keepme.txt").write_text("keep\n", encoding="utf-8")
    (repo / "subdir").mkdir()
    (repo / "subdir" / "x.txt").write_text("x\n", encoding="utf-8")

    db = tmp_path / "fixture.db"
    _create_fixture_db(
        db,
        [
            ("app", "skipme.txt", "name", 1),
            ("app", "keepme.txt", "name", 0),
            ("app", "subdir", "path", 1),
        ],
    )
    _patch_db(monkeypatch, db)

    # Scope "app": enabled name and path exclusions apply, disabled row does not.
    out_app = tmp_path / "app.jsonl"
    assert (
        indexer.main(
            ["--repo", str(repo), "--scope", "app", "--out", str(out_app)]
        )
        == 0
    )
    app_records = _read_manifest(out_app)
    app_paths = {record["path"] for record in app_records}
    assert "skipme.txt" not in app_paths
    assert "keepme.txt" in app_paths
    assert "subdir/x.txt" not in app_paths
    assert all(record["scope"] == "app" for record in app_records)

    # Scope "other": the same rows do not apply; skipme.txt is emitted.
    out_other = tmp_path / "other.jsonl"
    assert (
        indexer.main(
            ["--repo", str(repo), "--scope", "other", "--out", str(out_other)]
        )
        == 0
    )
    other_records = _read_manifest(out_other)
    other_paths = {record["path"] for record in other_records}
    assert "skipme.txt" in other_paths
    assert all(record["scope"] == "other" for record in other_records)
