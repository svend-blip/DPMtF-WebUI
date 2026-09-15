"""Knowledge API router: pure proxies to the standalone knowledge service.

``GET /api/knowledge/search``, ``POST /api/knowledge/refresh`` and
``GET /api/knowledge/learning`` forward to ``knowledge.service_client`` and
pass the service's HTTP status and body back unchanged. A transport failure
(status 0) becomes a 502. DPMtF keeps no provider, indexer, maintenance
routine or scope guard of its own, so this router has no local branch.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from knowledge import service_client

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class RefreshRequest(BaseModel):
    """Body for POST /api/knowledge/refresh."""

    scope: str
    repo_path: str


def _proxy_response(status: int, payload):
    """Return the service's status and body unchanged, or 502 on transport failure."""
    if status == 0:
        raise HTTPException(
            status_code=502,
            detail=(
                payload.get("detail")
                if isinstance(payload, dict)
                else str(payload)
            ),
        )
    return JSONResponse(status_code=status, content=payload)


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
    """Forward a search to the knowledge service and pass its response through."""
    status, payload = service_client.search(
        query=q,
        scope=scope,
        top_k=top_k,
        token_budget=token_budget,
        agent_role=agent_role,
        flow_key=flow_key,
        run_id=run_id,
        handoff_id=handoff_id,
    )
    return _proxy_response(status, payload)


@router.get("/learning")
async def list_learning(
    history: bool = False,
    repository: str = "",
):
    """Forward a learning-list request to the knowledge service and pass its response through."""
    status, payload = service_client.learning(
        history=history,
        repository=repository,
    )
    return _proxy_response(status, payload)


@router.post("/refresh")
async def refresh_knowledge(body: RefreshRequest):
    """Forward a refresh request to the knowledge service and pass its response through."""
    status, payload = service_client.refresh(
        scope=body.scope, repo_path=body.repo_path
    )
    return _proxy_response(status, payload)
