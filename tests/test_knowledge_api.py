"""Tests for the knowledge search API (GET /api/knowledge/search).

Provider-neutral by construction: no concrete provider is imported or named
in this module. The enabled path is exercised with a small stub provider so
the real optional backends are never pulled in.

Each test runs against a fresh temporary SQLite database that has only the
``knowledge_retrieval_log`` schema from ``scripts/db/107_knowledge_tables.sql``
(the production database is never touched). The log table is emptied before
every test so row-count assertions are independent of execution order.
"""

import sys

# First statements, before any project import: keep this test run from
# writing new __pycache__/ entries inside the repository.
sys.dont_write_bytecode = True

import json
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import app  # noqa: E402
import config  # noqa: E402
from knowledge import search as knowledge_search  # noqa: E402
from knowledge.provider import ProviderNotReady  # noqa: E402


# ── Stub provider (enabled-path tests) ────────────────────────────────


class StubProvider:
    """Provider stand-in with a ``search`` call recorder."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def preflight(self) -> None:
        return None

    def search(self, query, scope=None, top_k=None, token_budget=None):
        self.calls.append(
            {
                "query": query,
                "scope": scope,
                "top_k": top_k,
                "token_budget": token_budget,
            }
        )
        return list(self.results)


def _factory_returning(instance):
    """Return a zero-argument callable that yields ``instance``.

    ``routers/knowledge.py`` resolves a provider *class* and then calls it,
    so ``resolve_provider`` is patched to return this factory.
    """

    def factory():
        return instance

    return factory


def _tripwire(_name, scope=None):
    """Resolve-provider stand-in for no-provider-resolved paths."""
    raise AssertionError("resolve_provider must not be called on this path")


class IndexRecordingProvider:
    """Provider stand-in with an ``index`` call recorder."""

    def __init__(self):
        self.index_calls = []

    def preflight(self) -> None:
        return None

    def index(self, source):
        self.index_calls.append(source)


class NotReadyProvider:
    """Provider whose preflight fails and whose other methods tripwire."""

    def __init__(self):
        self.index_calls = []

    def preflight(self) -> None:
        raise ProviderNotReady(
            "knowledge provider not ready: no CUDA device is available"
        )

    def search(self, *args, **kwargs):
        raise AssertionError("search must not run when preflight fails")

    def index(self, source):
        self.index_calls.append(source)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def knowledge_db(tmp_path_factory):
    """Fresh temp SQLite file carrying only the knowledge schema."""
    db_path = tmp_path_factory.mktemp("knowledge_api") / "test_knowledge.db"
    schema_path = _PROJECT_ROOT / "scripts" / "db" / "107_knowledge_tables.sql"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return str(db_path)


@pytest.fixture(scope="module")
def knowledge_client(knowledge_db):
    """TestClient bound to the imported ``app`` with an isolated DB path.

    Does not use the shared conftest ``client`` fixture: that fixture's temp
    schema has no ``knowledge_retrieval_log`` table.
    """
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "get_db_path", lambda: knowledge_db)
    try:
        with TestClient(app.app) as client:
            yield client
    finally:
        mp.undo()


@pytest.fixture()
def knowledge_index_dir(tmp_path, monkeypatch):
    """Point the index dir at a fresh temp directory for one test."""
    index_dir = tmp_path / "knowledge_index"
    index_dir.mkdir()
    monkeypatch.setattr(config, "get_knowledge_index_dir", lambda: str(index_dir))
    return index_dir


@pytest.fixture(autouse=True)
def _clean_retrieval_log(knowledge_db):
    """Start every test with an empty append-only log."""
    conn = sqlite3.connect(knowledge_db)
    try:
        conn.execute("DELETE FROM knowledge_retrieval_log")
        conn.commit()
    finally:
        conn.close()


# ── Helpers ──────────────────────────────────────────────────────────


def _log_rows(knowledge_db):
    conn = sqlite3.connect(knowledge_db)
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM knowledge_retrieval_log").fetchall()
    finally:
        conn.close()


def _stub_config(monkeypatch, *, enabled, provider, top_k, token_budget):
    """Patch the four knowledge config getters used by the endpoint."""
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: enabled)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: provider)
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: top_k)
    monkeypatch.setattr(
        config, "get_knowledge_max_context_tokens", lambda: token_budget
    )


def _write_manifest_record(path, scope, rel_path, content):
    """Write one JSONL manifest record in the indexer's key set."""
    path.write_text(
        json.dumps({
            "scope": scope,
            "path": rel_path,
            "content": content,
            "size_bytes": len(content.encode("utf-8")),
            "indexed_at": "2026-09-12T00:00:00+00:00",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Tests ───────────────────────────────────────────────────────────


def test_disabled_mode_shape(knowledge_client, knowledge_db, monkeypatch):
    _stub_config(
        monkeypatch,
        enabled=False,
        provider="leann",
        top_k=8,
        token_budget=12000,
    )
    monkeypatch.setattr(knowledge_search, "resolve_provider", _tripwire)

    response = knowledge_client.get("/api/knowledge/search", params={"q": "anything"})

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "provider": "leann",
        "results": [],
        "bounded": True,
    }
    assert _log_rows(knowledge_db) == []


def test_none_provider_shape(knowledge_client, knowledge_db, monkeypatch):
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="none",
        top_k=8,
        token_budget=12000,
    )
    monkeypatch.setattr(knowledge_search, "resolve_provider", _tripwire)

    response = knowledge_client.get("/api/knowledge/search", params={"q": "anything"})

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "provider": "none",
        "results": [],
        "bounded": True,
    }
    assert _log_rows(knowledge_db) == []


