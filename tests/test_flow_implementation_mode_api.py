"""Tests for routers/bridge.py: implementation_mode on the flow endpoints.

The Deterministic Patcher's implementation_mode (spec sections 41-42) is
database-driven with precedence role > step > flow > default 'direct'.
Run 018 delivered the column and the dispatch wiring; the WebUI exposes
the FLOW level as a dropdown in the Bridge Flows edit form (2026-08-16,
Human-requested), following the target_project_path field's pattern.

The API contract these tests pin:

- PUT /api/bridge-v2/flows/{flow_key} accepts implementation_mode with
  'direct', 'deterministic_patch', or empty/None (stored as NULL =
  inherit), and rejects anything else with 400 — an invalid stored
  value would raise ValueError inside dispatch and stop the chain, so
  the API must refuse to store it in the first place.
- GET /api/bridge-v2/flows returns the field (list_flows_from_db does
  SELECT *), so the edit form can show the current value.
"""

from __future__ import annotations

import sqlite3

import pytest


def _mode_in_db(db_path: str, flow_key: str):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT implementation_mode FROM bridge_flows WHERE flow_key = ?",
            (flow_key,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


@pytest.fixture()
def clean_mode(seeded_db_path):
    """Reset test_flow's implementation_mode to NULL after each test."""
    yield seeded_db_path
    conn = sqlite3.connect(seeded_db_path)
    try:
        conn.execute(
            "UPDATE bridge_flows SET implementation_mode = NULL "
            "WHERE flow_key = 'test_flow'"
        )
        conn.commit()
    finally:
        conn.close()


class TestPutImplementationMode:
    def test_deterministic_patch_is_stored(self, client, clean_mode):
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "deterministic_patch"},
        )
        assert res.status_code == 200, res.text
        assert _mode_in_db(clean_mode, "test_flow") == "deterministic_patch"

    def test_direct_is_stored(self, client, clean_mode):
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "direct"},
        )
        assert res.status_code == 200, res.text
        assert _mode_in_db(clean_mode, "test_flow") == "direct"

    def test_empty_string_clears_to_null(self, client, clean_mode):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "deterministic_patch"},
        )
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": ""},
        )
        assert res.status_code == 200, res.text
        assert _mode_in_db(clean_mode, "test_flow") is None

    def test_none_clears_to_null(self, client, clean_mode):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "deterministic_patch"},
        )
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": None},
        )
        assert res.status_code == 200, res.text
        assert _mode_in_db(clean_mode, "test_flow") is None

    def test_invalid_value_is_rejected_with_400(self, client, clean_mode):
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "patcher_v3"},
        )
        assert res.status_code == 400, res.text
        assert "patcher_v3" in res.json()["detail"]
        assert _mode_in_db(clean_mode, "test_flow") is None

    def test_omitting_the_field_leaves_the_value_alone(self, client, clean_mode):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "deterministic_patch"},
        )
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"description": "unrelated edit"},
        )
        assert res.status_code == 200, res.text
        assert _mode_in_db(clean_mode, "test_flow") == "deterministic_patch"


class TestGetExposesImplementationMode:
    def test_list_flows_carries_the_field(self, client, clean_mode):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"implementation_mode": "deterministic_patch"},
        )
        res = client.get("/api/bridge-v2/flows")
        assert res.status_code == 200, res.text
        flows = {f["flow_key"]: f for f in res.json()["flows"]}
        assert "test_flow" in flows
        assert flows["test_flow"]["implementation_mode"] == "deterministic_patch"
