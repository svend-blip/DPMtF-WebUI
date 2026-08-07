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

    def worker_token_hashes(self) -> Dict[str, str]:
        """token_hash -> worker_id for active per-worker credentials.

        Empty means legacy mode (shared token, identity unknown). The
        in-memory store returns empty unless a test sets `_token_hashes`.
        """
        return getattr(self, "_token_hashes", {})


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


# The store raises this when a second attempt reports on an execution that
# already reached a terminal state. Imported lazily-safe: the durable store
# module owns the class, and the in-memory store in this file raises the same
# one, so a single except clause covers both backends.
try:  # pragma: no cover - trivial import guard
    from routers.lightworker_store import (
        ExecutionAlreadyCompleted as _AlreadyTerminal,
    )
except ImportError:  # pragma: no cover
    _AlreadyTerminal = ValueError  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Result validation (§17)
# ---------------------------------------------------------------------------

_REQUIRED_KEYS_BY_MODE: Dict[str, Set[str]] = {
    "deliverable_only": {"deliverable"},
    "patch": {"patch", "base_commit", "result_commit", "checksum"},
    "patch_and_deliverable": {
        "patch",
        "base_commit",
        "result_commit",
        "checksum",
        "deliverable",
    },
}

# The vocabulary is `worker_results.validate_result`'s, not this file's.
# Until lightworker run 001 they were different: this validator asked for
# `mode` and a `checksum` beside a deliverable path, while the return path
# that publishes the deliverable asked for `result_mode` and a deliverable
# *object* carrying `content` and `sha256`.
#
# A result could therefore pass here and be refused there, which is what
# EXEC-005 did — 422 on a completion the store had already recorded, and no
# way for the worker to report it because the execution was terminal by then.
#
# The return path is canonical because it is the one that has to produce a
# file. §17.2 lists what the worker reports *about* a deliverable; with no
# artifact transfer in this version, the content itself has to travel, which
# run 001's contract states outright. `tests/test_result_contract.py` asserts
# both validators against one literal so the two cannot drift apart again.
_MODE_KEY = "result_mode"

# The status a completion must declare. The value is the return path's
# `worker_results.ACCEPTED_STATUS`, restated here because the router must
# stay importable without the bridge scripts on sys.path;
# tests/test_result_contract.py asserts the two strings are equal so they
# cannot drift apart silently.
#
# Until 2026-08-07 the endpoint did not look at `status` at all. A result
# without one passed here, was recorded as completed, and was then refused
# by the return path -- no chain advance, no result file, no alarm. The
# same disagreement class as the `mode`/`result_mode` split this file was
# fixed for earlier the same day, surviving in one field.
_REQUIRED_STATUS = "role_execution_completed"


def _validate_result(result: Dict[str, Any]) -> Optional[str]:
    """Return ``None`` if ``result`` is valid; an error message otherwise.

    This is the cheap gate: shape and required keys. Whether the content is
    usable — non-empty, checksum matching — belongs to the return path, which
    refuses with a reason rather than a status code.

    ``summary`` and ``logs`` are recorded if present and are NOT required —
    §17.2 lists them in prose but this run does not demand them, and that
    narrowing is a deliberate choice.
    """
    if not isinstance(result, dict):
        return "result must be an object"
    if not result:
        return "result must not be empty"
    status = result.get("status")
    if status != _REQUIRED_STATUS:
        # A failed or partial execution is reported through /fail, not
        # /complete. Refusing here, before the store records anything, is
        # the point: a completion recorded and then refused leaves the
        # execution terminal with no deliverable and no signal.
        return (
            f"result.status must be {_REQUIRED_STATUS!r}, got {status!r}"
        )
    mode = result.get(_MODE_KEY)
    if not isinstance(mode, str):
        return f"result.{_MODE_KEY} must be a string"
    required = _REQUIRED_KEYS_BY_MODE.get(mode)
    if required is None:
        return f"unknown result.{_MODE_KEY}: {mode!r}"
    present = set(result)
    ref = str(result.get("patch_artifact_sha256", "") or "")
    if (len(ref) == 64 and all(c in "0123456789abcdef" for c in ref)):
        present.add("patch")     # the patch travels as an artifact reference
    missing = [k for k in sorted(required) if k not in present]
    if missing:
        return f"missing required keys for mode {mode!r}: {missing}"
    if "deliverable" in required:
        deliverable = result.get("deliverable")
        if not isinstance(deliverable, dict):
            # A bare path string is what the worker used to send. It reads as
            # a deliverable and carries nothing, so the endpoint accepted a
            # result that could never produce a file.
            return (
                "result.deliverable must be an object carrying the content, "
                f"not a {type(deliverable).__name__}"
            )
        content = deliverable.get("content")
        ref = str(deliverable.get("artifact_sha256", "") or "")
        if len(ref) == 64 and all(c in "0123456789abcdef" for c in ref):
            # §23 artifact_reference: the content was uploaded first and is
            # redeemed -- and hash-verified -- by the return path.
            return None
        if not isinstance(content, str) or not content.strip():
            # Checked here rather than only in the return path so an empty
            # result is refused *before* the store records a completion.
            # EXEC-005 was recorded as completed and then refused, which left
            # the execution terminal — the worker's follow-up fail could not
            # land, and the record said "completed" for something Father had
            # rejected.
            #
            # The checksum is deliberately NOT verified here. §23 makes that
            # Father's authoritative validation, and duplicating it in two
            # places is how the two validators drifted apart to begin with.
            return "result.deliverable.content is empty"
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


