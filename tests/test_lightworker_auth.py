"""Tests for worker authentication on the LightWorker endpoints (GOAL.md §27).

§27 requires the worker's identity to be authenticated and says plainly that
Tailscale membership must not be the sole authorization mechanism. Until this
existed, the endpoints took the `worker_id` from the request body and believed
it: anything that could reach the port was a worker.

What these tests pin is deliberately narrow, because the mechanism is narrow.
A shared secret proves the caller holds the secret. It does not distinguish
one worker from another, and `worker_id` remains self-asserted. Per-worker
credentials are a later step; a test suite that implied otherwise would be
worse than none.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from routers.lightworkers import InMemoryStore, create_router  # noqa: E402

TOKEN = "s3cr3t-worker-token"
OTHER = "s3cr3t-worker-tokeX"  # same length, one byte different


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_router(InMemoryStore()))
    return TestClient(app)


def _probe(client: TestClient, headers: dict | None = None):
    return client.post("/api/lightworkers/heartbeat",
                       json={"worker_id": "w1"}, headers=headers or {})


class TestTheDoorIsShut:

    def test_no_header_is_refused(self, monkeypatch):
        monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", TOKEN)
        assert _probe(_client()).status_code == 401

    def test_a_wrong_token_is_refused(self, monkeypatch):
        monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", TOKEN)
        r = _probe(_client(), {"Authorization": f"Bearer {OTHER}"})
        assert r.status_code == 401

    def test_the_right_token_is_admitted(self, monkeypatch):
        monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", TOKEN)
        r = _probe(_client(), {"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200

    def test_a_bare_token_without_the_scheme_is_refused(self, monkeypatch):
        """`Authorization: <token>` is not `Bearer <token>`."""
        monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", TOKEN)
        assert _probe(_client(), {"Authorization": TOKEN}).status_code == 401

    def test_every_endpoint_is_covered_not_just_the_one_we_probe(self, monkeypatch):
        """The dependency is on the router, so a new route inherits it.

        A per-endpoint decorator is the version of this that rots: the next
        endpoint someone adds is unprotected and nothing says so.
        """
        monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", TOKEN)
        client = _client()
        for method, path, body in (
            ("post", "/api/lightworkers/register", {"worker_id": "w1", "capabilities": {}}),
            ("get", "/api/lightworkers/w1/executions/next", None),
            ("post", "/api/lightworkers/executions/E1/claim", {"worker_id": "w1"}),
            ("post", "/api/lightworkers/executions/E1/events",
             {"worker_id": "w1", "event": {}}),
            ("post", "/api/lightworkers/executions/E1/complete",
             {"worker_id": "w1", "attempt_id": "a1", "result": {}}),
            ("post", "/api/lightworkers/executions/E1/fail",
             {"worker_id": "w1", "attempt_id": "a1", "failure": {}}),
        ):
            r = getattr(client, method)(path, json=body) if body is not None \
                else getattr(client, method)(path)
            assert r.status_code == 401, f"{method.upper()} {path} was reachable unauthenticated"


class TestAnUnconfiguredServerRefusesRatherThanOpens:
    """The failure mode that matters is the silent one.

    A server whose secret is unset and which therefore accepts everyone looks
    healthy in every check while being wide open. Refusing makes the
    misconfiguration visible at the moment it would otherwise be dangerous.
    """

    def test_no_configured_token_refuses_even_a_plausible_one(self, monkeypatch):
        monkeypatch.delenv("LIGHTWORKER_AUTH_TOKEN", raising=False)
        r = _probe(_client(), {"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 503
        assert "not configured" in r.json()["detail"]

    def test_an_empty_token_is_treated_as_unconfigured(self, monkeypatch):
        monkeypatch.setenv("LIGHTWORKER_AUTH_TOKEN", "")
        assert _probe(_client(), {"Authorization": "Bearer "}).status_code == 503


class TestTheComparisonIsConstantTime:

    def test_compare_digest_is_used(self):
        """A plain `==` leaks the secret one byte at a time to anyone timing it.

        Asserted on the source because the timing itself cannot be measured
        reliably in a test suite — the property is which primitive is called.
        """
        src = (PROJECT_ROOT / "routers" / "lightworkers.py").read_text(encoding="utf-8")
        auth = src.split("def require_worker_auth")[1].split("\ndef ")[0]
        assert "compare_digest" in auth, "the token comparison is not constant-time"
        assert "presented == expected" not in auth
