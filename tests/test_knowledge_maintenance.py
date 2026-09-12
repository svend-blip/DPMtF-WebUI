"""Tests for ``knowledge.maintenance``.

WORK 2 of run 2000/008. These are unit tests for the provider-neutral
maintenance module:

* ``detect_changes`` compares a repository tree against a hand-built JSONL
  manifest and reports ``noop``, ``changed``, or ``missing``.
* ``record_index`` upserts one ``knowledge_indexes`` row per scope.
* ``probe_provider_capabilities`` resolves a provider only through
  ``knowledge.search.resolve_provider`` and reports method support from the
  provider-neutral interface.

The bytecode guard below is set before any ``knowledge`` import so the test
run never writes ``__pycache__/`` inside the repository (the GOAL fence
forbids touching it).
"""

import sys

sys.dont_write_bytecode = True

import json
import sqlite3
from pathlib import Path

import pytest

import config
import knowledge.maintenance as maintenance


_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "db"
    / "107_knowledge_tables.sql"
)


@pytest.fixture()
def knowledge_db(tmp_path, monkeypatch):
    """Build the real knowledge schema in a temp DB and patch ``get_db_path``.

    Reads ``scripts/db/107_knowledge_tables.sql`` read-only and executes it
    against a ``tmp_path`` SQLite file. The production ``databases/dpmtf.db``
    is never opened because ``config.get_db_path`` is patched to the temp
    path; both ``knowledge.maintenance`` and ``knowledge.indexer`` resolve
    exclusions through ``config.get_db_path``, so this one patch isolates
    them both.
    """
    db_path = tmp_path / "knowledge.db"
    sql_text = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql_text)
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))
    yield str(db_path)


def _record(scope, path, content, size_bytes=None, indexed_at="2026-09-12T00:00:00+00:00"):
    """Build one manifest record with the keys ``knowledge.indexer`` emits."""
    if size_bytes is None:
        size_bytes = len(content.encode("utf-8"))
    return {
        "scope": scope,
        "path": path,
        "content": content,
        "size_bytes": size_bytes,
        "indexed_at": indexed_at,
    }


