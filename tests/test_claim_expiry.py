"""A claimed execution must not block the queue forever.

Nothing timed a claim out: EXEC-013 jammed the queue until a human closed it
through the API, and two steward mistakes the same day each cost a full
thirty-minute wait for the same reason. Expiry is lazy -- it runs when the
worker polls -- because that is the moment the queue can safely unblock, and
it needs no new daemon.

The 2026-08-07 heartbeats are what make this SAFE: without them a timeout
kills live, slow executions along with dead ones. Hence two thresholds: 300s
of heartbeat silence on an execution that HAS beaten, but 900s of grace for
one that never beat -- before the first heartbeat lies the model load, which
legitimately took minutes for the 35B.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from routers.lightworker_store import SqliteLightWorkerStore


def _iso(seconds_ago):
    return (datetime.now(timezone.utc)
            - timedelta(seconds=seconds_ago)).isoformat()


@pytest.fixture
def store(tmp_path):
    return SqliteLightWorkerStore(str(tmp_path / "t.db"))


def _claimed(store, eid, claimed_seconds_ago):
    store.offer({"execution_id": eid, "worker_id": "w1",
                 "target_role": "imple01LW", "handoff_id": "001"})
    store.offer_next("w1")
    assert store.claim(eid, "w1")
    store._conn.execute(
        "UPDATE lightworker_executions SET updated_at=? WHERE execution_id=?",
        (_iso(claimed_seconds_ago), eid))


def _beat(store, eid, seconds_ago):
    store._conn.execute(
        "INSERT INTO lightworker_execution_heartbeats "
        "(execution_id, worker_id, attempt_id, heartbeat_at) "
        "VALUES (?, 'w1', 'ATTEMPT-1', ?)", (eid, _iso(seconds_ago)))


def test_stale_heartbeats_expire_the_claim_and_free_the_queue(store):
    _claimed(store, "E1", claimed_seconds_ago=1200)
    _beat(store, "E1", seconds_ago=600)          # beat once, then silence
    store.offer({"execution_id": "E2", "worker_id": "w1",
                 "target_role": "imple01LW", "handoff_id": "002"})
    nxt = store.offer_next("w1")
    assert nxt is not None and nxt["execution_id"] == "E2", \
        "the dead claim still blocks the queue"
    state = store._conn.execute(
        "SELECT state FROM lightworker_executions WHERE execution_id='E1'"
    ).fetchone()[0]
    assert state == "failed"


def test_the_failure_says_father_expired_it(store):
    """The record must not read like the worker reported anything -- it
    did not, and EXEC-013 taught what a record that misattributes costs."""
    import json
    _claimed(store, "E1", claimed_seconds_ago=1200)
    _beat(store, "E1", seconds_ago=600)
    store.offer_next("w1")
    fj = store._conn.execute(
        "SELECT failure_json FROM lightworker_failures "
        "WHERE execution_id='E1'").fetchone()[0]
    failure = json.loads(fj)
    assert failure["category"] == "WORKER_INTERRUPTED"
    assert "Expired by Father" in failure["summary"]
    assert failure["retryability"] is True


def test_fresh_heartbeats_keep_the_claim_alive(store):
    _claimed(store, "E1", claimed_seconds_ago=1200)
    _beat(store, "E1", seconds_ago=30)
    assert store.offer_next("w1") is None        # still live, still blocking
    state = store._conn.execute(
        "SELECT state FROM lightworker_executions WHERE execution_id='E1'"
    ).fetchone()[0]
    assert state == "claimed"


def test_no_heartbeat_yet_gets_the_long_grace(store):
    """Model load is legitimately heartbeat-free and took minutes for the
    35B. A 300s rule here would kill every large-model execution at start."""
    _claimed(store, "E1", claimed_seconds_ago=600)   # 10 min, no beats
    assert store.offer_next("w1") is None
    state = store._conn.execute(
        "SELECT state FROM lightworker_executions WHERE execution_id='E1'"
    ).fetchone()[0]
    assert state == "claimed"


def test_no_heartbeat_beyond_grace_expires(store):
    _claimed(store, "E1", claimed_seconds_ago=1000)  # > 900s
    store.offer_next("w1")
    state = store._conn.execute(
        "SELECT state FROM lightworker_executions WHERE execution_id='E1'"
    ).fetchone()[0]
    assert state == "failed"


def test_other_workers_claims_are_untouched(store):
    """Expiry runs for the polling worker's own claims alone -- one worker's
    poll must never judge another's liveness."""
    _claimed(store, "E1", claimed_seconds_ago=2000)
    store._conn.execute(
        "UPDATE lightworker_executions SET worker_id='w2' "
        "WHERE execution_id='E1'")
    store.offer_next("w1")
    state = store._conn.execute(
        "SELECT state FROM lightworker_executions WHERE execution_id='E1'"
    ).fetchone()[0]
    assert state == "claimed"
