"""LightWorkers router (GOAL.md §20: Polling and Claim Protocol).

The eight endpoints in this module are the Father side of the polling
and claim protocol. They are reached by a LightWorker over its
`father_client.FatherClient` (``/home/svend/DPMtF-LightWorker/src/
dpmtf_lightworker/father_client.py``), which is the currently canonical
shape of the contract. Every path, method and body here was taken from
that client.

The router depends on a ``LightWorkerStore`` interface — the only
behavior the routers ask for. The InMemoryStore implementation is
shipped here for V1; a durable store is a later run.

State this handoff must hold (§20):

* Worker identity and static matching. An execution is offered to the
  ``worker_id`` it is addressed to and to no other. A claim from any
  other worker is refused.
* Atomic claim. Two claims for the same execution: exactly one wins.
* Duplicate-execution protection. A worker that already holds a live
  execution is offered no second one. §5.3 fixes
  ``max_parallel_executions: 1`` for V1.
* Idempotent completion and idempotent failure. The same
  ``(execution_id, attempt_id)`` reported twice changes state once.
  This holds for both ``complete`` and ``fail`` even though only
  ``complete`` is measured by the criteria — the client caches both
  and the server is where the property actually lives.
* Result validation (§17). A completion's ``result`` must be a
  non-empty dict with a known ``mode`` and the required keys for that
  mode. ``summary`` and ``logs`` are recorded if present and are NOT
  required; this run does not demand them.

§5.2 keeps Father on this side of the boundary: this router does not
move a flow forward, does not pick a next role, does not mark a job
complete. An accepted completion is a record; it continues nothing.
"""

from __future__ import annotations

import hmac
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Store interface and the in-memory implementation shipped in V1
# ---------------------------------------------------------------------------


