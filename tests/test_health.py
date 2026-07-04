"""Smoke tests for the /api/health endpoint.

The health endpoint must:
- Return HTTP 200
- Return a JSON body with `status` (healthy/unhealthy), `app`, and
  `database_exists` fields.

In the test suite, the DB_PATH is patched to point at a temp DB that is
guaranteed to exist, so we expect `status == "healthy"` and
`database_exists == True`.
"""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """GET /api/health must always return HTTP 200 (status field carries health)."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_reports_healthy_with_temp_db(client: TestClient) -> None:
    """With the temp DB fixture in place, /api/health reports healthy + db_exists."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database_exists"] is True


def test_health_response_shape(client: TestClient) -> None:
    """Health response must include the expected keys."""
    response = client.get("/api/health")
    body = response.json()
    assert "status" in body
    assert "app" in body
    assert "database_path" in body
    assert "database_exists" in body
    assert body["app"] == "DPMtF WebUI"