"""Tests for routers/lightworkers.py (GOAL.md §20 Polling and Claim Protocol).

The router is built INSIDE the test from the public factory and the
in-memory store. The router is not mounted on the running app, and
that is deliberate — the router is a Human step after this run
closes. These tests pin the behaviour the §20 properties rest on.

The fixture strategy mirrors what the criteria scripts do: build a
fresh ``FastAPI`` app, attach the router, hand back a ``TestClient``.
No temporary database, no file at all — the store is in-memory.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.lightworkers import InMemoryStore, create_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store() -> InMemoryStore:
    """A fresh in-memory store per test."""
    return InMemoryStore()


TEST_TOKEN = "test-worker-token"


@pytest.fixture(autouse=True)
def _auth_token(monkeypatch) -> None:
    """Every endpoint requires a bearer token (§27).

    Set for all tests in this module so the cases below stay about §20's
    protocol. The authentication behaviour itself is tested separately —
    see tests/test_lightworker_auth.py.
    """
    monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", TEST_TOKEN)


@pytest.fixture()
def client(store: InMemoryStore) -> TestClient:
    """A TestClient bound to a fresh app with the router mounted."""
    app = FastAPI()
    app.include_router(create_router(store))
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
    return c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(store: InMemoryStore, execution_id: str, worker_id: str,
          target_role: str = "imple01") -> None:
    """Push one execution into the unclaimed queue."""
    store.offer({
        "execution_id": execution_id,
        "worker_id": worker_id,
        "target_role": target_role,
    })


def _claim(client: TestClient, execution_id: str,
           worker_id: str) -> "object":  # type: ignore[name-defined]
    return client.post(
        f"/api/lightworkers/executions/{execution_id}/claim",
        json={"worker_id": worker_id},
    )


# ---------------------------------------------------------------------------
# Routes — every path the contract requires exists
# ---------------------------------------------------------------------------


def test_router_exposes_eight_endpoints() -> None:
    """Exactly the eight endpoints from the contract.
    ``create_router`` must not touch the store while building, so we
    pass ``object()`` rather than a real store.
    """
    router = create_router(object())
    paths = {
        method + " " + route.path
        for route in router.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
    }
    expected = {
        "POST /api/lightworkers/register",
        "POST /api/lightworkers/heartbeat",
        "GET /api/lightworkers/{worker_id}/executions/next",
        "POST /api/lightworkers/executions/{execution_id}/claim",
        "POST /api/lightworkers/executions/{execution_id}/heartbeat",
        "POST /api/lightworkers/executions/{execution_id}/events",
        "POST /api/lightworkers/executions/{execution_id}/complete",
        "POST /api/lightworkers/executions/{execution_id}/fail",
    }
    assert paths == expected


def test_create_router_does_not_touch_store() -> None:
    """Building the router does not invoke any store method.

    The criterion passes ``object()`` as the store; any method call
    would raise ``AttributeError`` and tells us the router is doing
    too much at build time.
    """
    # Will raise AttributeError on any attribute access if the router
    # tries to do anything with the store while building.
    create_router(object())  # noqa: S


# ---------------------------------------------------------------------------
# Worker identity and static matching
# ---------------------------------------------------------------------------


def test_next_offers_only_to_addressed_worker(
    client: TestClient, store: InMemoryStore
) -> None:
    """An execution is offered only to the worker it is addressed to."""
    _seed(store, "E1", "w1")
    _seed(store, "E2", "w2")

    a = client.get("/api/lightworkers/w1/executions/next")
    b = client.get("/api/lightworkers/w2/executions/next")
    c = client.get("/api/lightworkers/w3/executions/next")

    assert a.status_code == 200
    assert (a.json() or {}).get("execution_id") == "E1"

    assert b.status_code == 200
    assert (b.json() or {}).get("execution_id") == "E2"

    assert c.status_code == 200
    assert not (c.json() or {}), "w3 must not be offered anything"


def test_next_returns_falsy_body_when_nothing_to_offer(
    client: TestClient,
) -> None:
    """An empty /next returns 200 with a falsy body, not 404.

    A 404 would carry ``{"detail": "..."}`` which is truthy; a reader
    that does ``response.json() or {}`` would treat that as a
    successful offer.
    """
    r = client.get("/api/lightworkers/w1/executions/next")
    assert r.status_code == 200
    assert not (r.json() or {}), "an empty offer must be a falsy body"


def test_claim_from_a_foreign_worker_is_refused(
    client: TestClient, store: InMemoryStore
) -> None:
    """An execution offered to w1 cannot be claimed by w2."""
    _seed(store, "E1", "w1")
    r = _claim(client, "E1", "w2")
    assert r.status_code >= 400


# ---------------------------------------------------------------------------
# Atomic claim
# ---------------------------------------------------------------------------


def test_claim_succeeds_exactly_once(
    client: TestClient, store: InMemoryStore
) -> None:
    """Two claims for the same execution: exactly one wins.
    Even from the same worker the second call is refused — the server
    is the place atomicity lives.
    """
    _seed(store, "E1", "w1")
    r1 = _claim(client, "E1", "w1")
    r2 = _claim(client, "E1", "w1")
    winners = [r for r in (r1, r2) if r.status_code == 200]
    losers = [r for r in (r1, r2) if r.status_code >= 400]
    assert len(winners) == 1
    assert len(losers) == 1


def test_claim_then_claim_from_different_worker(
    client: TestClient, store: InMemoryStore
) -> None:
    """The second claim from a different worker is also refused."""
    _seed(store, "E1", "w1")
    r1 = _claim(client, "E1", "w1")
    r2 = _claim(client, "E1", "w2")
    assert r1.status_code == 200
    assert r2.status_code >= 400


def test_claim_unknown_execution_is_refused(client: TestClient) -> None:
    """Claiming an execution that was never offered is refused."""
    r = _claim(client, "nope", "w1")
    assert r.status_code >= 400


# ---------------------------------------------------------------------------
# Duplicate-execution protection (max_parallel_executions: 1)
# ---------------------------------------------------------------------------


def test_worker_is_offered_no_second_execution_while_one_is_live(
    client: TestClient, store: InMemoryStore
) -> None:
    """§5.3: a worker holding a live execution is offered no second one."""
    _seed(store, "E1", "w1")
    _seed(store, "E2", "w1")

    first = client.get("/api/lightworkers/w1/executions/next")
    assert (first.json() or {}).get("execution_id") == "E1"

    claim_r = _claim(client, "E1", "w1")
    assert claim_r.status_code == 200

    second = client.get("/api/lightworkers/w1/executions/next")
    assert second.status_code == 200
    assert not (second.json() or {}), (
        "a worker holding a live execution must not be offered a second one"
    )


def test_after_completion_a_new_execution_is_offered(
    client: TestClient, store: InMemoryStore
) -> None:
    """Completing the live execution frees the worker to be offered
    another one."""
    _seed(store, "E1", "w1")
    _seed(store, "E2", "w1")

    client.get("/api/lightworkers/w1/executions/next")
    _claim(client, "E1", "w1")

    body = {
        "worker_id": "w1",
        "attempt_id": "a1",
        "result": {
            "status": "role_execution_completed",
            "result_mode": "deliverable_only",
            "deliverable": {"path": "x", "content": "a document\n"},
        },
    }
    r = client.post("/api/lightworkers/executions/E1/complete", json=body)
    assert r.status_code == 200

    offered = client.get("/api/lightworkers/w1/executions/next")
    assert (offered.json() or {}).get("execution_id") == "E2"


# ---------------------------------------------------------------------------
# Idempotent completion
# ---------------------------------------------------------------------------


def test_complete_twice_returns_200_but_changes_state_once(
    client: TestClient, store: InMemoryStore
) -> None:
    """The same (execution_id, attempt_id) reported twice: 200 twice,
    state changes once."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")

    body = {
        "worker_id": "w1",
        "attempt_id": "a1",
        "result": {
            "status": "role_execution_completed",
            "result_mode": "deliverable_only",
            "deliverable": {"path": "x", "content": "a document\n"},
        },
    }
    r1 = client.post("/api/lightworkers/executions/E1/complete", json=body)
    r2 = client.post("/api/lightworkers/executions/E1/complete", json=body)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert store.completion_count("E1", "a1") == 1


