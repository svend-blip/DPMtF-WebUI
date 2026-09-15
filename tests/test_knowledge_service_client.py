"""Tests for the stdlib knowledge service client.

No test in this module reaches the network: the module-level ``_http`` seam
is monkeypatched, and the one request-construction assertion replaces
``urllib.request.urlopen`` with a fake response object.
"""

import sys

# First statements, before any project import: keep this test run from
# writing new __pycache__/ entries inside the repository.
sys.dont_write_bytecode = True

import urllib.error
import urllib.parse
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config  # noqa: E402
from knowledge import service_client  # noqa: E402


class _FakeResponse:
    """Minimal ``urlopen`` context-manager stand-in."""

    def __init__(self, status, body):
        self._status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def getcode(self):
        return self._status

    def read(self):
        return self._body


def test_search_sends_every_parameter_and_the_token_header(monkeypatch):
    monkeypatch.setattr(config, "get_knowledge_service_url",
                        lambda: "http://service.test")
    monkeypatch.setattr(config, "get_knowledge_service_token",
                        lambda: "secret-token")

    params = {
        "q": "q", "scope": "s", "top_k": 3, "token_budget": 100,
        "agent_role": "r", "flow_key": "f", "run_id": "run",
        "handoff_id": "h",
    }

    captured = {}

    def recording_http(method, url, params_or_body, timeout):
        captured["method"] = method
        captured["url"] = url
        captured["params_or_body"] = params_or_body
        captured["timeout"] = timeout
        return (200, {"ok": True})

    real_http = service_client._http
    monkeypatch.setattr(service_client, "_http", recording_http)

    status, payload = service_client.search(
        "q", scope="s", top_k=3, token_budget=100,
        agent_role="r", flow_key="f", run_id="run", handoff_id="h",
    )

    assert status == 200
    assert payload == {"ok": True}
    assert captured["method"] == "GET"
    assert captured["url"] == "http://service.test/v1/search"
    assert captured["timeout"] == 30.0
    assert captured["params_or_body"] == params

    # The seam monkeypatch hides the real request construction above, so
    # verify that ``_http`` itself encodes every parameter into the query
    # string and sets the token header by exercising it with a faked
    # ``urlopen`` (still no network).
    requests_seen = []

    def fake_urlopen(request, timeout):
        requests_seen.append((request, timeout))
        return _FakeResponse(200, b'{"ok": true}')

    monkeypatch.setattr(service_client.urllib.request, "urlopen", fake_urlopen)

    status2, payload2 = real_http(
        "GET", "http://service.test/v1/search", params, 10.0,
    )
    assert status2 == 200
    assert payload2 == {"ok": True}
    assert len(requests_seen) == 1
    request, timeout = requests_seen[0]
    assert timeout == 10.0

    parsed = urllib.parse.urlparse(request.full_url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "service.test"
    assert parsed.path == "/v1/search"
    query = urllib.parse.parse_qs(parsed.query)
    assert query["q"] == ["q"]
    assert query["scope"] == ["s"]
    assert query["top_k"] == ["3"]
    assert query["token_budget"] == ["100"]
    assert query["agent_role"] == ["r"]
    assert query["flow_key"] == ["f"]
    assert query["run_id"] == ["run"]
    assert query["handoff_id"] == ["h"]
    assert request.get_header("X-knowledge-token") == "secret-token"


def test_transport_failure_is_status_zero_not_an_exception(monkeypatch):
    def failing_http(method, url, params_or_body, timeout):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(service_client, "_http", failing_http)

    result = service_client.search("q")
    assert isinstance(result, tuple)
    status, payload = result
    assert status == 0
    assert "detail" in payload
    assert "network down" in payload["detail"]


def test_learning_sends_only_the_set_parameters_and_the_token_header(monkeypatch):
    monkeypatch.setattr(config, "get_knowledge_service_url",
                        lambda: "http://service.test")
    monkeypatch.setattr(config, "get_knowledge_service_token",
                        lambda: "secret-token")

    captured = {}

    def recording_http(method, url, params_or_body, timeout):
        captured["method"] = method
        captured["url"] = url
        captured["params_or_body"] = params_or_body
        captured["timeout"] = timeout
        return (200, {"artifacts": [{"repository": "dpmtf-webui"}]})

    real_http = service_client._http
    monkeypatch.setattr(service_client, "_http", recording_http)

    # Defaults: neither history nor repository travels.
    status, payload = service_client.learning()
    assert status == 200
    assert payload == {"artifacts": [{"repository": "dpmtf-webui"}]}
    assert captured["method"] == "GET"
    assert captured["url"] == "http://service.test/v1/learning"
    assert captured["timeout"] == 30.0
    assert captured["params_or_body"] == {}

    # Set case: exactly the two keys, history encoded lowercase.
    status, payload = service_client.learning(
        history=True, repository="dpmtf-webui"
    )
    assert status == 200
    assert payload == {"artifacts": [{"repository": "dpmtf-webui"}]}
    assert captured["method"] == "GET"
    assert captured["url"] == "http://service.test/v1/learning"
    assert captured["params_or_body"] == {
        "history": "true",
        "repository": "dpmtf-webui",
    }

    # Exercise the real ``_http`` with a faked ``urlopen`` (still no
    # network) to prove the query string and the token header.
    requests_seen = []

    def fake_urlopen(request, timeout):
        requests_seen.append((request, timeout))
        return _FakeResponse(
            200, b'{"artifacts": [{"repository": "dpmtf-webui"}]}'
        )

    monkeypatch.setattr(service_client.urllib.request, "urlopen", fake_urlopen)

    status2, payload2 = real_http(
        "GET",
        "http://service.test/v1/learning",
        {"history": "true", "repository": "dpmtf-webui"},
        10.0,
    )
    assert status2 == 200
    assert payload2 == {"artifacts": [{"repository": "dpmtf-webui"}]}
    assert len(requests_seen) == 1
    request, timeout = requests_seen[0]
    assert timeout == 10.0

    parsed = urllib.parse.urlparse(request.full_url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "service.test"
    assert parsed.path == "/v1/learning"
    assert urllib.parse.parse_qs(parsed.query) == {
        "history": ["true"],
        "repository": ["dpmtf-webui"],
    }
    assert request.get_header("X-knowledge-token") == "secret-token"
