import sys

sys.dont_write_bytecode = True

import sqlite3
from pathlib import Path

import pytest
import config
import knowledge.retrieval as retrieval
from knowledge.retrieval import retrieve_for_context
from knowledge.provider import ProviderNotReady


COMPILE_BODY = {
    "deployment_strategy": "standard",
    "target_project": "test-project",
    "phase_key": "test-phase",
    "goal": "Implement the requested change.",
    "scope_gate_confirmed": True,
}


def _create_retrieval_log_db(tmp_path):
    db = tmp_path / "retrieval_log.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE knowledge_scope_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            agent_role TEXT,
            flow_key TEXT,
            granted_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (scope, agent_role, flow_key)
        )
        """
    )
    conn.execute(
        "INSERT INTO knowledge_scope_grants (scope, agent_role, flow_key)"
        " VALUES (?, ?, ?)",
        ("dpmtf-webui", "Implementor", None),
    )
    conn.execute(
        """
        CREATE TABLE knowledge_retrieval_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            scope TEXT NOT NULL,
            query TEXT NOT NULL,
            result_count INTEGER NOT NULL DEFAULT 0 CHECK (result_count >= 0),
            sources TEXT NOT NULL DEFAULT '[]',
            retrieved_token_count INTEGER NOT NULL DEFAULT 0
                CHECK (retrieved_token_count >= 0),
            retrieval_duration_ms INTEGER NOT NULL DEFAULT 0
                CHECK (retrieval_duration_ms >= 0),
            agent_role TEXT,
            run_id TEXT,
            handoff_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()
    return db


def _create_retrieval_log_db_with_flow_key(tmp_path):
    """Build the same schema plus the post-114 ``flow_key`` column."""
    db = _create_retrieval_log_db(tmp_path)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "ALTER TABLE knowledge_retrieval_log "
            "ADD COLUMN flow_key TEXT DEFAULT NULL"
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _fetch_log_rows(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM knowledge_retrieval_log ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_disabled_flag_skips_retrieval_and_prompt_unchanged(client, monkeypatch):
    class Fake:
        def __init__(self):
            self.call_count = 0

        def __call__(self, *args, **kwargs):
            self.call_count += 1
            raise AssertionError("retrieval called while disabled")

    fake = Fake()
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    monkeypatch.setattr(retrieval, "retrieve_for_context", fake)

    resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert resp.status_code == 200
    assert fake.call_count == 0
    assert "<supplemental_knowledge>" not in resp.json()["prompt"]
    assert resp.json()["prompt"].rstrip().endswith("</constraint>")


def test_disabled_provider_none_returns_none_without_resolving(monkeypatch):
    class Fake:
        def __init__(self):
            self.call_count = 0

        def __call__(self, *args, **kwargs):
            self.call_count += 1
            raise AssertionError("resolve_provider called for provider none")

    fake = Fake()
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "none")
    monkeypatch.setattr(retrieval, "resolve_provider", fake)

    assert retrieve_for_context("q", "s", "a", "r", "h") is None
    assert fake.call_count == 0


def test_enabled_block_below_all_authoritative_sections(client, monkeypatch):
    received = {}

    def fake(query, scope, agent_role, run_id, handoff_id):
        received["args"] = (query, scope, agent_role, run_id, handoff_id)
        return (
            "<supplemental_knowledge>\n"
            "MARKER_SUPPLEMENTAL_XYZ\n"
            "</supplemental_knowledge>"
        )

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(retrieval, "retrieve_for_context", fake)

    resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert resp.status_code == 200
    prompt = resp.json()["prompt"]
    assert "MARKER_SUPPLEMENTAL_XYZ" in prompt
    assert prompt.index("MARKER_SUPPLEMENTAL_XYZ") > prompt.index("</task>")
    assert prompt.index("MARKER_SUPPLEMENTAL_XYZ") > prompt.index("</governance>")
    assert prompt.index("MARKER_SUPPLEMENTAL_XYZ") > prompt.index("</scope>")
    assert prompt.index("MARKER_SUPPLEMENTAL_XYZ") > prompt.index("</validation>")
    assert prompt.index("MARKER_SUPPLEMENTAL_XYZ") > prompt.index("</constraint>")

    query, scope, agent_role, run_id, handoff_id = received["args"]
    assert query == "Implement the requested change."
    assert handoff_id == "???"
    assert prompt.rstrip().endswith("</supplemental_knowledge>")


