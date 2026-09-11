"""Provider-neutral knowledge package.

The knowledge layer is disabled by default; the default provider is the
no-op ``NoneProvider``.
"""

from knowledge.provider import KnowledgeProvider, NoneProvider

__all__ = ["KnowledgeProvider", "NoneProvider"]