class LightWorkerStore:
    """The interface the router depends on.

    The router calls into a store for every operation that needs
    state. ``create_router`` does not touch the store while building
    the router — every method below is invoked only from inside a route
    handler.

    The semantics below are what the §20 properties rest on. A
    different implementation (durable, distributed, …) must honor
    them too.
    """

    def register(self, worker_id: str, capabilities: Dict[str, Any]) -> None:
        """Record that ``worker_id`` presented itself with ``capabilities``."""

    def heartbeat(self, worker_id: str) -> None:
        """Record a liveness ping from ``worker_id``."""

    def offer_next(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Find an execution addressed to ``worker_id`` that the worker
        does not already hold.

        Returns the execution dict (``execution_id``, ``worker_id``,
        ``target_role``, …) if one is offered, or ``None`` if nothing
        should be handed out — including the case where the worker is
        already busy with another live execution.
        """

    def claim(self, execution_id: str, worker_id: str) -> bool:
        """Atomically claim ``execution_id`` for ``worker_id``.

        Returns ``True`` if the claim succeeded. Returns ``False`` if
        the execution is already claimed, or if the execution is not
        addressed to ``worker_id`` (refusing a foreign worker is the
        server's invariant; the caller maps ``False`` to an HTTP
        status code in the right half of the accept/refuse split).
        """

    def execution_heartbeat(
        self, execution_id: str, worker_id: str, attempt_id: str
    ) -> None:
        """Record an attempt-bound heartbeat."""

    def record_event(
        self, execution_id: str, worker_id: str, event: Dict[str, Any]
    ) -> None:
        """Record an event sent by the worker for ``execution_id``."""

    def complete(
        self,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        result: Dict[str, Any],
    ) -> bool:
        """Record a completion for ``(execution_id, attempt_id)``.

        Returns ``True`` if the call changed state. Returns ``False``
        if the same ``(execution_id, attempt_id)`` had already been
        recorded — the second call is idempotent on the wire
        (still HTTP 200) but does not change state a second time.
        """

    def fail(
        self,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        failure: Dict[str, Any],
    ) -> bool:
        """Record a failure for ``(execution_id, attempt_id)``.

        Same idempotency semantics as :meth:`complete`.
        """

    def completion_count(self, execution_id: str, attempt_id: str) -> int:
        """How many times ``(execution_id, attempt_id)`` actually changed
        state.

        Returns an ``int``. Used by the criteria to assert that a
        duplicate ``complete`` only counted once.
        """

    def failure_count(self, execution_id: str, attempt_id: str) -> int:
        """How many times ``(execution_id, attempt_id)`` actually changed
        state via a failure report. Same shape as
        :meth:`completion_count`.
        """


class InMemoryStore(LightWorkerStore):
    """V1 in-memory store.

    Thread-safe enough for the test suite; not durable, not
    distributed. A production deployment uses a different
    implementation that satisfies the same interface.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._capabilities: Dict[str, Dict[str, Any]] = {}
        self._heartbeats: Dict[str, float] = {}
        # All executions ever offered to a worker, keyed by worker_id.
        # Each entry is the execution dict, with an internal
        # ``_status`` field that is one of:
        #   ``"available"``    — already in the queue, not yet polled
        #   ``"delivered"``    — handed out to the worker, not yet claimed
        #   ``"claimed"``      — claimed by the worker, in flight
        self._offers: Dict[str, List[Dict[str, Any]]] = {}
        # Claimed executions, keyed by execution_id.
        self._claimed_by: Dict[str, str] = {}
        # The execution a worker currently holds, keyed by worker_id.
        # §5.3: max_parallel_executions == 1.
        self._live: Dict[str, str] = {}
        # Idempotency bookkeeping for completion and failure.
        self._completions: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._failures: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # Counter used by completion_count / failure_count.
        self._completion_count: Dict[Tuple[str, str], int] = {}
        self._failure_count: Dict[Tuple[str, str], int] = {}
        # Event log per execution. Recorded without semantic meaning.
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    # --- store-only helpers used by tests ---------------------------------

    def offer(self, execution: Dict[str, Any]) -> None:
        """Seed an execution into the queue for ``worker_id``.

        ``execution`` is a single positional dict with at least
        ``execution_id``, ``worker_id`` and ``target_role``. The dict
        is stored as-is, so the test can later read back whatever
        fields it put in. A private ``_status`` field is added so
        the store can track whether the execution is still available,
        has been delivered, or has been claimed.
        """
        worker_id = execution["worker_id"]
        with self._lock:
            entry = dict(execution)
            entry["_status"] = "available"
            self._offers.setdefault(worker_id, []).append(entry)

    # --- LightWorkerStore implementation ---------------------------------

    def register(self, worker_id: str, capabilities: Dict[str, Any]) -> None:
        with self._lock:
            self._capabilities[worker_id] = dict(capabilities)
            self._heartbeats[worker_id] = _now()

    def heartbeat(self, worker_id: str) -> None:
        with self._lock:
            self._heartbeats[worker_id] = _now()

    def offer_next(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            # §5.3: max_parallel_executions == 1. A worker holding an
            # in-flight execution is offered no second one.
            if worker_id in self._live:
                return None
            queue = self._offers.get(worker_id, [])
            for entry in queue:
                if entry["_status"] == "available":
                    entry["_status"] = "delivered"
                    return entry
            return None

    def claim(self, execution_id: str, worker_id: str) -> bool:
        with self._lock:
            if worker_id in self._live and self._live[worker_id] != execution_id:
                return False
            if execution_id in self._claimed_by:
                return False
            for entry in self._offers.get(worker_id, []):
                if entry.get("execution_id") == execution_id:
                    if entry["_status"] == "claimed":
                        return False
                    entry["_status"] = "claimed"
                    self._claimed_by[execution_id] = worker_id
                    self._live[worker_id] = execution_id
                    return True
            return False

    def execution_heartbeat(
        self, execution_id: str, worker_id: str, attempt_id: str
    ) -> None:
        with self._lock:
            self._heartbeats[_hb_key(execution_id, worker_id, attempt_id)] = _now()

    def record_event(
        self, execution_id: str, worker_id: str, event: Dict[str, Any]
    ) -> None:
        with self._lock:
            self._events.setdefault(execution_id, []).append(
                {"worker_id": worker_id, "event": dict(event)}
            )

    def complete(
        self,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        result: Dict[str, Any],
    ) -> bool:
        key = (execution_id, attempt_id)
        with self._lock:
            if key in self._completions:
                return False
            self._completions[key] = {
                "worker_id": worker_id,
                "result": dict(result),
            }
            self._completion_count[key] = (
                self._completion_count.get(key, 0) + 1
            )
            self._live.pop(worker_id, None)
            return True

    def fail(
        self,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        failure: Dict[str, Any],
    ) -> bool:
        key = (execution_id, attempt_id)
        with self._lock:
            if key in self._failures:
                return False
            self._failures[key] = {
                "worker_id": worker_id,
                "failure": dict(failure),
            }
            self._failure_count[key] = self._failure_count.get(key, 0) + 1
            self._live.pop(worker_id, None)
            return True

    def completion_count(self, execution_id: str, attempt_id: str) -> int:
        return self._completion_count.get((execution_id, attempt_id), 0)

    def failure_count(self, execution_id: str, attempt_id: str) -> int:
        return self._failure_count.get((execution_id, attempt_id), 0)


def _now() -> float:
    import time
    return time.time()


def _hb_key(execution_id: str, worker_id: str, attempt_id: str) -> str:
    return f"{execution_id}|{worker_id}|{attempt_id}"


# ---------------------------------------------------------------------------
# Request bodies — the shapes the LightWorker POSTs in
# ---------------------------------------------------------------------------


class RegisterBody(BaseModel):
    worker_id: str
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class HeartbeatBody(BaseModel):
    worker_id: str


class ClaimBody(BaseModel):
    worker_id: str


class ExecutionHeartbeatBody(BaseModel):
    worker_id: str
    attempt_id: str


class EventBody(BaseModel):
    worker_id: str
    event: Dict[str, Any]


class CompleteBody(BaseModel):
    worker_id: str
    attempt_id: str
    result: Dict[str, Any]


class FailBody(BaseModel):
    worker_id: str
    attempt_id: str
    failure: Dict[str, Any]


# ---------------------------------------------------------------------------
# Result validation (§17)
# ---------------------------------------------------------------------------

_REQUIRED_KEYS_BY_MODE: Dict[str, Set[str]] = {
    "deliverable_only": {"deliverable", "checksum"},
    "patch": {"patch", "base_commit", "result_commit", "checksum"},
    "patch_and_deliverable": {
        "patch",
        "base_commit",
        "result_commit",
        "checksum",
        "deliverable",
    },
}


def _validate_result(result: Dict[str, Any]) -> Optional[str]:
    """Return ``None`` if ``result`` is valid; an error message otherwise.

    The shape is fixed by §17:

    * ``result`` must be a dict.
    * It must not be empty.
    * ``mode`` must be one of the three known modes.
    * All required keys for that mode must be present.
    * ``summary`` and ``logs`` are recorded if present and are NOT
      required — §17.2 lists them in prose but this run does not
      demand them, and that narrowing is a deliberate choice.
    """
    if not isinstance(result, dict):
        return "result must be an object"
    if not result:
        return "result must not be empty"
    mode = result.get("mode")
    if not isinstance(mode, str):
        return "result.mode must be a string"
    required = _REQUIRED_KEYS_BY_MODE.get(mode)
    if required is None:
        return f"unknown result.mode: {mode!r}"
    missing = [k for k in sorted(required) if k not in result]
    if missing:
        return f"missing required keys for mode {mode!r}: {missing}"
    return None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def _expected_token() -> Optional[str]:
    """The shared secret Father accepts, or None when none is configured."""
    token = os.environ.get("LIGHTWORKER_AUTH_TOKEN", "")
    return token or None


def require_worker_auth(authorization: str = Header(default="")) -> None:
    """Authenticate the caller as a known worker (GOAL.md §27).

    §27 requires worker identity to be authenticated and states plainly
    that Tailscale membership must not be the sole authorization
    mechanism. This is the second mechanism.

    **What it provides:** only a caller holding the shared secret may
    reach these endpoints. **What it does not:** it does not distinguish
    one worker from another — every worker presenting the secret is
    accepted, and the `worker_id` in the body is still self-asserted.
    Per-worker credentials are the next step and are not this. Say so
    rather than letting a green check imply more.

    Refusing when no token is configured is deliberate. A server that
    silently accepts everyone because its secret is unset is worse than
    one that refuses: the failure is invisible exactly when it matters.
    """
    expected = _expected_token()
    if expected is None:
        raise HTTPException(
            status_code=503,
            detail="LIGHTWORKER_AUTH_TOKEN is not configured on Father",
        )
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        raise HTTPException(status_code=401, detail="missing bearer token")
    # Constant-time: a plain == leaks the shared secret one byte at a time
    # to anyone who can measure the response.
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="invalid bearer token")


def create_router(
    store: LightWorkerStore,
    on_complete: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> APIRouter:
    """Build the LightWorkers router bound to ``store``.

    This function does not touch ``store`` — every method call below
    lives inside a route handler. A criterion instantiates the router
    with ``object()`` purely to enumerate the routes, so the store
    must not be queried at build time.
    """
    router = APIRouter(dependencies=[Depends(require_worker_auth)])

    # --- register / heartbeat (worker-level) ----------------------------

    @router.post("/api/lightworkers/register")
    def register(body: RegisterBody) -> Dict[str, Any]:
        store.register(body.worker_id, body.capabilities)
        return {"status": "registered", "worker_id": body.worker_id}

    @router.post("/api/lightworkers/heartbeat")
    def heartbeat(body: HeartbeatBody) -> Dict[str, Any]:
        store.heartbeat(body.worker_id)
        return {"status": "ok", "worker_id": body.worker_id}

    # --- next execution to run -----------------------------------------

    @router.get("/api/lightworkers/{worker_id}/executions/next")
    def next_execution(worker_id: str) -> Any:
        offered = store.offer_next(worker_id)
        if offered is None:
            # §20 says nothing to offer is success with no body.
            # A 404 here would be a wrong-failure shape: FastAPI's
            # 404 body is `{"detail": ...}`, which is truthy and
            # would mislead a caller that reads `body or {}`.
            return None
        return offered

    # --- claim ---------------------------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/claim")
    def claim(execution_id: str, body: ClaimBody) -> Dict[str, Any]:
        if store.claim(execution_id, body.worker_id):
            return {"status": "claimed", "execution_id": execution_id,
                    "worker_id": body.worker_id}
        # Refused. We do not distinguish "wrong worker" from
        # "already claimed" — the public contract is binary.
        raise HTTPException(status_code=409, detail="claim refused")

    # --- attempt-bound heartbeat ---------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/heartbeat")
    def execution_heartbeat(
        execution_id: str, body: ExecutionHeartbeatBody
    ) -> Dict[str, Any]:
        store.execution_heartbeat(
            execution_id, body.worker_id, body.attempt_id
        )
        return {"status": "ok"}

    # --- events --------------------------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/events")
    def events(execution_id: str, body: EventBody) -> Dict[str, Any]:
        store.record_event(execution_id, body.worker_id, body.event)
        return {"status": "ok"}

    # --- complete ------------------------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/complete")
    def complete(execution_id: str, body: CompleteBody) -> Dict[str, Any]:
        error = _validate_result(body.result)
        if error is not None:
            raise HTTPException(status_code=422, detail=error)
        # Idempotent: returns 200 on both first and repeat calls.
        changed = store.complete(
            execution_id, body.worker_id, body.attempt_id, body.result
        )
        # §23: worker completion is not Father acceptance. The result is
        # recorded either way — the worker did what it did — but the chain
        # advances only on the first report, and only if Father accepts it.
        # A rejection is 422 and leaves the recorded completion in place.
        if changed and on_complete is not None:
            try:
                on_complete(execution_id, body.result)
            except Exception as exc:  # noqa: BLE001 - reported, never swallowed
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"status": "recorded", "execution_id": execution_id}

    # --- fail ----------------------------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/fail")
    def fail(execution_id: str, body: FailBody) -> Dict[str, Any]:
        store.fail(
            execution_id, body.worker_id, body.attempt_id, body.failure
        )
        return {"status": "recorded", "execution_id": execution_id}

    return router


__all__ = [
    "LightWorkerStore",
    "InMemoryStore",
    "create_router",
]
