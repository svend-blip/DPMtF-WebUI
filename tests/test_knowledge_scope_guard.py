"""Provider-neutral tests for the knowledge scope guard (GOAL-DRAFT-009).

These tests prove the guard's exact-match contract and the two call sites'
wiring:

* internal scopes default to deny without an explicit grant;
* ``scope`` and ``agent_role`` match exactly; a grant row whose ``flow_key``
  is NULL is a wildcard on the flow dimension only and matches any caller
  flow, while a non-NULL grant ``flow_key`` matches only that flow;
* a grant recorded for another role does not allow;
* non-internal scopes allow without any database access;
* the enabled search endpoint returns 403 for a denied internal scope and
  denies BEFORE provider resolution;
* ``knowledge.retrieval.retrieve_for_context`` returns ``None`` on denial
  BEFORE provider resolution;
* disabled mode returns the unchanged disabled envelope / ``None`` and never
  consults the guard or a provider;
* a grant row whose ``agent_role`` is NULL does NOT authorize a
  ``None``-role caller, even though the NULL ``flow_key`` wildcard would
  otherwise relax the flow dimension (SQLite ``NULL = ?`` never matches;
  default-deny).

The file is provider-neutral: it imports only the neutral service layer and
the guard, never a concrete provider, and ``sys.dont_write_bytecode`` is set
before any project module import so no ``__pycache__/`` files are written.
"""

import sys

# Must be set before importing any project module so the checkout keeps no
# __pycache__/ files from this test run (scope fence: never touch __pycache__).
sys.dont_write_bytecode = True

import sqlite3
from pathlib import Path

import pytest

import config
import knowledge.retrieval as retrieval
import knowledge.scope_guard as scope_guard
import knowledge.search as knowledge_search


_KNOWLEDGE_SCHEMA_SQL = (
    "scripts/db/107_knowledge_tables.sql",
    "scripts/db/109_knowledge_scope_grants.sql",
)


