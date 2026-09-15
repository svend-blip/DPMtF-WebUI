"""Tests for the knowledge API router (pure proxies to the knowledge service).

DPMtF keeps no local provider path: ``GET /api/knowledge/search`` and
``POST /api/knowledge/refresh`` forward to ``knowledge.service_client`` and
pass the service's status and body through unchanged. A transport failure
(status 0) becomes a 502. No test in this module reaches the network:
``service_client._http`` is monkeypatched.
"""

import sys

sys.dont_write_bytecode = True

from pathlib import Path

from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import app  # noqa: E402
from knowledge import service_client  # noqa: E402


def test_search_and_refresh_are_pure_proxies(monkeypatch):
    search_calls = []
    refresh_calls = []

    search_responses = {
        "ok": (
            200,
            {
                "enabled": True,
                "provider": "svc",
                "results": [{"path": "a.md", "content": "alpha"}],
                "bounded": True,
            },
        ),
        "bad": (400, {"detail": "bad request"}),
        "denied": (403, {"detail": "scope access denied"}),
        "busy": (503, {"detail": "not ready"}),
        "down": (0, {"detail": "connection refused"}),
    }

    refresh_responses = {
        "ok": (200, {"status": "ok"}),
        "bad": (400, {"detail": "bad repo"}),
        "busy": (503, {"detail": "not ready"}),
        "down": (0, {"detail": "connection refused"}),
    }

    def fake_http(method, url, params_or_body, timeout):
        if url.endswith("/v1/search"):
            search_calls.append((method, url, params_or_body, timeout))
            return search_responses[params_or_body.get("q")]
        if url.endswith("/v1/refresh"):
            refresh_calls.append((method, url, params_or_body, timeout))
            return refresh_responses[params_or_body.get("scope")]
        raise AssertionError(f"unexpected call: {method} {url}")

    monkeypatch.setattr(service_client, "_http", fake_http)

    with TestClient(app.app) as client:
        ok = client.get("/api/knowledge/search", params={"q": "ok"})
        assert ok.status_code == 200
        assert ok.json() == {
            "enabled": True,
            "provider": "svc",
            "results": [{"path": "a.md", "content": "alpha"}],
            "bounded": True,
        }

        bad = client.get("/api/knowledge/search", params={"q": "bad"})
        assert bad.status_code == 400
        assert bad.json() == {"detail": "bad request"}

        denied = client.get("/api/knowledge/search", params={"q": "denied"})
        assert denied.status_code == 403
        assert denied.json() == {"detail": "scope access denied"}

        busy = client.get("/api/knowledge/search", params={"q": "busy"})
        assert busy.status_code == 503
        assert busy.json() == {"detail": "not ready"}

        down = client.get("/api/knowledge/search", params={"q": "down"})
        assert down.status_code == 502
        assert down.json() == {"detail": "connection refused"}

        refresh_ok = client.post(
            "/api/knowledge/refresh",
            json={"scope": "ok", "repo_path": "/tmp/x"},
        )
        assert refresh_ok.status_code == 200
        assert refresh_ok.json() == {"status": "ok"}

        refresh_bad = client.post(
            "/api/knowledge/refresh",
            json={"scope": "bad", "repo_path": "/tmp/x"},
        )
        assert refresh_bad.status_code == 400
        assert refresh_bad.json() == {"detail": "bad repo"}

        refresh_busy = client.post(
            "/api/knowledge/refresh",
            json={"scope": "busy", "repo_path": "/tmp/x"},
        )
        assert refresh_busy.status_code == 503
        assert refresh_busy.json() == {"detail": "not ready"}

        refresh_down = client.post(
            "/api/knowledge/refresh",
            json={"scope": "down", "repo_path": "/tmp/x"},
        )
        assert refresh_down.status_code == 502
        assert refresh_down.json() == {"detail": "connection refused"}

    assert search_calls[0][0] == "GET"
    assert search_calls[0][2]["q"] == "ok"
    assert refresh_calls[0][0] == "POST"
    assert refresh_calls[0][2] == {"scope": "ok", "repo_path": "/tmp/x"}


def test_learning_is_a_pure_proxy(monkeypatch):
    learning_calls = []

    two_row_payload = {
        "artifacts": [
            {
                "repository": "dpmtf-webui",
                "family": "2000",
                "run": "044",
                "topic": "learning proxy",
                "evidence_level": "anecdote",
                "confidence": 0.9,
                "admitted_by": "cli",
                "supersedes": None,
            },
            {
                "repository": "dpmtf-webui",
                "family": "2000",
                "run": "042",
                "topic": "learning proxy",
                "evidence_level": "validated",
                "confidence": 1.0,
                "admitted_by": "cli",
                "supersedes": None,
                "superseded_by": None,
                "retracted_at": None,
            },
        ]
    }

    def fake_http(method, url, params_or_body, timeout):
        assert url.endswith("/v1/learning"), f"unexpected call: {method} {url}"
        learning_calls.append((method, url, params_or_body, timeout))
        repo = params_or_body.get("repository")
        if repo == "busy":
            return (503, {"detail": "not ready"})
        if repo == "down":
            return (0, {"detail": "connection refused"})
        return (200, two_row_payload)

    monkeypatch.setattr(service_client, "_http", fake_http)

    with TestClient(app.app) as client:
        ok = client.get(
            "/api/knowledge/learning",
            params={"history": "true", "repository": "slug"},
        )
        assert ok.status_code == 200
        assert ok.json() == two_row_payload

        busy = client.get(
            "/api/knowledge/learning", params={"repository": "busy"}
        )
        assert busy.status_code == 503
        assert busy.json() == {"detail": "not ready"}

        down = client.get(
            "/api/knowledge/learning", params={"repository": "down"}
        )
        assert down.status_code == 502
        assert down.json() == {"detail": "connection refused"}

        bare = client.get("/api/knowledge/learning")
        assert bare.status_code == 200
        assert bare.json() == two_row_payload

    assert learning_calls[0][0] == "GET"
    assert learning_calls[0][1].endswith("/v1/learning")
    assert learning_calls[0][2] == {"history": "true", "repository": "slug"}
    assert learning_calls[3][2] == {}
