"""In-process tests for ``scripts/knowledge_success_gate.py`` (client path).

These tests pin the gate's contract: ``main()`` returns an ``int`` and prints
exactly the six ``criterion_N PASS``/``FAIL`` lines, and the six criteria
drive ``knowledge.service_client._http`` only — the gate never imports a
provider module and never touches the network.

Loading the gate via ``importlib.util`` from its absolute path keeps the import
independent of ``sys.path`` ordering and avoids creating a ``__pycache__``
file. Every write these tests perform goes to pytest's ``tmp_path`` (the
throwaway SQLite DB used for log-row assertions); the production
``databases/dpmtf.db`` is never opened.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
from pathlib import Path

import pytest

_GATE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "knowledge_success_gate.py"
)


@pytest.fixture(scope="session")
def gate_module():
    """Load the gate as a module without depending on sys.path or pycache."""
    spec = importlib.util.spec_from_file_location("knowledge_success_gate", _GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_service_http(gate_module):
    """Caller-owned fake service keyed by the gate's criterion markers."""

    def fake_http(method, url, params_or_body, timeout):
        query = (params_or_body or {}).get("q")
        if query == gate_module._C1_QUERY:
            return (200, {
                "enabled": False,
                "provider": "service",
                "results": [],
                "bounded": True,
            })
        if query == gate_module._C5_QUERY:
            return (403, {"detail": "scope access denied"})
        if query == gate_module._C6_QUERY:
            return (0, {"detail": "connection refused"})
        if query == gate_module._C4_QUERY:
            return (200, {
                "enabled": True,
                "provider": "service",
                "results": [
                    {"path": f"fat-{index}.md",
                     "content": " ".join(["token"] * 2000)}
                    for index in range(8)
                ],
                "bounded": True,
            })
        return (200, {
            "enabled": True,
            "provider": "service",
            "results": [
                {"path": f"doc-{index}.md", "content": f"content {index}"}
                for index in range(3)
            ],
            "bounded": True,
        })

    return fake_http


def test_gate_criteria_touch_only_the_service_client_seam(
    gate_module, monkeypatch, capsys
):
    monkeypatch.setattr(
        gate_module.service_client, "_http", _fake_service_http(gate_module)
    )

    result = gate_module.main()
    captured = capsys.readouterr()

    assert isinstance(result, int)
    assert result == 0
    assert captured.out == (
        "criterion_1 PASS\n"
        "criterion_2 PASS\n"
        "criterion_3 PASS\n"
        "criterion_4 PASS\n"
        "criterion_5 PASS\n"
        "criterion_6 PASS\n"
    )

    for forbidden in (
        "knowledge_search",
        "knowledge_indexer",
        "knowledge_maintenance",
        "knowledge_provider",
        "ProviderNotReady",
        "KnowledgeProvider",
        "NoneProvider",
    ):
        assert forbidden not in gate_module.__dict__


def test_gate_main_returns_nonzero_when_a_criterion_fails(
    gate_module, monkeypatch, capsys
):
    monkeypatch.setattr(
        gate_module, "criterion_1", lambda *args: ("criterion_1", False)
    )

    result = gate_module.main()
    captured = capsys.readouterr()

    assert result == 1
    assert "criterion_1 FAIL" in captured.out