def _build_knowledge_db(db_path: Path) -> None:
    """Create a fresh SQLite file with the knowledge schema (107 then 109)."""
    conn = sqlite3.connect(str(db_path))
    try:
        for sql_file in _KNOWLEDGE_SCHEMA_SQL:
            conn.executescript(Path(sql_file).read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def _insert_grant(db_path: Path, scope, agent_role, flow_key) -> None:
    """Insert one grant row using parameterized SQL only."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO knowledge_scope_grants (scope, agent_role, flow_key)"
            " VALUES (?, ?, ?)",
            (scope, agent_role, flow_key),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def knowledge_db(tmp_path, monkeypatch):
    """Fresh knowledge-schema DB; ``config.get_db_path`` points at it.

    Reads the two schema files read-only, applies them to a temp SQLite file
    under ``tmp_path``, and monkeypatches ``config.get_db_path`` so the guard
    and the endpoint resolve this temp DB instead of the production database.
    """
    db_path = tmp_path / "knowledge_test.db"
    _build_knowledge_db(db_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))
    return db_path


@pytest.fixture()
def failing_resolver(monkeypatch):
    """Stub ``resolve_provider`` so any provider resolution fails the test.

    Both bindings are patched: ``routers/knowledge.py`` resolves through the
    ``knowledge.search`` module attribute, while ``knowledge/retrieval.py``
    imported ``resolve_provider`` directly into its own namespace.
    """

    def _fail(name):
        raise AssertionError(
            f"resolve_provider was called with {name!r}; "
            "the guard must deny before any provider resolution"
        )

    monkeypatch.setattr(knowledge_search, "resolve_provider", _fail)
    monkeypatch.setattr(retrieval, "resolve_provider", _fail)


def test_internal_scope_denies_without_grant(knowledge_db):
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="external",
        db_path=str(knowledge_db),
    ) is False


def test_exact_grant_allows(knowledge_db):
    _insert_grant(knowledge_db, "dpmtf-webui", "flow-app", "external")
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="external",
        db_path=str(knowledge_db),
    ) is True


def test_grant_for_another_role_does_not_allow(knowledge_db):
    _insert_grant(knowledge_db, "dpmtf-webui", "flow-app", "external")
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app-other",
        flow_key="external",
        db_path=str(knowledge_db),
    ) is False


def test_non_internal_scope_allows_without_db(tmp_path):
    nonexistent = tmp_path / "does-not-exist.db"
    assert not nonexistent.exists()
    assert scope_guard.can_access_scope(
        "flowapp-public",
        db_path=str(nonexistent),
    ) is True


def test_search_endpoint_denies_internal_scope_before_provider(
    client, knowledge_db, monkeypatch, failing_resolver
):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_mode", lambda: "local")
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")

    response = client.get(
        "/api/knowledge/search",
        params={"q": "x", "scope": "dpmtf-webui", "agent_role": "flow-app"},
    )

    assert response.status_code == 403
    assert "Scope access denied" in response.json()["detail"]


def test_retrieval_returns_none_on_denial_before_provider(
    knowledge_db, monkeypatch, failing_resolver
):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_mode", lambda: "local")
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")

    result = retrieval.retrieve_for_context(
        "q", "dpmtf-webui", "flow-app", None, None
    )

    assert result is None


def test_disabled_mode_leaves_guard_unconsulted(
    client, knowledge_db, monkeypatch, failing_resolver
):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    monkeypatch.setattr(config, "get_knowledge_mode", lambda: "local")
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")

    response = client.get(
        "/api/knowledge/search",
        params={"q": "x", "scope": "dpmtf-webui"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "provider": "stub",
        "results": [],
        "bounded": True,
    }
    assert (
        retrieval.retrieve_for_context(
            "q", "dpmtf-webui", "flow-app", None, None
        )
        is None
    )


def test_stored_null_grant_does_not_authorize_null_caller(knowledge_db):
    # A grant whose agent_role is NULL authorizes no caller, even one that
    # names no role: SQLite ``NULL = ?`` never matches for the role column,
    # and the ``flow_key IS NULL`` wildcard only relaxes the flow dimension —
    # never scope or agent_role.
    _insert_grant(knowledge_db, "dpmtf-webui", None, None)
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role=None,
        flow_key=None,
        db_path=str(knowledge_db),
    ) is False

    # Contrast: the same NULL flow_key is a wildcard once agent_role matches
    # exactly, so this grant authorizes the same caller flow of ``None``.
    _insert_grant(knowledge_db, "dpmtf-webui", "flow-app", None)
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key=None,
        db_path=str(knowledge_db),
    ) is True


def test_wildcard_grant_matches_any_flow(knowledge_db, tmp_path):
    _insert_grant(knowledge_db, "dpmtf-webui", "flow-app", None)
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="2000",
        db_path=str(knowledge_db),
    ) is True
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="2001",
        db_path=str(knowledge_db),
    ) is True

    # A non-NULL grant flow_key stays exact: use a separate DB so the
    # wildcard row above cannot keep the door open for the other flow.
    exact_db = tmp_path / "exact_grant.db"
    _build_knowledge_db(exact_db)
    _insert_grant(exact_db, "dpmtf-webui", "flow-app", "2000")
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="2000",
        db_path=str(exact_db),
    ) is True
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="2001",
        db_path=str(exact_db),
    ) is False


def test_unauthorized_internal_scope_is_still_denied(knowledge_db):
    _insert_grant(knowledge_db, "dpmtf-webui", "flow-app", "2000")
    assert scope_guard.can_access_scope(
        "dpmtf-webui",
        agent_role="flow-app",
        flow_key="2001",
        db_path=str(knowledge_db),
    ) is False


def test_authorized_internal_search_returns_results(
    client, knowledge_db, monkeypatch
):
    _insert_grant(knowledge_db, "dpmtf-webui", "flow-app", None)
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_mode", lambda: "local")
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 3)
    monkeypatch.setattr(
        config, "get_knowledge_max_context_tokens", lambda: 12000
    )

    class _StubProvider:
        def __init__(self):
            self.results = [{"path": "notes.md", "content": "alpha beta"}]

        def preflight(self):
            return None

        def search(self, query, scope=None, top_k=None, token_budget=None):
            return list(self.results)

    monkeypatch.setattr(
        knowledge_search, "resolve_provider", lambda name, scope=None: _StubProvider
    )

    response = client.get(
        "/api/knowledge/search",
        params={
            "q": "x",
            "scope": "dpmtf-webui",
            "agent_role": "flow-app",
            "flow_key": "2000",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["provider"] == "stub"
    assert body["results"] == [{"path": "notes.md", "content": "alpha beta"}]
    assert body["bounded"] is True

    conn = sqlite3.connect(str(knowledge_db))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT scope, result_count FROM knowledge_retrieval_log"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["scope"] == "dpmtf-webui"
    assert rows[0]["result_count"] == 1
