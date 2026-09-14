#!/usr/bin/env python3
"""End-to-end knowledge smoke test through the running app's API.

This script proves the full retrieval path for one Father-targeted step and
one foreign-targeted step:

1. POST /api/prompt-compiler/compile for each step with the GOAL's mandated
   fields and the step identity, then assert the compiled prompt carries the
   ``<supplemental_knowledge>`` block AFTER the last ``</constraint>``, that
   the block quotes at least one ``source:`` line, and that the newest
   ``knowledge_retrieval_log`` row records the expected scope and agent_role.
2. GET /api/knowledge/search once per scope with the granted role and assert
   ``"enabled": true`` plus a non-empty results list whose entries carry a
   ``path`` field.

Read-only toward the repository: the only writes happen through the product
(the compile endpoint's retrieval-log rows and the search endpoint's
retrieval-log rows). The script opens ``databases/dpmtf.db`` read-only for
its own assertions, never writes repository files, never calls
``assign-handoff-id``, and never starts/stops/restarts uvicorn or a model
server.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_BRIDGE_LIB_DIR = _PROJECT_ROOT / "scripts" / "bridgeV002"
if str(_BRIDGE_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_LIB_DIR))

import config  # noqa: E402
from bridge_lib import get_flow_target_project  # noqa: E402

_GOAL = (
    "GOAL: verify the end-to-end knowledge retrieval path through the "
    "prompt compiler for a Father-targeted step and a foreign-targeted step."
)

_STEPS = (
    {
        "name": "llama_SG",
        "flow_key": "llama_SG",
        "step_key": "supervisor-imple01",
        "expected_scope": "dpmtf-webui",
        "expected_agent_role": "imple01SG",
    },
    {
        "name": "1020-02-ELOOP",
        "flow_key": "1020-02-ELOOP",
        "step_key": "decomposer-implementer",
        "expected_scope": "ai_advisoryboard",
        "expected_agent_role": "1020-implementer",
    },
)

_SEARCH_CHECKS = (
    {"scope": "dpmtf-webui", "agent_role": "imple01SG", "flow_key": "llama_SG"},
    {
        "scope": "ai_advisoryboard",
        "agent_role": "1020-implementer",
        "flow_key": "1020-02-ELOOP",
    },
)


class SmokeFailure(Exception):
    """A check failed; the caller prints exactly one FAIL line and exits 1."""


def _http_json(method: str, url: str, payload: dict | None = None) -> dict:
    """Perform an HTTP request and return the decoded JSON object.

    Raises SmokeFailure on a 503 or a ProviderNotReady body so the caller
    records a blocker and stops instead of retrying into an outage.
    """
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 503 or "ProviderNotReady" in body:
            raise SmokeFailure(
                f"HTTP {exc.code} / ProviderNotReady — GPU or provider outage, "
                f"stopping: {body[:200]}"
            ) from exc
        raise SmokeFailure(
            f"HTTP {exc.code} on {method} {url}: {body[:200]}"
        ) from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SmokeFailure(f"request to {method} {url} failed: {exc}") from exc


def _latest_retrieval_log() -> tuple[str | None, str | None]:
    """Return (scope, agent_role) of the newest knowledge_retrieval_log row.

    The database is opened read-only so the smoke test itself can never write
    a row; only the product writes retrieval-log rows.
    """
    db_path = config.get_db_path()
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute(
            "SELECT scope, agent_role "
            "FROM knowledge_retrieval_log "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return (None, None)
    return (row[0], row[1])


def _find_prompt_text(response: dict) -> str:
    """Return the response field that is a string containing ``</constraint>``.

    The compile endpoint puts the compiled prompt under ``prompt``; this
    lookup stays key-agnostic so a field-name change fails loudly instead of
    being silently guessed.
    """
    for value in response.values():
        if isinstance(value, str) and "</constraint>" in value:
            return value
    raise SmokeFailure(
        "compile response has no string field containing '</constraint>'"
    )


def _check(passed: bool, name: str, reason: str = "") -> None:
    """Print one PASS line, or raise SmokeFailure for exactly one FAIL line."""
    if passed:
        print(f"PASS {name}")
        return
    raise SmokeFailure(f"FAIL {name}: {reason}")


def _compile_step(base_url: str, step: dict) -> str:
    """POST /api/prompt-compiler/compile for one step and return its prompt."""
    target_project = get_flow_target_project(step["flow_key"])
    payload = {
        "scope_gate_confirmed": True,
        "deployment_strategy": "standard",
        "flow_key": step["flow_key"],
        "step_key": step["step_key"],
        "target_project": target_project,
        "goal": _GOAL,
    }
    response = _http_json(
        "POST", f"{base_url}/api/prompt-compiler/compile", payload
    )
    return _find_prompt_text(response)


def _check_compile_prompt(step: dict, prompt: str) -> None:
    """Assert the supplemental block, its position, and the log row."""
    name = step["name"]

    # The retrieved passages may quote these tags literally (this script is
    # itself indexed in the Father scope and answers its own query), so the
    # position check looks only at the prompt outside the block: the block
    # runs from its first opening tag to its last closing tag.
    block_pos = prompt.find("<supplemental_knowledge>")
    block_end = prompt.rfind("</supplemental_knowledge>")
    outside = prompt[:block_pos] if block_pos != -1 else prompt
    if block_pos != -1 and block_end != -1:
        outside += prompt[block_end + len("</supplemental_knowledge>"):]
    last_constraint = outside.rfind("</constraint>")
    _check(
        last_constraint != -1
        and block_pos != -1
        and block_end > block_pos
        and block_pos > last_constraint,
        f"compile-block-position:{name}",
        "<supplemental_knowledge> not found after the last </constraint>",
    )

    has_source = any(
        line.startswith("source:") for line in prompt.splitlines()
    )
    _check(
        has_source,
        f"compile-source-lines:{name}",
        "compiled prompt contains no 'source:' line",
    )

    scope, agent_role = _latest_retrieval_log()
    _check(
        scope == step["expected_scope"]
        and agent_role == step["expected_agent_role"],
        f"compile-log-row:{name}",
        f"newest retrieval-log row is ({scope!r}, {agent_role!r}), "
        f"expected ({step['expected_scope']!r}, {step['expected_agent_role']!r})",
    )


def _check_search(base_url: str, scope: str, agent_role: str, flow_key: str) -> None:
    """Assert the search endpoint answers enabled with usable results."""
    query = urllib.parse.urlencode(
        {"q": "x", "scope": scope, "agent_role": agent_role, "flow_key": flow_key}
    )
    data = _http_json(
        "GET", f"{base_url}/api/knowledge/search?{query}"
    )

    _check(
        data.get("enabled") is True,
        f"search-enabled:{scope}",
        f"expected enabled true, got {data.get('enabled')!r}",
    )

    results = data.get("results")
    usable = (
        isinstance(results, list)
        and len(results) > 0
        and all(
            isinstance(item, dict) and str(item.get("path", "")).strip()
            for item in results
        )
    )
    _check(
        usable,
        f"search-results:{scope}",
        f"expected non-empty results with path fields, got {results!r}",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:9130",
        help="Base URL of the running app (default: http://127.0.0.1:9130)",
    )
    args = parser.parse_args(argv)
    base_url = args.base_url.rstrip("/")

    try:
        for step in _STEPS:
            prompt = _compile_step(base_url, step)
            _check_compile_prompt(step, prompt)

        for search in _SEARCH_CHECKS:
            _check_search(
                base_url,
                search["scope"],
                search["agent_role"],
                search["flow_key"],
            )
    except SmokeFailure as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
