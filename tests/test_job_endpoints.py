"""Tests for Job Queue API endpoints (Task 4)."""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_create_job(client):
    """POST /api/bridge-v2/jobs creates a draft job."""
    resp = client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review",
        "role_key": "archi01",
        "goal": "Add feature X",
        "target_project": "/tmp/test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["job_id"].startswith("JOB-")


def test_create_job_missing_field(client):
    """POST with missing field returns 400."""
    resp = client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review",
    })
    assert resp.status_code == 400


def test_approve_job(client):
    """PUT /api/bridge-v2/jobs/{id}/approve transitions to APPROVED."""
    create = client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review",
        "role_key": "archi01",
        "goal": "test",
        "target_project": "/tmp/test",
    })
    job_id = create.json()["job_id"]
    
    resp = client.put(f"/api/bridge-v2/jobs/{job_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"


def test_list_jobs(client):
    """GET /api/bridge-v2/jobs returns all jobs."""
    client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review", "role_key": "archi01",
        "goal": "g1", "target_project": "/tmp",
    })
    resp = client.get("/api/bridge-v2/jobs")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_list_jobs_by_status(client):
    """GET /api/bridge-v2/jobs?status=DRAFT filters by status."""
    client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review", "role_key": "archi01",
        "goal": "g1", "target_project": "/tmp",
    })
    resp = client.get("/api/bridge-v2/jobs?status=DRAFT")
    assert resp.json()["count"] >= 1
    resp = client.get("/api/bridge-v2/jobs?status=COMPLETED")
    # Other tests may have completed jobs — just verify filter works
    for job in resp.json()["jobs"]:
        assert job["status"] == "COMPLETED"


def test_get_job_detail(client):
    """GET /api/bridge-v2/jobs/{id} returns job + events."""
    create = client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review", "role_key": "archi01",
        "goal": "test", "target_project": "/tmp",
    })
    job_id = create.json()["job_id"]
    
    resp = client.get(f"/api/bridge-v2/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job"]["job_id"] == job_id
    assert len(data["events"]) >= 1  # at least the create event


def test_get_job_not_found(client):
    """GET non-existent job returns 404."""
    resp = client.get("/api/bridge-v2/jobs/NONEXISTENT")
    assert resp.status_code == 404


def test_cancel_job(client):
    """POST /api/bridge-v2/jobs/{id}/cancel cancels the job."""
    create = client.post("/api/bridge-v2/jobs", json={
        "flow_key": "strict_review", "role_key": "archi01",
        "goal": "test", "target_project": "/tmp",
    })
    job_id = create.json()["job_id"]
    
    resp = client.post(f"/api/bridge-v2/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_scheduler_tick(client):
    """POST /api/bridge-v2/jobs/scheduler/tick runs one pass."""
    resp = client.post("/api/bridge-v2/jobs/scheduler/tick")
    assert resp.status_code == 200
    data = resp.json()
    assert "claimed" in data
    assert "recovered" in data