class ArtifactBody(BaseModel):
    worker_id: str
    sha256: str
    content_b64: str


# Decoded size cap for one artifact. Base64-over-JSON is the wire format the
# existing FatherClient transport already speaks; the 33% inflation is the
# price of not inventing a second transport for the first artifact. Raise it
# when something real hits it.
ARTIFACT_MAX_BYTES = 32 * 1024 * 1024


def create_router(
    store: LightWorkerStore,
    on_complete: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    artifacts_dir: str = "",
) -> APIRouter:
    """Build the LightWorkers router bound to ``store``.

    This function does not touch ``store`` — every method call below
    lives inside a route handler. A criterion instantiates the router
    with ``object()`` purely to enumerate the routes, so the store
    must not be queried at build time.
    """
    def authenticated_worker(authorization: str = Header(default="")) -> str:
        """The worker the presented token belongs to, or "" in legacy mode.

        A closure over the store, deliberately: the token table travels
        with the store, so InMemory-backed tests never read the live
        database, and the live router reads the live table -- the exact
        test-hygiene split the day's earlier fixtures had to relearn.
        """
        hashes = store.worker_token_hashes()
        if hashes:
            scheme, _, presented = authorization.partition(" ")
            if scheme.lower() != "bearer" or not presented:
                raise HTTPException(status_code=401,
                                    detail="missing bearer token")
            import hashlib
            digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
            for token_hash, worker_id in hashes.items():
                if hmac.compare_digest(digest, token_hash):
                    return worker_id
            raise HTTPException(status_code=401, detail="invalid bearer token")
        # Legacy: no per-worker tokens minted yet. Delegate wholesale so the
        # original semantics survive untouched -- including 503 when the
        # shared secret is UNCONFIGURED, which must stay louder than a 401:
        # a server that reads misconfiguration as bad credentials hides the
        # failure exactly when it matters.
        require_worker_auth(authorization)
        return ""

    def enforce_identity(worker: str, asserted: str) -> None:
        """The body's worker_id must be the token's worker.

        Only enforced when identity exists ("" is legacy). A mismatch is
        403, not 401: the caller IS authenticated -- as somebody else.
        """
        if worker and asserted and worker != asserted:
            raise HTTPException(
                status_code=403,
                detail=f"token belongs to {worker!r}, "
                       f"request asserts {asserted!r}")

    router = APIRouter()

    # --- artifacts (§23 artifact_reference) -----------------------------

    @router.post("/api/lightworkers/artifacts")
    def upload_artifact(body: ArtifactBody,
                        worker: str = Depends(authenticated_worker)
                        ) -> Dict[str, Any]:
        """Store a content-addressed artifact; §23's artifact_reference.

        A deliverable or patch too large to travel inline in the result
        JSON is uploaded first; the result then carries only the sha256.
        Content-addressed on purpose: the name IS the integrity check, a
        re-upload of identical bytes is a no-op, and nothing needs a
        cleanup policy tied to execution ids.

        Father verifies the declared sha against the decoded bytes before
        writing -- the same never-trust-the-checksum stance §23 takes on
        results -- and writes atomically so a crashed upload leaves no
        half-artifact behind the hash that promises its content.
        """
        enforce_identity(worker, body.worker_id)
        if not artifacts_dir:
            raise HTTPException(status_code=503,
                                detail="artifact storage is not configured")
        import base64
        import hashlib as _hl
        try:
            data = base64.b64decode(body.content_b64, validate=True)
        except Exception:
            raise HTTPException(status_code=422,
                                detail="content_b64 is not valid base64")
        if len(data) > ARTIFACT_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"artifact exceeds {ARTIFACT_MAX_BYTES} bytes")
        actual = _hl.sha256(data).hexdigest()
        if actual != body.sha256:
            raise HTTPException(
                status_code=422,
                detail=f"declared sha256 {body.sha256[:12]}… does not match "
                       f"content ({actual[:12]}…)")
        os.makedirs(artifacts_dir, exist_ok=True)
        final = os.path.join(artifacts_dir, actual)
        if not os.path.exists(final):
            import tempfile
            fd, tmp = tempfile.mkstemp(dir=artifacts_dir, suffix=".part")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, final)
        return {"status": "stored", "sha256": actual, "size": len(data)}

    # --- register / heartbeat (worker-level) ----------------------------

    @router.post("/api/lightworkers/register")
    def register(body: RegisterBody,
                 worker: str = Depends(authenticated_worker)) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
        store.register(body.worker_id, body.capabilities)
        return {"status": "registered", "worker_id": body.worker_id}

    @router.post("/api/lightworkers/heartbeat")
    def heartbeat(body: HeartbeatBody,
                  worker: str = Depends(authenticated_worker)) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
        store.heartbeat(body.worker_id)
        return {"status": "ok", "worker_id": body.worker_id}

    # --- next execution to run -----------------------------------------

    @router.get("/api/lightworkers/{worker_id}/executions/next")
    def next_execution(worker_id: str,
                       worker: str = Depends(authenticated_worker)) -> Any:
        enforce_identity(worker, worker_id)
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
    def claim(execution_id: str, body: ClaimBody,
              worker: str = Depends(authenticated_worker)) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
        if store.claim(execution_id, body.worker_id):
            return {"status": "claimed", "execution_id": execution_id,
                    "worker_id": body.worker_id}
        # Refused. We do not distinguish "wrong worker" from
        # "already claimed" — the public contract is binary.
        raise HTTPException(status_code=409, detail="claim refused")

    # --- attempt-bound heartbeat ---------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/heartbeat")
    def execution_heartbeat(
        execution_id: str, body: ExecutionHeartbeatBody,
        worker: str = Depends(authenticated_worker),
    ) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
        store.execution_heartbeat(
            execution_id, body.worker_id, body.attempt_id
        )
        return {"status": "ok"}

    # --- events --------------------------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/events")
    def events(execution_id: str, body: EventBody,
               worker: str = Depends(authenticated_worker)) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
        store.record_event(execution_id, body.worker_id, body.event)
        return {"status": "ok"}

    # --- complete ------------------------------------------------------

    @router.post("/api/lightworkers/executions/{execution_id}/complete")
    def complete(execution_id: str, body: CompleteBody,
                 worker: str = Depends(authenticated_worker)) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
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
    def fail(execution_id: str, body: FailBody,
             worker: str = Depends(authenticated_worker)) -> Dict[str, Any]:
        enforce_identity(worker, body.worker_id)
        try:
            store.fail(
                execution_id, body.worker_id, body.attempt_id, body.failure
            )
        except _AlreadyTerminal as exc:
            # 409, not 500. `ExecutionAlreadyCompleted` says in its own
            # docstring that it is named so the mounting run can map it to a
            # status code -- the mapping was never built, so it escaped as an
            # unhandled server error.
            #
            # EXEC-005 hit it: the completion was recorded, the return path
            # refused the result, and the worker's follow-up fail arrived at
            # an execution that was already terminal. A 500 tells the worker
            # Father is broken. A 409 tells it the truth, which is that
            # Father already has an answer for this execution.
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "recorded", "execution_id": execution_id}

    return router


__all__ = [
    "LightWorkerStore",
    "InMemoryStore",
    "create_router",
]