def test_enabled_none_block_leaves_prompt_byte_identical(client, monkeypatch):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(retrieval, "retrieve_for_context", lambda *a, **k: None)
    enabled_resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert enabled_resp.status_code == 200
    enabled_prompt = enabled_resp.json()["prompt"]

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    disabled_resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert disabled_resp.status_code == 200
    disabled_prompt = disabled_resp.json()["prompt"]

    assert enabled_prompt == disabled_prompt
    assert "<supplemental_knowledge>" not in enabled_prompt
    assert "<supplemental_knowledge>" not in disabled_prompt


def test_token_budget_measured_on_rendered_block(monkeypatch):
    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=2, token_budget=40):
            # 3 oversized items; the service must truncate/trim to fit.
            return [
                {"path": f"file{i}.md", "content": " ".join(["token"] * 50)}
                for i in range(3)
            ]

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 2)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 40)
    monkeypatch.setattr(retrieval, "resolve_provider", lambda key, scope=None: StubProvider)

    block = retrieve_for_context("q", "s", "a", "r", "h")
    assert block is not None
    assert len(block.split()) <= 40
    assert "<supplemental_knowledge>" in block
    assert "</supplemental_knowledge>" in block


def test_empty_results_return_none(monkeypatch):
    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=8, token_budget=100):
            return []

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 100)
    monkeypatch.setattr(retrieval, "resolve_provider", lambda key, scope=None: StubProvider)

    assert retrieve_for_context("q", "s", "a", "r", "h") is None


def test_compile_records_one_retrieval_row(client, monkeypatch, tmp_path):
    db = _create_retrieval_log_db(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db))
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    stub_results = [{"path": "a.md", "content": "alpha beta gamma"}]

    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=None, token_budget=None):
            return list(stub_results)

    monkeypatch.setattr(retrieval, "resolve_provider", lambda key, scope=None: StubProvider)

    resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert resp.status_code == 200

    rows = _fetch_log_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "stub"
    assert row["scope"] == "dpmtf-webui"
    assert row["query"] == "Implement the requested change."
    assert row["result_count"] == 1
    assert row["retrieved_token_count"] == 3
    assert row["retrieval_duration_ms"] >= 0
    assert row["agent_role"] == "Implementor"
    assert row["run_id"] == ""
    assert row["handoff_id"] == "???"

    stub_results.clear()
    resp2 = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert resp2.status_code == 200

    rows = _fetch_log_rows(db)
    assert len(rows) == 2
    second = rows[1]
    assert second["result_count"] == 0
    assert second["sources"] == "[]"
    assert second["retrieved_token_count"] == 0


def test_compile_records_the_flow_key_in_the_retrieval_row(
    client, monkeypatch, tmp_path
):
    db = _create_retrieval_log_db_with_flow_key(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db))
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    stub_results = [{"path": "a.md", "content": "alpha beta gamma"}]

    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=None, token_budget=None):
            return list(stub_results)

    monkeypatch.setattr(
        retrieval, "resolve_provider", lambda key, scope=None: StubProvider
    )

    resp = client.post(
        "/api/prompt-compiler/compile",
        json={**COMPILE_BODY, "flow_key": "test_flow"},
    )
    assert resp.status_code == 200

    rows = _fetch_log_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["flow_key"] == "test_flow"
    assert row["provider"] == "stub"
    assert row["result_count"] == 1


