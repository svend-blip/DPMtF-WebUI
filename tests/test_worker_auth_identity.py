"""Per-worker credentials: the token says who calls; the body may not disagree.

The shared LIGHTWORKER_AUTH_TOKEN proved the caller held *a* secret. Every
worker presenting it was accepted, and worker_id stayed self-asserted in the
request body -- one compromised worker could claim, complete or fail any
other worker's executions. END-REPORT run 001 listed it as known-missing.

Legacy mode is deliberate and bounded: while NO per-worker token exists, the
shared secret still authenticates (rollout order: mint, install, restart).
The moment one exists, it alone does.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.lightworkers import InMemoryStore, create_router


def _client(store):
    app = FastAPI()
    app.include_router(create_router(store))
    return TestClient(app)


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", "shared-legacy")
    store = InMemoryStore()
    store._token_hashes = {
        hashlib.sha256(b"tok-A").hexdigest(): "worker-A",
        hashlib.sha256(b"tok-B").hexdigest(): "worker-B",
    }
    return store, _client(store)


def _post(client, token, path, body):
    return client.post(path, json=body,
                       headers={"Authorization": f"Bearer {token}"})


def test_the_token_authenticates_its_own_worker(rig):
    _, client = rig
    r = _post(client, "tok-A", "/api/lightworkers/register",
              {"worker_id": "worker-A", "capabilities": {}})
    assert r.status_code == 200


def test_the_body_may_not_assert_someone_else(rig):
    """The defect this exists for: one worker acting as another."""
    _, client = rig
    r = _post(client, "tok-A", "/api/lightworkers/register",
              {"worker_id": "worker-B", "capabilities": {}})
    assert r.status_code == 403
    assert "worker-A" in r.json()["detail"]


def test_the_path_worker_id_is_enforced_too(rig):
    _, client = rig
    r = rig[1].get("/api/lightworkers/worker-B/executions/next",
                   headers={"Authorization": "Bearer tok-A"})
    assert r.status_code == 403


def test_the_shared_token_dies_when_identities_exist(rig):
    """A shared secret alongside real identities would undermine what the
    identities are for."""
    _, client = rig
    r = _post(client, "shared-legacy", "/api/lightworkers/register",
              {"worker_id": "worker-A", "capabilities": {}})
    assert r.status_code == 401


def test_legacy_mode_still_works_while_no_token_is_minted(monkeypatch):
    """Rollout order must not brick the fleet: mint, install, restart."""
    monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", "shared-legacy")
    store = InMemoryStore()          # no _token_hashes
    client = _client(store)
    r = _post(client, "shared-legacy", "/api/lightworkers/register",
              {"worker_id": "anybody", "capabilities": {}})
    assert r.status_code == 200


def test_a_claim_for_another_workers_execution_is_403(rig):
    store, client = rig
    store.offer({"execution_id": "E1", "worker_id": "worker-B",
                 "target_role": "r"})
    r = _post(client, "tok-A", "/api/lightworkers/executions/E1/claim",
              {"worker_id": "worker-B"})
    assert r.status_code == 403


def test_a_wrong_token_is_401_not_403(rig):
    """401: we do not know you. 403: we know you, and you are not them."""
    _, client = rig
    r = _post(client, "tok-WRONG", "/api/lightworkers/register",
              {"worker_id": "worker-A", "capabilities": {}})
    assert r.status_code == 401
