"""Provider resolution for the knowledge search API.

``routers/knowledge.py`` must stay free of any concrete provider name
(TG4), so the configured-provider-key to provider-class mapping lives
here. ``"none"`` maps to the no-op ``NoneProvider`` and ``"leann"`` maps
to the LEANN-backed provider. The LEANN-backed class is imported lazily
inside its loader so importing this service layer never imports the
optional LEANN dependency. Unknown provider keys resolve to
``NoneProvider`` and never raise, matching the disabled-by-default
contract: a misconfigured provider key must not take the API down.
"""

from __future__ import annotations

from typing import Callable

from knowledge.provider import KnowledgeProvider, NoneProvider

__all__ = ["PROVIDER_LOADERS", "resolve_provider"]


def _load_leann_provider() -> type[KnowledgeProvider]:
    """Import and return the LEANN-backed provider class on first use."""
    from knowledge.leann_provider import LeannProvider

    return LeannProvider


# Maps a configured provider key to a zero-argument loader returning the
# provider class. Loaders (rather than already-imported classes) keep the
# LEANN import lazy: importing this module must not import leann_provider.
PROVIDER_LOADERS: dict[str, Callable[[], type[KnowledgeProvider]]] = {
    "none": lambda: NoneProvider,
    "leann": _load_leann_provider,
}


def resolve_provider(name: str) -> type[KnowledgeProvider]:
    """Return the provider class for a configured provider key.

    ``"none"`` resolves to the no-op provider, and any unknown key also
    resolves to it, so a misconfigured provider key can never raise.
    """
    loader = PROVIDER_LOADERS.get(name)
    if loader is None:
        return NoneProvider
    return loader()