def test_provider_failure_leaves_prompt_byte_identical(client, monkeypatch):
    import routers.prompt_compiler as prompt_compiler

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)

    def explode(*args, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(
        prompt_compiler.retrieval, "retrieve_for_context", explode
    )

    enabled_resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert enabled_resp.status_code == 200
    enabled_prompt = enabled_resp.json()["prompt"]

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    disabled_resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert disabled_resp.status_code == 200
    disabled_prompt = disabled_resp.json()["prompt"]

    assert enabled_prompt == disabled_prompt
    assert "<supplemental_knowledge>" not in enabled_prompt
    assert "<supplemental_knowledge>" not in disabled_prompt


def test_flow_branch_disabled_is_byte_identical(client, seed_db, monkeypatch):
    import routers.prompt_compiler as prompt_compiler

    conn = sqlite3.connect(seed_db)
    try:
        conn.execute(
            "INSERT INTO bridge_flow_steps "
            "(flow_key, step_key, from_role, to_role, deliverable_dir, "
            " sort_order, is_active) "
            "VALUES ('test_flow', 'step1', 'architect', 'implementer', '', 1, 1)"
        )
        conn.commit()
    finally:
        conn.close()

    payload = {
        "deployment_strategy": "standard",
        "target_project": "test-project",
        "flow_key": "test_flow",
        "step_key": "step1",
        "goal": "Do the thing.",
        "scope_gate_confirmed": True,
    }

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(
        prompt_compiler.retrieval, "retrieve_for_context", lambda *a, **k: None
    )

    enabled_resp = client.post("/api/prompt-compiler/compile", json=payload)
    assert enabled_resp.status_code == 200
    enabled_prompt = enabled_resp.json()["prompt"]

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    disabled_resp = client.post("/api/prompt-compiler/compile", json=payload)
    assert disabled_resp.status_code == 200
    disabled_prompt = disabled_resp.json()["prompt"]

    assert enabled_prompt == disabled_prompt
    assert "<supplemental_knowledge>" not in enabled_prompt
    assert "<supplemental_knowledge>" not in disabled_prompt


def test_compile_queries_the_configured_scope_not_the_flow_key(client, seed_db, monkeypatch):
    conn = sqlite3.connect(seed_db)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO bridge_flow_steps "
            "(flow_key, step_key, from_role, to_role, deliverable_dir, sort_order, is_active) "
            "VALUES ('test_flow', 'step1', 'architect', 'implementer', '', 1, 1)"
        )
        conn.commit()
    finally:
        conn.close()

    payload = {
        "deployment_strategy": "standard",
        "target_project": "test-project",
        "flow_key": "test_flow",
        "step_key": "step1",
        "goal": "Do the thing.",
        "scope_gate_confirmed": True,
    }

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    guard_seen = {}

    def _record_guard(scope, agent_role=None, flow_key=None):
        guard_seen["scope"] = scope
        guard_seen["agent_role"] = agent_role
        guard_seen["flow_key"] = flow_key

    monkeypatch.setattr(
        retrieval.scope_guard, "require_scope_access", _record_guard
    )
    # Keep the seed_db clean: it has no knowledge_retrieval_log table, and the
    # log write is not what this test pins.
    monkeypatch.setattr(retrieval, "_record_retrieval", lambda *a, **k: None)

    search_seen = {}

    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=None, token_budget=None):
            search_seen["scope"] = scope
            return [{"path": "a.md", "content": "alpha beta gamma"}]

    monkeypatch.setattr(retrieval, "resolve_provider", lambda key, scope=None: StubProvider)

    resp = client.post("/api/prompt-compiler/compile", json=payload)
    assert resp.status_code == 200

    # Half 1: the search scope is the configured scope, not the flow key.
    assert search_seen["scope"] == "dpmtf-webui"
    assert search_seen["scope"] != "test_flow"
    # Half 2: the flow key still reaches require_scope_access (run 019 contract).
    assert guard_seen["scope"] == "dpmtf-webui"
    assert guard_seen["flow_key"] == "test_flow"


