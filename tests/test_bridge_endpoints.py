"""Tests for the BridgeV002 database-backed endpoints.

Exercises /api/bridge-v2/status and /api/bridge-v2/flows against a temp
SQLite DB that has the required bridge_roles / bridge_flows /
bridge_flow_steps schema and one seeded role + flow row.
"""

import sqlite3

from fastapi.testclient import TestClient


EXPECTED_BRIDGE_TABLES = [
    "bridge_roles",
    "bridge_flows",
    "bridge_flow_steps",
]


def test_bridge_v2_status_reports_available(client: TestClient) -> None:
    """GET /api/bridge-v2/status must report available=True when tables exist."""
    response = client.get("/api/bridge-v2/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["tables"] == EXPECTED_BRIDGE_TABLES


def test_bridge_v2_status_reports_missing_when_no_tables(
    client: TestClient, seed_db: str
) -> None:
    """GET /api/bridge-v2/status must report available=False when tables are missing.

    Drops the bridge tables temporarily and confirms the endpoint correctly
    detects the absence. The original schema is restored on teardown so
    other tests in the session are not affected.
    """
    conn = sqlite3.connect(seed_db)
    try:
        conn.execute("DROP TABLE IF EXISTS bridge_flow_steps")
        conn.execute("DROP TABLE IF EXISTS bridge_flows")
        conn.execute("DROP TABLE IF EXISTS bridge_roles")
        conn.commit()
    finally:
        conn.close()

    try:
        response = client.get("/api/bridge-v2/status")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert body["tables"] == []
    finally:
        # Restore the schema so other tests aren't affected.
        from tests.conftest import _create_temp_db
        _create_temp_db(seed_db)
        conn = sqlite3.connect(seed_db)
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, start_cmd,
                 default_model_source, default_model_alias, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            ("test_role", "test_tmux_session", "echo test", "model_allocator", "test-alias"),
        )
        conn.execute(
            """
            INSERT INTO bridge_flows
                (flow_key, name, description, step_order,
                 is_default, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (
                "test_flow",
                "Test Flow",
                "A minimal flow used by the test suite.",
                "step1,step2",
            ),
        )
        conn.commit()
        conn.close()


def test_bridge_v2_flows_returns_seeded_flow(client: TestClient) -> None:
    """GET /api/bridge-v2/flows must return the seeded test_flow row."""
    response = client.get("/api/bridge-v2/flows")
    assert response.status_code == 200
    body = response.json()
    assert "flows" in body
    assert "count" in body
    assert body["count"] == len(body["flows"])
    assert body["count"] >= 1

    flow_keys = [flow.get("flow_key") for flow in body["flows"]]
    assert "test_flow" in flow_keys

    seeded_flow = next(f for f in body["flows"] if f["flow_key"] == "test_flow")
    assert seeded_flow["name"] == "Test Flow"
    assert seeded_flow["is_active"] == 1


def test_bridge_v2_flows_returns_empty_when_no_tables(
    client: TestClient, seed_db: str
) -> None:
    """GET /api/bridge-v2/flows must return an empty list when tables are missing.

    Same restore-on-teardown pattern as the status test.
    """
    conn = sqlite3.connect(seed_db)
    try:
        conn.execute("DROP TABLE IF EXISTS bridge_flow_steps")
        conn.execute("DROP TABLE IF EXISTS bridge_flows")
        conn.execute("DROP TABLE IF EXISTS bridge_roles")
        conn.commit()
    finally:
        conn.close()

    try:
        response = client.get("/api/bridge-v2/flows")
        assert response.status_code == 200
        body = response.json()
        assert body["flows"] == []
        assert body["count"] == 0
    finally:
        from tests.conftest import _create_temp_db
        _create_temp_db(seed_db)
        conn = sqlite3.connect(seed_db)
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, start_cmd,
                 default_model_source, default_model_alias, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            ("test_role", "test_tmux_session", "echo test", "model_allocator", "test-alias"),
        )
        conn.execute(
            """
            INSERT INTO bridge_flows
                (flow_key, name, description, step_order,
                 is_default, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (
                "test_flow",
                "Test Flow",
                "A minimal flow used by the test suite.",
                "step1,step2",
            ),
        )
        conn.commit()
        conn.close()

# ── Per-flow target project (migration 016) ────────────────────────────


def test_flow_list_exposes_target_project_path(client: TestClient) -> None:
    """The frontend edit form reads this field straight off the flow row."""
    response = client.get("/api/bridge-v2/flows")
    assert response.status_code == 200
    flows = response.json()["flows"]
    assert flows, "fixture must seed at least one flow"
    assert "target_project_path" in flows[0]


def test_update_flow_rejects_a_target_that_does_not_exist(
    client: TestClient, tmp_path
) -> None:
    """A stored path that is not there sends roles into the wrong repository.

    This is the goal-009 failure in a different disguise: dispatch would name
    a directory nobody can cd to, and the role would run its checks wherever
    its session happened to be sitting. Refuse at write time instead.
    """
    missing = tmp_path / "not-created"
    response = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"target_project_path": str(missing)},
    )
    assert response.status_code == 400
    assert str(missing) in response.json()["detail"]

    # and nothing was written
    after = client.get("/api/bridge-v2/flows/test_flow").json()["flow"]
    assert after["target_project_path"] is None


def test_update_flow_accepts_an_existing_directory(
    client: TestClient, tmp_path
) -> None:
    target = tmp_path / "some-repo"
    target.mkdir()

    response = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"target_project_path": str(target)},
    )
    assert response.status_code == 200

    after = client.get("/api/bridge-v2/flows/test_flow").json()["flow"]
    assert after["target_project_path"] == str(target)


def test_update_flow_treats_blank_as_unset(client: TestClient, tmp_path) -> None:
    """A cleared field must store NULL, not an empty string.

    get_flow_target_project() reads "" as unset and falls back to Father, but
    only NULL says so unambiguously to anything reading the row directly.
    """
    target = tmp_path / "some-repo"
    target.mkdir()
    client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"target_project_path": str(target)},
    )

    response = client.put(
        "/api/bridge-v2/flows/test_flow", json={"target_project_path": "   "}
    )
    assert response.status_code == 200

    after = client.get("/api/bridge-v2/flows/test_flow").json()["flow"]
    assert after["target_project_path"] is None
