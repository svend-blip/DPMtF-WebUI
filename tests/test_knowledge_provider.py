"""Tests for the provider-neutral knowledge interface (GOAL-DRAFT-001).

The knowledge layer is disabled by default and the only concrete provider in
this Run is ``NoneProvider``, whose retrieval methods are no-ops.
"""

from __future__ import annotations

import inspect
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.provider import (  # noqa: E402
    KnowledgeProvider,
    NoneProvider,
    ProviderNotReady,
)
from knowledge.leann_provider import LeannProvider  # noqa: E402


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


def test_resolve_provider_binds_the_requested_scope_index_path(
    monkeypatch, tmp_path
):
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
        lambda: "configured-scope",
    )

    factory = knowledge_search.resolve_provider("leann", scope="flowrunner")
    provider = factory()
    assert isinstance(provider, FakeLeann)
    assert provider.index_path == str(tmp_path / "idx" / "flowrunner.leann")


def test_resolve_provider_without_scope_binds_the_configured_scope(
    monkeypatch, tmp_path
):
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
        lambda: "configured-scope",
    )

    factory = knowledge_search.resolve_provider("leann")
    provider = factory()
    assert isinstance(provider, FakeLeann)
    assert provider.index_path == str(tmp_path / "idx" / "configured-scope.leann")


def test_preflight_default_is_ready():
    assert NoneProvider().preflight() is None


def test_leann_preflight_rejects_when_no_cuda(monkeypatch):
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(
        is_available=lambda: False,
        mem_get_info=lambda: (0, 0),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    provider = LeannProvider(index_path="/nonexistent/x.leann")
    with pytest.raises(ProviderNotReady) as exc_info:
        provider.preflight()
    assert "no CUDA device is available" in str(exc_info.value)
    assert "leann" not in sys.modules


def test_leann_preflight_rejects_when_free_vram_below_threshold(monkeypatch):
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(
        is_available=lambda: True,
        mem_get_info=lambda: (638 * 1024 * 1024, 8 * 1024**3),  # 638 MiB free
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(
        "config.get_knowledge_min_free_vram_mib", lambda: 4096
    )

    provider = LeannProvider(index_path="/nonexistent/x.leann")
    with pytest.raises(ProviderNotReady) as exc_info:
        provider.preflight()
    assert "below the configured minimum" in str(exc_info.value)
    assert "leann" not in sys.modules


def test_leann_preflight_passes_when_free_vram_sufficient(monkeypatch):
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(
        is_available=lambda: True,
        mem_get_info=lambda: (8192 * 1024 * 1024, 16 * 1024**3),  # 8192 MiB free
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(
        "config.get_knowledge_min_free_vram_mib", lambda: 4096
    )

    provider = LeannProvider(index_path="/nonexistent/x.leann")
    assert provider.preflight() is None
    assert "leann" not in sys.modules
