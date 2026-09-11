"""Tests for the provider-neutral knowledge interface (GOAL-DRAFT-001).

The knowledge layer is disabled by default and the only concrete provider in
this Run is ``NoneProvider``, whose retrieval methods are no-ops.
"""

from __future__ import annotations

import inspect
import sys
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