def test_complete_different_attempts_each_count(
    client: TestClient, store: InMemoryStore
) -> None:
    """Different attempt_ids for the same execution are distinct
    state changes — only the same (execution_id, attempt_id) is
    idempotent."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")

    base = {
        "worker_id": "w1",
        "result": {
            "status": "role_execution_completed",
            "result_mode": "deliverable_only",
            "deliverable": {"path": "x", "content": "a document\n"},
        },
    }
    r1 = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={**base, "attempt_id": "a1"},
    )
    # Reset the live execution binding so a second complete is
    # accepted by the wire layer; in practice a new attempt would be
    # created after a failure.
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r2 = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={**base, "attempt_id": "a2"},
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert store.completion_count("E1", "a1") == 1
    assert store.completion_count("E1", "a2") == 1


# ---------------------------------------------------------------------------
# Idempotent failure (the criteria do not reach this; the client caches
# ``fail`` for the same reason it caches ``complete``).
# ---------------------------------------------------------------------------


def test_fail_twice_changes_state_once(
    client: TestClient, store: InMemoryStore
) -> None:
    """The same (execution_id, attempt_id) failed twice: state changes
    once. The wire response is 200 on both calls — a retry after a
    lost response must not be a different status, otherwise the
    client cannot rely on its cache."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")

    body = {
        "worker_id": "w1",
        "attempt_id": "a1",
        "failure": {"reason": "model timeout"},
    }
    r1 = client.post("/api/lightworkers/executions/E1/fail", json=body)
    r2 = client.post("/api/lightworkers/executions/E1/fail", json=body)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert store.failure_count("E1", "a1") == 1