def test_enabled_stub_budget_and_log_row(knowledge_client, knowledge_db, monkeypatch):
    items = [
        {"path": "docs/a.md", "content": "alpha beta gamma", "score": 0.9},
        {"path": "docs/b.md", "content": "delta epsilon"},
        {"path": "docs/c.md", "content": "zeta eta theta iota"},
        {"path": "docs/d.md", "content": "kappa lambda mu nu xi"},
        {"path": "docs/e.md", "content": "omicron pi"},
        {"path": "docs/f.md", "content": "rho sigma tau upsilon phi chi psi"},
    ]
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="stub",
        top_k=3,
        token_budget=12000,
    )
    stub = StubProvider(items)
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(stub)
    )

    response = knowledge_client.get("/api/knowledge/search", params={"q": "where is knowledge"})

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "provider": "stub",
        "results": items[:3],
        "bounded": True,
    }
    # Result items pass through unchanged: the score field survives, and no
    # field is stripped or invented.
    assert response.json()["results"] == items[:3]

    rows = _log_rows(knowledge_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "stub"
    assert row["scope"] == ""
    assert row["query"] == "where is knowledge"
    assert row["result_count"] == 3
    assert json.loads(row["sources"]) == ["docs/a.md", "docs/b.md", "docs/c.md"]
    assert row["retrieved_token_count"] == 9  # 3 + 2 + 4 whitespace tokens
    assert isinstance(row["retrieval_duration_ms"], int)
    assert row["retrieval_duration_ms"] >= 0
    assert row["agent_role"] is None
    assert row["run_id"] is None
    assert row["handoff_id"] is None


def test_budget_and_scope_pass_through(knowledge_client, knowledge_db, monkeypatch):
    items = [
        {"path": "p1", "content": "one two"},
        {"path": "p2", "content": "three four"},
        {"path": "p3", "content": "five six"},
        {"path": "p4", "content": "seven eight"},
    ]
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="stub",
        top_k=2,
        token_budget=55,
    )
    stub = StubProvider(items)
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(stub)
    )

    response = knowledge_client.get(
        "/api/knowledge/search",
        params={"q": "scope query", "scope": "repo-alpha"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == items[:2]
    # The API passes `scope` through unchanged, and clamps
    # `top_k`/`token_budget` to the configured ceilings; in this test the
    # requested values equal the config fallbacks, so the recorded call is
    # unchanged by the clamp.
    assert stub.calls == [
        {
            "query": "scope query",
            "scope": "repo-alpha",
            "top_k": 2,
            "token_budget": 55,
        }
    ]

    rows = _log_rows(knowledge_db)
    assert len(rows) == 1
    assert rows[0]["scope"] == "repo-alpha"
    assert rows[0]["result_count"] == 2


def test_caller_bounds_clamped_to_config_ceiling(
    knowledge_client, knowledge_db, monkeypatch
):
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="stub",
        top_k=3,
        token_budget=100,
    )
    stub = StubProvider(
        {"path": f"p{i}", "content": "one two"} for i in range(50)
    )
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(stub)
    )

    response = knowledge_client.get(
        "/api/knowledge/search",
        params={"q": "ceiling", "top_k": 50, "token_budget": 999999},
    )

    assert response.status_code == 200
    assert stub.calls == [
        {"query": "ceiling", "scope": None, "top_k": 3, "token_budget": 100}
    ]
    assert len(response.json()["results"]) == 3

    rows = _log_rows(knowledge_db)
    assert len(rows) == 1
    assert rows[0]["result_count"] == 3


