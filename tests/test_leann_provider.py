"""Tests for the LEANN-backed knowledge provider (GOAL-DRAFT-004).

The module sets ``sys.dont_write_bytecode`` before importing ``knowledge`` so
running the tests does not write ``__pycache__`` directories for the package
modules. The interface-conformance test proves the adapter imports without
``leann`` and fails clearly when LEANN is needed but absent. The live
roundtrip drives the real ``LeannProvider``, ``LeannBuilder`` and
``LeannSearcher`` against a temporary JSONL manifest. It stays offline by
monkeypatching only ``leann.embedding_compute.compute_embeddings`` — the
single embedding entry point both the builder and the searcher reach through
their lazy imports — to return a deterministic zero vector. The builder and
searcher classes remain the real LEANN classes; only the embedding function
is stubbed, and the test never touches the network.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Keep the imported package modules from writing bytecode caches.
sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.provider import KnowledgeProvider  # noqa: E402
from knowledge.leann_provider import LeannProvider  # noqa: E402

_LEANN_AVAILABLE = importlib.util.find_spec("leann") is not None


def _write_manifest(path: Path, records: list[dict]) -> None:
    """Write ``records`` as a JSONL manifest, one JSON object per line."""
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_interface_conformance_without_leann(monkeypatch, tmp_path):
    """The adapter imports and exposes the interface when LEANN is absent.

    ``leann`` is removed from ``sys.modules`` and any import of exactly
    ``leann`` is forced to fail. The adapter must still import (lazy-load
    proof) and an operation that needs LEANN must raise the clear en-US
    ``ImportError`` produced by ``_import_leann``.
    """
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [{"scope": "s", "path": "p.md", "content": "hello world"}],
    )

    real_import = builtins.__import__
    saved_modules = {
        name: sys.modules.pop(name)
        for name in ("knowledge.leann_provider", "leann")
        if name in sys.modules
    }

    def _blocked_import(name, *args, **kwargs):
        if name == "leann":
            raise ImportError("LEANN is blocked for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    try:
        module = importlib.import_module("knowledge.leann_provider")
        assert "leann" not in sys.modules
        assert issubclass(module.LeannProvider, KnowledgeProvider)
        with pytest.raises(ImportError, match="LEANN is not installed"):
            module.LeannProvider().index(str(manifest))
    finally:
        monkeypatch.undo()
        sys.modules.update(saved_modules)


def test_update_and_remove_are_honest_for_default_backend(tmp_path):
    """Default backend must not fake in-place update/remove success."""
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [{"scope": "s", "path": "p.md", "content": "hello world"}],
    )
    provider = LeannProvider()
    with pytest.raises(NotImplementedError, match="LEANN update is not supported"):
        provider.update(str(manifest))
    with pytest.raises(NotImplementedError, match="LEANN remove is not supported"):
        provider.remove(str(manifest))


@pytest.mark.skipif(
    not _LEANN_AVAILABLE,
    reason="LEANN is not installed; the registry gate check requires it",
)
def test_ivf_branch_is_gated_on_backend_registry(tmp_path):
    """The retained ivf branch is gated on ``leann.BACKEND_REGISTRY``.

    This checkout registers only ``hnsw`` and ``diskann``, so the ivf
    delegation must not be attempted and the methods must raise a clear
    ``NotImplementedError`` instead of falling through to an unregistered
    backend.
    """
    import leann

    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [{"scope": "s", "path": "p.md", "content": "hello world"}],
    )
    provider = LeannProvider(backend_name="ivf")
    if "ivf" in leann.BACKEND_REGISTRY:
        pytest.skip("ivf backend is registered; live ivf branch is out of scope")
    with pytest.raises(NotImplementedError, match="does not register the ivf backend"):
        provider.update(str(manifest))
    with pytest.raises(NotImplementedError, match="does not register the ivf backend"):
        provider.remove(str(manifest))


@pytest.mark.skipif(
    not _LEANN_AVAILABLE,
    reason="LEANN is not installed; live roundtrip requires the real package",
)
def test_live_index_search_roundtrip(monkeypatch, tmp_path):
    """Drive the real adapter, builder and searcher offline.

    Only ``leann.embedding_compute.compute_embeddings`` is stubbed with a
    deterministic zero vector; ``LeannBuilder`` and ``LeannSearcher`` are the
    real LEANN classes. This keeps the roundtrip offline and deterministic
    while still exercising the real index build, metadata persistence,
    searcher construction, metadata filtering and result mapping.
    """
    import numpy as np

    import leann.embedding_compute as leann_embedding

    def _offline_embeddings(
        texts,
        model_name,
        mode="sentence-transformers",
        is_build=False,
        batch_size=32,
        adaptive_optimization=True,
        manual_tokenize=False,
        max_length=512,
        provider_options=None,
    ):
        del model_name, mode, is_build, batch_size, adaptive_optimization
        del manual_tokenize, max_length, provider_options
        return np.zeros((len(texts), 8), dtype=np.float32)

    monkeypatch.setattr(leann_embedding, "compute_embeddings", _offline_embeddings)

    records = [
        {
            "scope": "repoA",
            "path": "a/one.md",
            "content": "the llama lives in the andes mountains of peru",
        },
        {
            "scope": "repoA",
            "path": "a/two.md",
            "content": "alpacas are smaller than llamas and live in herds",
        },
        {
            "scope": "repoB",
            "path": "b/three.md",
            "content": "llamas are domesticated south american camelids",
        },
    ]
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, records)

    provider = LeannProvider(
        backend_name="hnsw",
        embedding_model="offline-test-model",
        backend_kwargs={"is_compact": False, "is_recompute": False},
        searcher_kwargs={"recompute_embeddings": False, "enable_warmup": False},
    )
    provider.index(str(manifest))

    all_paths = {record["path"] for record in records}

    results = provider.search("llama", top_k=5)
    assert isinstance(results, list)
    assert results
    for item in results:
        assert item["path"] in all_paths
        assert item["content"].strip()

    top_two = provider.search("llama", top_k=2)
    assert len(top_two) <= 2

    token_budget = 6
    budgeted = provider.search("llama", top_k=2, token_budget=token_budget)
    total_tokens = sum(len(item["content"].split()) for item in budgeted)
    assert total_tokens <= token_budget
    if budgeted:
        # The last snippet is truncated to fit the budget, never padded.
        assert len(budgeted[-1]["content"].split()) <= token_budget

    scoped = provider.search("llama", scope="repoB")
    assert scoped
    assert {item["scope"] for item in scoped} == {"repoB"}
    assert {item["path"] for item in scoped} == {"b/three.md"}