def test_compile_queries_the_target_project_scope_for_a_foreign_flow(
    client, seed_db, monkeypatch, tmp_path
):
    foreign_dir = tmp_path / "FooProj"
    foreign_dir.mkdir()

    conn = sqlite3.connect(seed_db)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO bridge_flows "
            "(flow_key, name, target_project_path) "
            "VALUES ('foreign_flow', 'Foreign Flow', ?)",
            (str(foreign_dir),),
        )
        conn.execute(
            "INSERT OR IGNORE INTO bridge_flow_steps "
            "(flow_key, step_key, from_role, to_role, deliverable_dir, "
            " sort_order, is_active) "
            "VALUES ('foreign_flow', 'step1', 'architect', 'implementer', '', 1, 1)"
        )
        conn.commit()
    finally:
        conn.close()

    payload = {
        "deployment_strategy": "standard",
        "target_project": "test-project",
        "flow_key": "foreign_flow",
        "step_key": "step1",
        "goal": "Do the thing.",
        "scope_gate_confirmed": True,
    }

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    guard_seen = {}

    def _record_guard(scope, agent_role=None, flow_key=None):
        guard_seen["scope"] = scope
        guard_seen["agent_role"] = agent_role
        guard_seen["flow_key"] = flow_key

    monkeypatch.setattr(
        retrieval.scope_guard, "require_scope_access", _record_guard
    )
    # The temp DB has no knowledge_retrieval_log table; the log write is not
    # what this test pins.
    monkeypatch.setattr(retrieval, "_record_retrieval", lambda *a, **k: None)

    search_seen = {}

    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=None, token_budget=None):
            search_seen["scope"] = scope
            return [{"path": "a.md", "content": "alpha beta gamma"}]

    monkeypatch.setattr(retrieval, "resolve_provider", lambda key, scope=None: StubProvider)

    resp = client.post("/api/prompt-compiler/compile", json=payload)
    assert resp.status_code == 200

    # Half 1: the search scope is the slug of the flow's target, not the
    # checkout's configured scope and not the flow key.
    assert search_seen["scope"] == "fooproj"
    assert search_seen["scope"] != "dpmtf-webui"
    assert search_seen["scope"] != "foreign_flow"
    # Half 2: the flow key still reaches require_scope_access (run 019
    # contract), and the guard receives the same foreign scope.
    assert guard_seen["scope"] == "fooproj"
    assert guard_seen["flow_key"] == "foreign_flow"


def test_retrieval_returns_none_and_logs_error_when_provider_not_ready(
    monkeypatch, caplog
):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)
    # ``dpmtf-webui`` is an internal scope; bypass the grant DB so the test
    # reaches provider.preflight() and pins the ProviderNotReady path only.
    monkeypatch.setattr(
        retrieval.scope_guard, "require_scope_access", lambda *a, **k: None
    )

    called = []
    monkeypatch.setattr(
        retrieval.retrieval_log, "record_retrieval", lambda **k: called.append(1)
    )

    class NotReadyProvider:
        def preflight(self) -> None:
            raise ProviderNotReady(
                "knowledge provider not ready: no CUDA device is available"
            )

        def search(self, *args, **kwargs):
            raise AssertionError("search must not run when preflight fails")

    monkeypatch.setattr(retrieval, "resolve_provider", lambda key, scope=None: NotReadyProvider)

    with caplog.at_level("ERROR", logger="knowledge.retrieval"):
        result = retrieve_for_context("q", "dpmtf-webui", "a", "r", "h")

    assert result is None
    assert called == []  # no knowledge_retrieval_log row was written
    assert "not ready" in caplog.text


def test_retrieval_resolves_the_provider_for_the_requested_scope(monkeypatch):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_provider", lambda: "stub")
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)
    monkeypatch.setattr(
        retrieval.scope_guard, "require_scope_access", lambda *a, **k: None
    )
    monkeypatch.setattr(retrieval, "_record_retrieval", lambda *a, **k: None)

    resolve_calls = []

    class StubProvider:
        def preflight(self) -> None:
            return None

        def search(self, query, scope=None, top_k=None, token_budget=None):
            return [{"path": "docs/a.md", "content": "alpha beta gamma"}]

    def _spy_resolve(key, scope=None):
        resolve_calls.append((key, scope))
        return StubProvider

    monkeypatch.setattr(retrieval, "resolve_provider", _spy_resolve)

    block = retrieve_for_context(
        "How is a FlowApp exported and imported?",
        "flowrunner",
        "9000-implementer",
        "",
        "run-029",
    )

    assert block is not None
    assert resolve_calls == [("stub", "flowrunner")]