def test_nonpositive_bounds_clamped_to_one(
    knowledge_client, knowledge_db, monkeypatch
):
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="stub",
        top_k=3,
        token_budget=100,
    )
    stub = StubProvider(
        {"path": f"p{i}", "content": "one two"} for i in range(4)
    )
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(stub)
    )

    response = knowledge_client.get(
        "/api/knowledge/search",
        params={"q": "negative", "top_k": -5, "token_budget": 0},
    )

    assert response.status_code == 200
    assert stub.calls == [
        {"query": "negative", "scope": None, "top_k": 1, "token_budget": 1}
    ]
    assert len(response.json()["results"]) == 1

    rows = _log_rows(knowledge_db)
    assert len(rows) == 1
    assert rows[0]["result_count"] == 1


def test_unknown_provider_key_contract(knowledge_client, knowledge_db, monkeypatch):
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="bogus",
        top_k=8,
        token_budget=12000,
    )

    response = knowledge_client.get("/api/knowledge/search", params={"q": "anything"})

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "provider": "bogus",
        "results": [],
        "bounded": True,
    }
    rows = _log_rows(knowledge_db)
    assert len(rows) == 1
    assert rows[0]["provider"] == "bogus"
    assert rows[0]["result_count"] == 0


def test_connect_failure_is_a_logged_500(knowledge_client, knowledge_db, monkeypatch):
    _stub_config(
        monkeypatch,
        enabled=True,
        provider="stub",
        top_k=3,
        token_budget=12000,
    )
    stub = StubProvider([{"path": "p1", "content": "one two"}])
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(stub)
    )
    missing_dir = (
        Path(tempfile.gettempdir())
        / f"knowledge-api-missing-{uuid.uuid4().hex}"
    )
    monkeypatch.setattr(
        config, "get_db_path", lambda: str(missing_dir / "db.sqlite")
    )

    response = knowledge_client.get("/api/knowledge/search", params={"q": "boom"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to record knowledge retrieval"
    assert _log_rows(knowledge_db) == []


# ── GOAL-DRAFT-021: POST /api/knowledge/refresh ─────────────────────────


def test_refresh_rejects_missing_repo_path(
    knowledge_client, knowledge_db, knowledge_index_dir, tmp_path, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )
    monkeypatch.setattr(knowledge_search, "resolve_provider", _tripwire)

    response = knowledge_client.post(
        "/api/knowledge/refresh",
        json={"scope": "s", "repo_path": str(tmp_path / "does-not-exist")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "repo_path must be an existing directory"


def test_refresh_noop_when_manifest_unchanged(
    knowledge_client, knowledge_db, knowledge_index_dir, tmp_path, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("hello", encoding="utf-8")

    manifest = knowledge_index_dir / "s.jsonl"
    _write_manifest_record(manifest, "s", "a.txt", "hello")

    provider = IndexRecordingProvider()
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(provider)
    )

    response = knowledge_client.post(
        "/api/knowledge/refresh",
        json={"scope": "s", "repo_path": str(repo)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "noop",
        "manifest": str(manifest.resolve()),
    }
    assert provider.index_calls == []


def test_refresh_reindexes_when_manifest_changed(
    knowledge_client, knowledge_db, knowledge_index_dir, tmp_path, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("new", encoding="utf-8")

    manifest = knowledge_index_dir / "s.jsonl"
    _write_manifest_record(manifest, "s", "a.txt", "old")

    provider = IndexRecordingProvider()
    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _factory_returning(provider)
    )

    response = knowledge_client.post(
        "/api/knowledge/refresh",
        json={"scope": "s", "repo_path": str(repo)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "reindexed",
        "documents": 1,
        "manifest": str(manifest.resolve()),
    }
    assert provider.index_calls == [str(manifest.resolve())]

    conn = sqlite3.connect(knowledge_db)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT provider, document_count, status, location "
            "FROM knowledge_indexes WHERE scope = ?",
            ("s",),
        ).fetchone()
        assert row is not None
        assert row["provider"] == "stub"
        assert row["document_count"] == 1
        assert row["status"] == "changed"
        assert row["location"] == str(manifest.resolve())
    finally:
        conn.close()


def test_search_returns_503_when_provider_not_ready(
    knowledge_client, knowledge_db, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )
    provider = NotReadyProvider()
    monkeypatch.setattr(
        knowledge_search, "resolve_provider",
        lambda name, scope=None: _factory_returning(provider),
    )

    response = knowledge_client.get(
        "/api/knowledge/search", params={"q": "anything"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "knowledge provider not ready: no CUDA device is available"
    )
    assert _log_rows(knowledge_db) == []


def test_refresh_returns_503_when_provider_not_ready(
    knowledge_client, knowledge_db, knowledge_index_dir, tmp_path, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("new", encoding="utf-8")

    manifest = knowledge_index_dir / "s.jsonl"
    _write_manifest_record(manifest, "s", "a.txt", "old")  # changed -> reaches preflight

    provider = NotReadyProvider()
    monkeypatch.setattr(
        knowledge_search, "resolve_provider",
        lambda name, scope=None: _factory_returning(provider),
    )

    response = knowledge_client.post(
        "/api/knowledge/refresh",
        json={"scope": "s", "repo_path": str(repo)},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "knowledge provider not ready: no CUDA device is available"
    )
    assert provider.index_calls == []


def test_refresh_preflights_before_indexing(
    knowledge_client, knowledge_db, knowledge_index_dir, tmp_path, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("new", encoding="utf-8")

    manifest = knowledge_index_dir / "s.jsonl"
    _write_manifest_record(manifest, "s", "a.txt", "old")
    # Pin the pre-refresh bytes so "unchanged" is a content assertion.
    manifest_bytes_before = manifest.read_bytes()

    provider = NotReadyProvider()
    monkeypatch.setattr(
        knowledge_search, "resolve_provider",
        lambda name, scope=None: _factory_returning(provider),
    )

    response = knowledge_client.post(
        "/api/knowledge/refresh",
        json={"scope": "s", "repo_path": str(repo)},
    )

    assert response.status_code == 503
    assert provider.index_calls == []
    # The GOAL reviewer duty: a preflight failure must leave the existing
    # manifest byte-identical (content, not just "the indexer mock was not called").
    assert manifest.read_bytes() == manifest_bytes_before


def test_refresh_endpoint_delegates_to_refresh_scope(
    knowledge_client, knowledge_db, knowledge_index_dir, tmp_path, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    calls = []

    def fake_refresh_scope(scope, repo_path):
        calls.append((scope, repo_path))
        return {"status": "noop", "manifest": "/tmp/fake"}

    monkeypatch.setattr(
        "knowledge.maintenance.refresh_scope", fake_refresh_scope
    )

    response = knowledge_client.post(
        "/api/knowledge/refresh",
        json={"scope": "s", "repo_path": str(repo)},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "noop", "manifest": "/tmp/fake"}
    assert calls == [("s", str(Path(repo).resolve()))]


def test_search_endpoint_resolves_the_provider_for_the_requested_scope(
    knowledge_client, knowledge_db, monkeypatch
):
    _stub_config(
        monkeypatch, enabled=True, provider="stub", top_k=3, token_budget=12000
    )

    resolve_calls = []
    stub = StubProvider([{"path": "p1", "content": "one two"}])

    def _spy_resolve(name, scope=None):
        resolve_calls.append((name, scope))
        return _factory_returning(stub)

    monkeypatch.setattr(knowledge_search, "resolve_provider", _spy_resolve)

    response = knowledge_client.get(
        "/api/knowledge/search",
        params={"q": "anything", "scope": "flowrunner"},
    )

    assert response.status_code == 200
    assert resolve_calls == [("stub", "flowrunner")]
    assert stub.calls == [
        {
            "query": "anything",
            "scope": "flowrunner",
            "top_k": 3,
            "token_budget": 12000,
        }
    ]
