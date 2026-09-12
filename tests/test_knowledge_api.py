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


# ── Stub provider (enabled-path tests) ────────────────────────────────


class StubProvider:
    """Provider stand-in with a ``search`` call recorder."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

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


def _tripwire(_name):
    """Resolve-provider stand-in for no-provider-resolved paths."""
    raise AssertionError("resolve_provider must not be called on this path")


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
        knowledge_search, "resolve_provider", lambda name: _factory_returning(stub)
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
        knowledge_search, "resolve_provider", lambda name: _factory_returning(stub)
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
        knowledge_search, "resolve_provider", lambda name: _factory_returning(stub)
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
        knowledge_search, "resolve_provider", lambda name: _factory_returning(stub)
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
        knowledge_search, "resolve_provider", lambda name: _factory_returning(stub)
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
