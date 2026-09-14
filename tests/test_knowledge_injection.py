"""Tests for the knowledge retrieval injection path (Prompt Compiler).

DPMtF keeps only its client: retrieval always goes through
``knowledge.service_client``. These tests pin the compiler integration —
disabled retrieval leaves the prompt byte-for-byte unchanged, a retrieved
block lands below every authoritative section, and one local log row is
written per retrieval — and pin that the retrieval module namespace carries
no local provider path.
"""

import sys

sys.dont_write_bytecode = True

import logging
import sqlite3
from pathlib import Path

import pytest
import config
import knowledge.retrieval as retrieval
from knowledge.retrieval import retrieve_for_context


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


def _service_search_result(provider="test", results=None):
    return {
        "enabled": True,
        "provider": provider,
        "results": results or [{"path": "a.md", "content": "alpha beta gamma"}],
        "bounded": True,
    }


# ── Compiler integration ──────────────────────────────────────────────


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


# ── Service-path retrieval ─────────────────────────────────────────────


def test_retrieval_module_has_no_local_provider_path(monkeypatch, tmp_path):
    for forbidden in ("resolve_provider", "scope_guard", "_retrieve_locally"):
        assert not hasattr(retrieval, forbidden)

    db = _create_retrieval_log_db_with_flow_key(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db))
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)
    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (
            200,
            {
                "enabled": True,
                "provider": "test",
                "results": [
                    {"path": "a.md", "content": "alpha beta gamma", "score": 1.0}
                ],
                "bounded": True,
            },
        ),
    )

    block = retrieve_for_context("q", "s", "a", "r", "h", flow_key="test_flow")

    assert block is not None
    assert "<supplemental_knowledge>" in block
    assert "source: a.md" in block

    rows = _fetch_log_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "service:test"
    assert row["flow_key"] == "test_flow"
    assert row["result_count"] == 1
    assert row["handoff_id"] == "h"


def test_disabled_returns_none_without_calling_the_service(monkeypatch):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)

    def tripwire(*args, **kwargs):
        raise AssertionError("service called while disabled")

    monkeypatch.setattr(retrieval.service_client, "search", tripwire)

    assert retrieve_for_context("q", "s", "a", "r", "h") is None


def test_token_budget_measured_on_rendered_block(monkeypatch, tmp_path):
    db = _create_retrieval_log_db_with_flow_key(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db))
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 2)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 40)
    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (
            200,
            {
                "enabled": True,
                "provider": "test",
                "results": [
                    {"path": f"file{i}.md", "content": " ".join(["token"] * 50)}
                    for i in range(3)
                ],
                "bounded": True,
            },
        ),
    )

    block = retrieve_for_context("q", "s", "a", "r", "h")
    assert block is not None
    assert len(block.split()) <= 40
    assert "<supplemental_knowledge>" in block
    assert "</supplemental_knowledge>" in block


def test_empty_results_return_none(monkeypatch, tmp_path):
    db = _create_retrieval_log_db_with_flow_key(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db))
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 100)
    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (
            200,
            {"enabled": True, "provider": "test", "results": [], "bounded": True},
        ),
    )

    assert retrieve_for_context("q", "s", "a", "r", "h") is None


def test_compile_records_one_retrieval_row(client, monkeypatch, tmp_path):
    db = _create_retrieval_log_db_with_flow_key(tmp_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db))
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    stub_results = [{"path": "a.md", "content": "alpha beta gamma"}]
    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (
            200,
            {
                "enabled": True,
                "provider": "test",
                "results": list(stub_results),
                "bounded": True,
            },
        ),
    )

    resp = client.post("/api/prompt-compiler/compile", json=COMPILE_BODY)
    assert resp.status_code == 200

    rows = _fetch_log_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "service:test"
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
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (
            200,
            {
                "enabled": True,
                "provider": "test",
                "results": [{"path": "a.md", "content": "alpha beta gamma"}],
                "bounded": True,
            },
        ),
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
    assert row["provider"] == "service:test"
    assert row["result_count"] == 1


def test_service_denied_and_transport_failure_leave_the_prompt_unchanged(
    monkeypatch, caplog
):
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    monkeypatch.setattr(config, "get_knowledge_top_k", lambda: 8)
    monkeypatch.setattr(config, "get_knowledge_max_context_tokens", lambda: 1000)

    log_calls = []
    monkeypatch.setattr(
        retrieval.retrieval_log,
        "record_retrieval",
        lambda **kwargs: log_calls.append(kwargs) or None,
    )

    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (403, {"detail": "scope access denied"}),
    )
    assert retrieve_for_context("q", "s", "a", "r", "h") is None
    assert log_calls == []

    monkeypatch.setattr(
        retrieval.service_client,
        "_http",
        lambda *args, **kwargs: (503, {"detail": "knowledge service not ready"}),
    )
    with caplog.at_level(logging.ERROR, logger="knowledge.retrieval"):
        result = retrieve_for_context("q", "s", "a", "r", "h")

    assert result is None
    assert "not ready" in caplog.text
    assert log_calls == []
