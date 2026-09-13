"""Tests for the provider-neutral knowledge interface (GOAL-DRAFT-001).

The knowledge layer is disabled by default and the only concrete provider in
this Run is ``NoneProvider``, whose retrieval methods are no-ops.
"""

from __future__ import annotations

import inspect
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.provider import KnowledgeProvider, NoneProvider  # noqa: E402


def test_knowledge_provider_is_abstract():
    assert inspect.isabstract(KnowledgeProvider)


def test_interface_declares_the_four_operations():
    for name in ("index", "update", "remove", "search"):
        assert hasattr(KnowledgeProvider, name)


def test_knowledge_provider_cannot_be_instantiated():
    try:
        KnowledgeProvider()
    except TypeError:
        pass
    else:
        raise AssertionError("KnowledgeProvider must be abstract")


def test_none_provider_is_a_knowledge_provider():
    assert isinstance(NoneProvider(), KnowledgeProvider)


def test_none_provider_search_returns_empty_list():
    result = NoneProvider().search(
        "q", scope="dpmtf", filters={}, top_k=5, token_budget=1000
    )
    assert result == []
    assert isinstance(result, list)


def test_none_provider_maintenance_methods_do_not_raise():
    provider = NoneProvider()
    assert provider.index("source") is None
    assert provider.update("source") is None
    assert provider.remove("source") is None


def test_leann_loader_uses_the_configured_index_dir(monkeypatch, tmp_path):
    import knowledge.search as knowledge_search

    class FakeLeann:
        def __init__(self, index_path=None):
            self.index_path = index_path

    fake_module = types.ModuleType("knowledge.leann_provider")
    fake_module.LeannProvider = FakeLeann
    monkeypatch.setitem(sys.modules, "knowledge.leann_provider", fake_module)

    monkeypatch.setattr(
        knowledge_search.config,
        "get_knowledge_index_dir",
        lambda: str(tmp_path / "idx"),
    )
    monkeypatch.setattr(
        knowledge_search.config,
        "get_knowledge_scope",
        lambda: "custom-scope",
    )

    loader = knowledge_search._load_leann_provider()
    provider = loader()
    assert isinstance(provider, FakeLeann)
    assert provider.index_path == str(tmp_path / "idx" / "custom-scope.leann")
