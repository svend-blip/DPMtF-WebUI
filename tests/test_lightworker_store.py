"""Tests for routers/lightworker_store.py (run 009 — durable store).

Cover what the criteria cover and what they do not:

* the migration applies and is idempotent (the store applies it on
  construction, so a fresh database bootstraps)
* the interface is satisfied method-for-method
* the router's §20 behaviour holds with the durable store in place
* durability across instances — the run's whole point
* the run-007 resolution: a different attempt on a completed
  execution raises; a replay returns False
* the foreign-claim-does-not-consume-offer invariant
* the one-live-execution rule in ``offer_next``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from routers.lightworker_store import (
    ExecutionAlreadyCompleted,
    SqliteLightWorkerStore,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> SqliteLightWorkerStore:
    """A fresh store on a fresh file under pytest's tmp_path."""
    return SqliteLightWorkerStore(str(tmp_path / "store.db"))


def _seed(store: SqliteLightWorkerStore, execution_id: str,
          worker_id: str = "w1", target_role: str = "imple01") -> None:
    store.offer({
        "execution_id": execution_id,
        "worker_id": worker_id,
        "target_role": target_role,
    })


def _deliverable_result(deliverable: str = "x", checksum: str = "y") -> dict:
    return {
        "mode": "deliverable_only",
        "deliverable": deliverable,
        "checksum": checksum,
    }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_constructor_creates_schema(tmp_path: Path) -> None:
    """A fresh store on a non-existent file creates the schema."""
    db_path = tmp_path / "fresh.db"
    assert not db_path.exists()

    SqliteLightWorkerStore(str(db_path))

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'lightworker%'"
        ).fetchall()
        names = sorted(r[0] for r in rows)
        assert "lightworker_executions" in names
        assert "lightworker_completions" in names
        assert "lightworker_failures" in names
        assert "lightworker_events" in names
    finally:
        conn.close()


def test_constructor_is_idempotent(tmp_path: Path) -> None:
    """Constructing twice on the same file does not raise."""
    db_path = str(tmp_path / "store.db")
    SqliteLightWorkerStore(db_path)
    SqliteLightWorkerStore(db_path)


def test_offer_creates_an_execution(store: SqliteLightWorkerStore) -> None:
    """offer() inserts an execution in 'offered' state."""
    _seed(store, "E1")
    payload = store.offer_next("w1")
    assert payload is not None
    assert payload.get("execution_id") == "E1"


# ---------------------------------------------------------------------------
# Worker identity and static matching
# ---------------------------------------------------------------------------