# ---------------------------------------------------------------------------
# Result validation (§17)
# ---------------------------------------------------------------------------


def _deliverable_only_result() -> dict:
    # `result_mode`, and a deliverable that is an OBJECT carrying the content.
    # It used to be `mode` and a bare path string, which is the vocabulary the
    # return path never spoke -- a result could pass here and be refused where
    # the file actually gets written. tests/test_result_contract.py holds both
    # validators to one literal so they cannot drift apart again.
    return {
        "status": "role_execution_completed",
        "result_mode": "deliverable_only",
        "deliverable": {"path": "doc.md", "content": "a document\n"},
    }


def _patch_result() -> dict:
    return {
        "result_mode": "patch",
        "patch": "diff --git ...",
        "base_commit": "abc123",
        "result_commit": "def456",
        "checksum": "sha256:...",
    }


def _patch_and_deliverable_result() -> dict:
    out = _patch_result()
    out["result_mode"] = "patch_and_deliverable"
    out["deliverable"] = {"path": "doc.md", "content": "a document\n"}
    return out


def test_complete_with_empty_result_is_refused(
    client: TestClient, store: InMemoryStore
) -> None:
    """An empty result is refused (§17)."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={"worker_id": "w1", "attempt_id": "a1", "result": {}},
    )
    assert r.status_code >= 400


def test_complete_with_unknown_mode_is_refused(
    client: TestClient, store: InMemoryStore
) -> None:
    """An unknown mode is refused (§17)."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": {"result_mode": "guess", "k": "v"},
        },
    )
    assert r.status_code >= 400


def test_complete_with_missing_mode_is_refused(
    client: TestClient, store: InMemoryStore
) -> None:
    """A result without a ``result_mode`` is refused."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": {"deliverable": {"content": "x"}},
        },
    )
    assert r.status_code >= 400


def test_complete_deliverable_only_with_missing_keys_is_refused(
    client: TestClient, store: InMemoryStore
) -> None:
    """``deliverable_only`` requires a deliverable carrying content."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": {"result_mode": "deliverable_only"},
        },
    )
    assert r.status_code >= 400


