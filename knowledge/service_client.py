"""HTTP client for the standalone knowledge service.

DPMtF's knowledge layer can run in ``service`` mode, where retrieval and
refresh are delegated to a standalone service over HTTP. This module is the
only place in the codebase that talks to that service. It is deliberately
stdlib-only: ``urllib`` plus the ``config`` getters, no third-party HTTP
library.

Every public function returns ``(status, payload)`` and never raises. A
transport failure is ``(0, {"detail": str(exc)})``.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

import config


def _http(method, url, params_or_body, timeout):
    """Return ``(status, payload)``; never raise.

    Builds a ``urllib.request.Request``. For GET the parameters are encoded
    into the URL query string; for other methods they are JSON-encoded as
    the request body. ``X-Knowledge-Token`` is sent only when
    ``config.get_knowledge_service_token()`` is non-empty.

    An HTTP response (including 400/403/503) is not a transport failure:
    the response body is JSON-decoded and returned with its status. A body
    that is not valid JSON is returned as ``{"detail": <text>}``. Transport
    failures are returned as ``(0, {"detail": str(exc)})``.
    """
    method = method.upper()
    try:
        headers = {}
        token = config.get_knowledge_service_token()
        if token:
            headers["X-Knowledge-Token"] = token

        data = None
        if method == "GET":
            query = urllib.parse.urlencode(params_or_body or {})
            if query:
                url = f"{url}?{query}"
        else:
            headers["Content-Type"] = "application/json"
            data = json.dumps(params_or_body or {}).encode("utf-8")

        request = urllib.request.Request(
            url, data=data, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.getcode()
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return (0, {"detail": str(exc)})

    if not raw:
        return (status, {})
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {"detail": raw}
    return (status, payload)


def _service_call(method, path, params):
    """Build the full URL, encode parameters, and never let a raise escape.

    The public functions below are the only callers. A monkeypatched
    ``_http`` that raises is still converted to ``(0, {"detail": ...})`` so
    no exception can escape through the public API.
    """
    url = f"{config.get_knowledge_service_url()}{path}"
    if method.upper() == "GET":
        params = {key: value for key, value in params.items()
                  if value is not None}
    try:
        return _http(method, url, params, timeout=30.0)
    except Exception as exc:
        return (0, {"detail": str(exc)})


def search(query, scope=None, top_k=None, token_budget=None,
           agent_role=None, flow_key=None, run_id=None, handoff_id=None):
    """Search the knowledge service. Returns ``(status, payload)``."""
    return _service_call("GET", "/v1/search",
                         {"q": query, "scope": scope, "top_k": top_k,
                          "token_budget": token_budget,
                          "agent_role": agent_role, "flow_key": flow_key,
                          "run_id": run_id, "handoff_id": handoff_id})


def refresh(scope, repo_path):
    """Refresh the knowledge service index. Returns ``(status, payload)``."""
    return _service_call("POST", "/v1/refresh",
                         {"scope": scope, "repo_path": repo_path})


def learning(history=False, repository=""):
    """List the validated learning artifacts. Returns ``(status, payload)``."""
    params = {}
    if history:
        params["history"] = "true"
    if repository:
        params["repository"] = repository
    return _service_call("GET", "/v1/learning", params)


def health():
    """Ask the knowledge service for its health. Returns ``(status, payload)``."""
    return _service_call("GET", "/v1/health", {})