def test_offer_next_offers_only_to_addressed_worker(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    _seed(store, "E2", worker_id="w2")

    a = store.offer_next("w1")
    b = store.offer_next("w2")
    c = store.offer_next("w3")

    assert a is not None and a["execution_id"] == "E1"
    assert b is not None and b["execution_id"] == "E2"
    assert c is None


def test_claim_from_a_foreign_worker_returns_false(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    assert store.claim("E1", "intruder") is False
    # And the execution is still claimable by the rightful worker.
    assert store.claim("E1", "w1") is True


def test_claim_unknown_execution_returns_false(
    store: SqliteLightWorkerStore,
) -> None:
    assert store.claim("nope", "w1") is False


def test_two_claims_one_winner(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    a = store.claim("E1", "w1")
    b = store.claim("E1", "w1")
    assert a is True
    assert b is False


# ---------------------------------------------------------------------------
# Atomic claim — one conditional UPDATE, rowcount decides
# ---------------------------------------------------------------------------


def test_concurrent_claim_is_atomic_within_one_process(
    store: SqliteLightWorkerStore,
) -> None:
    """Two claim calls in a single process: only one wins.

    This is the single-threaded case the read-then-write defect
    passes. The three-process case lives in the criteria scripts.
    """
    _seed(store, "E1", worker_id="w1")
    # Same worker trying to claim twice — second one is refused.
    assert store.claim("E1", "w1") is True
    assert store.claim("E1", "w1") is False


# ---------------------------------------------------------------------------
# Duplicate-execution protection (§5.3, max_parallel_executions == 1)
# ---------------------------------------------------------------------------


def test_offer_next_returns_none_while_a_claim_is_live(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    _seed(store, "E2", worker_id="w1")

    first = store.offer_next("w1")
    assert first is not None and first["execution_id"] == "E1"

    # Claim E1 — the worker is now "holding" a live execution.
    assert store.claim("E1", "w1") is True

    # A second offer_next for w1 must return None — §5.3.
    assert store.offer_next("w1") is None


def test_offer_next_returns_next_execution_after_completion(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    _seed(store, "E2", worker_id="w1")

    store.offer_next("w1")
    store.claim("E1", "w1")
    store.complete("E1", "w1", "a1", _deliverable_result())

    second = store.offer_next("w1")
    assert second is not None and second["execution_id"] == "E2"


# ---------------------------------------------------------------------------
# Idempotent completion and failure
# ---------------------------------------------------------------------------


def test_complete_twice_records_once(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    store.claim("E1", "w1")

    result = _deliverable_result()
    assert store.complete("E1", "w1", "a1", result) is True
    assert store.complete("E1", "w1", "a1", result) is False
    assert store.completion_count("E1", "a1") == 1


def test_fail_twice_records_once(
    store: SqliteLightWorkerStore,
) -> None:
    _seed(store, "E1", worker_id="w1")
    store.claim("E1", "w1")

    failure = {"reason": "model timeout"}
    assert store.fail("E1", "w1", "a1", failure) is True
    assert store.fail("E1", "w1", "a1", failure) is False
    assert store.failure_count("E1", "a1") == 1


# ---------------------------------------------------------------------------
# Run 007 resolution: a different attempt on a terminal execution raises
# ---------------------------------------------------------------------------


def test_complete_after_complete_with_different_attempt_raises(
    store: SqliteLightWorkerStore,
) -> None:
    """The run-007 case: a fresh attempt_id on a completed execution
    is refused, not silently accepted."""
    _seed(store, "E1", worker_id="w1")
    store.claim("E1", "w1")

    assert store.complete(
        "E1", "w1", "a1", _deliverable_result(deliverable="REAL")
    ) is True
    assert store.completion_count("E1", "a1") == 1

    with pytest.raises(ExecutionAlreadyCompleted):
        store.complete(
            "E1", "w1", "a2", _deliverable_result(deliverable="STALE")
        )


def test_fail_after_complete_with_different_attempt_raises(
    store: SqliteLightWorkerStore,
) -> None:
    """A fail() arriving on a completed execution is refused too.

    The execution is in a terminal state; either terminal call wins,
    the other raises.
    """
    _seed(store, "E1", worker_id="w1")
    store.claim("E1", "w1")

    assert store.complete("E1", "w1", "a1", _deliverable_result()) is True

    with pytest.raises(ExecutionAlreadyCompleted):
        store.fail("E1", "w1", "a2", {"reason": "spurious"})


def test_complete_after_fail_with_different_attempt_raises(
    store: SqliteLightWorkerStore,
) -> None:
    """And the reverse — a complete() arriving on a failed execution."""
    _seed(store, "E1", worker_id="w1")
    store.claim("E1", "w1")

    assert store.fail("E1", "w1", "a1", {"reason": "x"}) is True

    with pytest.raises(ExecutionAlreadyCompleted):
        store.complete("E1", "w1", "a2", _deliverable_result())


def test_complete_on_nonexistent_execution_returns_false(
    store: SqliteLightWorkerStore,
) -> None:
    """No row to update — return False rather than raise."""
    assert store.complete("nope", "w1", "a1", _deliverable_result()) is False


# ---------------------------------------------------------------------------
# Durability — the whole point of the run
# ---------------------------------------------------------------------------


def test_state_survives_a_new_instance(tmp_path: Path) -> None:
    """A new store on the same file sees what the previous recorded."""
    db_path = str(tmp_path / "store.db")
    a = SqliteLightWorkerStore(db_path)
    a.offer({
        "execution_id": "E1",
        "worker_id": "w1",
        "target_role": "imple01",
    })
    assert a.claim("E1", "w1") is True
    assert a.complete("E1", "w1", "a1", _deliverable_result()) is True

    b = SqliteLightWorkerStore(db_path)
    assert b.completion_count("E1", "a1") == 1


def test_idempotent_replay_across_instances(tmp_path: Path) -> None:
    """The same completion recorded twice across instances counts once."""
    db_path = str(tmp_path / "store.db")
    a = SqliteLightWorkerStore(db_path)
    a.offer({
        "execution_id": "E1",
        "worker_id": "w1",
        "target_role": "imple01",
    })
    a.claim("E1", "w1")

    result = _deliverable_result()
    assert a.complete("E1", "w1", "a1", result) is True

    b = SqliteLightWorkerStore(db_path)
    assert b.complete("E1", "w1", "a1", result) is False
    assert b.completion_count("E1", "a1") == 1


# ---------------------------------------------------------------------------
# record_event — append-only, one INSERT per call
# ---------------------------------------------------------------------------


def test_record_event_appends(tmp_path: Path) -> None:
    """Events accumulate and survive a new instance."""
    db_path = str(tmp_path / "store.db")
    a = SqliteLightWorkerStore(db_path)
    a.offer({
        "execution_id": "E1",
        "worker_id": "w1",
        "target_role": "imple01",
    })

    a.record_event("E1", "w1", {"type": "log", "message": "starting"})
    a.record_event("E1", "w1", {"type": "log", "message": "running"})

    b = SqliteLightWorkerStore(db_path)
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT event_json FROM lightworker_events "
            "WHERE execution_id = ? ORDER BY event_id ASC",
            ("E1",),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    import json
    messages = [json.loads(r[0])["message"] for r in rows]
    assert messages == ["starting", "running"]


# ---------------------------------------------------------------------------
# register / heartbeat / execution_heartbeat
# ---------------------------------------------------------------------------


def test_register_and_heartbeat_record_liveness(
    store: SqliteLightWorkerStore,
) -> None:
    """register() upserts the row; heartbeat() updates the timestamp."""
    import sqlite3
    store.register("w1", {"gpu_count": 1})
    store.heartbeat("w1")

    conn = sqlite3.connect(store._db_path)
    try:
        row = conn.execute(
            "SELECT worker_id, capabilities_json FROM lightworker_worker_state "
            "WHERE worker_id = ?",
            ("w1",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == "w1"
    import json
    assert json.loads(row[1]) == {"gpu_count": 1}


def test_execution_heartbeat_upserts(
    store: SqliteLightWorkerStore,
) -> None:
    """execution_heartbeat() records a per-attempt timestamp."""
    import sqlite3
    _seed(store, "E1", worker_id="w1")
    store.claim("E1", "w1")
    store.execution_heartbeat("E1", "w1", "a1")
    store.execution_heartbeat("E1", "w1", "a1")  # idempotent upsert

    conn = sqlite3.connect(store._db_path)
    try:
        rows = conn.execute(
            "SELECT execution_id, attempt_id FROM "
            "lightworker_execution_heartbeats"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("E1", "a1")]


# ---------------------------------------------------------------------------
# The router, with this store swapped in
# ---------------------------------------------------------------------------


def test_router_drop_in(tmp_path: Path) -> None:
    """Mounting the router with this store preserves the §20 shape."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.lightworkers import create_router

    store = SqliteLightWorkerStore(str(tmp_path / "router.db"))
    store.offer({
        "execution_id": "E1",
        "worker_id": "w1",
        "target_role": "imple01",
    })

    app = FastAPI()
    app.include_router(create_router(store))
    client = TestClient(app)

    assert (
        client.get("/api/lightworkers/w1/executions/next").json() or {}
    ).get("execution_id") == "E1"
    assert not (
        client.get("/api/lightworkers/w2/executions/next").json() or {}
    )
    assert client.post(
        "/api/lightworkers/executions/E1/claim",
        json={"worker_id": "intruder"},
    ).status_code >= 400
    assert client.post(
        "/api/lightworkers/executions/E1/claim",
        json={"worker_id": "w1"},
    ).status_code == 200