def _write_manifest(path, records):
    """Write JSONL manifest records (the indexer's key set) to ``path``."""
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_repo(tmp_path, files):
    """Create ``tmp_path/repo`` with the given ``{rel_path: content}`` files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel_path, content in files.items():
        target = repo / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return repo


def test_unchanged_repo_reports_noop(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "hello"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [_record("test", "a.txt", "hello")])

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "noop"
    assert plan.changed_paths == []
    assert plan.removed_paths == []


def test_added_file_reports_changed(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "hello", "b.txt": "world"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [_record("test", "a.txt", "hello")])

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "changed"
    assert plan.changed_paths == ["b.txt"]
    assert plan.removed_paths == []


def test_modified_file_reports_changed(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "v2"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [_record("test", "a.txt", "v1")])

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "changed"
    assert plan.changed_paths == ["a.txt"]
    assert plan.removed_paths == []


def test_deleted_file_reports_removed(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "hello"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [_record("test", "a.txt", "hello"), _record("test", "b.txt", "bye")],
    )

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "changed"
    assert plan.changed_paths == []
    assert plan.removed_paths == ["b.txt"]


def test_same_length_content_edit_counts_as_changed(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "abd"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [_record("test", "a.txt", "abc")])

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "changed"
    assert plan.changed_paths == ["a.txt"]


def test_metadata_only_drift_reports_noop(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "abc"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [
            _record(
                "test",
                "a.txt",
                "abc",
                size_bytes=999,
                indexed_at="2000-01-01T00:00:00+00:00",
            )
        ],
    )

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "noop"
    assert plan.changed_paths == []
    assert plan.removed_paths == []


def test_other_scope_records_skipped(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "hello"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [
            _record("test", "a.txt", "hello"),
            _record("other", "ghost.txt", "boo"),
        ],
    )

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "noop"
    assert plan.removed_paths == []


def test_duplicate_path_last_record_wins(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "v2"})
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [_record("test", "a.txt", "v1"), _record("test", "a.txt", "v2")],
    )

    plan = maintenance.detect_changes(repo, "test", manifest)

    assert plan.status == "noop"
    assert plan.changed_paths == []
    assert plan.removed_paths == []


def test_missing_manifest_reports_missing(knowledge_db, tmp_path):
    repo = _write_repo(tmp_path, {"a.txt": "hello"})

    absent_plan = maintenance.detect_changes(
        repo, "test", tmp_path / "none.jsonl"
    )
    assert absent_plan == maintenance.MaintenancePlan("missing", [], [])

    manifest_dir = tmp_path / "manifest_dir"
    manifest_dir.mkdir()
    directory_plan = maintenance.detect_changes(repo, "test", manifest_dir)
    assert directory_plan == maintenance.MaintenancePlan("missing", [], [])


def test_malformed_manifest_line_exits_nonzero(knowledge_db, tmp_path, capsys):
    repo = _write_repo(tmp_path, {"a.txt": "hello"})
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("this is not json\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        maintenance.detect_changes(repo, "test", manifest)

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "invalid JSON" in captured.err


def test_record_index_upserts_single_row(knowledge_db):
    maintenance.record_index("scope-a", "prov1", "/loc1", 3, "noop")
    maintenance.record_index("scope-a", "prov2", "/loc2", 7, "changed")

    conn = sqlite3.connect(knowledge_db)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT provider, location, document_count, status "
            "FROM knowledge_indexes WHERE scope = ?",
            ("scope-a",),
        )
        rows = cur.fetchall()
        cur.execute(
            "SELECT COUNT(*) FROM knowledge_indexes WHERE scope = ?",
            ("scope-a",),
        )
        count = cur.fetchone()[0]
    finally:
        conn.close()

    assert count == 1
    assert rows == [("prov2", "/loc2", 7, "changed")]


def test_record_index_refuses_when_table_missing(
    knowledge_db, tmp_path, monkeypatch, capsys
):
    # The fixture first isolates get_db_path away from production; this test
    # then re-points it at an empty file to exercise the missing-table path.
    empty_db = tmp_path / "empty.db"
    conn = sqlite3.connect(empty_db)
    conn.close()
    monkeypatch.setattr(config, "get_db_path", lambda: str(empty_db))

    with pytest.raises(SystemExit) as excinfo:
        maintenance.record_index("scope-a", "prov1", "/loc1", 3, "noop")

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "knowledge_indexes table is missing" in captured.err

    conn = sqlite3.connect(empty_db)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'knowledge_indexes'"
        )
        assert cur.fetchone() is None
    finally:
        conn.close()


def test_record_index_document_count_validation(knowledge_db):
    for value in (True, "3", 3.0, -1):
        with pytest.raises(SystemExit) as excinfo:
            maintenance.record_index("s", "p", "l", value, "noop")
        assert excinfo.value.code == 1


def test_probe_not_implemented_reports_unsupported(monkeypatch):
    """A ``NotImplementedError`` method is unsupported, not capability proof.

    Note: an unknown provider key resolves to the no-op provider through
    ``knowledge.search.resolve_provider`` and therefore reports ``true`` /
    ``true``; that is ``knowledge/search.py``'s documented contract, not
    evidence that a real provider supports update/remove.
    """

    class StubProvider:
        def index(self, source):
            raise NotImplementedError

        def update(self, source):
            raise NotImplementedError

        def remove(self, source):
            raise NotImplementedError

    monkeypatch.setattr(
        maintenance.search, "resolve_provider", lambda key: StubProvider
    )

    assert maintenance.probe_provider_capabilities("stub") == {
        "index_supported": False,
        "update_supported": False,
        "remove_supported": False,
    }


def test_probe_other_exception_propagates(monkeypatch):
    class BrokenProvider:
        def index(self, source):
            return None

        def update(self, source):
            raise RuntimeError("boom")

        def remove(self, source):
            return None

    monkeypatch.setattr(
        maintenance.search, "resolve_provider", lambda key: BrokenProvider
    )

    with pytest.raises(RuntimeError, match="boom"):
        maintenance.probe_provider_capabilities("broken")


def test_probe_supported_methods_report_true(monkeypatch):
    class SupportedProvider:
        def index(self, source):
            return None

        def update(self, source):
            return None

        def remove(self, source):
            return None

    monkeypatch.setattr(
        maintenance.search, "resolve_provider", lambda key: SupportedProvider
    )

    assert maintenance.probe_provider_capabilities("supported") == {
        "index_supported": True,
        "update_supported": True,
        "remove_supported": True,
    }
