"""Tests for routers/bridge.py: POST /api/bridge-v2/flows/{flow_key}/intent.

The intent API is a CLOSED, enum-based surface over the BridgeV002
dispatch signals. It must:

  - reject any ``intent`` outside the ``DispatchIntent`` enum (422, nothing
    dispatched);
  - validate the flow and referenced roles against the DB before calling
    anything (404 for a missing flow, 422 for a missing role);
  - derive ``bridge_dir`` server-side (``dispatch._bridge_dir()``) — the
    client never supplies a path or target;
  - call the existing ``dispatch.signal_*`` function VERBATIM, one per
    intent, with the normalized/allocated handoff id;
  - preserve idempotency/receipts (explicit-id normalization mirrors
    ``dispatch.main()``; a missing id is allocated from the flow counter).

Because the bridge chain is LIVE in tmux, every test monkeypatches the
four ``dispatch.signal_*`` functions (plus ``_bridge_dir``) so no real
dispatch, injection or model stop ever runs from the suite.
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient


def _seed_intent_rows(seeded_db_path: str) -> None:
    """Insert the preferred_cloud flow + Pre-super-cl/Pre-imple-cl roles.

    Idempotent (INSERT OR IGNORE). Mirrors test_bridge_dispatch.py: the
    route only reads ``flow_key``/``is_active`` and
    ``role_key``/``is_active``.
    """
    conn = sqlite3.connect(seeded_db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO bridge_flows
                (flow_key, name, description, step_order, is_default, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (
                "preferred_cloud",
                "preferred_cloud (seeded for intent tests)",
                "Minimal flow used by tests/test_intent_api.py.",
                "Pre-super-cl,Pre-imple-cl",
            ),
        )
        for role_key in ("Pre-super-cl", "Pre-imple-cl"):
            conn.execute(
                """
                INSERT OR IGNORE INTO bridge_roles
                    (role_key, tmux_session, start_cmd,
                     default_model_source, default_model_alias, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    role_key,
                    f"{role_key}-tmux",
                    f"echo {role_key}",
                    "model_allocator",
                    f"{role_key}-alias",
                ),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def intent_db(seeded_db_path: str) -> str:
    """Temp DB with preferred_cloud + the two Pre-* roles seeded."""
    _seed_intent_rows(seeded_db_path)
    return seeded_db_path


@pytest.fixture()
def intent_dispatch(monkeypatch):
    """Wire fakes over the four dispatch.signal_* functions + _bridge_dir.

    Every fake records its call and returns True by default. ``_bridge_dir``
    is pinned to a sentinel so a test can prove the router derived the path
    server-side (the client body never carried it). Returns the recorder
    dict keyed by function name.
    """
    import routers.bridge as bridge_module

    calls = {
        "signal_send": [],
        "signal_complete": [],
        "signal_escalation": [],
        "signal_answer": [],
    }

    def _fake(name):
        def _impl(*args, **kwargs):
            calls[name].append({"args": args, "kwargs": kwargs})
            return True

        return _impl

    monkeypatch.setattr(bridge_module.dispatch, "signal_send", _fake("signal_send"))
    monkeypatch.setattr(bridge_module.dispatch, "signal_complete", _fake("signal_complete"))
    monkeypatch.setattr(bridge_module.dispatch, "signal_escalation", _fake("signal_escalation"))
    monkeypatch.setattr(bridge_module.dispatch, "signal_answer", _fake("signal_answer"))
    monkeypatch.setattr(bridge_module.dispatch, "_bridge_dir", lambda: "/sentinel/bridge-dir")
    return calls


# ── closed enum ─────────────────────────────────────────────────────────