def test_complete_patch_with_missing_base_commit_is_refused(
    client: TestClient, store: InMemoryStore
) -> None:
    """``patch`` requires ``patch``, ``base_commit``, ``result_commit``
    and ``checksum``. A missing ``base_commit`` is refused."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": {
                "mode": "patch",
                "patch": "diff",
                "result_commit": "def456",
                "checksum": "y",
            },
        },
    )
    assert r.status_code >= 400


def test_complete_patch_and_deliverable_requires_union(
    client: TestClient, store: InMemoryStore
) -> None:
    """``patch_and_deliverable`` requires the union of both."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")

    # Missing ``deliverable`` (we have the patch keys).
    body = {
        "worker_id": "w1",
        "attempt_id": "a1",
        "result": {
            "result_mode": "patch_and_deliverable",
            "patch": "diff",
            "base_commit": "abc",
            "result_commit": "def",
            "checksum": "y",
        },
    }
    r = client.post("/api/lightworkers/executions/E1/complete", json=body)
    assert r.status_code >= 400

    # Now a complete one — different attempt_id to reset the live
    # binding, since the previous refused call left the execution
    # unclaimed.
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    ok_body = {
        "worker_id": "w1",
        "attempt_id": "a2",
        "result": {
            "result_mode": "patch_and_deliverable",
            "patch": "diff",
            "base_commit": "abc",
            "result_commit": "def",
            "checksum": "y",
            "deliverable": {"path": "doc", "content": "a document\n"},
        },
    }
    r2 = client.post("/api/lightworkers/executions/E1/complete", json=ok_body)
    assert r2.status_code == 200


def test_complete_with_valid_deliverable_only_succeeds(
    client: TestClient, store: InMemoryStore
) -> None:
    """A complete ``deliverable_only`` result is accepted."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": _deliverable_only_result(),
        },
    )
    assert r.status_code == 200
    assert store.completion_count("E1", "a1") == 1


def test_complete_with_valid_patch_succeeds(
    client: TestClient, store: InMemoryStore
) -> None:
    """A complete ``patch`` result is accepted."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": _patch_result(),
        },
    )
    assert r.status_code == 200
    assert store.completion_count("E1", "a1") == 1


def test_complete_with_optional_summary_and_logs_succeeds(
    client: TestClient, store: InMemoryStore
) -> None:
    """``summary`` and ``logs`` are NOT required but are recorded if
    present (§17 prose)."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    result = _deliverable_only_result()
    result["summary"] = "5 tests passed"
    result["logs"] = "stdout..."
    r = client.post(
        "/api/lightworkers/executions/E1/complete",
        json={
            "worker_id": "w1",
            "attempt_id": "a1",
            "result": result,
        },
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Worker-level and execution-level endpoints
# ---------------------------------------------------------------------------


def test_register_is_accepted(client: TestClient) -> None:
    """POST /register returns 200 and accepts a capabilities body."""
    r = client.post(
        "/api/lightworkers/register",
        json={
            "worker_id": "w1",
            "capabilities": {"gpu_count": 1, "max_parallel_executions": 1},
        },
    )
    assert r.status_code == 200
    assert r.json().get("worker_id") == "w1"


def test_heartbeat_is_accepted(client: TestClient) -> None:
    """POST /heartbeat returns 200."""
    r = client.post(
        "/api/lightworkers/heartbeat",
        json={"worker_id": "w1"},
    )
    assert r.status_code == 200


def test_execution_heartbeat_is_accepted(
    client: TestClient, store: InMemoryStore
) -> None:
    """POST /executions/{id}/heartbeat accepts ``worker_id`` and
    ``attempt_id``."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/heartbeat",
        json={"worker_id": "w1", "attempt_id": "a1"},
    )
    assert r.status_code == 200


def test_events_are_accepted(
    client: TestClient, store: InMemoryStore
) -> None:
    """POST /executions/{id}/events accepts an event payload."""
    _seed(store, "E1", "w1")
    _claim(client, "E1", "w1")
    r = client.post(
        "/api/lightworkers/executions/E1/events",
        json={
            "worker_id": "w1",
            "event": {"type": "log", "message": "starting"},
        },
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# §5.2 — nothing in this router advances a flow.
# ---------------------------------------------------------------------------


def test_router_does_not_reach_across_the_boundary() -> None:
    """The router file must not contain any of the forbidden strings
    that would let it reach back into the bridge / dispatch layer.
    The test file is not scanned by this check, so it is safe to
    string-match here.
    """
    import pathlib
    src = pathlib.Path(
        "/home/svend/DPMtF-WebUI/routers/lightworkers.py"
    ).read_text()
    forbidden = (
        "bridgeV002",
        "_advance_chain",
        "dispatch",
        "signal_complete",
        "include_router",
    )
    hits = [w for w in forbidden if w in src]
    assert not hits, f"router file contains forbidden strings: {hits}"
