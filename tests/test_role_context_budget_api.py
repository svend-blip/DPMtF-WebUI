"""The role editor's context budget field, through the API it uses.

PUT /api/bridge-v2/roles/{role_key} persists context_budget, GET returns it,
an empty value clears it, and a value that is not a positive whole number is
refused — a budget of zero or less is not a smaller budget, it is a mistake,
and the launch would silently treat it as "no budget".
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def budget_column(seed_db: str):
    conn = sqlite3.connect(seed_db)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(bridge_roles)")}
        if "context_budget" not in existing:
            conn.execute("ALTER TABLE bridge_roles ADD COLUMN context_budget INTEGER")
        conn.commit()
    finally:
        conn.close()
    return seed_db


def test_the_budget_round_trips_and_can_be_cleared(client: TestClient, budget_column: str) -> None:
    put = client.put("/api/bridge-v2/roles/test_role", json={"context_budget": 131072})
    assert put.status_code == 200, put.text
    assert client.get("/api/bridge-v2/roles/test_role").json()["role"]["context_budget"] == 131072

    cleared = client.put("/api/bridge-v2/roles/test_role", json={"context_budget": None})
    assert cleared.status_code == 200, cleared.text
    assert client.get("/api/bridge-v2/roles/test_role").json()["role"]["context_budget"] is None


@pytest.mark.parametrize("bad", [0, -5, "plenty", 1.5, True])
def test_a_value_that_is_not_a_positive_whole_number_is_refused(
        client: TestClient, budget_column: str, bad) -> None:
    client.put("/api/bridge-v2/roles/test_role", json={"context_budget": 65536})
    resp = client.put("/api/bridge-v2/roles/test_role", json={"context_budget": bad})
    assert resp.status_code == 400, (bad, resp.status_code, resp.text)
    assert "context_budget" in resp.text
    # and the stored value is untouched
    assert client.get("/api/bridge-v2/roles/test_role").json()["role"]["context_budget"] == 65536