def test_unknown_intent_returns_422_and_dispatches_nothing(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    """Any intent outside the closed enum is 422 and no signal function runs."""
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={"intent": "signal_explode", "from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 422, response.text
    detail = response.json().get("detail", "")
    assert "signal_explode" in detail
    for value in ("signal_send", "signal_complete", "signal_escalation", "signal_answer"):
        assert value in detail, f"allowed enum must be listed; got {detail!r}"
    assert all(calls == [] for calls in intent_dispatch.values())


def test_missing_intent_returns_422(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={"from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 422, response.text
    assert all(calls == [] for calls in intent_dispatch.values())


# ── server-side validation order ────────────────────────────────────────


def test_unknown_flow_returns_404_and_dispatches_nothing(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    response = client.post(
        "/api/bridge-v2/flows/no-such-flow/intent",
        json={"intent": "signal_send", "from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 404, response.text
    assert "no-such-flow" in response.json().get("detail", "")
    assert all(calls == [] for calls in intent_dispatch.values())


def test_unknown_role_returns_422_and_dispatches_nothing(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={"intent": "signal_send", "from_role": "Pre-super-cl", "to_role": "also-absent"},
    )
    assert response.status_code == 422, response.text
    assert "also-absent" in response.json().get("detail", "")
    assert all(calls == [] for calls in intent_dispatch.values())


# ── per-intent required fields ──────────────────────────────────────────


def test_signal_send_requires_to_role(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={"intent": "signal_send", "from_role": "Pre-super-cl"},
    )
    assert response.status_code == 422, response.text
    assert "to_role" in response.json().get("detail", "")
    assert intent_dispatch["signal_send"] == []


def test_signal_complete_requires_step_key(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={"intent": "signal_complete", "from_role": "Pre-super-cl"},
    )
    assert response.status_code == 422, response.text
    assert "step_key" in response.json().get("detail", "")
    assert intent_dispatch["signal_complete"] == []


# ── verbatim reuse + server-side derivation + idempotency ───────────────


def test_signal_send_calls_dispatch_verbatim_with_server_derived_bridge_dir(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    """A valid signal_send calls dispatch.signal_send once, verbatim.

    bridge_dir is the server-derived sentinel (not from the request body),
    and the handoff id is passed through unchanged.
    """
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={
            "intent": "signal_send",
            "from_role": "Pre-super-cl",
            "to_role": "Pre-imple-cl",
            "id": "019",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok", body
    assert body["intent"] == "signal_send"
    assert body["handoff_id"] == "019"
    assert body["to_role"] == "Pre-imple-cl"

    assert len(intent_dispatch["signal_send"]) == 1, intent_dispatch
    call = intent_dispatch["signal_send"][0]
    assert call["args"] == (
        "preferred_cloud",
        "Pre-super-cl",
        "Pre-imple-cl",
        "019",
        "/sentinel/bridge-dir",
    )
    # Only the named intent ran — nothing else.
    for name in ("signal_complete", "signal_escalation", "signal_answer"):
        assert intent_dispatch[name] == []


def test_explicit_id_is_normalized_like_the_cli(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    """A model-polluted id ('064_humantrade') is normalized to its leading run number."""
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={
            "intent": "signal_send",
            "from_role": "Pre-super-cl",
            "to_role": "Pre-imple-cl",
            "id": "064_humantrade",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["handoff_id"] == "064"
    assert intent_dispatch["signal_send"][0]["args"][3] == "064"


def test_missing_id_is_allocated_server_side(
    intent_db: str, client: TestClient, intent_dispatch: dict, monkeypatch
) -> None:
    """No id in the body -> the flow counter allocates it (zero-padded)."""
    import routers.bridge as bridge_module

    monkeypatch.setattr(bridge_module, "get_next_id_for_flow", lambda flow, db_path=None: 42)

    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={"intent": "signal_send", "from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["handoff_id"] == "042"
    assert intent_dispatch["signal_send"][0]["args"][3] == "042"


def test_signal_function_false_returns_dispatch_error(
    intent_db: str, client: TestClient, monkeypatch
) -> None:
    """A signal function returning False is surfaced as status dispatch_error (200)."""
    import routers.bridge as bridge_module

    monkeypatch.setattr(
        bridge_module.dispatch,
        "signal_send",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(bridge_module.dispatch, "_bridge_dir", lambda: "/sentinel/bridge-dir")

    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={
            "intent": "signal_send",
            "from_role": "Pre-super-cl",
            "to_role": "Pre-imple-cl",
            "id": "019",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "dispatch_error"


def test_signal_complete_routes_with_step_key_and_force(
    intent_db: str, client: TestClient, intent_dispatch: dict
) -> None:
    """signal_complete calls dispatch.signal_complete with step_key + force."""
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={
            "intent": "signal_complete",
            "from_role": "Pre-super-cl",
            "step_key": "step-1",
            "id": "019",
            "force": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["step_key"] == "step-1"
    assert "to_role" not in body  # complete derives the target from the step

    assert len(intent_dispatch["signal_complete"]) == 1, intent_dispatch
    call = intent_dispatch["signal_complete"][0]
    assert call["args"] == (
        "preferred_cloud",
        "step-1",
        "Pre-super-cl",
        "019",
        "/sentinel/bridge-dir",
    )
    assert call["kwargs"] == {"force": True}


@pytest.mark.parametrize("intent,fn", [
    ("signal_escalation", "signal_escalation"),
    ("signal_answer", "signal_answer"),
])
def test_escalation_and_answer_route_to_their_function(
    intent_db: str, client: TestClient, intent_dispatch: dict, intent: str, fn: str
) -> None:
    """Each intent dispatches to exactly its own signal function."""
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/intent",
        json={
            "intent": intent,
            "from_role": "Pre-super-cl",
            "to_role": "Pre-imple-cl",
            "id": "019",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["intent"] == intent
    assert len(intent_dispatch[fn]) == 1, intent_dispatch
    assert intent_dispatch[fn][0]["args"] == (
        "preferred_cloud",
        "Pre-super-cl",
        "Pre-imple-cl",
        "019",
        "/sentinel/bridge-dir",
    )
