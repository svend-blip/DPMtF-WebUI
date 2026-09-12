"""Knowledge search API router (GET /api/knowledge/search).

Provider-neutral by construction: this module imports only
``knowledge.search`` and never names or imports a concrete provider
(TG4). ``top_k`` and ``token_budget`` fall back to the configured values
and are clamped to the configured ceilings (a caller may lower them,
never raise them); the endpoint still keeps the defensive
post-truncation of the returned list to ``top_k`` so a misbehaving
provider can never make the endpoint exceed the configured result bound.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time

from fastapi import APIRouter, HTTPException

import config
from knowledge import search as knowledge_search
from knowledge import scope_guard


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

logger = logging.getLogger(__name__)


def _record_retrieval(
    *,
    provider: str,
    scope: str | None,
    query: str,
    results: list,
    duration_ms: int,
    agent_role: str | None,
    run_id: str | None,
    handoff_id: str | None,
) -> None:
    """Append one ``knowledge_retrieval_log`` row for a real retrieval.

    Parameterized SQL only (``?`` placeholders, never string
    concatenation). A database failure is logged and surfaced to the
    caller as a 500 rather than swallowed silently.
    """
    sources = json.dumps([item["path"] for item in results])
    token_count = sum(len(item.get("content", "").split()) for item in results)

    conn = None
    try:
        conn = sqlite3.connect(config.get_db_path())
        conn.execute(
            "INSERT INTO knowledge_retrieval_log "
            "(provider, scope, query, result_count, sources, "
            "retrieved_token_count, retrieval_duration_ms, "
            "agent_role, run_id, handoff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                provider,
                scope or "",
                query,
                len(results),
                sources,
                token_count,
                duration_ms,
                agent_role,
                run_id,
                handoff_id,
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        logger.error("knowledge retrieval log insert failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to record knowledge retrieval",
        ) from exc
    finally:
        if conn is not None:
            conn.close()


@router.get("/search")
async def search_knowledge(
    q: str,
    scope: str | None = None,
    top_k: int | None = None,
    token_budget: int | None = None,
    agent_role: str | None = None,
    run_id: str | None = None,
    handoff_id: str | None = None,
):
    """Search the configured knowledge provider and record the retrieval.

    Disabled mode (``knowledge.enabled`` false, or configured provider
    ``none``) returns the stable disabled envelope and writes no log row.
    Enabled mode resolves the configured provider, searches it, and
    appends one ``knowledge_retrieval_log`` row. ``top_k`` and
    ``token_budget`` fall back to the configured values and are then
    clamped to the configured ceilings, so a caller may lower them but
    never raise them; the returned list is still defensively truncated
    to ``top_k``.
    """
    provider_key = config.get_knowledge_provider()

    if not config.get_knowledge_enabled() or provider_key == "none":
        return {
            "enabled": False,
            "provider": provider_key,
            "results": [],
            "bounded": True,
        }

    if top_k is None:
        top_k = config.get_knowledge_top_k()
    if token_budget is None:
        token_budget = config.get_knowledge_max_context_tokens()

    # Configured values are both fallback and ceiling: a caller may only
    # lower them, never raise them. A non-positive bound is clamped to the
    # minimum sensible value (1) so the defensive slice below can never
    # mis-bound (e.g. ``results[:-5]`` dropping the tail instead of the head).
    top_k = max(1, min(top_k, config.get_knowledge_top_k()))
    token_budget = max(1, min(token_budget, config.get_knowledge_max_context_tokens()))

    try:
        scope_guard.require_scope_access(
            scope,
            agent_role=agent_role,
            flow_key=None,
        )
    except scope_guard.ScopeAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    provider_cls = knowledge_search.resolve_provider(provider_key)
    provider = provider_cls()

    start = time.perf_counter()
    results = provider.search(
        q,
        scope=scope,
        top_k=top_k,
        token_budget=token_budget,
    )
    duration_ms = int((time.perf_counter() - start) * 1000)

    # Defensive bound: never return more than the configured ``top_k``,
    # even if the provider ignores its own contract. Result items pass
    # through unchanged (no fields stripped, no scores invented).
    results = results[:top_k]

    _record_retrieval(
        provider=provider_key,
        scope=scope,
        query=q,
        results=results,
        duration_ms=duration_ms,
        agent_role=agent_role,
        run_id=run_id,
        handoff_id=handoff_id,
    )

    return {
        "enabled": True,
        "provider": provider_key,
        "results": results,
        "bounded": True,
    }
