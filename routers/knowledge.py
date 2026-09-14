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

import contextlib
import io
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from knowledge import indexer as knowledge_indexer
from knowledge import maintenance as knowledge_maintenance
from knowledge import search as knowledge_search
from knowledge import retrieval_log
from knowledge import scope_guard
from knowledge.provider import ProviderNotReady


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

logger = logging.getLogger(__name__)


class RefreshRequest(BaseModel):
    """Body for POST /api/knowledge/refresh."""

    scope: str
    repo_path: str


def _stderr_from_system_exit(exc: SystemExit) -> str:
    """Return the error text a ``_fail`` call printed before ``SystemExit``.

    ``knowledge.maintenance`` and ``knowledge.indexer`` report fatal errors by
    printing to stderr and then raising ``SystemExit(1)``. The refresh
    endpoint turns that into an HTTP 400 with the captured message instead of
    letting the traceback (or an empty detail) reach the client.
    """
    try:
        message = str(exc)
    except Exception:
        message = ""
    if message:
        return message
    return "operation failed"


def _run_capturing_stderr(func, *args):
    """Run ``func`` with stderr captured and return ``(ok, message)``.

    ``message`` is the captured stderr (stripped) on failure and the
    captured stderr (possibly empty, e.g. the indexer's ``indexed N
    document(s)`` report) on success.
    """
    stream = io.StringIO()
    with contextlib.redirect_stderr(stream):
        try:
            result = func(*args)
        except SystemExit as exc:
            captured = stream.getvalue().strip()
            return False, captured or _stderr_from_system_exit(exc)
    captured = stream.getvalue().strip()
    return True, (result, captured)


@router.get("/search")
async def search_knowledge(
    q: str,
    scope: str | None = None,
    top_k: int | None = None,
    token_budget: int | None = None,
    agent_role: str | None = None,
    run_id: str | None = None,
    handoff_id: str | None = None,
    flow_key: str | None = None,
):
    """Search the configured knowledge provider and record the retrieval.

    Disabled mode (``knowledge.enabled`` false, or configured provider
    ``none``) returns the stable disabled envelope and writes no log row.
    Enabled mode resolves the configured provider, searches it, and
    appends one ``knowledge_retrieval_log`` row. The optional ``flow_key`` is
    passed to the scope guard for grant matching and is not recorded in the
    retrieval log. ``top_k`` and
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
            flow_key=flow_key,
        )
    except scope_guard.ScopeAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    provider_cls = knowledge_search.resolve_provider(provider_key)
    provider = provider_cls()

    try:
        provider.preflight()
    except ProviderNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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

    retrieval_log.record_retrieval(
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


@router.post("/refresh")
async def refresh_knowledge(body: RefreshRequest):
    """Re-index a scope when its repository changed since the last index.

    Maintenance-only endpoint: it performs no scope-guard check and writes no
    ``knowledge_retrieval_log`` row. Validation and HTTP mapping stay here;
    the detect/index/provider/record work is delegated to
    ``knowledge.maintenance.refresh_scope``.
    """
    provider_key = config.get_knowledge_provider()

    # Disabled short-circuit first: mirror the search endpoint's envelope and
    # do no validation, no indexer call, no provider call, no DB write.
    if not config.get_knowledge_enabled() or provider_key == "none":
        return {
            "enabled": False,
            "provider": provider_key,
            "results": [],
            "bounded": True,
        }

    repo_path = Path(body.repo_path).expanduser().resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="repo_path must be an existing directory",
        )

    scope = body.scope.strip()
    if not scope:
        raise HTTPException(status_code=400, detail="scope must not be empty")

    index_dir = Path(config.get_knowledge_index_dir())
    try:
        index_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=400, detail=f"cannot create index dir: {exc}"
        ) from exc

    manifest_path = (index_dir / f"{scope}.jsonl").resolve()
    if manifest_path.is_relative_to(repo_path):
        raise HTTPException(
            status_code=400,
            detail="manifest must be outside repo_path",
        )

    try:
        ok, message = _run_capturing_stderr(
            lambda: knowledge_maintenance.refresh_scope(scope, str(repo_path))
        )
    except ProviderNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except knowledge_indexer.RepoExclusionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"refresh failed: {exc}"
        ) from exc
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    result, _captured_stderr = message
    return result
